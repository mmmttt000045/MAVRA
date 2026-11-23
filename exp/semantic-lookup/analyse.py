#!/usr/bin/env python3
"""Paper numbers and LaTeX macros for semantic lookup scaling (Table 3 and Figure 8).

Methods evaluated across nested catalogs M in {26, 100, 500, 1000}:
  - MAVRA (refreshed): catalog-tuned bge-m3 top-8 + three peer-difference XLM-R judges + confirmation.
  - MAVRA (0-retrain): frozen 26-definition judges with W + C routing on off-the-shelf bge-m3.
  - Top-8 + LLM:       LLM judge over the catalog-tuned retriever's top-8 candidates.
  - Single CE (no diff): cross-encoder trained on the same multi-domain corpus without peer differences.
  - Name match, Embedding top-1, TeCoD NLI.

When run without `--results-dir`, loads archived `scale-summary.json` and `risk-coverage.json`
directly and writes all `Ls*` LaTeX macros to `--tex` (`results/gen/lookup-scale.tex`) without
overwriting tracked summary JSONs. When `--results-dir` is supplied, aggregates live score caches
and LLM confirmation outputs into `--out-summary` and `--out-rc`.
"""
import argparse
from math import comb
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCALES = ["26", "100", "500", "1000"]
STAG = {"26": "Base", "100": "C", "500": "D", "1000": "K"}
QTAG = {"orig_96": "Orig", "glm_174": "Glm", "scale_120": "Scale", "all_390": "All"}


