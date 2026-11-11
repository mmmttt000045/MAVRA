"""查找原型：智能体的问题 -> 目录里的定义。比较六种做法的准确率与开销。

N   名字匹配：目录名出现在问题里（最长者优先，同名全给），即现有 find_metric 的做法
E   向量相似度取最像的一条，低于阈值算没有（GPTCache / vCache 式；阈值取本题集上最好的，偏向基线）
L   大模型读整个目录（全部定义原文）后给出匹配编号
R   向量召回 k 条，大模型读这 k 条定义原文后给出匹配编号
C   本方案：向量召回 k 条；大模型只判断问题说了哪些口径（维度与可选值取自候选的口径）；按口径规则筛选
Ca  本方案不召回：口径可选值取自整个目录

正确答案：目录中与问题所述口径都一致的全部定义（consistent()）。问题没提商品类别或渠道时按不限定算；
问题没说清、而几条定义恰好在这点上不同时，几条都要给。L、R 的提示里写的是同一套规则。

用法：python lookup.py catalog.json requests.json out_dir [repeats]
密钥从 /root/agentdb-mid/.env 读取 DEEPSEEK_*，不打印。
"""
import collections
import concurrent.futures as cf
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

CAT_PATH, REQ_PATH, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
REPEATS = int(sys.argv[4]) if len(sys.argv) > 4 else 1
K = 8
OUT.mkdir(parents=True, exist_ok=True)

CAT = json.load(open(CAT_PATH))
DEFS = CAT["definitions"]
BYID = {d["id"]: d for d in DEFS}
FN = CAT["facet_names"]
SLOTS = list(FN)
REQS = json.load(open(REQ_PATH))["requests"]


def consistent(f, stated):
    """f: 定义的口径；stated: 维度 -> 问题允许的值列表（只含问题说了的维度）。"""
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


def gold(r):
    return sorted(d["id"] for d in DEFS if consistent(d["facets"], r["stated"]))


# ---------------- 大模型 ----------------
ENV = {}
for line in Path("/root/agentdb-mid/.env").read_text(encoding="utf-8-sig").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip().strip("\"'")
KEY, MODEL = Path("/root/.deepseek-change-study.key").read_text().strip(), ENV["DEEPSEEK_MODEL"]  # GLM study: change-study key
BASE = ENV.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
EXTRA = {"max_tokens": 8192}
if ENV.get("DEEPSEEK_REASONING_EFFORT"):
    EXTRA["reasoning_effort"] = ENV["DEEPSEEK_REASONING_EFFORT"]
if ENV.get("DEEPSEEK_THINKING"):
    EXTRA["thinking"] = {"type": ENV["DEEPSEEK_THINKING"]}


