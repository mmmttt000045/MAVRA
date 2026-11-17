#!/usr/bin/env python3
"""GPU benchmark runner for P1-1 Lookup Scaling (M = 26, 100, 500, 1,000) & Risk-Coverage.

Runs entirely offline on NVIDIA RTX 5880 Ada (zero API keys required):
  1. Stage-1 bge-m3 dense retrieval: Recall@{1,4,8,16,32} + GPU latency across M in {26,100,500,1000}
  2. Exact Name Match (N)
  3. Embedding Top-1 (bge-m3): fixed threshold + oracle threshold + Risk-Coverage sweep
  4. TeCoD Template Matcher (Qwen3-Embedding-4B + Qwen3-Re4B-SQL-TeCoD-TMM on CUDA BF16) + Risk-Coverage sweep
  5. Single Cross-Encoder without Peer Diffs:
       - single_ce_zero (frozen 26-def ft_base/base-xl-plain-s13)
       - single_ce_refreshed (3-seed ft_scale/scale-plain-s13..15)
  6. MAVRA Peer-Diff Cross-Encoder Ensemble:
       - mavra_zero (frozen 26-def ft_base/base-dc-xl-s13..15, ZERO retraining!)
       - mavra_refreshed (3-seed ft_scale/scale-dc-s13..15)

Exports compact candidate + first-response JSONLs in `out_dir/for_llm/` so `run_llm_methods.py` on noctis
can run `Top-8 Recall + LLM Judge` and `MAVRA Refer Confirmation` via DeepSeek official API.
"""
import argparse
import json
import re
import statistics
import time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="results_gpu")
ap.add_argument("--scales", default="26,100,500,1000")
ap.add_argument("--skip-tecod", action="store_true")
args = ap.parse_args()

OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
LLM_EXPORT = OUT / "for_llm"
LLM_EXPORT.mkdir(parents=True, exist_ok=True)

SCALES = [int(x) for x in args.scales.split(",")]
K = 8
DEV = "cuda" if torch.cuda.is_available() else "cpu"

BASE_CAT = json.load(open("catalog_1000.json", encoding="utf-8"))
FN = BASE_CAT["facet_names"]
SLOTS = list(FN)

QSETS = {
    "orig_96": json.load(open("requests_orig_96.json", encoding="utf-8"))["requests"],
    "glm_174": json.load(open("requests_glm_174.json", encoding="utf-8"))["requests"],
    "scale_120": json.load(open("requests_scale_120.json", encoding="utf-8"))["requests"],
}
ALL_REQS = []
for qset_name, qs in QSETS.items():
    for r in qs:
        ALL_REQS.append({**r, "qset": qset_name, "uid": f"{qset_name}:{r['id']}"})


def consistent(f, stated):
    for s in SLOTS:
        v = f.get(s)
        st = stated.get(s)
        if st:
            vals = [st] if isinstance(st, str) else st
            if v is None or v not in vals:
                return False
        elif s == "category" and v is not None:
            return False
        elif s == "channel" and v not in (None, "全渠道"):
            return False
    return True


def fv(d, s):
    v = d["facets"].get(s)
    return v if v else ("全部商品" if s == "category" else "无")


def def_text(d):
    return f"{d['name']}：{d['text']}"


def render(d, pool, contrast):
    out = def_text(d)
    if not contrast:
        return out
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


def explain(ids, byid):
    if len(ids) < 2:
        return ""
    ds = [byid[i] for i in ids]
    slots = [s for s in FN if len({fv(d, s) for d in ds}) > 1]
    return "；".join(f"{FN[s]}：" + " / ".join(f"{d['name']}（{d['id']}）为{fv(d, s)}" for d in ds) for s in slots)


def describe(d):
    return f"{d['name']}（{d['id']}）：" + "，".join(f"{FN[s]}={fv(d, s)}" for s in FN if d["facets"].get(s))


def sync():
    if DEV == "cuda":
        torch.cuda.synchronize()