def mcnemar(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def build_macros(summ: dict, rc: dict) -> dict[str, str]:
    mac = {}
    pct = lambda x: f"{100.0 * float(x):.1f}"  # noqa: E731
    rec_tuned = summ["recall_tuned"]
    first_ref = summ["mavra_refreshed_first"]
    first_zero = summ["mavra_zero_first"]
    first_ref_r = summ["mavra_refreshed_first_r"]
    paired = summ["paired"]
    fresh = summ["fresh"]

    for sc, st in STAG.items():
        mac[f"LsRecLat{st}Ms"] = f"{summ['recall_bge_m3'][sc]['latency_ms_mean']:.0f}"
        for qs, qt in QTAG.items():
            mac[f"LsRecEight{st}{qt}"] = pct(summ["recall_bge_m3"][sc][qs]["recall@8_all"])
            mac[f"LsRecTunedEight{st}{qt}"] = pct(rec_tuned[sc][qs]["recall@8_all"])
            mac[f"LsName{st}{qt}"] = pct(summ["name_match"][sc][qs]["exact_rate"])
            mac[f"LsEmb{st}{qt}"] = pct(summ["emb_top1"][sc][qs]["oracle_exact_rate"])
            if sc in summ["tecod_nli_gpu"]:
                mac[f"LsTecod{st}{qt}"] = pct(summ["tecod_nli_gpu"][sc][qs]["exact_rate"])
                mac[f"LsTecodLat{st}Ms"] = f"{summ['tecod_nli_gpu'][sc]['latency_ms_mean']:.0f}"
            t = summ["top8_llm_judge"][sc][qs]
            mac[f"LsTopLlm{st}{qt}"] = pct(t["exact_rate"])
            mac[f"LsTopLlmTok{st}{qt}"] = f"{t['tokens_mean']:.0f}"
            mac[f"LsTopLlmSec{st}{qt}"] = f"{t['seconds_mean']:.1f}"
            for fam, mt, first in (
                ("mavra_refreshed", "MavRef", first_ref),
                ("mavra_zero", "MavZero", first_zero),
            ):
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
            else:
                mac[f"LsSceRef{st}{qt}"] = mac[f"LsSceRefOne{st}{qt}"] = "??"
            if "thin_density" in summ:
                r = summ["thin_density"][sc][qs]
                mac[f"LsThinFirst{st}{qt}"] = pct(r["first_exact_rate"])
                mac[f"LsThinRisk{st}{qt}"] = pct(r["selective_risk"])
                mac[f"LsThinCov{st}{qt}"] = pct(r["direct_coverage"])
            else:
                mac[f"LsThinFirst{st}{qt}"] = mac[f"LsThinRisk{st}{qt}"] = mac[f"LsThinCov{st}{qt}"] = "??"
            a = first_ref_r[sc][qs]
            mac[f"LsMavRefNoWcFirst{st}{qt}"] = pct(a["first_exact_rate"])
            mac[f"LsMavRefNoWcCov{st}{qt}"] = pct(a["direct_coverage"])
            mac[f"LsMavRefNoWcRisk{st}{qt}"] = pct(a["selective_risk"])
            if "single_ce_rule" in summ:
                for cfg_key, tag in (("full", "SceRule"), ("r", "SceRuleNoWc")):
                    a = summ["single_ce_rule"][cfg_key][sc][qs]
                    mac[f"Ls{tag}First{st}{qt}"] = pct(a["first_exact_rate"])
                    mac[f"Ls{tag}Cov{st}{qt}"] = pct(a["direct_coverage"])
                    mac[f"Ls{tag}Risk{st}{qt}"] = pct(a["selective_risk"])
            p = paired["main"][sc][qs]
            mac[f"LsPairP{st}{qt}"] = f"{p['mcnemar_p']:.2f}"
        mac[f"LsMavRefLat{st}Ms"] = f"{summ['mavra_refreshed_latency_ms'][sc]:.0f}"
        mac[f"LsSceZeroLat{st}Ms"] = f"{summ['single_ce_zero_latency_ms'][sc]:.0f}"
        fa = fresh["mavra_refreshed_first"][sc]["glm_scale"]
        fb = fresh["mavra_confirmed"][sc]["glm_scale"]
        ft = fresh["top8_llm_judge"][sc]["glm_scale"]
        mac[f"LsFreshMavFinal{st}"] = pct(fb["final_exact_rate"])
        mac[f"LsFreshMavRisk{st}"] = pct(fa["selective_risk"])
        mac[f"LsFreshMavCov{st}"] = pct(fa["direct_coverage"])
        mac[f"LsFreshLlm{st}"] = pct(ft["exact_rate"])
        mac[f"LsFreshPairP{st}"] = f"{paired['fresh'][sc]['glm_scale']['mcnemar_p']:.3f}"
        mac[f"LsFreshAbsN{st}"] = str(paired["fresh"][sc]["glm_scale"]["absent_n"])
        mac[f"LsFreshAbsAnsMav{st}"] = str(paired["fresh"][sc]["glm_scale"]["absent_answered_mavra"])
        mac[f"LsFreshAbsAnsLlm{st}"] = str(paired["fresh"][sc]["glm_scale"]["absent_answered_llm"])

    k = "1000"
    mac["LsTokRatioK"] = f"{summ['top8_llm_judge'][k]['all_390']['tokens_mean'] / summ['mavra_confirmed']['mavra_refreshed'][k]['all_390']['tokens_mean']:.1f}"
    mac["LsSecRatioK"] = f"{summ['top8_llm_judge'][k]['all_390']['seconds_mean'] / summ['mavra_confirmed']['mavra_refreshed'][k]['all_390']['seconds_mean']:.1f}"
    strict = [p for p in rc[k]["mavra_refreshed"]["all_390"] if p["selective_risk"] <= 0.02]
    best = max(strict, key=lambda p: p["coverage"])
    mac["LsMavRefStrictRiskK"], mac["LsMavRefStrictCovK"] = pct(best["selective_risk"]), pct(best["coverage"])
    mac["LsTopLlmRawKAll"] = pct(summ["top8_llm_judge_raw"][k]["all_390"]["exact_rate"])
    mac["LsEmbRiskFullK"] = pct(rc[k]["emb_top1"]["all_390"][-1]["selective_risk"])
    mac["LsTecodRiskFullK"] = pct(rc[k]["tecod_nli"]["all_390"][-1]["selective_risk"])
    pm = paired["main"]["26"]["all_390"]
    mac["LsMainAbsNBase"] = str(pm["absent_n"])
    mac["LsMainAbsAnsMavBase"] = str(pm["absent_answered_mavra"])
    mac["LsMainAbsAnsLlmBase"] = str(pm["absent_answered_llm"])
    mac["LsRecTunedLatMs"] = f"{summ['tuned_query_ms']:.0f}"
    train = summ["train_runs"]
    dc = [train[f"scale-dc-llm-s{s}"]["train_seconds"] for s in (13, 14, 15)]
    mac["LsScaleTrainMeanMin"] = f"{statistics.mean(dc) / 60:.0f}"
    mac["LsScaleTrainQ"] = f"{train['scale-dc-llm-s13']['train_questions'] / 1000:.1f}"
    mac["LsRetrTrainMin"] = f"{train['bge-m3-cat-llm-s13']['train_seconds'] / 60:.0f}"
    gen = summ["gen_train_stats"]
    mac["LsGenCalls"] = f"{gen['calls']:,}".replace(",", "{,}")
    mac["LsGenQ"] = f"{gen['questions']:,}".replace(",", "{,}")
    mac["LsCorePerIntent"], mac["LsAddPerIntent"] = "78", "6"
    if "matched_coverage_attribution" in summ:
        mca = summ["matched_coverage_attribution"]
        mac["LsGridBothRiskK"] = f"{mca['both_risk_pct']:.1f}"
        mac["LsGridChecksRiskK"] = f"{mca['checks_only_risk_pct']:.1f}"
        mac["LsGridInputRiskK"] = f"{mca['input_only_risk_pct']:.1f}"
        mac["LsGridNoneRiskK"] = f"{mca['neither_risk_pct']:.1f}"
        mac["LsChkGainMinK"] = f"{mca['checks_gain_min_pp']:.1f}"
        mac["LsChkGainMaxK"] = f"{mca['checks_gain_max_pp']:.1f}"
    return mac


def aggregate_live(results_dir: Path, base_summary: dict, base_rc: dict) -> tuple[dict, dict]:
    import numpy as np

    jload = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    rows = lambda p: {x["uid"]: x for x in map(json.loads, Path(p).read_text(encoding="utf-8").splitlines() if Path(p).is_file() else [])}  # noqa: E731

    main_dir = results_dir / "lookup"
    fresh_dir = results_dir / "lookup_fresh"
    plain_dir = results_dir / "lookup_plain"
    thin_dir = results_dir / "lookup_thin"

    P = jload(main_dir / "policy-summary.json")
    Pf = jload(fresh_dir / "policy-summary.json")
    L = jload(main_dir / "llm/llm-summary.json")
    Lf = jload(fresh_dir / "llm/llm-summary.json")
    RC = jload(main_dir / "risk-coverage.json")
    C = jload(main_dir / "cache.json")

    summ = dict(base_summary)
    summ["recall_tuned"] = P["recall"]["tuned"]
    summ["recall_raw_replay"] = P["recall"]["raw"]
    summ["tuned_query_ms"] = round(1000 * statistics.mean(C["meta"]["query_encode_seconds"]["tuned"]), 2)
    summ["mavra_refreshed_first"] = P["mavra_refreshed"]["full"]
    summ["mavra_zero_first"] = P["mavra_zero"]["wc"]
    summ["mavra_refreshed_first_r"] = P["mavra_refreshed"]["r"]
    summ["mavra_confirmed"] = {
        "mavra_refreshed": L["mavra_confirmed"].get("mavra_refreshed") or L["mavra_confirmed"]["mavra_refreshed_full"],
        "mavra_zero": L["mavra_confirmed"].get("mavra_zero") or L["mavra_confirmed"]["mavra_zero_wc"],
    }
    summ["top8_llm_judge"] = L["top8_llm_judge"]
    summ["fresh"] = {
        "mavra_refreshed_first": Pf["mavra_refreshed"]["full"],
        "mavra_confirmed": Lf["mavra_confirmed"].get("mavra_refreshed") or Lf["mavra_confirmed"]["mavra_refreshed_full"],
        "top8_llm_judge": Lf["top8_llm_judge"],
        "recall_tuned": Pf["recall"]["tuned"],
        "recall_raw": Pf["recall"]["raw"],
    }
    if C.get("timing"):
        summ["mavra_refreshed_latency_ms"] = {str(k): v["latency_ms_mean"] for k, v in C["timing"].items()}

    paired = {}
    for tag, d, subs in (("main", main_dir, ("all_390", "orig_96", "glm_174", "scale_120")), ("fresh", fresh_dir, ("glm_scale",))):
        for m in SCALES:
            cf_path = d / f"llm/confirm_mavra_refreshed_M{m}.jsonl"
            if not cf_path.is_file():
                cf_path = d / f"llm/confirm_mavra_refreshed_full_M{m}.jsonl"
            cf = rows(cf_path)
            lj = rows(d / f"llm/top8_llm_M{m}.jsonl")
            for sub in subs:
                u = [k for k in cf if sub == "all_390" or cf[k]["qset"] == sub]
                b = sum(cf[k]["final_ok"] and not lj[k]["exact"] for k in u)
                c = sum(lj[k]["exact"] and not cf[k]["final_ok"] for k in u)
                ab = [k for k in u if not cf[k]["gold"]]
                paired.setdefault(tag, {}).setdefault(m, {})[sub] = {
                    "mavra_only": b,
                    "llm_only": c,
                    "mcnemar_p": round(mcnemar(b, c), 4),
                    "absent_n": len(ab),
                    "absent_answered_mavra": sum(bool(cf[k]["final"]) for k in ab),
                    "absent_answered_llm": sum(bool(lj[k]["got"]) for k in ab),
                }
    summ["paired"] = paired

    rc = {m: dict(base_rc.get(m, {})) for m in SCALES}
    for m in SCALES:
        rc[m]["mavra_refreshed"] = RC[m]["mavra_refreshed_full"]
        rc[m]["mavra_zero"] = RC[m]["mavra_zero_wc"]
        rc[m]["mavra_refreshed_r"] = RC[m]["mavra_refreshed_r"]

    if (plain_dir / "cache.json").is_file():
        CP = jload(plain_dir / "cache.json")
        reqs = CP["meta"]["requests"]
        cat = {m: jload(HERE / f"catalog_{m}.json")["definitions"] for m in SCALES}
        fn = list(jload(HERE / "catalog_1000.json")["facet_names"])

        def consistent(f, stated):
            for s in fn:
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
        for m in SCALES:
            gold = [sorted(d["id"] for d in cat[m] if consistent(d["facets"], r["stated"])) for r in reqs]
            ids = CP["recall"]["tuned"][m]["ids"]
            per = np.array(CP["scores"]["single_ce_refreshed"]["tuned"][m])[:, :, :8]
            mean = per.mean(axis=0)
            mper = np.array(C["scores"]["mavra_refreshed"]["tuned"][m])[:, :, :8]
            sce[m], mor[m] = {}, {}
            for sub in QTAG:
                idx = [i for i, r in enumerate(reqs) if sub == "all_390" or r["qset"] == sub]
                exact = lambda sc_arr, tau: sum(sorted(c for c, s in zip(ids[i][:8], sc_arr[i]) if s >= tau) == gold[i] for i in idx)  # noqa: E731
                taus = np.linspace(0.05, 0.95, 91)
                best = max(taus, key=lambda t: exact(mean, t))
                seeds = [max(exact(per[j], t) for t in np.linspace(0.05, 0.95, 46)) / len(idx) for j in range(per.shape[0])]
                sce[m][sub] = {
                    "n": len(idx),
                    "no_abstain_best_tau": round(float(best), 3),
                    "no_abstain_exact_rate": round(exact(mean, best) / len(idx), 4),
                    "per_seed_exact_rates": [round(x, 4) for x in seeds],
                }
                mm = mper.mean(axis=0)
                mb = max(taus, key=lambda t: exact(mm, t))
                mor[m][sub] = {
                    "no_abstain_best_tau": round(float(mb), 3),
                    "no_abstain_exact_rate": round(exact(mm, mb) / len(idx), 4),
                    "per_seed_exact_rates": [
                        round(max(exact(mper[j], t) for t in np.linspace(0.05, 0.95, 46)) / len(idx), 4)
                        for j in range(mper.shape[0])
                    ],
                }
        summ["single_ce_refreshed"] = sce
        summ["mavra_refreshed_oracle"] = mor

    if (plain_dir / "policy-summary.json").is_file():
        PP = jload(plain_dir / "policy-summary.json")
        RP = jload(plain_dir / "risk-coverage.json")
        summ["single_ce_rule"] = {"full": PP["mavra_refreshed"]["full"], "r": PP["mavra_refreshed"]["r"]}
        for m in SCALES:
            rc[m]["single_ce_refreshed"] = RP[m]["mavra_refreshed_full"]
            rc[m]["single_ce_refreshed_r"] = RP[m]["mavra_refreshed_r"]

    if (thin_dir / "policy-summary.json").is_file():
        summ["thin_density"] = jload(thin_dir / "policy-summary.json")["mavra_refreshed"]["full"]

    return summ, rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results-dir", type=Path, default=None, help="Live lookup results root (optional)")
    ap.add_argument("--out-summary", type=Path, default=HERE / "scale-summary.json")
    ap.add_argument("--out-rc", type=Path, default=HERE / "risk-coverage.json")
    ap.add_argument("--tex", type=Path, default=ROOT / "results/gen/lookup-scale.tex")
    args = ap.parse_args()

    summ = json.loads(args.out_summary.read_text(encoding="utf-8"))
    rc = json.loads(args.out_rc.read_text(encoding="utf-8"))

    if args.results_dir is not None:
        summ, rc = aggregate_live(args.results_dir, summ, rc)
        args.out_summary.write_text(json.dumps(summ, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        args.out_rc.write_text(json.dumps(rc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    mac = build_macros(summ, rc)
    tex = ["% Generated by exp/semantic-lookup/analyse.py; do not edit."]
    tex += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(mac.items())]
    args.tex.parent.mkdir(parents=True, exist_ok=True)
    args.tex.write_text("\n".join(tex) + "\n", encoding="utf-8")
    print(
        f"wrote {len(mac)} macros to {args.tex}; "
        f"single CE: {'yes' if 'single_ce_refreshed' in summ else 'pending'}; "
        f"density: {'yes' if 'thin_density' in summ else 'pending'}"
    )


if __name__ == "__main__":
    main()
