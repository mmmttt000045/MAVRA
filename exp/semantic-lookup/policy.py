#!/usr/bin/env python3
"""Replay selective semantic lookup routing policies from score_cache.py's cache.

Configurations:
  raw_base  off-the-shelf bge-m3 top-8 without W/C
  wc        off-the-shelf bge-m3 + absence widening (W) + peer-group coherence (C) (= MAVRA 0-retrain)
  r         catalog-tuned recall only (R)
  full      R + W + C (= MAVRA refreshed)

Writes policy-summary.json, risk-coverage.json, and, for LLM confirmation,
for_llm/responses_<family>_<config>_M<m>.jsonl plus top8_M<m>.jsonl.
"""
import argparse
import json
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--cache", default="results/lookup/cache.json")
ap.add_argument("--out", default="results/lookup")
args = ap.parse_args()

HERE = Path(__file__).resolve().parent
OUT = Path(args.out)
(OUT / "for_llm").mkdir(parents=True, exist_ok=True)
C = json.load(open(args.cache, encoding="utf-8"))
META = C["meta"]
SCALES = META["scales"]
REQS = META["requests"]
K, LO, HI, SIGMA = 8, 0.10, 0.90, 0.60
QSET_NAMES = list(dict.fromkeys(r["qset"] for r in REQS))
SUBSETS = QSET_NAMES + (["all_390"] if QSET_NAMES == ["orig_96", "glm_174", "scale_120"] else [])
TIMED = bool(C.get("timing"))

CAT = json.load(open(HERE / "catalog_1000.json", encoding="utf-8"))
FN = CAT["facet_names"]
SLOTS = list(FN)
CATALOGS = {m: json.load(open(HERE / f"catalog_{m}.json", encoding="utf-8"))["definitions"] for m in SCALES}


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


GOLD = {m: [sorted(d["id"] for d in CATALOGS[m] if consistent(d["facets"], r["stated"])) for r in REQS] for m in SCALES}


def fv(d, s):
    v = d["facets"].get(s)
    return v if v else ("全部商品" if s == "category" else "无")


def describe(d):
    return f"{d['name']}（{d['id']}）：" + "，".join(f"{FN[s]}={fv(d, s)}" for s in FN if d["facets"].get(s))


def explain(ids, byid):
    if len(ids) < 2:
        return ""
    ds = [byid[i] for i in ids]
    slots = [s for s in FN if len({fv(d, s) for d in ds}) > 1]
    return "；".join(f"{FN[s]}：" + " / ".join(f"{d['name']}（{d['id']}）为{fv(d, s)}" for d in ds) for s in slots)


def group(d):
    f = d["facets"]
    return (f.get("subject"), f.get("category"), f.get("channel") or "全渠道")


dev_raw = np.array(META["dev_top1_cos"]["raw"]["1000"])
dev_tuned = np.sort(np.array(META["dev_top1_cos"]["tuned"]["1000"]))


def map_sigma(s):
    if s > 1.0:
        return s
    frac_above = float((dev_raw >= s).mean())
    if frac_above <= 0:
        return 1.01
    return float(np.quantile(dev_tuned, 1.0 - frac_above))


SIGMA_TUNED = map_sigma(SIGMA)


def decide(cands, cos, sc, byid, lo, hi, sig, coherence, widen):
    """Return (mode, picked). cands/cos/sc are top-32 lists; the first K are the deployed top-8."""
    c8, s8 = cands[:K], sc[:K]
    acc = [c for c, s in zip(c8, s8) if s >= hi]
    unc = [c for c, s in zip(c8, s8) if lo <= s < hi]
    if unc:
        return "refer", sorted(acc + unc)
    if acc:
        if len(acc) > 1 and coherence and len({group(byid[c]) for c in acc}) > 1:
            return "refer", sorted(acc)
        return "answer", sorted(acc)
    if widen:
        extra = [c for c, s in zip(cands[K:], sc[K:]) if s >= lo]
        if extra:
            return "refer", sorted(extra)
    if cos[0] >= sig:
        return "similar", [cands[0]]
    return "none", []


