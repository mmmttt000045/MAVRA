#!/usr/bin/env python3
"""Online LLM lookup & confirmation runner across catalog scales M in {26, 100, 500, 1000}.

Evaluates across subsets {orig_96, glm_174, scale_120, all_390} (or held-out fresh paraphrases):
  1. Top-8 Recall + LLM Judge
  2. MAVRA Confirmation Turn on uncertain (`refer` / `similar`) replies for `mavra_zero` and `mavra_refreshed`

Reads API credentials from `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` (or optional `--key-file`).
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--for-llm", required=True, help="Directory containing top8_M*.jsonl and responses_*_M*.jsonl")
ap.add_argument("--key-file", default=None, help="Optional path to API key file (defaults to DEEPSEEK_API_KEY / OPENAI_API_KEY)")
ap.add_argument("--out", required=True)
ap.add_argument("--scales", default="26,100,500,1000")
ap.add_argument("--workers", type=int, default=20)
args = ap.parse_args()

FOR_LLM = Path(args.for_llm)
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
KEY = (
    Path(args.key_file).read_text(encoding="utf-8").strip()
    if args.key_file
    else (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
)
if not KEY:
    raise SystemExit("Set DEEPSEEK_API_KEY (or OPENAI_API_KEY) or pass --key-file")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")).rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", os.environ.get("OPENAI_MODEL", "deepseek-flash"))
SCALES = [int(x) for x in args.scales.split(",")]
SUBSETS = ["orig_96", "glm_174", "scale_120", "all_390"]

TOP8_RULES = """你是指标目录的查找器。给你一个智能体的问题，找出目录中能回答该问题所问指标的全部定义。规则：
1. 问题可能用与目录不同的说法称呼同一个指标。
2. 问题没有说明某个选择、而几条定义恰好在这个选择上不同（例如金额取哪一列、按件数还是按金额、按哪个日期归属、毛利还是净利润），这几条都要返回。
3. 只覆盖某个子集的定义（某个商品类别、某个渠道），只有问题明确提到这个限定时才算匹配；问题没有提渠道时，指全部渠道合计。
4. 问题中的时间、门店名等参数不影响匹配。
5. 目录中没有能回答的定义时返回空列表。
只输出 JSON：{"ids": ["D..", ...]}"""

CONFIRM_PROMPT = (
    "你是一个数据分析智能体。你向共享指标目录提出了下面的问题，目录没有直接给出唯一定义，而是返回了候选定义及其差别。"
    "请判断你的问题指的是哪一条或哪几条定义：问题没有说明区分它们的口径时，返回所有与问题一致的定义；"
    "候选都与问题不一致时，返回空列表。只输出 JSON，例如 {\"ids\": [\"D01\"]} 或 {\"ids\": []}。\n\n"
    "问题：{q}\n\n目录回复：{r}"
)


def call_deepseek(messages, thinking=False, json_mode=False):
    body = {"model": MODEL, "messages": messages, "max_tokens": 4096}
    if thinking:
        body["thinking"] = {"type": "enabled"}
        body["reasoning_effort"] = "low"
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body).encode("utf-8")
    err = ""
    for attempt in range(5):
        req = urllib.request.Request(
            BASE_URL + "/chat/completions",
            data=data,
            headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                res = json.load(resp)
            dt = time.time() - t0
            u = res.get("usage", {})
            content = res["choices"][0]["message"].get("content") or ""
            return content, {
                "seconds": dt,
                "prompt": u.get("prompt_tokens", 0),
                "completion": u.get("completion_tokens", 0),
            }
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            err = str(e).replace(KEY, "[REDACTED]")
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("DeepSeek call failed: " + err)


def parse_ids(s):
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return []
    try:
        got = json.loads(m.group(0)).get("ids", [])
        return [x for x in got if isinstance(x, str)]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 1. Top-8 Recall + LLM Judge
# ---------------------------------------------------------------------------
top8_summary = {}
for m in SCALES:
    src = FOR_LLM / f"top8_M{m}.jsonl"
    rows = [json.loads(l) for l in src.open(encoding="utf-8") if l.strip()]
    cache_file = OUT / f"top8_llm_M{m}.jsonl"
    done = {}
    if cache_file.exists():
        for l in cache_file.open(encoding="utf-8"):
            if l.strip():
                x = json.loads(l)
                done[x["uid"]] = x

    todo = [r for r in rows if r["uid"] not in done]
    print(f"[Top-8 LLM M={m}] total={len(rows)} cached={len(done)} todo={len(todo)}", flush=True)

    def run_one_top8(r):
        cand_ids = {c["id"] for c in r["top8"]}
        listing = "\n".join(f"{c['id']}｜{c['name']}｜{c['text']}" for c in r["top8"])
        msgs = [
            {"role": "system", "content": TOP8_RULES + "\n\n目录：\n" + listing},
            {"role": "user", "content": "问题：" + r["text"]},
        ]
        out_txt, u = call_deepseek(msgs, thinking=True, json_mode=False)
        got = sorted({i for i in parse_ids(out_txt) if i in cand_ids})
        return {
            "uid": r["uid"],
            "qset": r["qset"],
            "id": r["id"],
            "kind": r["kind"],
            "gold": sorted(r["gold"]),
            "got": got,
            "exact": got == sorted(r["gold"]),
            "total_s": round(r["recall_s"] + u["seconds"], 4),
            "llm_s": round(u["seconds"], 4),
            "prompt_tokens": u["prompt"],
            "completion_tokens": u["completion"],
        }

    if todo:
        with cache_file.open("a", encoding="utf-8") as cf_out, cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            for rec in ex.map(run_one_top8, todo):
                done[rec["uid"]] = rec
                cf_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                cf_out.flush()

    ordered = [done[r["uid"]] for r in rows]
    top8_summary[str(m)] = {}
    for sub in SUBSETS:
        sub_r = ordered if sub == "all_390" else [x for x in ordered if x["qset"] == sub]
        abs_r = [x for x in sub_r if not x["gold"]]
        toks = [x["prompt_tokens"] + x["completion_tokens"] for x in sub_r]
        secs = [x["total_s"] for x in sub_r]
        top8_summary[str(m)][sub] = {
            "n": len(sub_r),
            "exact": sum(x["exact"] for x in sub_r),
            "exact_rate": round(sum(x["exact"] for x in sub_r) / len(sub_r), 4),
            "absent_n": len(abs_r),
            "absent_rejected": sum(x["got"] == [] for x in abs_r),
            "absent_reject_rate": round(sum(x["got"] == [] for x in abs_r) / max(1, len(abs_r)), 4),
            "tokens_mean": round(statistics.mean(toks), 1),
            "seconds_mean": round(statistics.mean(secs), 3),
            "seconds_p95": round(sorted(secs)[int(0.95 * len(secs))], 3),
        }
    print(f"  Top-8 LLM M={m} orig_96={top8_summary[str(m)]['orig_96']['exact_rate']} all_390={top8_summary[str(m)]['all_390']['exact_rate']}", flush=True)


# ---------------------------------------------------------------------------
# 2. MAVRA Confirmation Turn (mavra_zero & mavra_refreshed)
# ---------------------------------------------------------------------------
confirm_summary = {}
for fam in ("mavra_zero", "mavra_refreshed"):
    if not (FOR_LLM / f"responses_{fam}_M{SCALES[0]}.jsonl").exists():
        continue
    confirm_summary[fam] = {}
    for m in SCALES:
        src = FOR_LLM / f"responses_{fam}_M{m}.jsonl"
        rows = [json.loads(l) for l in src.open(encoding="utf-8") if l.strip()]
        cache_file = OUT / f"confirm_{fam}_M{m}.jsonl"
        done = {}
        if cache_file.exists():
            for l in cache_file.open(encoding="utf-8"):
                if l.strip():
                    x = json.loads(l)
                    done[x["uid"]] = x

        todo = [r for r in rows if r["uid"] not in done]
        print(f"[Confirm {fam} M={m}] total={len(rows)} cached={len(done)} todo={len(todo)}", flush=True)

        def run_one_confirm(r):
            first = sorted(r["ids"]) if r["mode"] in ("answer", "refer") else []
            g = sorted(r["gold"])
            rec = {
                "uid": r["uid"],
                "qset": r["qset"],
                "req": r["req"],
                "kind": r["kind"],
                "mode": r["mode"],
                "gold": g,
                "first": first,
                "first_ok": first == g,
                "lookup_s": r["seconds"],
            }
            if r["mode"] in ("refer", "similar"):
                prompt = CONFIRM_PROMPT.replace("{q}", r["text"]).replace("{r}", r["reply"])
                out_txt, u = call_deepseek([{"role": "user", "content": prompt}], thinking=False, json_mode=True)
                cand_allowed = set(r["ids"])
                ids = sorted(i for i in parse_ids(out_txt) if i in cand_allowed)
                rec.update(
                    confirmed=ids,
                    final=ids,
                    final_ok=(ids == g),
                    confirm_s=round(u["seconds"], 4),
                    total_s=round(r["seconds"] + u["seconds"], 4),
                    prompt_tokens=u["prompt"],
                    completion_tokens=u["completion"],
                )
            else:
                rec.update(
                    final=first,
                    final_ok=(first == g),
                    confirm_s=0.0,
                    total_s=round(r["seconds"], 4),
                    prompt_tokens=0,
                    completion_tokens=0,
                )
            return rec

        if todo:
            with cache_file.open("a", encoding="utf-8") as cf_out, cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
                for rec in ex.map(run_one_confirm, todo):
                    done[rec["uid"]] = rec
                    cf_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    cf_out.flush()

        ordered = [done[r["uid"]] for r in rows]
        confirm_summary[fam][str(m)] = {}
        for sub in SUBSETS:
            sub_r = ordered if sub == "all_390" else [x for x in ordered if x["qset"] == sub]
            abs_r = [x for x in sub_r if not x["gold"]]
            direct_r = [x for x in sub_r if x["mode"] in ("answer", "none")]
            conf_r = [x for x in sub_r if x["mode"] in ("refer", "similar")]
            toks = [x["prompt_tokens"] + x["completion_tokens"] for x in sub_r]
            secs = [x["total_s"] for x in sub_r]
            confirm_summary[fam][str(m)][sub] = {
                "n": len(sub_r),
                "first_exact": sum(x["first_ok"] for x in sub_r),
                "first_exact_rate": round(sum(x["first_ok"] for x in sub_r) / len(sub_r), 4),
                "final_exact": sum(x["final_ok"] for x in sub_r),
                "final_exact_rate": round(sum(x["final_ok"] for x in sub_r) / len(sub_r), 4),
                "direct_coverage": round(len(direct_r) / len(sub_r), 4),
                "direct_precision": round(sum(x["first_ok"] for x in direct_r) / max(1, len(direct_r)), 4),
                "confirmations": len(conf_r),
                "confirm_rate": round(len(conf_r) / len(sub_r), 4),
                "absent_n": len(abs_r),
                "absent_final_rejected": sum(x["final"] == [] for x in abs_r),
                "absent_reject_rate": round(sum(x["final"] == [] for x in abs_r) / max(1, len(abs_r)), 4),
                "tokens_mean": round(statistics.mean(toks), 1),
                "seconds_mean": round(statistics.mean(secs), 3),
                "seconds_p95": round(sorted(secs)[int(0.95 * len(secs))], 3),
            }
        print(
            f"  Confirm {fam} M={m} orig_96={confirm_summary[fam][str(m)]['orig_96']['final_exact_rate']} "
            f"all_390={confirm_summary[fam][str(m)]['all_390']['final_exact_rate']}",
            flush=True,
        )

out_json = {"scales": SCALES, "top8_llm_judge": top8_summary, "mavra_confirmed": confirm_summary}
(OUT / "llm-summary.json").write_text(json.dumps(out_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("=== ALL LLM LOOKUP & CONFIRMATION RUNS COMPLETE ===", flush=True)
