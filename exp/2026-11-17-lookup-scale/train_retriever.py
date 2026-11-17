#!/usr/bin/env python3
"""Catalog-tuned Stage-1 retriever for lookup revision v2 (registered 2026-11-17, see README section 4).

Fine-tunes BAAI/bge-m3 (dense CLS embedding) on exactly the synthetic phrasings the judges are trained on
(train_26_clean.jsonl + train_scale_extra.jsonl, labels from Definition 4.1 over catalog_1000.json). No test
request is read. The dev split is the judges' seed-13 split (12% of stated-attribute keys held out), used only to
report dev Recall@K before and after training.

Loss: InfoNCE over in-batch documents (each anchor's positive + one same-channel/same-subject hard negative per
anchor), temperature 0.02; documents that are also gold for an anchor are masked out of its negatives (homonymous
pairs and multi-definition answers are gold together). Fixed recipe, no tuning: 2 epochs, batch 64, lr 1e-5,
warmup 10%, BF16 autocast.
"""
import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer
from transformers import get_linear_schedule_with_warmup

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="ft_retriever/bge-m3-cat-s13")
ap.add_argument("--catalog", default="catalog_1000.json")
ap.add_argument("--train-base", default="train_26_clean.jsonl")
ap.add_argument("--train-extra", default="train_scale_extra.jsonl", help="comma-separated; v3 adds train_scale_llm.jsonl")
ap.add_argument("--base", default="models/bge-m3")
ap.add_argument("--seed", type=int, default=13)
ap.add_argument("--epochs", type=int, default=2)
ap.add_argument("--batch", type=int, default=64)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--temp", type=float, default=0.02)
ap.add_argument("--q-len", type=int, default=96)
ap.add_argument("--d-len", type=int, default=192)
args = ap.parse_args()

OUT = Path(args.out)
if (OUT / "summary.json").exists():
    print(f"Already completed {OUT}, skipping.", flush=True)
    raise SystemExit(0)
OUT.mkdir(parents=True, exist_ok=True)
random.seed(args.seed)
np.random.seed(args.seed)
torch.manual_seed(args.seed)
torch.cuda.manual_seed_all(args.seed)

CAT = json.load(open(args.catalog, encoding="utf-8"))
DEFS = CAT["definitions"]
SLOTS = list(CAT["facet_names"])
BY_ID = {d["id"]: d for d in DEFS}


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


def def_text(d):
    return f"{d['name']}：{d['text']}"


qs = [json.loads(l) for l in open(args.train_base, encoding="utf-8") if l.strip()]
qs += [json.loads(l) for f in args.train_extra.split(",") for l in open(f, encoding="utf-8") if l.strip()]
for q in qs:
    q["gold_full"] = sorted(d["id"] for d in DEFS if consistent(d["facets"], q["stated"]))

# Same dev split as train_scale_ce.py with the same seed.
keys = sorted({json.dumps(q["stated"], ensure_ascii=False, sort_keys=True) for q in qs})
rng = random.Random(args.seed)
rng.shuffle(keys)
dev_keys = set(keys[: max(1, int(len(keys) * 0.12))])
key = lambda q: json.dumps(q["stated"], ensure_ascii=False, sort_keys=True)  # noqa: E731
train_q = [q for q in qs if key(q) not in dev_keys and q["gold_full"]]
dev_q = [q for q in qs if key(q) in dev_keys]
print(f"train anchors={len(train_q)} dev questions={len(dev_q)} (present {sum(bool(q['gold_full']) for q in dev_q)})", flush=True)

by_channel, by_subject = {}, {}
for d in DEFS:
    by_channel.setdefault(d["facets"].get("channel"), []).append(d["id"])
    by_subject.setdefault(d["facets"].get("subject"), []).append(d["id"])


def hard_negative(q):
    gold = set(q["gold_full"])
    pos = [BY_ID[i] for i in q["gold_full"]]
    chans = {d["facets"].get("channel") for d in pos}
    subs = {d["facets"].get("subject") for d in pos}
    both = [i for c in chans for i in by_channel.get(c, []) if i not in gold and BY_ID[i]["facets"].get("subject") in subs]
    either = [i for c in chans for i in by_channel.get(c, []) if i not in gold]
    either += [i for s in subs for i in by_subject.get(s, []) if i not in gold]
    pool = both if both and rng.random() < 0.5 else either
    if not pool:
        pool = [d["id"] for d in DEFS if d["id"] not in gold]
    return rng.choice(pool)


