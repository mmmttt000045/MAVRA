#!/usr/bin/env python3
"""Multi-domain scale cross-encoder trainer (runs in BF16 on CUDA).

Trains either:
  --def-contrast : MAVRA consistency judge with structured facets & bounded peer differences
  (omit flag)    : Controlled Single Cross-Encoder baseline WITHOUT facets or peer differences

Uses the catalog-synthesized training data (train_26_clean.jsonl + train_scale_extra.jsonl + train_scale_llm.jsonl),
pair ratio (~13 pairs/question), AdamW + linear warmup schedule, and BCEWithLogitsLoss.
"""
import argparse
import json
import random
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--catalog", default="catalog_1000.json")
ap.add_argument("--train-base", default="train_26_clean.jsonl")
ap.add_argument("--train-extra", default="train_scale_extra.jsonl", help="comma-separated extra training JSONL files")
ap.add_argument("--base", default="BAAI/bge-reranker-base")
ap.add_argument("--seed", type=int, default=13)
ap.add_argument("--epochs", type=int, default=4)
ap.add_argument("--batch", type=int, default=64)
ap.add_argument("--lr", type=float, default=2e-5)
ap.add_argument("--pos-weight", type=float, default=1.0)
ap.add_argument("--max-hard", type=int, default=10)
ap.add_argument("--rand-neg", type=int, default=3)
ap.add_argument("--def-contrast", action="store_true")
ap.add_argument("--max-len", type=int, default=384)
args = ap.parse_args()

OUT = Path(args.out)
if (OUT / "summary.json").exists() and (OUT / "model").exists():
    print(f"Already completed {OUT}, skipping.", flush=True)
    raise SystemExit(0)
OUT.mkdir(parents=True, exist_ok=True)
random.seed(args.seed)
torch.manual_seed(args.seed)
torch.cuda.manual_seed_all(args.seed)

CAT = json.load(open(args.catalog, encoding="utf-8"))
DEFS = CAT["definitions"]
FN = CAT["facet_names"]
SLOTS = list(FN)


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


DTEXT = {d["id"]: render(d, DEFS, args.def_contrast) for d in DEFS}

qs = [json.loads(l) for l in open(args.train_base, encoding="utf-8") if l.strip()]
qs += [json.loads(l) for f in args.train_extra.split(",") for l in open(f, encoding="utf-8") if l.strip()]
for q in qs:
    q["gold_full"] = sorted(d["id"] for d in DEFS if consistent(d["facets"], q["stated"]))

keys = sorted({json.dumps(q["stated"], ensure_ascii=False, sort_keys=True) for q in qs})
rng = random.Random(args.seed)
rng.shuffle(keys)
dev_keys = set(keys[: max(1, int(len(keys) * 0.12))])
train_q = [q for q in qs if json.dumps(q["stated"], ensure_ascii=False, sort_keys=True) not in dev_keys]

by_id = {d["id"]: d for d in DEFS}
by_channel = {}
by_subject = {}
for d in DEFS:
    by_channel.setdefault(d["facets"].get("channel"), []).append(d)
    by_subject.setdefault(d["facets"].get("subject"), []).append(d)


def make_pairs(q):
    pos_ids = set(q["gold_full"])
    pos = [by_id[i] for i in q["gold_full"]]
    st = q["stated"]
    chans = set([st["channel"]] if isinstance(st.get("channel"), str) else st.get("channel", [])) | {d["facets"].get("channel") for d in pos}
    subs = set([st["subject"]] if isinstance(st.get("subject"), str) else st.get("subject", [])) | {d["facets"].get("subject") for d in pos}
    cats = set([st["category"]] if isinstance(st.get("category"), str) else st.get("category", [])) | {d["facets"].get("category") for d in pos}

    cand_hard = {}
    for ch in chans:
        for d in by_channel.get(ch, []):
            if d["id"] not in pos_ids:
                cand_hard[d["id"]] = d
    for sb in subs:
        for d in by_subject.get(sb, []):
            if d["id"] not in pos_ids:
                cand_hard[d["id"]] = d

    hard_list = list(cand_hard.values())
    # Prioritize peers sharing BOTH channel and subject, or category, then shuffle within tier
    rng.shuffle(hard_list)
    hard_list.sort(
        key=lambda d: (
            not (d["facets"].get("channel") in chans and d["facets"].get("subject") in subs),
            not (d["facets"].get("category") in cats),
        )
    )
    picked_hard = hard_list[: args.max_hard]
    picked_ids = pos_ids | {d["id"] for d in picked_hard}
    rand_pool = [d for d in DEFS if d["id"] not in picked_ids]
    picked_rand = rng.sample(rand_pool, min(args.rand_neg, len(rand_pool)))
    pick = pos + picked_hard + picked_rand
    return [(q["text"], DTEXT[d["id"]], float(d["id"] in pos_ids)) for d in pick]