def reply_text(mode, picked, byid):
    if mode == "refer":
        rep = "拿不准，以下定义相近，请确认是否其中之一：" + "；".join(describe(byid[i]) for i in picked)
        if len(picked) > 1:
            rep += "。区别：" + explain(picked, byid)
        return rep
    if mode == "answer":
        if len(picked) == 1:
            return "命中：" + describe(byid[picked[0]])
        return f"同名不同义，共 {len(picked)} 条：" + "；".join(describe(byid[i]) for i in picked) + "。区别：" + explain(picked, byid)
    if mode == "similar":
        return "没有找到口径一致的定义；最相近的是 " + describe(byid[picked[0]]) + "，请确认它是否就是你要的，否则需要自己计算"
    return "目录中没有与之一致的定义。"


CONFIGS = {
    "raw_base": dict(retriever="raw", coherence=False, widen=False),
    "wc": dict(retriever="raw", coherence=True, widen=True),
    "r": dict(retriever="tuned", coherence=False, widen=False),
    "full": dict(retriever="tuned", coherence=True, widen=True),
}
EXPORT = {
    ("mavra_refreshed", "raw_base"),
    ("mavra_refreshed", "full"),
    ("mavra_zero", "raw_base"),
    ("mavra_zero", "wc"),
    ("mavra_refreshed", "r"),
    ("mavra_refreshed", "wc"),
}


def subset_idx(sub):
    return list(range(len(REQS))) if sub == "all_390" else [i for i, r in enumerate(REQS) if r["qset"] == sub]


def schedule():
    tau_c, pts = 0.30, []
    for k in range(21):
        u = k / 20.0
        if u <= 0.5:
            a = u / 0.5
            pts.append((0.005 + a * 0.095, 0.995 - a * 0.095, 0.45 + a * 0.15))
        else:
            a = (u - 0.5) / 0.5
            pts.append((0.10 + a * (tau_c - 0.10), 0.90 + a * (tau_c - 0.90), 0.60 + a * 0.41))
    return pts


summary, rc = {"sigma_tuned": round(SIGMA_TUNED, 4), "dev_questions": META["dev_questions"]}, {}
for fam in ("mavra_zero", "mavra_refreshed"):
    for cname, cfg in CONFIGS.items():
        rname = cfg["retriever"]
        sig_of = (lambda s: s) if rname == "raw" else map_sigma
        for m in SCALES:
            ms = str(m)
            byid = {d["id"]: d for d in CATALOGS[m]}
            cands = C["recall"][rname][ms]["ids"]
            coss = C["recall"][rname][ms]["cos"]
            per = C["scores"][fam][rname][ms]
            mean = [list(np.mean([per[j][qi] for j in range(len(per))], axis=0)) for qi in range(len(REQS))]
            rows = []
            for qi, r in enumerate(REQS):
                mode, picked = decide(cands[qi], coss[qi], mean[qi], byid, LO, HI, sig_of(SIGMA), cfg["coherence"], cfg["widen"])
                g = GOLD[m][qi]
                first = picked if mode in ("answer", "refer") else []
                usable = (mode in ("answer", "none") and first == g) or (mode in ("refer", "similar") and (set(g) <= set(picked) if g else True))
                secs = C["timing"][ms]["seconds"][qi] if (cname == "full" and fam == "mavra_refreshed" and TIMED) else None
                rows.append({
                    "uid": r["uid"],
                    "qset": r["qset"],
                    "req": r["id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "mode": mode,
                    "ids": picked,
                    "first_set": first,
                    "first_exact": first == g,
                    "usable": usable,
                    "gold": g,
                    "seconds": secs,
                    "reply": reply_text(mode, picked, byid),
                })
            if (fam, cname) in EXPORT:
                payload = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)
                (OUT / "for_llm" / f"responses_{fam}_{cname}_M{m}.jsonl").write_text(payload, encoding="utf-8")
                if (fam, cname) in {("mavra_refreshed", "full"), ("mavra_zero", "wc")}:
                    (OUT / "for_llm" / f"responses_{fam}_M{m}.jsonl").write_text(payload, encoding="utf-8")
            res = {}
            for sub in SUBSETS:
                sr = [rows[i] for i in subset_idx(sub)]
                direct = [x for x in sr if x["mode"] in ("answer", "none")]
                refer = [x for x in sr if x["mode"] in ("refer", "similar")]
                absr = [x for x in sr if not x["gold"]]
                prec = sum(x["first_set"] == x["gold"] for x in direct) / max(1, len(direct))
                res[sub] = {
                    "n": len(sr),
                    "first_exact": sum(x["first_exact"] for x in sr),
                    "first_exact_rate": round(sum(x["first_exact"] for x in sr) / len(sr), 4),
                    "direct_n": len(direct),
                    "direct_coverage": round(len(direct) / len(sr), 4),
                    "direct_precision": round(prec, 4),
                    "selective_risk": round(1 - prec, 4),
                    "direct_wrong": sum(x["first_set"] != x["gold"] for x in direct),
                    "refer_n": len(refer),
                    "refer_contains_gold": sum(x["usable"] for x in refer),
                    "usable_rate": round(sum(x["usable"] for x in sr) / len(sr), 4),
                    "absent_n": len(absr),
                    "absent_first_rejected": sum(x["first_set"] == [] for x in absr),
                    "modes": {k: sum(x["mode"] == k for x in sr) for k in ("answer", "refer", "similar", "none")},
                }
            if cname == "full" and fam == "mavra_refreshed" and TIMED:
                res["latency_ms_mean"] = C["timing"][ms]["latency_ms_mean"]
                res["widened"] = C["timing"][ms]["widened"]
            summary.setdefault(fam, {}).setdefault(cname, {})[ms] = res
            curves = {}
            for sub in SUBSETS:
                pts = []
                for lo_s, hi_s, sg in schedule():
                    dn = wn = 0
                    for qi in subset_idx(sub):
                        mode, picked = decide(cands[qi], coss[qi], mean[qi], byid, lo_s, hi_s, sig_of(sg), cfg["coherence"], cfg["widen"])
                        if mode in ("answer", "none"):
                            dn += 1
                            wn += (picked if mode == "answer" else []) != GOLD[m][qi]
                    n = len(subset_idx(sub))
                    pts.append({
                        "lo": round(lo_s, 4),
                        "hi": round(hi_s, 4),
                        "sigma": round(sig_of(sg), 4),
                        "coverage": round(dn / n, 4),
                        "selective_risk": round(wn / max(1, dn), 4),
                        "direct_precision": round(1 - wn / max(1, dn), 4),
                        "overall_wrong_rate": round(wn / n, 4),
                    })
                curves[sub] = pts
            rc.setdefault(ms, {})[f"{fam}_{cname}"] = curves

