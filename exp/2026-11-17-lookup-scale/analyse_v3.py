#!/usr/bin/env python3
"""Paper numbers for lookup scaling after revision v3 (README 4-7).

MAVRA (refreshed) = v3 (results_v3*/, policy config "v2" on the v3 cache, confirmation family mavra_refreshed_v3).
MAVRA (0-retrain) = frozen 26-definition judges with W + C on raw bge-m3 (registered v2 config "wc").
Top-8 + LLM       = LLM judge over the v3 retriever's top-8 (the same candidates MAVRA scores).
Single CE (no diff) = README 7.1 (v3 data, no peer differences, oracle threshold, v3 top-8), when present; README 7.3
                      adds the same judges under the full v3 rule (replay_plain_rule.py -> results_v3_plain/).
Name match, Embedding top-1, TeCoD and raw bge-m3 recall are unchanged from Section 3 (scale-summary.json).

Writes scale-summary-v3.json, risk-coverage-v3.json and overleaf/gen/lookup-scale.tex.
"""
import json
import statistics
from math import comb
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
SCALES = ["26", "100", "500", "1000"]
STAG = {"26": "Base", "100": "C", "500": "D", "1000": "K"}
QTAG = {"orig_96": "Orig", "glm_174": "Glm", "scale_120": "Scale", "all_390": "All"}
J = lambda p: json.load(open(H / p, encoding="utf-8"))  # noqa: E731
E = lambda p: (H / p).exists()  # noqa: E731

v1 = J("scale-summary.json")
v1rc = J("risk-coverage.json")
P3, P3f = J("results_v3/policy-summary.json"), J("results_v3_fresh/policy-summary.json")
L3, L3f = J("results_v3/llm/llm-summary.json"), J("results_v3_fresh/llm/llm-summary.json")
P2, L2 = J("results_v2/policy-summary.json"), J("results_v2/llm/llm-summary.json")
RC3 = J("results_v3/risk-coverage-v2.json")
C3 = J("results_v3/cache.json")


def rows(path):
    return {x["uid"]: x for x in map(json.loads, open(H / path, encoding="utf-8"))}