# ---------------------------------------------------------------------------
# 1. Stage-1 Dense Retrieval (bge-m3) + Name Match + Embedding Top-1
# ---------------------------------------------------------------------------
print("=== Stage 1: bge-m3 retrieval & Embedding baselines ===", flush=True)
emb_model = SentenceTransformer("models/bge-m3", device=DEV)
# Warmup
emb_model.encode(["预热查询"], normalize_embeddings=True)

CATALOGS = {}
GOLD = {}
STAGE1 = {}

for m in SCALES:
    defs = json.load(open(f"catalog_{m}.json", encoding="utf-8"))["definitions"]
    CATALOGS[m] = defs
    GOLD[m] = {r["uid"]: sorted(d["id"] for d in defs if consistent(d["facets"], r["stated"])) for r in ALL_REQS}

# Pre-encode all 1,000 definitions once (since catalogs are nested!)
all_1000_defs = CATALOGS[max(SCALES)]
D_ALL = emb_model.encode([def_text(d) for d in all_1000_defs], normalize_embeddings=True, batch_size=64, show_progress_bar=False)

# Measure per-query Stage-1 latency + top-K indices per scale
Q_VECS = []
q_encode_secs = []
for r in ALL_REQS:
    sync()
    t0 = time.time()
    v = emb_model.encode([r["text"]], normalize_embeddings=True, show_progress_bar=False)[0]
    sync()
    q_encode_secs.append(time.time() - t0)
    Q_VECS.append(v)
Q_MAT = np.stack(Q_VECS)

recall_summary = {}
emb_summary = {}
name_summary = {}
rc_curves = {}


def subset_indices(subset_name):
    if subset_name == "all_390":
        return list(range(len(ALL_REQS)))
    return [i for i, r in enumerate(ALL_REQS) if r["qset"] == subset_name]


SUBSETS = ["orig_96", "glm_174", "scale_120", "all_390"]

