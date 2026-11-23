#!/usr/bin/env python3
"""Measure token and wall-clock cost per synthetic phrasing-generation call (lookup amortization).

Samples 6 core intents (seed 7) from the 26-definition catalog and issues the phrasing-generation prompt
at PER=15 phrasings per call via DEEPSEEK_API_KEY / OPENAI_API_KEY.
"""
import json
import os
import random
import statistics
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCALE_DIR = HERE.parents[1] / "semantic-lookup"
sys.path.insert(0, str(SCALE_DIR))
import build_seed_pairs as bsp  # noqa: E402

SYSTEM = (
    "你在为企业数据平台的指标查找器造训练问句。给定一组已说明的指标口径维度，写出 15 个不同说法的业务问题，"
    "要求只表达给定的口径维度，不额外添加未说明的口径，输出 JSON 字符串数组。"
)


def describe_intent(st: dict, fn: dict) -> str:
    return "\n".join(f"- {fn[k]}：{' / '.join(v)}" for k, v in st.items() if k in fn)


def main():
    key = (
        Path(sys.argv[1]).read_text(encoding="utf-8").strip()
        if len(sys.argv) > 1 and sys.argv[1] != "-"
        else (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    )
    if not key:
        raise SystemExit("Set DEEPSEEK_API_KEY (or OPENAI_API_KEY) or pass KEY_FILE")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", os.environ.get("OPENAI_MODEL", "deepseek-flash"))

    cat26 = json.loads((SCALE_DIR / "catalog_26.json").read_text(encoding="utf-8"))
    fn = cat26["facet_names"]
    intents = [st for st, _ in bsp.build_core_intents()]
    random.seed(7)
    use = []
    for st in random.sample(intents, 6):
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "口径：\n" + describe_intent(st, fn) + "\n\n写 15 个问题。"},
            ],
            "max_tokens": 4096,
        }).encode("utf-8")
        req = urllib.request.Request(
            base_url + "/chat/completions",
            data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=180) as resp:
            res = json.load(resp)
        dt = time.time() - t0
        u = res.get("usage", {})
        rec = {
            "prompt": u.get("prompt_tokens", 0),
            "completion": u.get("completion_tokens", 0),
            "seconds": dt,
        }
        use.append(rec)
        print(rec, flush=True)
    print(json.dumps({
        "calls": len(use),
        "prompt_mean": statistics.mean(x["prompt"] for x in use),
        "completion_mean": statistics.mean(x["completion"] for x in use),
        "seconds_mean": statistics.mean(x["seconds"] for x in use),
        "model": model,
    }, indent=2))


if __name__ == "__main__":
    main()