rec = {}
for rname in ("raw", "tuned"):
    for m in SCALES:
        ids = C["recall"][rname][str(m)]["ids"]
        row = {}
        for sub in SUBSETS:
            idx = subset_idx(sub)
            for k in (1, 4, 8, 16, 32):
                row.setdefault(sub, {})[f"recall@{k}_all"] = round(sum(set(GOLD[m][i]) <= set(ids[i][:k]) for i in idx) / len(idx), 4)
        rec.setdefault(rname, {})[str(m)] = row
summary["recall"] = rec

for m in SCALES:
    byid = {d["id"]: d for d in CATALOGS[m]}
    rows = []
    for qi, r in enumerate(REQS):
        cands = C["recall"]["tuned"][str(m)]["ids"][qi][:K]
        rows.append({
            "uid": r["uid"],
            "qset": r["qset"],
            "id": r["id"],
            "kind": r["kind"],
            "text": r["text"],
            "gold": GOLD[m][qi],
            "top8": [{"id": c, "name": byid[c]["name"], "text": byid[c]["text"]} for c in cands],
            "top1_sim": C["recall"]["tuned"][str(m)]["cos"][qi][0],
            "recall_s": round(C["meta"]["query_encode_seconds"]["tuned"][qi], 5),
        })
    (OUT / "for_llm" / f"top8_M{m}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

(OUT / "policy-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(OUT / "risk-coverage.json").write_text(json.dumps(rc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"sigma tuned = {SIGMA_TUNED:.4f}")
for fam in ("mavra_zero", "mavra_refreshed"):
    for cname in CONFIGS:
        for m in SCALES:
            x = summary[fam][cname][str(m)]
            print(
                f"{fam:16s} {cname:8s} M={m:5d} "
                + "  ".join(
                    f"{s}: exact {x[s]['first_exact_rate']:.3f} cov {x[s]['direct_coverage']:.3f} "
                    f"risk {x[s]['selective_risk']:.3f} use {x[s]['usable_rate']:.3f}"
                    for s in SUBSETS
                )
            )
for rname in ("raw", "tuned"):
    print(rname, {m: {s: rec[rname][str(m)][s]["recall@8_all"] for s in SUBSETS} for m in SCALES})