for m in SCALES:
    defs = CATALOGS[m]
    ids = [d["id"] for d in defs]
    byid = {d["id"]: d for d in defs}
    D_M = D_ALL[:m]

    # Measure vector search latency per query at scale m
    search_secs = []
    sims_m = np.zeros((len(ALL_REQS), m), dtype=np.float32)
    for qi in range(len(ALL_REQS)):
        sync()
        t0 = time.time()
        row_sim = Q_MAT[qi] @ D_M.T
        _ = np.argsort(-row_sim)[:K]
        sync()
        search_secs.append(q_encode_secs[qi] + (time.time() - t0))
        sims_m[qi] = row_sim

    STAGE1[m] = {"sims": sims_m, "ids": ids, "byid": byid, "latencies": search_secs}

    # Export top-8 candidates for LLM judge on noctis
    top8_export = []
    for qi, r in enumerate(ALL_REQS):
        order = np.argsort(-sims_m[qi])[:K]
        cands = [ids[j] for j in order]
        top8_export.append({
            "uid": r["uid"],
            "qset": r["qset"],
            "id": r["id"],
            "kind": r["kind"],
            "text": r["text"],
            "gold": GOLD[m][r["uid"]],
            "top8": [{"id": cid, "name": byid[cid]["name"], "text": byid[cid]["text"]} for cid in cands],
            "top1_sim": round(float(sims_m[qi, order[0]]), 4),
            "recall_s": round(search_secs[qi], 5),
        })
    (LLM_EXPORT / f"top8_M{m}.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in top8_export), encoding="utf-8"
    )

    # Recall@K
    recall_summary[str(m)] = {"latency_ms_mean": round(statistics.mean(search_secs) * 1000, 2),
                              "latency_ms_p95": round(sorted(search_secs)[int(0.95 * len(search_secs))] * 1000, 2)}
    for sub in SUBSETS:
        idxs = subset_indices(sub)
        r_dict = {}
        for rk in (1, 4, 8, 16, 32):
            kk = min(rk, m)
            ok = 0
            present_ok = 0
            present_n = 0
            for qi in idxs:
                g = GOLD[m][ALL_REQS[qi]["uid"]]
                cand = {ids[j] for j in np.argsort(-sims_m[qi])[:kk]}
                if set(g) <= cand:
                    ok += 1
                if g:
                    present_n += 1
                    if set(g) <= cand:
                        present_ok += 1
            r_dict[f"recall@{rk}_all"] = round(ok / len(idxs), 4)
            r_dict[f"recall@{rk}_present"] = round(present_ok / max(1, present_n), 4)
        recall_summary[str(m)][sub] = r_dict

    # Exact Name Match
    name_summary[str(m)] = {}
    name_got_all = []
    for qi, r in enumerate(ALL_REQS):
        hits = [d for d in defs if d["name"] in r["text"]]
        names = {d["name"] for d in hits}
        keep = {n for n in names if not any(n != o and n in o for o in names)}
        name_got_all.append(sorted(d["id"] for d in hits if d["name"] in keep))
    for sub in SUBSETS:
        idxs = subset_indices(sub)
        exact = sum(name_got_all[qi] == GOLD[m][ALL_REQS[qi]["uid"]] for qi in idxs)
        abs_idx = [qi for qi in idxs if not GOLD[m][ALL_REQS[qi]["uid"]]]
        abs_rej = sum(name_got_all[qi] == [] for qi in abs_idx)
        name_summary[str(m)][sub] = {
            "n": len(idxs),
            "exact": exact,
            "exact_rate": round(exact / len(idxs), 4),
            "absent_n": len(abs_idx),
            "absent_rejected": abs_rej,
            "absent_reject_rate": round(abs_rej / max(1, len(abs_idx)), 4),
        }

    # Embedding Top-1 (fixed threshold 0.68 + oracle threshold + Risk-Coverage curve)
    emb_summary[str(m)] = {}
    top1_id = [ids[int(np.argmax(sims_m[qi]))] for qi in range(len(ALL_REQS))]
    top1_sim = [float(np.max(sims_m[qi])) for qi in range(len(ALL_REQS))]
    for sub in SUBSETS:
        idxs = subset_indices(sub)
        best = None
        for tau in np.linspace(0.40, 0.90, 101):
            ex = sum(([top1_id[qi]] if top1_sim[qi] >= tau else []) == GOLD[m][ALL_REQS[qi]["uid"]] for qi in idxs)
            if best is None or ex > best[1]:
                best = (float(tau), ex)
        tau_opt = best[0]
        got_opt = [[top1_id[qi]] if top1_sim[qi] >= tau_opt else [] for qi in idxs]
        got_fix = [[top1_id[qi]] if top1_sim[qi] >= 0.68 else [] for qi in idxs]
        abs_pos = [pos for pos, qi in enumerate(idxs) if not GOLD[m][ALL_REQS[qi]["uid"]]]
        emb_summary[str(m)][sub] = {
            "n": len(idxs),
            "oracle_tau": round(tau_opt, 3),
            "oracle_exact": best[1],
            "oracle_exact_rate": round(best[1] / len(idxs), 4),
            "oracle_absent_rejected": sum(got_opt[p] == [] for p in abs_pos),
            "fixed_tau": 0.68,
            "fixed_exact": sum(got_fix[pos] == GOLD[m][ALL_REQS[qi]["uid"]] for pos, qi in enumerate(idxs)),
            "fixed_exact_rate": round(sum(got_fix[pos] == GOLD[m][ALL_REQS[qi]["uid"]] for pos, qi in enumerate(idxs)) / len(idxs), 4),
            "fixed_absent_rejected": sum(got_fix[p] == [] for p in abs_pos),
            "absent_n": len(abs_pos),
            "latency_ms_mean": recall_summary[str(m)]["latency_ms_mean"],
        }

    # Risk-Coverage sweep for Embedding Top-1 around center tau=0.68
    rc_curves.setdefault(str(m), {})["emb_top1"] = {}
    for sub in SUBSETS:
        idxs = subset_indices(sub)
        pts = []
        for w in np.linspace(0.28, 0.0, 29):
            lo_t, hi_t = 0.68 - w, 0.68 + w
            direct_n = wrong_n = 0
            for qi in idxs:
                s = top1_sim[qi]
                g = GOLD[m][ALL_REQS[qi]["uid"]]
                if s >= hi_t:
                    direct_n += 1
                    wrong_n += [top1_id[qi]] != g
                elif s < lo_t:
                    direct_n += 1
                    wrong_n += [] != g
            cov = direct_n / len(idxs)
            sel_risk = wrong_n / max(1, direct_n)
            pts.append({"w": round(float(w), 3), "coverage": round(cov, 4), "selective_risk": round(sel_risk, 4),
                        "direct_precision": round(1.0 - sel_risk, 4), "overall_wrong_rate": round(wrong_n / len(idxs), 4)})
        rc_curves[str(m)]["emb_top1"][sub] = pts

