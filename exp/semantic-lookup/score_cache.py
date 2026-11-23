#!/usr/bin/env python3
"""Score cache builder: top-32 dense recall + per-judge cross-encoder scores across catalog scales.

For each retriever (off-the-shelf BAAI/bge-m3; catalog-tuned bge-m3 from train_retriever.py), each catalog size, and
each request, stores the top-32 candidate IDs and cosines plus the sigmoid score of every candidate under each judge
family (frozen 26-definition judges; refreshed multi-domain judges), with peer differences rendered from the catalog
at that size. Decision policies are replayed on CPU by policy.py.
"""
import argparse
import json
import random
import statistics
import time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--out", default="results/lookup")
ap.add_argument("--scales", default="26,100,500,1000")
ap.add_argument("--raw-base", default="BAAI/bge-m3")
ap.add_argument("--tuned", default="ft_retriever/bge-m3-cat-llm-s13/model")
ap.add_argument("--kmax", type=int, default=32)
ap.add_argument(
    "--qsets",
    default="orig_96=requests_orig_96.json,glm_174=requests_glm_174.json,scale_120=requests_scale_120.json",
    help="name=path pairs; held-out paraphrase evaluation uses glm_scale=requests_glm_scale.json",
)
ap.add_argument("--skip-timing", action="store_true")
ap.add_argument(
    "--refreshed-dirs",
    default="ft_scale/scale-dc-llm-s13,ft_scale/scale-dc-llm-s14,ft_scale/scale-dc-llm-s15",
    help="comma-separated checkpoint directories for the refreshed peer-difference judges",
)
ap.add_argument(
    "--train-files",
    default="train_26_clean.jsonl,train_scale_extra.jsonl,train_scale_llm.jsonl",
    help="training files of the tuned retriever, for its seed-13 dev split",
)
ap.add_argument(
    "--families",
    default="mavra_zero,mavra_refreshed",
    help="judge families to score; ablation adds single_ce_refreshed (needs --plain-dirs)",
)
ap.add_argument("--plain-dirs", default="", help="judges trained without peer differences (render = name + text)")
args = ap.parse_args()

OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
SCALES = [int(x) for x in args.scales.split(",")]
KMAX = args.kmax
K = 8
DEV = "cuda"
LO, HI = 0.10, 0.90

BASE_CAT = json.load(open("catalog_1000.json", encoding="utf-8"))
FN = BASE_CAT["facet_names"]
QSETS = {n: json.load(open(p, encoding="utf-8"))["requests"] for n, p in (x.split("=") for x in args.qsets.split(","))}
ALL_REQS = [{**r, "qset": n, "uid": f"{n}:{r['id']}"} for n, qs in QSETS.items() for r in qs]
CATALOGS = {m: json.load(open(f"catalog_{m}.json", encoding="utf-8"))["definitions"] for m in SCALES}
DEFS_ALL = CATALOGS[max(SCALES)]


def fv(d, s):
    v = d["facets"].get(s)
    return v if v else ("全部商品" if s == "category" else "无")


def def_text(d):
    return f"{d['name']}：{d['text']}"


def render(d, pool):
    out = def_text(d)
    f = d["facets"]
    out += "｜口径：" + "；".join(f"{FN[s]}={fv(d, s)}" for s in FN if f.get(s) or s == "category")
    group = lambda e: (e["facets"].get("channel"), e["facets"].get("subject"))  # noqa: E731
    peers = [e for e in pool if e is not d and (group(e) == group(d) or e["name"] == d["name"])]
    peers.sort(key=lambda e: (e["name"] != d["name"], e["facets"].get("category") != f.get("category"), e["id"]))
    parts = []
    for e in peers[:4]:
        who = "同名的另一条" if e["name"] == d["name"] else f"“{e['name']}”"
        diff = [s for s in FN if f.get(s) != e["facets"].get(s)]
        if diff:
            parts.append(f"{who}：" + "，".join(f"{FN[s]}为{fv(e, s)}（本条为{fv(d, s)}）" for s in diff))
    if parts:
        out += "｜与相近定义的区别：" + "；".join(parts)
    return out


def sync():
    torch.cuda.synchronize()


_train = [json.loads(l) for f in args.train_files.split(",") for l in open(f, encoding="utf-8") if l.strip()]
_keys = sorted({json.dumps(q["stated"], ensure_ascii=False, sort_keys=True) for q in _train})
random.Random(13).shuffle(_keys)
_dev_keys = set(_keys[: max(1, int(len(_keys) * 0.12))])
DEV_Q = [q["text"] for q in _train if json.dumps(q["stated"], ensure_ascii=False, sort_keys=True) in _dev_keys]
dev_top1 = {}

RETRIEVERS = {"raw": args.raw_base, "tuned": args.tuned}
recall = {}


def def_text_pool(d, pool):
    return def_text(d)