pairs = [p for q in train_q for p in make_pairs(q)]
print(f"[seed={args.seed} contrast={args.def_contrast}] train_q={len(train_q)} pairs={len(pairs)} pos={int(sum(p[2] for p in pairs))}", flush=True)

DEV = "cuda"
tok = AutoTokenizer.from_pretrained(args.base)
model = AutoModelForSequenceClassification.from_pretrained(args.base, num_labels=1).to(DEV)
opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
steps = args.epochs * ((len(pairs) + args.batch - 1) // args.batch)
sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
lossf = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(args.pos_weight, device=DEV))

torch.cuda.synchronize()
t0 = time.time()
# Pre-tokenize all pairs once with fast Rust tokenizer and bucket within megabatches to minimize PAD waste
enc_all = tok([x[0] for x in pairs], [x[1] for x in pairs], truncation=True, max_length=args.max_len, padding=False)
items = list(zip(enc_all["input_ids"], enc_all["attention_mask"], [x[2] for x in pairs]))
pad_id = tok.pad_token_id if tok.pad_token_id is not None else 1
mega = 32 * args.batch

for ep in range(args.epochs):
    rng.shuffle(items)
    batches = []
    for m0 in range(0, len(items), mega):
        chunk = sorted(items[m0 : m0 + mega], key=lambda z: len(z[0]))
        for i in range(0, len(chunk), args.batch):
            batches.append(chunk[i : i + args.batch])
    rng.shuffle(batches)
    model.train()
    total_loss = 0.0
    nb = 0
    for b in batches:
        ml = max(len(z[0]) for z in b)
        ids_t = torch.tensor([z[0] + [pad_id] * (ml - len(z[0])) for z in b], dtype=torch.long, device=DEV)
        msk_t = torch.tensor([z[1] + [0] * (ml - len(z[1])) for z in b], dtype=torch.long, device=DEV)
        y = torch.tensor([z[2] for z in b], dtype=torch.float32, device=DEV)
        opt.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(input_ids=ids_t, attention_mask=msk_t).logits.squeeze(-1)
            loss = lossf(logits, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        total_loss += float(loss.detach().cpu())
        nb += 1
    print(f"  epoch {ep+1}/{args.epochs} loss={total_loss/max(1,nb):.4f} elapsed={time.time()-t0:.1f}s", flush=True)

torch.cuda.synchronize()
train_sec = round(time.time() - t0, 2)
model_dir = OUT / "model"
model_dir.mkdir(parents=True, exist_ok=True)
model.save_pretrained(model_dir)
tok.save_pretrained(model_dir)

summary = {
    "base": args.base,
    "catalog": args.catalog,
    "definitions": len(DEFS),
    "seed": args.seed,
    "epochs": args.epochs,
    "batch": args.batch,
    "lr": args.lr,
    "def_contrast": args.def_contrast,
    "max_len": args.max_len,
    "train_questions": len(train_q),
    "train_pairs": len(pairs),
    "positive_pairs": int(sum(p[2] for p in pairs)),
    "device": torch.cuda.get_device_name(0),
    "bf16": True,
    "train_seconds": train_sec,
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("DONE:", json.dumps(summary, ensure_ascii=False), flush=True)