del emb_model
if DEV == "cuda":
    torch.cuda.empty_cache()


# ---------------------------------------------------------------------------
# 2. Cross-Encoder Evaluation Helper (Single CE & MAVRA Ensemble)
# ---------------------------------------------------------------------------
def eval_ce_family(family_name, run_dirs, contrast, max_len=384, band=(0.10, 0.90), sigma=0.60, export_for_llm=False):
    print(f"=== Evaluating CE family: {family_name} ({len(run_dirs)} models, contrast={contrast}) ===", flush=True)
    tok = AutoTokenizer.from_pretrained(Path(run_dirs[0]) / "model")
    judges = [AutoModelForSequenceClassification.from_pretrained(Path(r) / "model").to(DEV).eval() for r in run_dirs]
    # Warmup
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        w_enc = tok(["预热"] * K, ["定义"] * K, truncation=True, max_length=max_len, padding=True, return_tensors="pt").to(DEV)
        for j in judges:
            _ = j(**w_enc)
    sync()

    fam_summary = {}
    lo_def, hi_def = band

    for m in SCALES:
        defs = CATALOGS[m]
        ids = STAGE1[m]["ids"]
        byid = STAGE1[m]["byid"]
        sims_m = STAGE1[m]["sims"]
        s1_secs = STAGE1[m]["latencies"]
        dtext = {d["id"]: render(d, defs, contrast) for d in defs}

        cand_list = []
        cand_scores = []  # shape (N_req, K)
        ce_secs = []
        per_model_scores = [[] for _ in judges]

        for qi, r in enumerate(ALL_REQS):
            order = np.argsort(-sims_m[qi])[:K]
            cands = [ids[j] for j in order]
            cand_list.append((cands, float(sims_m[qi, order[0]])))
            sync()
            t0 = time.time()
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                enc = tok([r["text"]] * len(cands), [dtext[c] for c in cands], truncation=True, max_length=max_len,
                          padding=True, return_tensors="pt").to(DEV)
                per_j = [torch.sigmoid(j(**enc).logits.squeeze(-1).float()).cpu().numpy() for j in judges]
            sync()
            ce_secs.append(s1_secs[qi] + (time.time() - t0))
            for ji, arr in enumerate(per_j):
                per_model_scores[ji].append(arr)
            cand_scores.append(np.mean(per_j, axis=0))

        def build_reply(qi, lo_v, hi_v, sig_v, score_vec):
            cands, top1_s = cand_list[qi]
            acc = [c for c, s in zip(cands, score_vec) if s >= hi_v]
            unc = [c for c, s in zip(cands, score_vec) if lo_v <= s < hi_v]
            picked = sorted(acc + unc)
            if unc:
                mode = "refer"
                rep = "拿不准，以下定义相近，请确认是否其中之一：" + "；".join(describe(byid[i]) for i in picked)
                if len(picked) > 1:
                    rep += "。区别：" + explain(picked, byid)
            elif len(acc) == 1:
                mode, rep = "answer", "命中：" + describe(byid[acc[0]])
            elif acc:
                mode, rep = "answer", f"同名不同义，共 {len(acc)} 条：" + "；".join(describe(byid[i]) for i in acc) + "。区别：" + explain(acc, byid)
            elif top1_s >= sig_v:
                mode, picked = "similar", [cands[0]]
                rep = "没有找到口径一致的定义；最相近的是 " + describe(byid[cands[0]]) + "，请确认它是否就是你要的，否则需要自己计算"
            else:
                mode, rep = "none", "目录中没有与之一致的定义。"
            return mode, picked, rep

        # Export responses at default band (0.10, 0.90, sigma=0.60) if requested
        default_rows = []
        for qi, r in enumerate(ALL_REQS):
            mode, picked, rep = build_reply(qi, lo_def, hi_def, sigma, cand_scores[qi])
            g = GOLD[m][r["uid"]]
            first_set = picked if mode in ("answer", "refer") else []
            usable = (mode in ("answer", "none") and first_set == g) or (mode in ("refer", "similar") and (set(g) <= set(picked) if g else True))
            default_rows.append({
                "uid": r["uid"],
                "qset": r["qset"],
                "req": r["id"],
                "kind": r["kind"],
                "text": r["text"],
                "mode": mode,
                "ids": picked,
                "first_set": first_set,
                "first_exact": first_set == g,
                "usable": usable,
                "gold": g,
                "seconds": round(ce_secs[qi], 5),
                "reply": rep,
            })

        if export_for_llm:
            (LLM_EXPORT / f"responses_{family_name}_M{m}.jsonl").write_text(
                "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in default_rows), encoding="utf-8"
            )

        fam_summary[str(m)] = {
            "latency_ms_mean": round(statistics.mean(ce_secs) * 1000, 2),
            "latency_ms_p95": round(sorted(ce_secs)[int(0.95 * len(ce_secs))] * 1000, 2),
        }

        for sub in SUBSETS:
            idxs = subset_indices(sub)
            sub_rows = [default_rows[qi] for qi in idxs]
            direct = [x for x in sub_rows if x["mode"] in ("answer", "none")]
            refer = [x for x in sub_rows if x["mode"] in ("refer", "similar")]
            abs_rows = [x for x in sub_rows if not x["gold"]]

            # Also compute best single-threshold accuracy (no abstention, coverage = 100%)
            best_tau_ex = 0
            best_tau = 0.5
            for tau in np.linspace(0.05, 0.95, 91):
                ex = sum(sorted([c for c, s in zip(cand_list[qi][0], cand_scores[qi]) if s >= tau]) == GOLD[m][ALL_REQS[qi]["uid"]]
                         for qi in idxs)
                if ex > best_tau_ex:
                    best_tau_ex = ex
                    best_tau = float(tau)

            # Per-seed single-threshold accuracy at tau=0.15 and oracle tau
            seed_rates = []
            for ji in range(len(judges)):
                best_j = max(
                    sum(sorted([c for c, s in zip(cand_list[qi][0], per_model_scores[ji][qi]) if s >= tau]) == GOLD[m][ALL_REQS[qi]["uid"]]
                        for qi in idxs)
                    for tau in np.linspace(0.05, 0.95, 46)
                )
                seed_rates.append(round(best_j / len(idxs), 4))

            direct_prec = sum(x["first_set"] == x["gold"] for x in direct) / max(1, len(direct))
            fam_summary[str(m)][sub] = {
                "n": len(sub_rows),
                "first_exact": sum(x["first_exact"] for x in sub_rows),
                "first_exact_rate": round(sum(x["first_exact"] for x in sub_rows) / len(sub_rows), 4),
                "direct_n": len(direct),
                "direct_coverage": round(len(direct) / len(sub_rows), 4),
                "direct_precision": round(direct_prec, 4),
                "selective_risk": round(1.0 - direct_prec, 4),
                "refer_n": len(refer),
                "refer_contains_gold": sum(x["usable"] for x in refer),
                "usable_rate": round(sum(x["usable"] for x in sub_rows) / len(sub_rows), 4),
                "absent_n": len(abs_rows),
                "absent_first_rejected": sum(x["first_set"] == [] for x in abs_rows),
                "no_abstain_best_tau": round(best_tau, 3),
                "no_abstain_exact": best_tau_ex,
                "no_abstain_exact_rate": round(best_tau_ex / len(sub_rows), 4),
                "per_seed_exact_rates": seed_rates,
            }

        # Risk-Coverage sweep from wide abstention band to zero abstention (100% direct coverage)
        # Schedule t in [0, 1]:
        #   t = 0.0 -> lo=0.005, hi=0.995, sigma=0.45 (conservative)
        #   t = 0.5 -> lo=0.10,  hi=0.90,  sigma=0.60 (MAVRA default)
        #   t = 1.0 -> lo=tau_c, hi=tau_c, sigma=1.01 (100% direct coverage, 0 referrals)
        tau_c = 0.30
        rc_curves.setdefault(str(m), {})[family_name] = {}
        schedule = []
        for k_step in range(21):
            u = k_step / 20.0
            if u <= 0.5:
                a = u / 0.5
                lo_s = 0.005 + a * (0.10 - 0.005)
                hi_s = 0.995 + a * (0.90 - 0.995)
                sig_s = 0.45 + a * (0.60 - 0.45)
            else:
                a = (u - 0.5) / 0.5
                lo_s = 0.10 + a * (tau_c - 0.10)
                hi_s = 0.90 + a * (tau_c - 0.90)
                sig_s = 0.60 + a * (1.01 - 0.60)
            schedule.append((lo_s, hi_s, sig_s))

        for sub in SUBSETS:
            idxs = subset_indices(sub)
            pts = []
            for lo_s, hi_s, sig_s in schedule:
                direct_n = wrong_n = 0
                for qi in idxs:
                    mode, picked, _ = build_reply(qi, lo_s, hi_s, sig_s, cand_scores[qi])
                    if mode in ("answer", "none"):
                        direct_n += 1
                        first_set = picked if mode == "answer" else []
                        wrong_n += first_set != GOLD[m][ALL_REQS[qi]["uid"]]
                cov = direct_n / len(idxs)
                sel_risk = wrong_n / max(1, direct_n)
                pts.append({
                    "lo": round(float(lo_s), 4),
                    "hi": round(float(hi_s), 4),
                    "sigma": round(float(sig_s), 3),
                    "coverage": round(cov, 4),
                    "selective_risk": round(sel_risk, 4),
                    "direct_precision": round(1.0 - sel_risk, 4),
                    "overall_wrong_rate": round(wrong_n / len(idxs), 4),
                })
            rc_curves[str(m)][family_name][sub] = pts

    del judges
    if DEV == "cuda":
        torch.cuda.empty_cache()
    return fam_summary