DEV = "cuda"
model = SentenceTransformer(args.base, device=DEV)
model[0].auto_model.gradient_checkpointing_enable()
tokenizer = model.tokenizer
DTEXT = {d["id"]: def_text(d) for d in DEFS}


def encode_batch(texts, max_len):
    feats = tokenizer(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt").to(DEV)
    out = model[0].auto_model(**feats)
    return F.normalize(out.last_hidden_state[:, 0], dim=-1)  # bge-m3 dense = normalized CLS


@torch.no_grad()
def dev_recall(tag):
    model.eval()
    ids = [d["id"] for d in DEFS]
    dv = model.encode([DTEXT[i] for i in ids], normalize_embeddings=True, batch_size=128, show_progress_bar=False)
    pres = [q for q in dev_q if q["gold_full"]]
    qv = model.encode([q["text"] for q in pres], normalize_embeddings=True, batch_size=128, show_progress_bar=False)
    sims = qv @ dv.T
    res = {}
    for k in (1, 4, 8, 16, 32):
        top = np.argsort(-sims, axis=1)[:, :k]
        ok = sum(set(q["gold_full"]) <= {ids[j] for j in top[n]} for n, q in enumerate(pres))
        res[f"recall@{k}"] = round(ok / len(pres), 4)
    print(f"  dev Recall ({tag}, M=1000, {len(pres)} present dev questions): {res}", flush=True)
    return res


dev_before = dev_recall("before")

steps_per_epoch = (len(train_q) + args.batch - 1) // args.batch
total_steps = args.epochs * steps_per_epoch
opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
sched = get_linear_schedule_with_warmup(opt, int(0.1 * total_steps), total_steps)

torch.cuda.synchronize()
t0 = time.time()
for ep in range(args.epochs):
    model.train()
    order = list(range(len(train_q)))
    rng.shuffle(order)
    tot, nb = 0.0, 0
    for b0 in range(0, len(order), args.batch):
        batch = [train_q[i] for i in order[b0 : b0 + args.batch]]
        pos_ids = [rng.choice(q["gold_full"]) for q in batch]
        neg_ids = [hard_negative(q) for q in batch]
        doc_ids = pos_ids + neg_ids
        # mask[i, j] = True where document j is gold for anchor i but is not anchor i's own positive column
        mask = torch.tensor(
            [[(doc_ids[j] in set(q["gold_full"])) and j != i for j in range(len(doc_ids))] for i, q in enumerate(batch)],
            device=DEV,
        )
        opt.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            qv = encode_batch([q["text"] for q in batch], args.q_len)
            dv = encode_batch([DTEXT[i] for i in doc_ids], args.d_len)
        logits = (qv.float() @ dv.float().T) / args.temp
        logits = logits.masked_fill(mask, -1e4)
        loss = F.cross_entropy(logits, torch.arange(len(batch), device=DEV))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        tot += float(loss.detach())
        nb += 1
    print(f"  epoch {ep + 1}/{args.epochs} loss={tot / max(1, nb):.4f} elapsed={time.time() - t0:.1f}s", flush=True)

torch.cuda.synchronize()
train_sec = round(time.time() - t0, 2)
dev_after = dev_recall("after")
model.save(str(OUT / "model"))
summary = {
    "base": args.base,
    "catalog": args.catalog,
    "seed": args.seed,
    "epochs": args.epochs,
    "batch": args.batch,
    "lr": args.lr,
    "temperature": args.temp,
    "train_anchors": len(train_q),
    "dev_questions_present": sum(bool(q["gold_full"]) for q in dev_q),
    "dev_recall_before": dev_before,
    "dev_recall_after": dev_after,
    "device": torch.cuda.get_device_name(0),
    "train_seconds": train_sec,
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("DONE:", json.dumps(summary, ensure_ascii=False), flush=True)
