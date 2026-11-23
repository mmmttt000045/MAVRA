#!/usr/bin/env python3
"""LLM-written training phrasings for the 974 added definitions in catalog_1000.json.

Synthesizes training phrasings from the catalog alone:
  1. each name-level group (same channel, subject, category) of added definitions: state only those;
  2. each distinguishing attribute value inside the group (amount, profit, ratio; date for return subjects);
  3. combinations the catalog vocabulary forms but the catalog lacks: missing attribute values inside a group,
     channel x subject for the added channels, and category sales for two categories per added channel;
  4. out-of-catalog metrics for each added channel (subject outside the catalog vocabulary), the LLM's choice.

The LLM sees only the catalog's attribute values (canonical channel names, subject hints); no test request, no
channel synonym list. Labels follow from Definition 4.1 (consistent()). Phrasings equal to, contained in, or
containing a test request of any set (after removing spaces and punctuation) are dropped.
Usage: gen_train_scale_llm.py OUT_JSONL [KEY_FILE]   (defaults to DEEPSEEK_API_KEY / OPENAI_API_KEY; PER=6)
"""
import concurrent.futures as cf
import itertools
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = sys.argv[1]
KEY = (
    Path(sys.argv[2]).read_text(encoding="utf-8").strip()
    if len(sys.argv) > 2 and sys.argv[2] != "-"
    else (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
)
if not KEY:
    raise SystemExit("Set DEEPSEEK_API_KEY (or OPENAI_API_KEY) or pass KEY_FILE")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")).rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", os.environ.get("OPENAI_MODEL", "deepseek-flash"))
PER = int(os.environ.get("PER", "6"))
CAT = json.load(open(HERE / "catalog_1000.json", encoding="utf-8"))
DEFS = CAT["definitions"]
FN = CAT["facet_names"]
SLOTS = list(FN)
CORE = {f"D{i:02d}" for i in range(1, 27)}
ADDED = [d for d in DEFS if d["id"] not in CORE]


def consistent(f, stated):
    for s in SLOTS:
        v = f.get(s)
        if stated.get(s):
            if v is None or v not in stated[s]:
                return False
        elif s == "category" and v is not None:
            return False
        elif s == "channel" and v not in (None, "全渠道"):
            return False
    return True


