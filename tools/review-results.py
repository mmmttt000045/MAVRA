#!/usr/bin/env python3
"""Generate Q5 system and replay summary macros from exp/cache-baseline-tpcds into results/gen/.

Usage: python3 tools/review-results.py [--exp DIR] [--out results/gen]
Outputs:
  review.tex           Numeric macros (\\Rp* replay, \\Sn* snapshot binding, \\Cb* cache baseline, \\Eone* scaling,
                       \\Tp* TPC-DS condition sharing, \\Wr* wait-for-repair, \\Du* declared use)
  snapshot-stress.tex  Concurrent writer x reader snapshot isolation stress table
"""

import argparse
import collections
import gzip
import json
import os


def exists(d, name):
    return os.path.exists(os.path.join(d, name))


def load(d, name):
    p = os.path.join(d, name)
    if name.endswith(".gz"):
        return json.load(gzip.open(p, "rt", encoding="utf-8"))
    return json.load(open(p, encoding="utf-8"))


def fmt(x, nd=1):
    if isinstance(x, int):
        return f"{x:,}".replace(",", "{,}")
    return f"{x:.{nd}f}"


def replay_groups(tl):
    primary = "snapshot" if "condition/snapshot" in tl else "example"
    groups = [("Cond", f"condition/{primary}"), ("Gold", "condition/judge"), ("Def", f"definition/{primary}"),
              ("Cache", f"definition-cache/{primary}"), ("Schema", f"schema/{primary}"), ("Revoke", f"revoke/{primary}"),
              ("Table", f"tabletest/{primary}")]
    if primary != "example":
        groups.insert(1, ("Cur", "condition/example"))
    return primary, groups


def group(tl, g):
    """Non-repairing policies are independent of the G8 reference oracle."""
    if g in tl:
        return g
    policy, _ = g.split("/")
    for alt in ("judge", "example"):
        if policy != "condition" and f"{policy}/{alt}" in tl:
            return f"{policy}/{alt}"
    return None


def key_of(x):
    return (x["lib"], x["change"], x["entry"], x["task"])


def common_keys(outs):
    groups = collections.defaultdict(set)
    for x in outs:
        groups[(x["policy"], x["oracle"])].add(key_of(x))
    return set.intersection(*groups.values()) if groups else set()


def reference_pair(m, prefix, tag, outs, paired, primary, other):
    """Paired accuracy comparison between MAVRA's primary snapshot oracle and an ablation oracle."""
    idx = {(x["oracle"],) + key_of(x): x for x in outs if x["policy"] == "condition"}
    both = [(x, idx[(other,) + k[1:]]) for k, x in idx.items() if k[0] == primary and (other,) + k[1:] in idx]
    m[f"{prefix}{tag}PairN"] = len(both)
    m[f"{prefix}{tag}PairCond"] = sum(a["class"] == "correct" for a, _ in both)
    m[f"{prefix}{tag}PairOther"] = sum(b["class"] == "correct" for _, b in both)
    m[f"{prefix}{tag}PairExtraWrong"] = sum(a["class"] == "served_wrong" for a, _ in both) - sum(b["class"] == "served_wrong" for _, b in both)
    m[f"{prefix}{tag}Diff"] = paired["correct_diff_pp"]
    m[f"{prefix}{tag}DiffLo"] = paired["ci95_pp"][0]
    m[f"{prefix}{tag}DiffHi"] = paired["ci95_pp"][1]
    for ch, name in [("revision", "Revision"), ("dimhist", "Dimhist"), ("status", "Status")]:
        sel = [(a, b) for a, b in both if a["change"] == ch]
        m[f"{prefix}{tag}{name}N"] = len(sel)
        m[f"{prefix}{tag}{name}Cond"] = sum(a["class"] == "correct" for a, _ in sel)
        m[f"{prefix}{tag}{name}Other"] = sum(b["class"] == "correct" for _, b in sel)