ce_results = {}
# Zero-retrain 26-def models
ce_results["single_ce_zero"] = eval_ce_family(
    "single_ce_zero", ["ft_base/base-xl-plain-s13"], contrast=False, max_len=192
)
ce_results["mavra_zero"] = eval_ce_family(
    "mavra_zero",
    ["ft_base/base-dc-xl-s13", "ft_base/base-dc-xl-s14", "ft_base/base-dc-xl-s15"],
    contrast=True,
    max_len=384,
    export_for_llm=True,
)

# Multi-domain refreshed models (if trained in ft_scale/)
if (Path("ft_scale/scale-plain-s13/model")).exists():
    plain_dirs = [f"ft_scale/scale-plain-s{s}" for s in (13, 14, 15) if Path(f"ft_scale/scale-plain-s{s}/model").exists()]
    ce_results["single_ce_refreshed"] = eval_ce_family("single_ce_refreshed", plain_dirs, contrast=False, max_len=384)

if (Path("ft_scale/scale-dc-s13/model")).exists():
    dc_dirs = [f"ft_scale/scale-dc-s{s}" for s in (13, 14, 15) if Path(f"ft_scale/scale-dc-s{s}/model").exists()]
    ce_results["mavra_refreshed"] = eval_ce_family(
        "mavra_refreshed", dc_dirs, contrast=True, max_len=384, export_for_llm=True
    )