def chat(system, user):
    body = json.dumps({"model": MODEL, "messages": [{"role": "system", "content": system},
                                                    {"role": "user", "content": user}],
                       "max_tokens": 4096}).encode()
    err = ""
    for attempt in range(5):
        req = urllib.request.Request(BASE_URL + "/chat/completions", data=body,
                                     headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                res = json.load(resp)
            u = res.get("usage", {})
            return res["choices"][0]["message"].get("content") or "", u
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            err = str(e).replace(KEY, "[REDACTED]")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("API call failed: " + err)


def parse_json(s):
    m = re.search(r"[\[{].*[\]}]", s, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


# Hints exactly as in gen_train.py; added channels are named by their catalog value only.
SUBJ_HINT = {
    "销售额": "销售收入金额", "标价总额": "按商品原价（标价）计的金额合计", "销量": "售出的商品件数", "订单数": "成交的单数（小票数）",
    "客单价": "平均每单的金额", "利润": "利润", "优惠券金额": "优惠券抵扣的金额", "折扣额": "标价与实际售价之差（打折让掉的金额）",
    "退货金额": "退货退回的金额", "退货件数": "退回的商品件数", "退货率": "退货占销售的比例", "退货净损失": "退货造成的净损失",
    "库存量": "在手的库存数量",
}
CHANNEL_HINT = {"门店": "门店（实体店）", "目录": "目录渠道（邮购目录）", "网店": "网店（线上商城）", "全渠道": "全部渠道合计（公司整体）"}
DISTINCT = ("amount", "profit", "ratio", "date")

targets = []
_seen = set()


def add(stated):
    key = json.dumps(stated, ensure_ascii=False, sort_keys=True)
    if key not in _seen:
        _seen.add(key)
        targets.append(stated)


groups = {}
for d in ADDED:
    f = d["facets"]
    base = {s: [f[s]] for s in ("channel", "subject", "category") if f.get(s)}
    groups.setdefault(json.dumps(base, ensure_ascii=False, sort_keys=True), []).append(d)
for key, ds in groups.items():
    base = json.loads(key)
    add(base)
    for d in ds:
        for s in DISTINCT:
            v = d["facets"].get(s)
            if v is None or (s == "date" and not d["facets"]["subject"].startswith("退货")):
                continue
            add({**base, s: [v]})
    for s in DISTINCT:
        have = {d["facets"].get(s) for d in ds} - {None}
        if not have or (s == "date" and not base["subject"][0].startswith("退货")):
            continue
        allv = {d["facets"].get(s) for d in DEFS if d["facets"].get(s)}
        for v in sorted(allv - have):
            add({**base, s: [v]})

core_channels = {"门店", "目录", "网店", "全渠道", None}
added_channels = sorted({d["facets"].get("channel") for d in ADDED} - core_channels)
vocab_subjects = sorted({d["facets"]["subject"] for d in DEFS if d["facets"]["subject"] in SUBJ_HINT}
                        - {"库存量", "标价总额", "退货净损失"})
for c, s in itertools.product(added_channels, vocab_subjects):
    add({"channel": [c], "subject": [s]})
categories = sorted({d["facets"]["category"] for d in DEFS if d["facets"].get("category")})
rng = random.Random(17)
for c in added_channels:
    for cat in rng.sample(categories, 2):
        add({"channel": [c], "subject": ["销售额"], "category": [cat]})


def describe(stated):
    lines = []
    for s, vs in stated.items():
        v = vs[0]
        if s == "channel":
            v = CHANNEL_HINT.get(v, v)
        elif s == "subject":
            v = f"{v}（{SUBJ_HINT[v]}）"
        lines.append(f"- {FN[s]}：{v}")
    if "channel" not in stated:
        lines.append("- 不要提渠道")
    return "\n".join(lines)


SYSTEM = """你在为数据智能体的指标查找构造训练问题。给定一个指标要说明的口径，写出智能体可能向数据平台提出的问题。要求：
- 每个问题都问这个指标的某个取值（可以带不同的年份、月份、季度、门店或城市等参数，也可以问排名、最大值、比较）；
- 说法尽量多样：同义词、口语、书面语都要有，至少一个用英文；至少一半不直接使用口径里的原词；
- 必须体现列出的每一项口径；不要涉及没列出的口径（例如没列出金额口径就不要提是否扣券、是否含税；没列出比率口径就不要提按件数或按金额；没列出日期归属就不要提按哪个日期算；没列出利润口径就不要区分毛利和净利润；没列出商品范围就不要提商品类别）。
只输出 JSON 字符串数组。"""

OTHER_SYSTEM = """你在为数据智能体的指标查找构造训练问题。写出智能体可能向数据平台提出的、关于“{channel}”这个渠道的问题，问的指标必须不属于下面任何一种统计对象，也不能是它们的同义说法：
{subjects}
可以是该渠道常见的其他业务指标（例如与用户、流量、营销、运营效率、成本、服务质量相关的指标）。说法多样，可带时间等参数，至少两个用英文。只输出 JSON 字符串数组。"""


def gen(stated):
    out, u = chat(SYSTEM, f"口径：\n{describe(stated)}\n\n写 {PER} 个问题。")
    qs = parse_json(out) or []
    return [{"text": q.strip(), "stated": stated} for q in qs if isinstance(q, str) and q.strip()], u


def gen_other(channel):
    out, u = chat(OTHER_SYSTEM.format(channel=channel, subjects="、".join(sorted(SUBJ_HINT))), "写 8 个问题，每个问不同的指标。")
    qs = parse_json(out) or []
    return [{"text": q.strip(), "stated": {"channel": [channel], "subject": ["其他"]}} for q in qs
            if isinstance(q, str) and q.strip()], u


if os.environ.get("COUNT_ONLY"):
    print(json.dumps({"targets": len(targets), "groups": len(groups), "added_channels": len(added_channels),
                      "expected_phrasings": len(targets) * PER + 8 * len(added_channels)}, ensure_ascii=False))
    raise SystemExit(0)

rows, usage, failed = [], {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}, 0
with cf.ThreadPoolExecutor(int(os.environ.get("WORKERS", "16"))) as ex:
    futs = [ex.submit(gen, t) for t in targets] + [ex.submit(gen_other, c) for c in added_channels]
    for fu in cf.as_completed(futs):
        try:
            got, u = fu.result()
        except RuntimeError:
            failed += 1
            continue
        rows += got
        usage["calls"] += 1
        usage["prompt_tokens"] += u.get("prompt_tokens", 0)
        usage["completion_tokens"] += u.get("completion_tokens", 0)


def norm(s):
    return re.sub(r"[\s\W_]+", "", s.lower())


tests = []
for f in ("requests_orig_96.json", "requests_glm_174.json", "requests_scale_120.json", "requests_glm_scale.json"):
    tests += [norm(r["text"]) for r in json.load(open(HERE / f, encoding="utf-8"))["requests"]]
seen, kept, overlap = set(), [], 0
for r in rows:
    n = norm(r["text"])
    if not n or n in seen:
        continue
    if any(n == t or (len(n) >= 8 and n in t) or (len(t) >= 8 and t in n) for t in tests):
        overlap += 1
        continue
    seen.add(n)
    r["gold"] = sorted(d["id"] for d in DEFS if consistent(d["facets"], r["stated"]))
    kept.append(r)
with open(OUT, "w", encoding="utf-8") as f:
    for r in kept:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(json.dumps({"targets": len(targets), "calls": usage["calls"], "failed_calls": failed, "questions": len(kept),
                  "dropped_test_overlap": overlap, "absent_questions": sum(1 for r in kept if not r["gold"]),
                  **usage}, ensure_ascii=False))