def chat(system, user):
    body = {"model": MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], **EXTRA}
    data = json.dumps(body).encode()
    for attempt in range(4):
        req = urllib.request.Request(BASE + "/chat/completions", data=data,
                                     headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                res = json.load(resp)
            dt = time.time() - t0
            u = res.get("usage", {})
            msg = res["choices"][0]["message"]
            return msg.get("content") or "", {
                "seconds": dt, "prompt": u.get("prompt_tokens", 0), "completion": u.get("completion_tokens", 0),
                "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                "cache_hit": u.get("prompt_cache_hit_tokens", 0)}
        except (urllib.error.URLError, TimeoutError, KeyError) as e:
            err = str(e).replace(KEY, "[REDACTED]")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("API 调用失败：" + err)


def parse_json(s):
    m = re.search(r"\{.*\}", s, re.S)
    return json.loads(m.group(0)) if m else {}


RULES = """你是指标目录的查找器。给你一个智能体的问题，找出目录中能回答该问题所问指标的全部定义。规则：
1. 问题可能用与目录不同的说法称呼同一个指标。
2. 问题没有说明某个选择、而几条定义恰好在这个选择上不同（例如金额取哪一列、按件数还是按金额、按哪个日期归属、毛利还是净利润），这几条都要返回。
3. 只覆盖某个子集的定义（某个商品类别、某个渠道），只有问题明确提到这个限定时才算匹配；问题没有提渠道时，指全部渠道合计。
4. 问题中的时间、门店名等参数不影响匹配。
5. 目录中没有能回答的定义时返回空列表。
只输出 JSON：{"ids": ["D..", ...]}"""


def listing(ids):
    return "\n".join(f"{i}｜{BYID[i]['name']}｜{BYID[i]['text']}" for i in ids)


def ask_ids(question, ids):
    system = RULES + "\n\n目录：\n" + listing(ids)
    out, u = chat(system, "问题：" + question)
    got = parse_json(out).get("ids", [])
    return sorted({i for i in got if i in ids}), u


FACET_RULES = """你在帮指标目录判断一个问题说明了哪些口径。下面给出若干维度及每个维度的可选值。对每个维度：
- 问题明确说出或必然蕴含的值，列出来；问题本身有歧义、可能指其中几个值时，把可能的值都列出；
- 问题没有涉及这个维度，返回 []；
- 问题说的值不在可选值中，返回 ["其他"]。
时间、门店名等参数不算口径。只输出 JSON，键为维度名，值为列表。"""


def ask_facets(question, ids):
    vals = collections.OrderedDict((s, []) for s in SLOTS)
    for i in ids:
        for s, v in BYID[i]["facets"].items():
            if v not in vals[s]:
                vals[s].append(v)
    lines, shown = [], set()
    for s, vs in vals.items():
        if vs:
            lines.append(f"- {FN[s]}：" + " / ".join(vs))
            shown.add(s)
        elif s in ("channel", "category"):
            lines.append(f"- {FN[s]}：（候选中没有限定{FN[s]}的定义）")
            shown.add(s)
    out, u = chat(FACET_RULES, f"问题：{question}\n\n维度与可选值：\n" + "\n".join(lines))
    raw = parse_json(out)
    inv = {v: k for k, v in FN.items()}
    stated = {}
    for name, got in raw.items():
        s = inv.get(name)
        if s not in shown or not isinstance(got, list) or not got:
            continue
        stated[s] = [g for g in got if g in vals[s]] or ["其他"]
    picked = sorted(i for i in ids if consistent(BYID[i]["facets"], stated))
    return picked, u, stated


# ---------------- 向量 ----------------
from sentence_transformers import SentenceTransformer  # noqa: E402

emb = SentenceTransformer("BAAI/bge-m3")
t0 = time.time()
D = emb.encode([f"{d['name']}：{d['text']}" for d in DEFS], normalize_embeddings=True)
Dn = emb.encode([d["name"] for d in DEFS], normalize_embeddings=True)
Q = emb.encode([r["text"] for r in REQS], normalize_embeddings=True)
t_emb = time.time() - t0
SIM = Q @ D.T
SIMN = Q @ Dn.T
IDS = [d["id"] for d in DEFS]


def topk(qi, k):
    order = np.argsort(-SIM[qi])[:k]
    return [IDS[j] for j in order]


def name_match(text):
    hits = [d for d in DEFS if d["name"] in text]
    names = {d["name"] for d in hits}
    keep = {n for n in names if not any(n != m and n in m for m in names)}
    return sorted(d["id"] for d in hits if d["name"] in keep)


# ---------------- 运行 ----------------
golds = {r["id"]: gold(r) for r in REQS}
rows = []
for qi, r in enumerate(REQS):
    rows.append({"req": r["id"], "kind": r["kind"], "method": "N", "rep": 0, "got": name_match(r["text"])})
    for key, S in (("E", SIM), ("En", SIMN)):
        j = int(np.argmax(S[qi]))
        rows.append({"req": r["id"], "kind": r["kind"], "method": key, "rep": 0, "top1": IDS[j], "sim": float(S[qi][j])})


def job(qi, method, rep):
    r = REQS[qi]
    rec = {"req": r["id"], "kind": r["kind"], "method": method, "rep": rep}
    if method == "L":
        rec["got"], rec["usage"] = ask_ids(r["text"], IDS)
    elif method == "R":
        cand = topk(qi, K)
        rec["cand"] = cand
        rec["got"], rec["usage"] = ask_ids(r["text"], cand)
    elif method == "C":
        cand = topk(qi, K)
        rec["cand"] = cand
        rec["got"], rec["usage"], rec["read"] = ask_facets(r["text"], cand)
    elif method == "Ca":
        rec["got"], rec["usage"], rec["read"] = ask_facets(r["text"], IDS)
    return rec


jobs = [(qi, m, rep) for rep in range(REPEATS) for m in ("L",) for qi in range(len(REQS))]  # GLM study: full-catalog judge only
with cf.ThreadPoolExecutor(8) as ex:
    for rec in ex.map(lambda a: job(*a), jobs):
        rows.append(rec)


# ---------------- 计分 ----------------
def score(got, g):
    got, g = set(got), set(g)
    if got == g:
        return "exact"
    if g and not got:
        return "miss"
    if got - g:
        return "wrong"  # 给出了不对的定义
    return "partial"  # 只给了正确集合的一部分（同名不同义时悄悄选了一个）


def summarize(recs):
    c = collections.Counter(score(x["got"], golds[x["req"]]) for x in recs)
    n = len(recs)
    by_gold = collections.defaultdict(list)
    for x in recs:
        g = golds[x["req"]]
        by_gold["absent" if not g else ("single" if len(g) == 1 else "multi")].append(score(x["got"], g) == "exact")
    out = {"n": n, **{k: c.get(k, 0) for k in ("exact", "wrong", "partial", "miss")},
           "exact_rate": round(c.get("exact", 0) / n, 3)}
    for k, v in by_gold.items():
        out[f"exact_{k}"] = f"{sum(v)}/{len(v)}"
    us = [x["usage"] for x in recs if "usage" in x]
    if us:
        out["prompt_tokens_mean"] = round(statistics.mean(u["prompt"] for u in us))
        out["completion_tokens_mean"] = round(statistics.mean(u["completion"] for u in us))
        secs = sorted(u["seconds"] for u in us)
        out["seconds_mean"] = round(statistics.mean(secs), 2)
        out["seconds_p50"] = round(secs[len(secs) // 2], 2)
        out["seconds_p95"] = round(secs[int(len(secs) * 0.95)], 2)
    return out


summary = {"requests": len(REQS), "definitions": len(DEFS), "k": K, "repeats": REPEATS, "model": MODEL,
           "embedding": "BAAI/bge-m3", "embedding_seconds_all": round(t_emb, 2),
           "gold_sizes": dict(collections.Counter(len(g) for g in golds.values()))}
summary["N"] = summarize([x for x in rows if x["method"] == "N"])

# 相似度：取最像的一条；阈值取本题集上最好的（偏向基线），并报告不设阈值的结果
for key in ("E", "En"):
    recs = [x for x in rows if x["method"] == key]
    best = None
    for tau in sorted({0.0} | {x["sim"] for x in recs}):
        for x in recs:
            x["got"] = [x["top1"]] if x["sim"] >= tau else []
        s = summarize(recs)
        if best is None or s["exact"] > best[1]["exact"]:
            best = (tau, s)
    for x in recs:
        x["got"] = [x["top1"]] if x["sim"] >= best[0] else []
    always = summarize([dict(x, got=[x["top1"]]) for x in recs])
    summary[key] = {"best_threshold": round(best[0], 4), **best[1], "exact_no_threshold": always["exact"]}

for m in ("L",):
    summary[m] = summarize([x for x in rows if x["method"] == m])
    per_rep = [summarize([x for x in rows if x["method"] == m and x["rep"] == rep])["exact"] for rep in range(REPEATS)]
    summary[m]["exact_per_repeat"] = per_rep

# 召回：正确定义是否都在前 k 条
rec_ok = sum(1 for qi, r in enumerate(REQS) if set(golds[r["id"]]) <= set(topk(qi, K)))
summary["recall_at_k"] = f"{rec_ok}/{len(REQS)}"

# 按请求类型的精确率
kinds = sorted({r["kind"] for r in REQS})
summary["exact_by_kind"] = {}
for m in ("N", "E", "En", "L"):
    recs = [x for x in rows if x["method"] == m]
    summary["exact_by_kind"][m] = {
        k: f"{sum(score(x['got'], golds[x['req']]) == 'exact' for x in recs if x['kind'] == k)}/"
           f"{sum(1 for x in recs if x['kind'] == k)}" for k in kinds}

with open(OUT / "outcomes.jsonl", "w") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
json.dump(summary, open(OUT / "summary.json", "w"), ensure_ascii=False, indent=1)
json.dump(golds, open(OUT / "gold.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