# ---------------------------------------------------------------------------
# 3. TeCoD Released Template Matcher (Qwen3-Embedding-4B + Qwen3-Re4B NLI on GPU)
# ---------------------------------------------------------------------------
tecod_summary = {}
if not args.skip_tecod and Path("tecod-models/Qwen3-Embedding-4B").exists():
    print("=== Stage 3: TeCoD Template Matcher on GPU (BF16) ===", flush=True)
    EMB_PROMPTS = {
        "query": "Instruct: Given a user query, retrieve the relevant question skeleton that best matches its semantic structure and intent.\nQuery:{query}",
        "skeleton": "{query}",
    }
    pool_all = json.load(open("pool_1000.json", encoding="utf-8"))
    masked_all = [re.sub(r"\d+", "_", x["text"]) for x in pool_all]

    t_emb_model = SentenceTransformer(
        "tecod-models/Qwen3-Embedding-4B",
        device=DEV,
        local_files_only=True,
        model_kwargs={"torch_dtype": torch.bfloat16},
    )
    nli_path = "tecod-models/Qwen3-Re4B-SQL-TeCoD-TMM"
    nli_tok = AutoTokenizer.from_pretrained(nli_path, local_files_only=True)
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        nli_path, local_files_only=True, torch_dtype=torch.bfloat16
    ).to(DEV).eval()
    id2label = nli_model.config.id2label
    ent_idx = [i for i, lbl in id2label.items() if lbl.lower() == "entailment"][0]

    print("  Encoding 6,000 TeCoD skeleton examples...", flush=True)
    P_VECS = t_emb_model.encode(
        [EMB_PROMPTS["skeleton"].format(query=t) for t in masked_all],
        convert_to_numpy=True,
        batch_size=64,
        show_progress_bar=False,
    )
    P_VECS = P_VECS / np.linalg.norm(P_VECS, axis=1, keepdims=True)

    # Warmup
    _ = t_emb_model.encode([EMB_PROMPTS["query"].format(query="预热")], convert_to_numpy=True, show_progress_bar=False)
    with torch.inference_mode():
        w_in = nli_tok([("预热", "预热")], return_tensors="pt", padding=True, truncation=True, max_length=512).to(DEV)
        _ = nli_model(**w_in)
    sync()

    # Pre-encode queries while measuring per-query embedding latency
    TQ_VECS = []
    tq_secs = []
    for r in ALL_REQS:
        sync()
        t0 = time.time()
        v = t_emb_model.encode([EMB_PROMPTS["query"].format(query=r["text"])], convert_to_numpy=True, show_progress_bar=False)[0]
        v = v / np.linalg.norm(v)
        sync()
        tq_secs.append(time.time() - t0)
        TQ_VECS.append(v)
    TQ_MAT = np.stack(TQ_VECS)

    # Free embedding model before running NLI across 4 scales if desired, though 49 GB fits both easily!
    del t_emb_model
    if DEV == "cuda":
        torch.cuda.empty_cache()

    for m in SCALES:
        n_pool = m * 6
        p_sub = pool_all[:n_pool]
        m_sub = masked_all[:n_pool]
        v_sub = P_VECS[:n_pool]
        # Template string sort tie-breaker matches `select sum(m_<def>) from metric_catalog`
        tmpl_str = {ex["def"]: f"select sum(m_{ex['def'].lower()}) from metric_catalog" for ex in p_sub}

        got_all = []
        ent_all = []
        top_def_all = []
        tot_secs = []

        for qi, r in enumerate(ALL_REQS):
            sync()
            t0 = time.time()
            cos = v_sub @ TQ_MAT[qi]
            order = sorted(range(len(cos)), key=lambda i: -cos[i])[:1000]
            top = order[:30]
            premises = [m_sub[i] for i in top]
            inputs = nli_tok(
                [(p, r["text"]) for p in premises],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(DEV)
            with torch.inference_mode():
                logits = nli_model(**inputs).logits
                prob = torch.nn.functional.softmax(logits.float(), dim=-1).cpu().numpy()
            sync()
            tot_secs.append(tq_secs[qi] + (time.time() - t0))

            by_t = {}
            for j, idx_ex in enumerate(top):
                did = p_sub[idx_ex]["def"]
                lbl = id2label[int(np.argmax(prob[j]))]
                by_t.setdefault(did, []).append({
                    "entailment": float(prob[j, ent_idx]),
                    "cosine": float(cos[idx_ex]),
                    "label": lbl,
                })
            considered = sorted(
                (
                    (
                        sum(x["entailment"] for x in g) / len(g),
                        sum(x["cosine"] for x in g) / len(g),
                        did,
                    )
                    for did, g in by_t.items()
                ),
                key=lambda x: (-x[0], -x[1], tmpl_str[x[2]]),
            )
            ent, _, best_did = considered[0]
            labels = [x["label"] for x in by_t[best_did]]
            maj_label = max(dict.fromkeys(labels), key=labels.count)
            matched = maj_label.lower() == "entailment"
            got_all.append([best_did] if matched else [])
            ent_all.append(float(ent))
            top_def_all.append(best_did)

        tecod_summary[str(m)] = {
            "pool_examples": n_pool,
            "latency_ms_mean": round(statistics.mean(tot_secs) * 1000, 2),
            "latency_ms_p95": round(sorted(tot_secs)[int(0.95 * len(tot_secs))] * 1000, 2),
        }
        for sub in SUBSETS:
            idxs = subset_indices(sub)
            exact = sum(got_all[qi] == GOLD[m][ALL_REQS[qi]["uid"]] for qi in idxs)
            abs_idx = [qi for qi in idxs if not GOLD[m][ALL_REQS[qi]["uid"]]]
            abs_rej = sum(got_all[qi] == [] for qi in abs_idx)
            two_idx = [qi for qi in idxs if len(GOLD[m][ALL_REQS[qi]["uid"]]) >= 2]
            one_idx = [qi for qi in idxs if len(GOLD[m][ALL_REQS[qi]["uid"]]) == 1]
            tecod_summary[str(m)][sub] = {
                "n": len(idxs),
                "exact": exact,
                "exact_rate": round(exact / len(idxs), 4),
                "single_n": len(one_idx),
                "single_exact": sum(got_all[qi] == GOLD[m][ALL_REQS[qi]["uid"]] for qi in one_idx),
                "multi_n": len(two_idx),
                "multi_exact": sum(got_all[qi] == GOLD[m][ALL_REQS[qi]["uid"]] for qi in two_idx),
                "absent_n": len(abs_idx),
                "absent_rejected": abs_rej,
                "absent_reject_rate": round(abs_rej / max(1, len(abs_idx)), 4),
            }

        # Risk-Coverage sweep for TeCoD NLI around entailment center 0.50
        rc_curves.setdefault(str(m), {})["tecod_nli"] = {}
        for sub in SUBSETS:
            idxs = subset_indices(sub)
            pts = []
            for w in np.linspace(0.48, 0.0, 25):
                lo_t, hi_t = 0.50 - w, 0.50 + w
                direct_n = wrong_n = 0
                for qi in idxs:
                    e_p = ent_all[qi]
                    g = GOLD[m][ALL_REQS[qi]["uid"]]
                    if e_p >= hi_t:
                        direct_n += 1
                        wrong_n += [top_def_all[qi]] != g
                    elif e_p < lo_t:
                        direct_n += 1
                        wrong_n += [] != g
                cov = direct_n / len(idxs)
                sel_risk = wrong_n / max(1, direct_n)
                pts.append({
                    "w": round(float(w), 3),
                    "coverage": round(cov, 4),
                    "selective_risk": round(sel_risk, 4),
                    "direct_precision": round(1.0 - sel_risk, 4),
                    "overall_wrong_rate": round(wrong_n / len(idxs), 4),
                })
            rc_curves[str(m)]["tecod_nli"][sub] = pts
        print(f"  TeCoD M={m} done: mean={tecod_summary[str(m)]['latency_ms_mean']}ms orig_96={tecod_summary[str(m)]['orig_96']['exact_rate']}", flush=True)


# Collect training time stats from ft_scale if present
train_stats = {}
for p in sorted(Path("ft_scale").glob("*/summary.json")) if Path("ft_scale").exists() else []:
    train_stats[p.parent.name] = json.loads(p.read_text(encoding="utf-8"))

full_out = {
    "device": torch.cuda.get_device_name(0) if DEV == "cuda" else "cpu",
    "scales": SCALES,
    "subsets": {k: len(subset_indices(k)) for k in SUBSETS},
    "recall_bge_m3": recall_summary,
    "name_match": name_summary,
    "emb_top1": emb_summary,
    "tecod_nli_gpu": tecod_summary,
    "cross_encoders": ce_results,
    "train_scale_stats": train_stats,
}
(OUT / "gpu-summary.json").write_text(json.dumps(full_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(OUT / "risk-coverage.json").write_text(json.dumps(rc_curves, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("=== ALL GPU BENCHMARKS COMPLETE ===", flush=True)
