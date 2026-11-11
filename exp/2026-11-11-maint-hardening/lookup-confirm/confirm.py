#!/usr/bin/env python3
"""Confirmation turn for C2 lookup (review point 4): the consuming agent reads MAVRA's reply to its request
(references with structural differences, or "not found, similar:" offers) and names the definition(s) it means.
Model: deepseek-flash (official API), one call per reply that needs confirmation (refer / similar). Writes
confirm-results.jsonl and prints set-exact accuracy before and after confirmation, tokens and latency.
Usage: confirm.py RESPONSES KEY_FILE OUT_DIR
"""
import json, sys, time, urllib.request
from pathlib import Path

PROMPT = ("你是一个数据分析智能体。你向共享指标目录提出了下面的问题，目录没有直接给出唯一定义，而是返回了候选定义及其差别。"
          "请判断你的问题指的是哪一条或哪几条定义：问题没有说明区分它们的口径时，返回所有与问题一致的定义；"
          "候选都与问题不一致时，返回空列表。只输出 JSON，例如 {\"ids\": [\"D01\"]} 或 {\"ids\": []}。\n\n"
          "问题：{q}\n\n目录回复：{r}")


def call(key, text):
    body = json.dumps({"model": "deepseek-flash", "messages": [{"role": "user", "content": text}],
                       "response_format": {"type": "json_object"}, "max_tokens": 2048}).encode()
    req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return d, time.time() - t0


def main():
    rows = [json.loads(x) for x in open(sys.argv[1]) if x.strip()]
    key = Path(sys.argv[2]).read_text().strip()
    out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    res = []
    for r in rows:
        first = sorted(r["ids"]) if r["mode"] in ("answer", "refer") else []
        rec = {"req": r["req"], "kind": r["kind"], "mode": r["mode"], "gold": sorted(r["gold"]), "first": first,
               "first_ok": first == sorted(r["gold"]), "lookup_s": r["seconds"]}
        if r["mode"] in ("refer", "similar"):
            d, s = call(key, PROMPT.replace("{q}", r["text"]).replace("{r}", r["reply"]))
            content = d["choices"][0]["message"]["content"]
            try:
                ids = sorted(json.loads(content).get("ids", []))
            except Exception:
                ids = None
            u = d.get("usage", {})
            rec.update(confirmed=ids, final=ids, final_ok=ids == sorted(r["gold"]), confirm_s=s,
                       prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"), raw=content)
        else:
            rec.update(final=first, final_ok=rec["first_ok"])
        res.append(rec)
        print(rec["req"], rec["mode"], rec["gold"], rec.get("confirmed", rec["first"]), rec["final_ok"], flush=True)
    (out / "confirm-results.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in res))
    conf = [x for x in res if "confirmed" in x]
    summary = {
        "requests": len(res), "first_exact": sum(x["first_ok"] for x in res), "final_exact": sum(x["final_ok"] for x in res),
        "confirmations": len(conf), "confirm_ok": sum(x["final_ok"] for x in conf),
        "confirm_mean_s": sum(x["confirm_s"] for x in conf) / len(conf),
        "confirm_mean_tokens": sum((x["prompt_tokens"] or 0) + (x["completion_tokens"] or 0) for x in conf) / len(conf),
        "ooc": sum(1 for x in res if not x["gold"]), "ooc_final_rejected": sum(1 for x in res if not x["gold"] and x["final"] == []),
        "mean_lookup_s": sum(x["lookup_s"] for x in res) / len(res),
    }
    (out / "confirm-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