query_secs = {}
for rname, path in RETRIEVERS.items():
    emb = SentenceTransformer(path, device=DEV)
    emb.encode(["预热查询"], normalize_embeddings=True)
    dvec = emb.encode([def_text(d) for d in DEFS_ALL], normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    dq = emb.encode(DEV_Q, normalize_embeddings=True, batch_size=128, show_progress_bar=False)
    dev_top1[rname] = {m: [round(float(x), 5) for x in (dq @ dvec[:m].T).max(axis=1)] for m in SCALES}
    qvec, secs = [], []
    for r in ALL_REQS:
        sync()
        t0 = time.time()
        v = emb.encode([r["text"]], normalize_embeddings=True, show_progress_bar=False)[0]
        sync()
        secs.append(time.time() - t0)
        qvec.append(v)
    qmat = np.stack(qvec)
    query_secs[rname] = secs
    recall[rname] = {}
    for m in SCALES:
        sims = qmat @ dvec[:m].T
        order = np.argsort(-sims, axis=1)[:, : min(KMAX, m)]
        recall[rname][m] = {
            "ids": [[DEFS_ALL[j]["id"] for j in row] for row in order],
            "cos": [[round(float(sims[i, j]), 5) for j in row] for i, row in enumerate(order)],
        }
    del emb
    torch.cuda.empty_cache()
    print(f"recall done: {rname}", flush=True)

FAMILIES = {
    "mavra_zero": ["ft_base/base-dc-xl-s13", "ft_base/base-dc-xl-s14", "ft_base/base-dc-xl-s15"],
    "mavra_refreshed": args.refreshed_dirs.split(","),
    "single_ce_refreshed": [d for d in args.plain_dirs.split(",") if d],
}
SCORED = args.families.split(",")
scores = {}
for fam, dirs in FAMILIES.items():
    if fam not in SCORED:
        continue
    rend = def_text_pool if fam == "single_ce_refreshed" else render
    tok = AutoTokenizer.from_pretrained(Path(dirs[0]) / "model")
    judges = [AutoModelForSequenceClassification.from_pretrained(Path(d) / "model").to(DEV).eval() for d in dirs]
    scores[fam] = {}
    for m in SCALES:
        defs = CATALOGS[m]
        dtext = {d["id"]: rend(d, defs) for d in defs}
        for rname in RETRIEVERS:
            per = [[] for _ in judges]
            for qi, r in enumerate(ALL_REQS):
                cands = recall[rname][m]["ids"][qi]
                with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                    outs = [[] for _ in judges]
                    for c0 in range(0, len(cands), K):
                        chunk = cands[c0 : c0 + K]
                        enc = tok(
                            [r["text"]] * len(chunk),
                            [dtext[c] for c in chunk],
                            truncation=True,
                            max_length=384,
                            padding=True,
                            return_tensors="pt",
                        ).to(DEV)
                        for ji, j in enumerate(judges):
                            outs[ji].extend(torch.sigmoid(j(**enc).logits.squeeze(-1).float()).cpu().numpy().tolist())
                for ji in range(len(judges)):
                    per[ji].append([round(x, 6) for x in outs[ji]])
            scores[fam].setdefault(rname, {})[m] = per
            print(f"scored {fam} {rname} M={m}", flush=True)
    del judges
    torch.cuda.empty_cache()

timing = {}
if not args.skip_timing:
    emb = SentenceTransformer(args.tuned, device=DEV)
    emb.encode(["预热查询"], normalize_embeddings=True)
    dvec = emb.encode([def_text(d) for d in DEFS_ALL], normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    tok = AutoTokenizer.from_pretrained(Path(FAMILIES["mavra_refreshed"][0]) / "model")
    judges = [AutoModelForSequenceClassification.from_pretrained(Path(d) / "model").to(DEV).eval() for d in FAMILIES["mavra_refreshed"]]
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        w = tok(["预热"] * K, ["定义"] * K, truncation=True, max_length=384, padding=True, return_tensors="pt").to(DEV)
        for j in judges:
            j(**w)
for m in ([] if args.skip_timing else SCALES):
    defs = CATALOGS[m]
    dtext = {d["id"]: render(d, defs) for d in defs}
    dm = torch.tensor(dvec[:m], device=DEV)
    secs, widened = [], 0
    for r in ALL_REQS:
        sync()
        t0 = time.time()
        qv = emb.encode([r["text"]], normalize_embeddings=True, show_progress_bar=False, convert_to_tensor=True)[0]
        order = torch.topk(dm @ qv.to(dm.dtype), min(KMAX, m)).indices.tolist()
        cands = [defs[j]["id"] for j in order]

        def run(chunk):
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                enc = tok(
                    [r["text"]] * len(chunk),
                    [dtext[c] for c in chunk],
                    truncation=True,
                    max_length=384,
                    padding=True,
                    return_tensors="pt",
                ).to(DEV)
                return np.mean([torch.sigmoid(j(**enc).logits.squeeze(-1).float()).cpu().numpy() for j in judges], axis=0)

        s8 = run(cands[:K])
        if (s8 < LO).all() and len(cands) > K:
            widened += 1
            for c0 in range(K, len(cands), K):
                run(cands[c0 : c0 + K])
        sync()
        secs.append(time.time() - t0)
    timing[m] = {
        "latency_ms_mean": round(statistics.mean(secs) * 1000, 2),
        "latency_ms_p95": round(sorted(secs)[int(0.95 * len(secs))] * 1000, 2),
        "widened": widened,
        "seconds": [round(x, 5) for x in secs],
    }
    print(f"timing M={m}: {timing[m]['latency_ms_mean']} ms, widened {widened}", flush=True)

meta = {
    "scales": SCALES,
    "kmax": KMAX,
    "requests": [{k: r[k] for k in ("uid", "qset", "id", "kind", "text", "stated")} for r in ALL_REQS],
    "query_encode_seconds": query_secs,
    "dev_questions": len(DEV_Q),
    "refreshed_dirs": FAMILIES["mavra_refreshed"],
    "families_scored": SCORED,
    "plain_dirs": FAMILIES["single_ce_refreshed"],
    "tuned_retriever": args.tuned,
    "dev_top1_cos": dev_top1,
}
(OUT / "cache.json").write_text(
    json.dumps({"meta": meta, "recall": recall, "scores": scores, "timing": timing}, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print("=== SCORE CACHE COMPLETE ===", flush=True)