def mcnemar(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


summ = {k: v1[k] for k in ("device", "scales", "subsets", "recall_bge_m3", "name_match", "emb_top1", "tecod_nli_gpu")}
summ["recall_tuned_v3"] = P3["recall"]["tuned"]
summ["recall_raw_replay"] = P3["recall"]["raw"]
summ["tuned_query_ms"] = round(1000 * statistics.mean(C3["meta"]["query_encode_seconds"]["tuned"]), 2)
summ["mavra_refreshed_first"] = P3["mavra_refreshed"]["v2"]
summ["mavra_zero_first"] = P2["mavra_zero"]["wc"]
summ["mavra_confirmed"] = {"mavra_refreshed": L3["mavra_confirmed"]["mavra_refreshed_v3"],
                           "mavra_zero": L2["mavra_confirmed"]["mavra_zero_wc"]}
summ["top8_llm_judge"] = L3["top8_llm_judge"]
summ["top8_llm_judge_raw_v1"] = v1["top8_llm_judge"]
summ["fresh"] = {"mavra_refreshed_first": P3f["mavra_refreshed"]["v2"],
                 "mavra_confirmed": L3f["mavra_confirmed"]["mavra_refreshed_v3"],
                 "top8_llm_judge": L3f["top8_llm_judge"],
                 "recall_tuned_v3": P3f["recall"]["tuned"], "recall_raw": P3f["recall"]["raw"]}
summ["train_v3"] = {n: J(f"logs_v3/summary-{n}.json") for n in
                    ("scale-dc-llm-s13", "scale-dc-llm-s14", "scale-dc-llm-s15", "bge-m3-cat-llm-s13")}

# paired tests MAVRA (final) vs Top-8 + LLM, and absent-request answers
paired = {}
for tag, d, subs in (("main", "results_v3", ("all_390", "orig_96", "glm_174", "scale_120")), ("fresh", "results_v3_fresh", ("glm_scale",))):
    for m in SCALES:
        cf, lj = rows(f"{d}/llm/confirm_mavra_refreshed_v3_M{m}.jsonl"), rows(f"{d}/llm/top8_llm_M{m}.jsonl")
        for sub in subs:
            u = [k for k in cf if sub == "all_390" or cf[k]["qset"] == sub]
            b = sum(cf[k]["final_ok"] and not lj[k]["exact"] for k in u)
            c = sum(lj[k]["exact"] and not cf[k]["final_ok"] for k in u)
            ab = [k for k in u if not cf[k]["gold"]]
            paired.setdefault(tag, {}).setdefault(m, {})[sub] = {
                "mavra_only": b, "llm_only": c, "mcnemar_p": round(mcnemar(b, c), 4), "absent_n": len(ab),
                "absent_answered_mavra": sum(bool(cf[k]["final"]) for k in ab),
                "absent_answered_llm": sum(bool(lj[k]["got"]) for k in ab)}
summ["paired"] = paired

# risk-coverage curves at every size
rc = {}
for m in SCALES:
    rc[m] = {"mavra_refreshed": RC3[m]["mavra_refreshed_v2"], "mavra_zero": RC3[m]["mavra_zero_wc"]}
    for k in ("emb_top1", "tecod_nli"):
        if k in v1rc.get(m, {}):
            rc[m][k] = v1rc[m][k]

# README 7.1: single CE without peer differences on the v3 top-8 (oracle threshold, no abstention)
if E("results_v3_plain/cache.json"):
    CP = J("results_v3_plain/cache.json")
    reqs = CP["meta"]["requests"]
    cat = {m: J(f"catalog_{m}.json")["definitions"] for m in SCALES}
    FN = list(J("catalog_1000.json")["facet_names"])

    def consistent(f, stated):
        for s in FN:
            v, st = f.get(s), stated.get(s)
            if st:
                if v is None or v not in ([st] if isinstance(st, str) else st):
                    return False
            elif s == "category" and v is not None:
                return False
            elif s == "channel" and v not in (None, "全渠道"):
                return False
        return True

    sce, mor = {}, {}
    dev_raw = np.array(CP["meta"]["dev_top1_cos"]["raw"]["1000"])
    dev_tuned = np.sort(np.array(CP["meta"]["dev_top1_cos"]["tuned"]["1000"]))

    def map_sigma(s):  # = policy_v2.map_sigma
        if s > 1.0:
            return s
        frac = float((dev_raw >= s).mean())
        return 1.01 if frac <= 0 else float(np.quantile(dev_tuned, 1.0 - frac))

    for m in SCALES:
        gold = [sorted(d["id"] for d in cat[m] if consistent(d["facets"], r["stated"])) for r in reqs]
        ids = CP["recall"]["tuned"][m]["ids"]
        cos = CP["recall"]["tuned"][m]["cos"]
        per = np.array(CP["scores"]["single_ce_refreshed"]["tuned"][m])[:, :, :8]  # judges x req x 8
        mean = per.mean(axis=0)
        mper = np.array(C3["scores"]["mavra_refreshed"]["tuned"][m])[:, :, :8]  # v3 judges, same metric (7.3)
        assert CP["recall"]["tuned"][m]["ids"] == C3["recall"]["tuned"][m]["ids"]
        sce[m], mor[m] = {}, {}
        for sub in QTAG:
            idx = [i for i, r in enumerate(reqs) if sub == "all_390" or r["qset"] == sub]

            def exact(sc, tau):
                return sum(sorted(c for c, s in zip(ids[i][:8], sc[i]) if s >= tau) == gold[i] for i in idx)

            taus = np.linspace(0.05, 0.95, 91)
            best = max(taus, key=lambda t: exact(mean, t))
            seeds = [max(exact(per[j], t) for t in np.linspace(0.05, 0.95, 46)) / len(idx) for j in range(per.shape[0])]
            sce[m][sub] = {"n": len(idx), "no_abstain_best_tau": round(float(best), 3),
                           "no_abstain_exact_rate": round(exact(mean, best) / len(idx), 4),
                           "per_seed_exact_rates": [round(x, 4) for x in seeds]}
            mm = mper.mean(axis=0)
            mb = max(taus, key=lambda t: exact(mm, t))
            mor[m][sub] = {"no_abstain_best_tau": round(float(mb), 3), "no_abstain_exact_rate": round(exact(mm, mb) / len(idx), 4),
                           "per_seed_exact_rates": [round(max(exact(mper[j], t) for t in np.linspace(0.05, 0.95, 46)) / len(idx), 4)
                                                    for j in range(mper.shape[0])]}
        # risk-coverage with the Section 3 schedule (v1 rule: no W/C)
        pts = []
        for u in [k / 20 for k in range(21)]:
            if u <= 0.5:
                a = u / 0.5
                lo, hi, sg = 0.005 + a * 0.095, 0.995 - a * 0.095, 0.45 + a * 0.15
            else:
                a = (u - 0.5) / 0.5
                lo, hi, sg = 0.10 + a * 0.20, 0.90 - a * 0.60, 0.60 + a * 0.41
            dn = wn = 0
            for i in range(len(reqs)):
                s8 = mean[i]
                acc = [c for c, s in zip(ids[i][:8], s8) if s >= hi]
                unc = [c for c, s in zip(ids[i][:8], s8) if lo <= s < hi]
                if unc:
                    continue
                if acc:
                    dn += 1
                    wn += sorted(acc) != gold[i]
                elif cos[i][0] < map_sigma(sg):
                    dn += 1
                    wn += gold[i] != []
            pts.append({"coverage": round(dn / len(reqs), 4), "selective_risk": round(wn / max(1, dn), 4)})
        rc[m]["single_ce_refreshed_v1rule"] = {"all_390": pts}   # registered 7.1 curve
    summ["single_ce_refreshed"] = sce
    summ["mavra_refreshed_oracle"] = mor
    summ["single_ce_refreshed_dirs"] = CP["meta"]["plain_dirs"]

# README 7.3 (attribution): plain judges under the full v3 rule; MAVRA's own judges without W/C (registered config r)
for m in SCALES:
    rc[m]["mavra_refreshed_r"] = RC3[m]["mavra_refreshed_r"]
summ["mavra_refreshed_first_r"] = P3["mavra_refreshed"]["r"]
if E("results_v3_plain/policy-summary.json"):
    PP, RP = J("results_v3_plain/policy-summary.json"), J("results_v3_plain/risk-coverage-v2.json")
    summ["single_ce_rule"] = {"v2": PP["mavra_refreshed"]["v2"], "r": PP["mavra_refreshed"]["r"]}
    for m in SCALES:
        rc[m]["single_ce_refreshed"] = RP[m]["mavra_refreshed_v2"]
        rc[m]["single_ce_refreshed_r"] = RP[m]["mavra_refreshed_r"]

# README 7.2: training density
if E("results_v3_thin/policy-summary.json"):
    summ["thin_density"] = J("results_v3_thin/policy-summary.json")["mavra_refreshed"]["v2"]

(H / "scale-summary-v3.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
(H / "risk-coverage-v3.json").write_text(json.dumps(rc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- macros
mac = {}
pct = lambda x: f"{100.0 * float(x):.1f}"  # noqa: E731
for sc, st in STAG.items():
    mac[f"LsRecLat{st}Ms"] = f"{v1['recall_bge_m3'][sc]['latency_ms_mean']:.0f}"
    for qs, qt in QTAG.items():
        mac[f"LsRecEight{st}{qt}"] = pct(v1["recall_bge_m3"][sc][qs]["recall@8_all"])
        mac[f"LsRecTunedEight{st}{qt}"] = pct(P3["recall"]["tuned"][sc][qs]["recall@8_all"])
        mac[f"LsName{st}{qt}"] = pct(v1["name_match"][sc][qs]["exact_rate"])
        mac[f"LsEmb{st}{qt}"] = pct(v1["emb_top1"][sc][qs]["oracle_exact_rate"])
        if sc in v1["tecod_nli_gpu"]:
            mac[f"LsTecod{st}{qt}"] = pct(v1["tecod_nli_gpu"][sc][qs]["exact_rate"])
            mac[f"LsTecodLat{st}Ms"] = f"{v1['tecod_nli_gpu'][sc]['latency_ms_mean']:.0f}"
        t = L3["top8_llm_judge"][sc][qs]
        mac[f"LsTopLlm{st}{qt}"] = pct(t["exact_rate"])
        mac[f"LsTopLlmTok{st}{qt}"] = f"{t['tokens_mean']:.0f}"
        mac[f"LsTopLlmSec{st}{qt}"] = f"{t['seconds_mean']:.1f}"
        for fam, mt, first in (("mavra_refreshed", "MavRef", P3["mavra_refreshed"]["v2"]),
                               ("mavra_zero", "MavZero", P2["mavra_zero"]["wc"])):
            a = first[sc][qs]
            mac[f"Ls{mt}First{st}{qt}"] = pct(a["first_exact_rate"])
            mac[f"Ls{mt}Cov{st}{qt}"] = pct(a["direct_coverage"])
            mac[f"Ls{mt}Prec{st}{qt}"] = pct(a["direct_precision"])
            mac[f"Ls{mt}Risk{st}{qt}"] = pct(a["selective_risk"])
            b = summ["mavra_confirmed"][fam][sc][qs]
            mac[f"Ls{mt}Final{st}{qt}"] = pct(b["final_exact_rate"])
            mac[f"Ls{mt}AbsRej{st}{qt}"] = pct(b["absent_reject_rate"])
            mac[f"Ls{mt}Tok{st}{qt}"] = f"{b['tokens_mean']:.0f}"
            mac[f"Ls{mt}Sec{st}{qt}"] = f"{b['seconds_mean']:.2f}"
        if "single_ce_refreshed" in summ:
            r = summ["single_ce_refreshed"][sc][qs]
            mac[f"LsSceRef{st}{qt}"] = pct(r["no_abstain_exact_rate"])
            mac[f"LsSceRefOne{st}{qt}"] = pct(statistics.mean(r["per_seed_exact_rates"]))
            mac[f"LsMavRefOracle{st}{qt}"] = pct(summ["mavra_refreshed_oracle"][sc][qs]["no_abstain_exact_rate"])
        else:  # README 7.1 still running: visible placeholder, never shipped
            mac[f"LsSceRef{st}{qt}"] = mac[f"LsSceRefOne{st}{qt}"] = "??"
        if "thin_density" in summ:
            r = summ["thin_density"][sc][qs]
            mac[f"LsThinFirst{st}{qt}"] = pct(r["first_exact_rate"])
            mac[f"LsThinRisk{st}{qt}"] = pct(r["selective_risk"])
            mac[f"LsThinCov{st}{qt}"] = pct(r["direct_coverage"])
        else:
            mac[f"LsThinFirst{st}{qt}"] = mac[f"LsThinRisk{st}{qt}"] = mac[f"LsThinCov{st}{qt}"] = "??"
        a = P3["mavra_refreshed"]["r"][sc][qs]
        mac[f"LsMavRefNoWcFirst{st}{qt}"], mac[f"LsMavRefNoWcCov{st}{qt}"], mac[f"LsMavRefNoWcRisk{st}{qt}"] = \
            pct(a["first_exact_rate"]), pct(a["direct_coverage"]), pct(a["selective_risk"])
        if "single_ce_rule" in summ:
            for cfg, tag in (("v2", "SceRule"), ("r", "SceRuleNoWc")):
                a = summ["single_ce_rule"][cfg][sc][qs]
                mac[f"Ls{tag}First{st}{qt}"], mac[f"Ls{tag}Cov{st}{qt}"], mac[f"Ls{tag}Risk{st}{qt}"] = \
                    pct(a["first_exact_rate"]), pct(a["direct_coverage"]), pct(a["selective_risk"])
        p = paired["main"][sc][qs]
        mac[f"LsPairP{st}{qt}"] = f"{p['mcnemar_p']:.2f}"
    mac[f"LsMavRefLat{st}Ms"] = f"{C3['timing_v2'][sc]['latency_ms_mean']:.0f}"
    # unchanged Section 3 method (Table V uses its latency)
    mac[f"LsSceZeroLat{st}Ms"] = f"{v1['cross_encoders']['single_ce_zero'][sc]['latency_ms_mean']:.0f}"
    # fresh check (204 GLM rewrites of the multi-domain requests)
    fa, fb, ft = P3f["mavra_refreshed"]["v2"][sc]["glm_scale"], L3f["mavra_confirmed"]["mavra_refreshed_v3"][sc]["glm_scale"], \
        L3f["top8_llm_judge"][sc]["glm_scale"]
    mac[f"LsFreshMavFinal{st}"] = pct(fb["final_exact_rate"])
    mac[f"LsFreshMavRisk{st}"] = pct(fa["selective_risk"])
    mac[f"LsFreshMavCov{st}"] = pct(fa["direct_coverage"])
    mac[f"LsFreshLlm{st}"] = pct(ft["exact_rate"])
    mac[f"LsFreshPairP{st}"] = f"{paired['fresh'][sc]['glm_scale']['mcnemar_p']:.3f}"
    mac[f"LsFreshAbsN{st}"] = str(paired["fresh"][sc]["glm_scale"]["absent_n"])
    mac[f"LsFreshAbsAnsMav{st}"] = str(paired["fresh"][sc]["glm_scale"]["absent_answered_mavra"])
    mac[f"LsFreshAbsAnsLlm{st}"] = str(paired["fresh"][sc]["glm_scale"]["absent_answered_llm"])

k = "1000"
mac["LsTokRatioK"] = f"{L3['top8_llm_judge'][k]['all_390']['tokens_mean'] / summ['mavra_confirmed']['mavra_refreshed'][k]['all_390']['tokens_mean']:.1f}"
mac["LsSecRatioK"] = f"{L3['top8_llm_judge'][k]['all_390']['seconds_mean'] / summ['mavra_confirmed']['mavra_refreshed'][k]['all_390']['seconds_mean']:.1f}"
strict = [p for p in RC3[k]["mavra_refreshed_v2"]["all_390"] if p["selective_risk"] <= 0.02]
best = max(strict, key=lambda p: p["coverage"])
mac["LsMavRefStrictRiskK"], mac["LsMavRefStrictCovK"] = pct(best["selective_risk"]), pct(best["coverage"])
mac["LsTopLlmRawKAll"] = pct(v1["top8_llm_judge"][k]["all_390"]["exact_rate"])
mac["LsEmbRiskFullK"] = pct(v1rc[k]["emb_top1"]["all_390"][-1]["selective_risk"])   # full coverage, unchanged method
mac["LsTecodRiskFullK"] = pct(v1rc[k]["tecod_nli"]["all_390"][-1]["selective_risk"])
pm = paired["main"]["26"]["all_390"]
mac["LsMainAbsNBase"], mac["LsMainAbsAnsMavBase"], mac["LsMainAbsAnsLlmBase"] = \
    str(pm["absent_n"]), str(pm["absent_answered_mavra"]), str(pm["absent_answered_llm"])
mac["LsRecTunedLatMs"] = f"{summ['tuned_query_ms']:.0f}"
dc = [summ["train_v3"][f"scale-dc-llm-s{s}"]["train_seconds"] for s in (13, 14, 15)]
mac["LsScaleTrainMeanMin"] = f"{statistics.mean(dc) / 60:.0f}"
mac["LsScaleTrainQ"] = f"{summ['train_v3']['scale-dc-llm-s13']['train_questions'] / 1000:.1f}"
mac["LsRetrTrainMin"] = f"{summ['train_v3']['bge-m3-cat-llm-s13']['train_seconds'] / 60:.0f}"
gen = json.loads((H / "gen_train_llm.log").read_text(encoding="utf-8").strip().splitlines()[-1])
mac["LsGenCalls"] = f"{gen['calls']:,}".replace(",", "{,}")
mac["LsGenQ"] = f"{gen['questions']:,}".replace(",", "{,}")
mac["LsCorePerIntent"], mac["LsAddPerIntent"] = "78", "6"  # medians, README 7.2

tex = ["% Generated by exp/2026-11-17-lookup-scale/analyse_v3.py (revision v3, README 4-7); do not edit."]
tex += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(mac.items())]
(ROOT / "overleaf/gen/lookup-scale.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
print(f"wrote {len(mac)} macros; single CE: {'yes' if 'single_ce_refreshed' in summ else 'pending'}; "
      f"density: {'yes' if 'thin_density' in summ else 'pending'}")