def replay_macros(m, prefix, stats, outs=None):
    """Task-level paired replay macros across common tasks."""
    tl = stats["task_level_common"]
    primary, groups = replay_groups(tl)
    common = common_keys(outs) if outs is not None else set()
    wrong_mod = (
        collections.Counter((x["policy"], x["oracle"]) for x in outs
                            if x["class"] == "served_wrong" and x["change"] != "unit" and key_of(x) in common)
        if outs is not None else None
    )
    for key, g in groups:
        g = group(tl, g)
        if g is None:
            continue
        t = tl[g]
        m[f"{prefix}{key}N"] = t["n"]
        m[f"{prefix}{key}Correct"] = t["correct"]
        m[f"{prefix}{key}Wrong"] = t["served_wrong"]
        m[f"{prefix}{key}Needed"] = t["unavailable_needed"]
        m[f"{prefix}{key}Unneeded"] = t["unavailable_unneeded"]
        m[f"{prefix}{key}CorrectPct"] = t["correct_pct"]
        m[f"{prefix}{key}DB"] = stats["maintenance_db_s"][g]["total"]
        if wrong_mod is not None:
            m[f"{prefix}{key}WrongModeled"] = wrong_mod[tuple(g.split("/"))]
        policy, oracle = g.split("/")
        if policy == "condition" and outs is not None:
            m[f"{prefix}{key}RepairedTasks"] = sum(1 for x in outs if x["policy"] == "condition" and x["oracle"] == oracle
                                                   and x["repaired"] and key_of(x) in common)
    pair = stats["paired"].get(f"condition/{primary} vs " + (group(tl, f"tabletest/{primary}") or ""))
    if pair:
        m[f"{prefix}TableVsCondDiff"] = pair["correct_diff_pp"]
        m[f"{prefix}TableVsCondLo"] = pair["ci95_pp"][0]
        m[f"{prefix}TableVsCondHi"] = pair["ci95_pp"][1]
        m[f"{prefix}TableOnlyCond"] = pair["cond_only_correct"]
        m[f"{prefix}TableOnlyTable"] = pair["other_only_correct"]
    for tag, other in (("Cur", "example"), ("Gold", "judge")):
        key = f"condition/{primary} vs condition/{other}"
        if other != primary and key in stats["paired"]:
            paired_entry = stats["paired"][key]
            m[f"{prefix}{tag}Diff"] = paired_entry["correct_diff_pp"]
            m[f"{prefix}{tag}DiffLo"] = paired_entry["ci95_pp"][0]
            m[f"{prefix}{tag}DiffHi"] = paired_entry["ci95_pp"][1]
            if outs is not None:
                reference_pair(m, prefix, tag, outs, paired_entry, primary, other)
    return primary


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exp", default="exp/cache-baseline-tpcds")
    ap.add_argument("--out", default="results/gen")
    o = ap.parse_args()
    os.makedirs(o.out, exist_ok=True)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ref_path = os.path.join(root, "tools", "figures", "reference_macros.json")
    ref_review = json.load(open(ref_path, encoding="utf-8")).get("review", {}) if os.path.exists(ref_path) else {}
    m = {}

    # 1. Definition library replay
    if exists(o.exp, "replay-stats.json"):
        rs = load(o.exp, "replay-stats.json")
        ro = load(o.exp, "replay-outcomes.json.gz") if exists(o.exp, "replay-outcomes.json.gz") else None
        if ro is not None:
            m["RpLibs"] = len(ro["libraries"])
            m["RpDefs"] = sum(len(l["entries"]) for l in ro["libraries"])
            m["RpChanges"] = len(ro["changes"])
        primary = replay_macros(m, "Rp", rs, ro["outcomes"] if ro is not None else None)
        db = rs["maintenance_db_s"]
        m["RpCacheVsCond"] = db[f"definition-cache/{primary}"]["total"] / db[f"condition/{primary}"]["total"]
        m["RpDefVsCond"] = db[f"definition/{primary}"]["total"] / db[f"condition/{primary}"]["total"]
        m["RpSameCondDef"] = rs["paired"][f"condition/{primary} vs definition/{primary}"]["same_class_pct"]
        m["RpSameCondCache"] = rs["paired"][f"condition/{primary} vs definition-cache/{primary}"]["same_class_pct"]

    # 2. Snapshot-bound execution vs. check-then-execute
    sn = load(o.exp, "snapshot-binding-stats.json")
    il = {(x["case"], x["mode"]): x for x in sn["interleavings"]}
    m["SnTrials"] = sn["trials"]
    m["SnPausePre"] = il[("write_during_pause", "precheck")]["violation"]
    m["SnPauseSnap"] = il[("write_during_pause", "snapshot")]["violation"]
    m["SnBeforePre"] = il[("write_before_call", "precheck")]["violation"]
    m["SnBeforeSnapRej"] = il[("write_before_call", "snapshot")]["rejected"]
    st = sn["stress"]
    pre_un = [x for x in st if x["mode"] == "precheck" and not x["notify"]]
    pre_an = [x for x in st if x["mode"] == "precheck" and x["notify"]]
    snap = [x for x in st if x["mode"] == "snapshot"]
    m["SnStressTrials"] = st[0]["trials"]
    m["SnPreUnannMin"] = min(x["violation_pct_of_answered"] for x in pre_un)
    m["SnPreUnannMax"] = max(x["violation_pct_of_answered"] for x in pre_un)
    m["SnPreUnannTrials"] = min(x["trials_with_violation"] for x in pre_un)
    m["SnPreUnannViol"] = sum(x["violation"] for x in pre_un)
    m["SnPreAnnMin"] = min(x["violation_pct_of_answered"] for x in pre_an)
    m["SnPreAnnMax"] = max(x["violation_pct_of_answered"] for x in pre_an)
    m["SnPreAnnViol"] = sum(x["violation"] for x in pre_an)
    m["SnSnapViol"] = sum(x["violation"] for x in snap)
    m["SnSnapAnswered"] = sum(x["served"] + x["violation"] for x in snap)
    m["SnSnapUpper"] = max(x["violation_wilson95_upper_pct"] for x in snap)
    m["SnUnannLagMax"] = max(x["violation_start_minus_commit_ms"].get("max", 0) for x in pre_un)

    rows = []
    for notify, distinct in [(False, False), (False, True), (True, False), (True, True)]:
        pre = next(x for x in st if x["mode"] == "precheck" and x["notify"] == notify and x["distinct"] == distinct)
        sb = next(x for x in st if x["mode"] == "snapshot" and x["notify"] == notify and x["distinct"] == distinct)
        ans = lambda x: x["served"] + x["violation"]
        proto = "announced" if notify else "unannounced"
        reads = "different" if distinct else "same"
        rows.append(f"{proto} & {reads} & {fmt(pre['violation'])} / {fmt(ans(pre))} ({pre['violation_pct_of_answered']:.2f}\\%) & "
                    f"{pre['trials_with_violation']} & {fmt(sb['violation'])} / {fmt(ans(sb))}\\\\")
    head = [
        "\\begin{tabularx}{\\linewidth}{@{}llLrr@{}}",
        "\\toprule",
        "& & \\multicolumn{2}{c}{Check-then-execute} & Same-snapshot\\\\",
        "\\cmidrule(lr){3-4}",
        "Writer & Months & violations / answered & trials with a violation & violations / answered\\\\",
        "\\midrule",
    ]
    tail = ["\\bottomrule", "\\end{tabularx}"]
    open(os.path.join(o.out, "snapshot-stress.tex"), "w", encoding="utf-8").write(
        "% generated by tools/review-results.py\n" + "\n".join(head + rows + tail) + "\n")

    rp = sn["reader_p50_ms"]
    m["SnSteadyPre"] = rp["precheck"]["steady_ms"]
    m["SnSteadySnap"] = rp["snapshot"]["steady_ms"]
    m["SnFirstPre"] = rp["precheck"]["first_after_write_ms"]
    m["SnFirstSnap"] = rp["snapshot"]["first_after_write_ms"]
    if exists(o.exp, "snapshot-binding-report.json"):
        raw = load(o.exp, "snapshot-binding-report.json")
        p50 = [x["latency_ms"]["p50"] for x in raw["stress"]]
        m["SnStressPFiftyLo"] = min(p50)
        m["SnStressPFiftyHi"] = max(p50)
    if exists(o.exp, "snapshot-binding-shards-stats.json"):
        sh = load(o.exp, "snapshot-binding-shards-stats.json")["writer_ratio_over_none"]
        m["SnWriteSeq"] = sh["shards16"]["sequential_stmt_per_s"]
        m["SnWriteConcEight"] = sh["shards16"]["concurrent8_stmt_per_s"]
        m["SnWriteConcTT"] = sh["shards16"]["concurrent32_stmt_per_s"]
        m["SnWriteHotTT"] = sh["shards1"]["concurrent32_stmt_per_s"]
        m["SnWriteBulk"] = sh["shards16"]["bulk_ms_per_stmt"]

    # 3. Query-cache baseline and scaling
    cb = load(o.exp, "cb-1m-share-stats.json")["rows"]
    get = lambda rows_, k, arr, p: next(r for r in rows_ if r["share"] == k and r["arrival"] == arr and r["policy"] == p)
    for arr, A in [("staggered", "Stag"), ("burst", "Burst")]:
        for k, K in [(1, "One"), (6, "Six")]:
            for p, P in [("definition-cache", "Cache"), ("condition", "Cond"), ("condition-scope", "Scope")]:
                m[f"Cb{A}{P}{K}"] = 100 * get(cb, k, arr, p)["vs_definition"]
            m[f"Cb{A}Def{K}"] = get(cb, k, arr, "definition")["db_s"]
    m["CbCondStagMin"] = min(get(cb, k, "staggered", "condition")["db_s"] for k in (1, 2, 4, 6))
    m["CbCondStagMax"] = max(get(cb, k, "staggered", "condition")["db_s"] for k in (1, 2, 4, 6))
    m["CbCacheStagMin"] = min(get(cb, k, "staggered", "definition-cache")["db_s"] for k in (1, 2, 4, 6))
    m["CbCacheStagMax"] = max(get(cb, k, "staggered", "definition-cache")["db_s"] for k in (1, 2, 4, 6))
    if exists(o.exp, "cb-1m-zero-stats.json"):
        zero = load(o.exp, "cb-1m-zero-stats.json")["rows"]
        ratios = [r["vs_definition"] for r in zero if r["policy"] != "definition"]
        m["CbZeroMin"] = 100 * min(ratios)
        m["CbZeroMax"] = 100 * max(ratios)
    if exists(o.exp, "cb-4m-stats.json"):
        four = load(o.exp, "cb-4m-stats.json")["rows"]
        m["CbFourStagCache"] = 100 * get(four, 6, "staggered", "definition-cache")["vs_definition"]
        m["CbFourStagCond"] = 100 * get(four, 6, "staggered", "condition")["vs_definition"]
        m["CbFourBurstCache"] = 100 * get(four, 6, "burst", "definition-cache")["vs_definition"]
        m["CbFourBurstCond"] = 100 * get(four, 6, "burst", "condition")["vs_definition"]
    if exists(o.exp, "e1b-4m-a32-stats.json"):
        a32 = load(o.exp, "e1b-4m-a32-stats.json")["rows"]
        m["CbAgentsStagCache"] = 100 * get(a32, 6, "staggered", "definition-cache")["vs_definition"]
        m["CbAgentsStagCond"] = 100 * get(a32, 6, "staggered", "condition")["vs_definition"]
        m["CbAgentsBurstCache"] = 100 * get(a32, 6, "burst", "definition-cache")["vs_definition"]
        m["CbAgentsBurstCond"] = 100 * get(a32, 6, "burst", "condition")["vs_definition"]
        m["CbAgentsUses"] = get(a32, 6, "burst", "condition")["uses"]
    if exists(o.exp, "e1-scaling-stats.json"):
        e1 = load(o.exp, "e1-scaling-stats.json")["rows"]
        for d, D in [("e1-maint-1m", "One"), ("e1-maint-4m", "Four"), ("e1-maint-16m", "Sixteen")]:
            rows_ = [r for r in e1 if r["dir"] == d]
            m[f"EoneDef{D}"] = get(rows_, 6, "staggered", "definition")["db_s"]
            m[f"EoneCond{D}"] = get(rows_, 6, "staggered", "condition")["db_s"]
            m[f"EoneRatio{D}"] = 100 * get(rows_, 6, "staggered", "condition")["vs_definition"]

    # 4. Natural condition sharing on TPC-DS
    if exists(o.exp, "tpcds-sharing.json"):
        tp = load(o.exp, "tpcds-sharing.json")
        m["TpTemplates"] = tp["templates"]
        m["TpQueries"] = tp["queries_with_definitions"]
        m["TpDefs"] = tp["definitions"]
        m["TpInst"] = tp["condition_instances"]
        m["TpConds"] = tp["distinct_conditions"]
        m["TpPer"] = tp["instances_per_distinct"]
        m["TpSharedPct"] = tp["instances_on_shared_conditions_pct"]
        ss = tp["per_table_update"]["store_sales"]
        m["TpSalesDefs"] = ss["affected_definitions"]
        m["TpSalesDefChecks"] = ss["definition_level_checks"]
        m["TpSalesConds"] = ss["condition_level_checks"]

    # 5. Wait-for-repair and declared use
    if exists(o.exp, "wait-repair-stats.json"):
        wr = load(o.exp, "wait-repair-stats.json")["rows"]
        off = [r for r in wr if r["dir"] == "wr-200k-nowait"]
        on = [r for r in wr if r["dir"] == "wr-200k-wait"]
        m["WrDefOff"] = next(r["unavailable"] for r in off if r["policy"] == "definition")
        m["WrCondOff"] = next(r["unavailable"] for r in off if r["policy"] == "condition")
        m["WrDefOn"] = next(r["unavailable"] for r in on if r["policy"] == "definition")
        m["WrCondOn"] = next(r["unavailable"] for r in on if r["policy"] == "condition")
        m["WrUses"] = next(r["uses"] for r in on if r["policy"] == "condition")
    if exists(o.exp, "declared-use.json"):
        du = load(o.exp, "declared-use.json")
        c = du["counts"]
        m["DuDeviate"] = c["deviate"]
        m["DuValid"] = c["follow"] + c["deviate"]
        m["DuDevPct"] = du["deviate_pct_of_valid_def"]
        m["DuUndeclared"] = c["undeclared"]
        m["DuRecords"] = du["records"]
        m["DuUndeclPct"] = 100.0 * c["undeclared"] / du["records"]

    # 6. TPC-DS paired replay (when present in --exp)
    if exists(o.exp, "tpcds-replay-stats.json"):
        ts = load(o.exp, "tpcds-replay-stats.json")
        to = load(o.exp, "tpcds-replay-outcomes.json.gz") if exists(o.exp, "tpcds-replay-outcomes.json.gz") else None
        if exists(o.exp, "tpcds-library.json"):
            lib = load(o.exp, "tpcds-library.json")["metric_report"]["entries"]
            m["TrDefs"] = len(lib)
            facts = collections.Counter(e["metric"]["fact"] for e in lib)
            m["TrStoreDefs"] = facts["store_sales"] + facts["store_returns"]
            m["TrJoinDefs"] = sum(1 for e in lib if e["metric"]["joins"])
            m["TrFilterDefs"] = sum(1 for e in lib if e["metric"]["filters"])
        primary = replay_macros(m, "Tr", ts, to["outcomes"] if to is not None else None)
        if to is not None:
            m["TrChanges"] = len(to["changes"])
            seed = next(s_ for s_ in to["seeds"] if s_["policy"] == "condition" and s_["oracle"] == primary)
            m["TrSeeded"] = seed["seeded"]
            m["TrSeedFailed"] = len(seed["failed"])
        if "dupload" in ts["maintenance_db_s"].get(f"condition/{primary}", {}):
            m["TrCondDuploadDB"] = ts["maintenance_db_s"][f"condition/{primary}"]["dupload"]

    formatted = {}
    for k, v in m.items():
        nd = 2 if isinstance(v, float) and k in ("RpCacheVsCond", "RpDefVsCond", "SnWriteSeq", "SnWriteConcEight", "SnWriteConcTT",
                                                  "SnWriteHotTT", "SnWriteBulk", "SnPreAnnMin", "SnPreAnnMax", "SnSnapUpper") else 1
        if isinstance(v, float) and k.startswith("Cb") and ("Def" in k and "Stag" not in k or k.endswith("Min") or k.endswith("Max")) and k not in ("CbZeroMin", "CbZeroMax"):
            nd = 1
        if isinstance(v, float) and k in ("CbZeroMin", "CbZeroMax", "SnStressPFiftyLo", "SnStressPFiftyHi", "SnFirstPre", "SnFirstSnap", "SnUnannLagMax"):
            nd = 0
        formatted[k] = fmt(v, nd)
    for k, v in ref_review.items():
        formatted.setdefault(k, v)

    lines = ["% generated by tools/review-results.py from " + o.exp + "; do not edit"]
    for k in sorted(formatted):
        lines.append(f"\\newcommand{{\\{k}}}{{{formatted[k]}}}")
    open(os.path.join(o.out, "review.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
