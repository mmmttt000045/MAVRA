#!/usr/bin/env python3
"""Cross-generator paraphrases of the 96 lookup test requests (review point 4): GLM (glm-5.3, Zhipu API), a model
family that wrote none of MAVRA's training phrasings (DeepSeek wrote those), rewrites each request twice without
adding or removing any metric choice: (a) as an agent with a sentence of business context, (b) colloquially or in
English. The stated choices, hence the gold sets, are those of the original request. Writes requests.json in the
lookup pilot's format (ids <orig>-a / <orig>-b) and drops rewrites that equal a training phrasing.
Usage: gen_glm.py ENV_FILE TRAIN_JSONL OUT_JSON
"""
import json, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROMPT = """把下面这个向零售数据平台提出的指标问题改写成两种不同的说法，供测试指标查找使用。要求：
- 保持问的是同一个指标、同样的口径：不能增加原问题没说的口径（例如原问题没说是否扣券、是否含税、按哪个日期、按金额还是件数、毛利还是净利润、哪个商品类别，就不要提），也不能丢掉原问题说了的口径；原问题本身含糊的地方保持含糊；
- 可以换期间参数（年份、月份），可以改成问排名或比较；
- 第一种：像数据分析智能体那样提问，先交代一句业务背景或用途；第二种：口语化的随口一问，或者用英文；
- 尽量不用原问题里的关键词，换成同义说法。
原问题：{q}
只输出 JSON 字符串数组，恰好两个元素。"""


def env(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def main():
    E = env(sys.argv[1])
    key, model = E["ZHIPU_API_KEY"], E.get("ZHIPU_MODEL", "glm-5.3")
    base = E.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    train = {json.loads(x)["text"].strip() for x in open(sys.argv[2]) if x.strip()}
    reqs = json.loads(Path(__file__).with_name("requests-orig.json").read_text())["requests"]
    usage = {"prompt": 0, "completion": 0, "calls": 0}

    def one(r):
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": PROMPT.replace("{q}", r["text"])}],
                           "max_tokens": 8192, "reasoning_effort": "low"}).encode()
        for attempt in range(4):
            try:
                req = urllib.request.Request(base + "/chat/completions", data=body,
                                             headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    d = json.load(resp)
                text = d["choices"][0]["message"].get("content") or ""
                m = re.search(r"\[.*\]", text, re.S)
                arr = json.loads(m.group(0)) if m else []
                u = d.get("usage", {})
                return r, [q.strip() for q in arr if isinstance(q, str) and q.strip()][:2], u
            except Exception as e:  # noqa: BLE001
                time.sleep(3 * (attempt + 1))
        return r, [], {}

    out, dropped = [], 0
    with ThreadPoolExecutor(6) as ex:
        for r, qs, u in ex.map(one, reqs):
            usage["calls"] += 1
            usage["prompt"] += u.get("prompt_tokens", 0)
            usage["completion"] += u.get("completion_tokens", 0)
            for tag, q in zip("ab", qs):
                if q in train or q == r["text"]:
                    dropped += 1
                    continue
                out.append({"id": f"{r['id']}-{tag}", "kind": r["kind"], "text": q, "stated": r["stated"], "orig": r["id"]})
    Path(sys.argv[3]).write_text(json.dumps({"note": "GLM paraphrases of the 96 test requests; stated choices copied from the originals.",
                                             "requests": out}, ensure_ascii=False, indent=1))
    print(json.dumps({"requests": len(out), "dropped": dropped, **usage}))


if __name__ == "__main__":
    main()
