#!/usr/bin/env python3
"""Deterministically build the 26-definition core training set (train_26_clean.jsonl).

Enumerates rule-labeled business phrasings (Chinese and English) over the 26 core
TPC-DS metric definitions in catalog_26.json and seed examples in pool_26.json:
  - 45 present core intents: full-facet single-definition specs, canonical name/subject
    specs, homonymous underspecified peer groups (e.g., D01/D02, D13/D14, D16/D17),
    and multi-subject / qualifier-partial specs.
  - 54 out-of-catalog (absent) core intents: unmodeled channel x subject combinations,
    unmodeled categories, tax-inclusive revenue, return-date return rates, and
    adjacent retail KPIs absent from the catalog.

Verifies:
  1. Exact core ground-truth invariance between catalog_26.json and catalog_1000.json.
  2. Strict normalized-text disjointness from all evaluation sets
     (requests_orig_96.json, requests_glm_174.json, requests_scale_120.json,
      requests_glm_scale.json).
"""
import argparse
import collections
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm_text(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s.lower(), flags=re.UNICODE)


def consistent(f: dict, stated: dict, slots: list[str]) -> bool:
    for s in slots:
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


CHANNEL_SYN = {
    "门店": ["门店", "线下门店", "实体门店", "线下实体店", "零售店铺", "街边店"],
    "目录": ["目录渠道", "邮购目录", "目录订购", "纸质目录渠道", "目录销售端"],
    "网店": ["网店", "官方网店", "线上商城", "自营网站", "电商网店"],
    "全渠道": ["全渠道", "全平台合计", "线上线下全渠道", "三大渠道汇总", "全域渠道"],
    None: ["全仓", "仓储端", "集团整体", "供应链端"],
}

CHANNEL_EN = {
    "门店": ["in-store", "brick-and-mortar store", "offline retail"],
    "目录": ["catalog channel", "mail-order catalog"],
    "网店": ["web store", "online shop"],
    "全渠道": ["omni-channel", "all-channel combined"],
    None: ["warehouse", "overall inventory"],
}

SUBJECT_SYN = {
    "销售额": ["营业额", "销售收入", "营收金额", "卖货收入"],
    "标价总额": ["标价总额", "吊牌价总额", "按定价汇总金额", "商品挂牌总价"],
    "销量": ["销量", "销售件数", "售出商品件数", "出货件数"],
    "订单数": ["订单数", "成交单数", "成交订单笔数", "下单笔数"],
    "客单价": ["客单价", "平均每单金额", "单均消费额", "笔单价"],
    "利润": ["利润", "盈利金额", "经营收益", "账面收益"],
    "优惠券金额": ["优惠券金额", "用券抵扣额", "礼券核销金额", "券类减免总额"],
    "折扣额": ["折扣额", "促销让利金额", "打折减免额", "标价折让金额"],
    "退货金额": ["退货金额", "退回货款总额", "售后退款金额", "退单金额"],
    "退货件数": ["退货件数", "退回商品数量", "售后退回件数", "退货商品数"],
    "退货率": ["退货率", "退货占比", "售后退回比例", "退单比率"],
    "退货净损失": ["退货净损失", "退货实际亏损额", "售后净损耗金额", "退货净亏损"],
    "库存量": ["平均库存量", "在库商品均值", "平均存货件数", "期初期末平均库存"],
    # Absent retail KPIs
    "坪效": ["坪效", "每平米营业额", "单店面积产出"],
    "客流量": ["客流量", "进店客流人次", "到店访客数"],
    "库存周转天数": ["库存周转天数", "存货周转周期", "平均周转天数"],
    "发货量": ["发货量", "仓库出库件数", "物流发运包裹数"],
    "复购率": ["复购率", "老客回头购买率", "二次购买比例"],
    "毛利率": ["毛利率", "销售毛利占比", "毛利百分比"],
    "连带率": ["连带率", "客单连带件数", "每单平均件数"],
    "转化率": ["成交转化率", "访客下单转化率", "进店购买转化率"],
    "加购数": ["加购件数", "购物车新增商品数", "加购次数"],
}

SUBJECT_EN = {
    "销售额": "revenue",
    "标价总额": "gross list-price total",
    "销量": "units sold",
    "订单数": "order count",
    "客单价": "average order value",
    "利润": "profit",
    "优惠券金额": "coupon discount total",
    "折扣额": "markdown discount amount",
    "退货金额": "return amount",
    "退货件数": "returned units",
    "退货率": "return rate",
    "退货净损失": "net return loss",
    "库存量": "average inventory level",
    "坪效": "sales per square meter",
    "客流量": "store foot traffic",
    "库存周转天数": "inventory turnover days",
    "发货量": "outbound shipment volume",
    "复购率": "repeat purchase rate",
    "毛利率": "gross margin percentage",
    "连带率": "units per transaction",
    "转化率": "conversion rate",
    "加购数": "add-to-cart count",
}

QUAL_ZH = {
    ("amount", "实付（扣券后，不含税）"): ["券后不含税实付口径", "扣除优惠券且不含增值税的实收口径", "净实付（扣券不含税）"],
    ("amount", "扣券前销售额（不含税）"): ["扣券前不含税口径", "未扣减优惠券且不含税的成交口径", "券前不含增值税口径"],
    ("amount", "含税"): ["含增值税口径", "价税合计含税口径", "包含销项税的总额口径"],
    ("profit", "净利润（实付减成本）"): ["实付减成本的净利润口径", "扣券后净利口径", "扣除优惠券与进货成本后的净收益"],
    ("profit", "毛利（扣券前销售额减成本）"): ["扣券前销售额减成本的毛利口径", "券前账面毛利口径", "未扣优惠券减商品成本的毛利"],
    ("ratio", "按金额"): ["按金额占比计算", "退货额除以销售额口径", "金额维度口径"],
    ("ratio", "按件数"): ["按件数占比计算", "退回件数除以销量口径", "数量维度口径"],
    ("date", "按销售日期"): ["按原销售日期归属", "按订单成交日期口径", "归属到售出日期"],
    ("date", "按退货日期"): ["按退货单日期归属", "按售后入库日期口径", "归属到实际退回日期"],
}

QUAL_EN = {
    ("amount", "实付（扣券后，不含税）"): "net paid after coupons (ex-tax)",
    ("amount", "扣券前销售额（不含税）"): "pre-coupon sales (ex-tax)",
    ("amount", "含税"): "tax-inclusive (with VAT)",
    ("profit", "净利润（实付减成本）"): "net profit (net paid minus cost)",
    ("profit", "毛利（扣券前销售额减成本）"): "gross profit (pre-coupon minus cost)",
    ("ratio", "按金额"): "by dollar amount",
    ("ratio", "按件数"): "by unit count",
    ("date", "按销售日期"): "attributed by sale date",
    ("date", "按退货日期"): "attributed by return date",
}

CAT_EN = {
    "电子": "electronics",
    "女装": "women's apparel",
    "家居": "home goods",
    "办公文具": "office stationery",
    "生鲜水果": "fresh fruit",
    "美妆": "beauty",
    "食品": "grocery",
    "运动": "sportswear",
    "母婴": "maternity & baby",
    "鞋靴": "footwear",
    "图书": "books",
}

PERIODS_ZH = [
    "2019年第一季度", "2019年上半年", "2019年11月",
    "2020年第二季度", "2020年下半年", "2020年7月",
    "2021年第一季度", "2021年第三季度", "2021年8月",
    "2022年第二季度", "2022年第四季度", "2022年5月",
    "2023年上半年", "2023年第四季度", "2023年9月",
    "2024年第一季度", "2024年上半年", "2024年10月",
]

PERIODS_EN = ["Q1 2020", "H2 2021", "Q3 2022", "FY 2023", "H1 2024", "Oct 2024"]

FRAMES_ZH = [
    "{per}{cat}{ch}的{subj}{qual}是多少？",
    "请统计{per}{cat}{ch}{subj}{qual}的汇总数值。",
    "财务复盘需要核对{per}{cat}{ch}的{subj}{qual}，结果是多少？",
    "经营月报中，{per}{cat}{ch}{subj}{qual}合计为多少？",
    "帮我查一下{per}{cat}{ch}对应的{subj}{qual}表现。",
    "对比去年同期前，先看{per}{cat}{ch}的{subj}{qual}具体是多少？",
]


def canonical_stated(st: dict) -> dict:
    out = {}
    for k in ("channel", "subject", "amount", "profit", "ratio", "date", "category"):
        if k in st and st[k]:
            v = st[k]
            out[k] = sorted(v) if isinstance(v, list) else [v]
    return out


def build_core_intents() -> list[tuple[dict, int]]:
    """Returns 99 distinct core stated-attribute specs (45 present, 54 absent) with target counts."""
    intents: list[tuple[dict, int]] = []
    seen = set()

    def add(st: dict, target_n: int):
        cst = canonical_stated(st)
        key = json.dumps(cst, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            intents.append((cst, target_n))

    # --- A. 45 Present Core Intents over D01..D26 ---
    # 1. Underspecified / canonical channel + subject (16)
    for ch, subjs in [
        ("门店", ["销售额", "标价总额", "销量", "订单数", "客单价", "利润", "优惠券金额", "折扣额",
                 "退货金额", "退货件数", "退货率", "退货净损失"]),
        ("目录", ["销售额", "销量", "退货金额"]),
        ("网店", ["销售额", "利润", "退货率"]),
        ("全渠道", ["销售额"]),
    ]:
        for sb in subjs:
            if (ch, sb) not in [("网店", "利润")]:  # 网店+利润 ambiguous added below
                add({"channel": [ch], "subject": [sb]}, 84)
    add({"channel": ["网店"], "subject": ["利润"]}, 78)
    add({"subject": ["库存量"]}, 80)

    # 2. Category-scoped present intents (4)
    for cat in ("电子", "女装"):
        add({"channel": ["门店"], "category": [cat], "subject": ["销售额"]}, 80)
        add({"channel": ["门店"], "category": [cat], "subject": ["销售额"],
             "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 78)

    # 3. Qualifier-disambiguated store & channel intents (20)
    add({"channel": ["门店"], "subject": ["销售额"], "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 84)
    add({"channel": ["门店"], "subject": ["销售额"], "amount": ["扣券前销售额（不含税）"], "date": ["按销售日期"]}, 84)
    add({"channel": ["门店"], "subject": ["标价总额"], "date": ["按销售日期"]}, 78)
    add({"channel": ["门店"], "subject": ["销量"], "date": ["按销售日期"]}, 78)
    add({"channel": ["门店"], "subject": ["订单数"], "date": ["按销售日期"]}, 78)
    add({"channel": ["门店"], "subject": ["客单价"], "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 78)
    add({"channel": ["门店"], "subject": ["利润"], "profit": ["净利润（实付减成本）"], "date": ["按销售日期"]}, 80)
    add({"channel": ["门店"], "subject": ["利润"], "profit": ["毛利（扣券前销售额减成本）"], "date": ["按销售日期"]}, 80)
    add({"channel": ["门店"], "subject": ["优惠券金额"], "date": ["按销售日期"]}, 78)
    add({"channel": ["门店"], "subject": ["折扣额"], "date": ["按销售日期"]}, 78)
    add({"channel": ["门店"], "subject": ["退货金额"], "date": ["按退货日期"]}, 80)
    add({"channel": ["门店"], "subject": ["退货金额"], "date": ["按销售日期"]}, 80)
    add({"channel": ["门店"], "subject": ["退货件数"], "date": ["按退货日期"]}, 78)
    add({"channel": ["门店"], "subject": ["退货率"], "ratio": ["按金额"], "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 80)
    add({"channel": ["门店"], "subject": ["退货率"], "ratio": ["按件数"], "date": ["按销售日期"]}, 80)
    add({"channel": ["门店"], "subject": ["退货净损失"], "date": ["按退货日期"]}, 78)
    add({"channel": ["目录"], "subject": ["销售额"], "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 78)
    add({"channel": ["网店"], "subject": ["销售额"], "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 78)
    add({"channel": ["网店"], "subject": ["利润"], "profit": ["净利润（实付减成本）"], "date": ["按销售日期"]}, 78)
    add({"channel": ["网店"], "subject": ["退货率"], "ratio": ["按金额"], "amount": ["实付（扣券后，不含税）"], "date": ["按销售日期"]}, 78)

    # 4. Multi-subject ambiguous lexical intents (1)
    add({"channel": ["门店"], "subject": ["优惠券金额", "折扣额"]}, 78)

    assert len(intents) == 45, f"Expected 45 present intents, got {len(intents)}"

    # --- B. 54 Absent Core Intents (gold == [] in catalog_26 AND catalog_1000) ---
    # 1. Missing channel x modeled-subject combinations (23)
    for ch, subjs in [
        ("目录", ["标价总额", "订单数", "客单价", "利润", "优惠券金额", "折扣额", "退货件数", "退货率", "退货净损失"]),
        ("网店", ["标价总额", "销量", "订单数", "客单价", "优惠券金额", "折扣额", "退货金额", "退货件数", "退货净损失"]),
        ("全渠道", ["销量", "订单数", "客单价", "利润", "退货金额"]),
    ]:
        for sb in subjs:
            add({"channel": [ch], "subject": [sb]}, 63)

    # 2. Missing category combinations across channels (12)
    for cat in ("家居", "办公文具", "生鲜水果", "美妆", "食品", "运动", "母婴", "鞋靴"):
        add({"channel": ["门店"], "category": [cat], "subject": ["销售额"]}, 63)
    for ch, cat in [("网店", "电子"), ("网店", "女装"), ("目录", "电子"), ("全渠道", "电子")]:
        add({"channel": [ch], "category": [cat], "subject": ["销售额"]}, 63)

    # 3. Unmodeled qualifier combinations on active channels (9)
    for ch in ("门店", "目录", "网店", "全渠道"):
        add({"channel": [ch], "subject": ["销售额"], "amount": ["含税"]}, 63)
    add({"channel": ["目录"], "subject": ["销售额"], "amount": ["扣券前销售额（不含税）"]}, 63)
    add({"channel": ["网店"], "subject": ["销售额"], "amount": ["扣券前销售额（不含税）"]}, 63)
    add({"channel": ["门店"], "subject": ["退货率"], "date": ["按退货日期"]}, 63)
    add({"channel": ["网店"], "subject": ["退货率"], "ratio": ["按件数"]}, 63)
    add({"channel": ["网店"], "subject": ["利润"], "profit": ["毛利（扣券前销售额减成本）"]}, 63)

    # 4. Unmodeled adjacent retail KPIs (10)
    for ch, sb in [
        ("门店", "坪效"),
        ("门店", "客流量"),
        ("门店", "库存周转天数"),
        ("门店", "毛利率"),
        ("门店", "连带率"),
        ("网店", "转化率"),
        ("网店", "加购数"),
        ("全渠道", "复购率"),
    ]:
        add({"channel": [ch], "subject": [sb]}, 78)
    add({"subject": ["发货量"]}, 78)
    add({"subject": ["复购率"]}, 78)

    assert len(intents) == 99, f"Expected 99 total intents, got {len(intents)}"
    return intents


def render_intent_phrasings(st: dict, limit: int, banned_norms: set[str]) -> list[str]:
    ch = st["channel"][0] if "channel" in st else None
    cat = st["category"][0] if "category" in st else None
    subjs = st["subject"]
    subj_key = subjs[0] if len(subjs) == 1 else None

    ch_syns = CHANNEL_SYN[ch]
    if subj_key:
        sb_syns = SUBJECT_SYN[subj_key]
    else:
        sb_syns = ["优惠减免总额", "券折合计让利额", "促销优惠总金额", "用券与打折减免额"]

    qual_parts_zh = []
    qual_parts_en = []
    for qk in ("amount", "profit", "ratio", "date"):
        if qk in st:
            qv = st[qk][0]
            qual_parts_zh.append(QUAL_ZH[(qk, qv)])
            qual_parts_en.append(QUAL_EN[(qk, qv)])

    cat_variants = [f"{cat}品类", f"{cat}类目", f"{cat}商品"] if cat else [""]

    out: list[str] = []
    seen_local: set[str] = set()

    def push(txt: str) -> bool:
        nt = norm_text(txt)
        if not nt or nt in banned_norms or nt in seen_local:
            return False
        seen_local.add(nt)
        out.append(txt)
        return len(out) >= limit

    # Generate diverse Chinese business phrasings
    idx = 0
    for per in PERIODS_ZH:
        for ch_s in ch_syns:
            for sb_s in sb_syns:
                cat_s = cat_variants[idx % len(cat_variants)]
                if qual_parts_zh:
                    q_str = "（" + "，".join(qp[idx % len(qp)] for qp in qual_parts_zh) + "）"
                else:
                    q_str = ""
                frame = FRAMES_ZH[idx % len(FRAMES_ZH)]
                txt = frame.format(per=per, cat=cat_s, ch=ch_s, subj=sb_s, qual=q_str)
                idx += 1
                if push(txt):
                    return out

    # Add English phrasings if more needed
    en_ch_list = CHANNEL_EN[ch]
    en_sb = SUBJECT_EN.get(subj_key, "promotional discount & coupon total")
    en_cat = f"for {CAT_EN[cat]} " if cat else ""
    en_qual = f" ({', '.join(qual_parts_en)})" if qual_parts_en else ""
    for per_en in PERIODS_EN:
        for ech in en_ch_list:
            txt = f"What was the { ech } {en_sb} {en_cat}in {per_en}{en_qual}?".replace("  ", " ")
            if push(txt):
                return out

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "train_26_clean.jsonl")
    args = ap.parse_args()

    cat26 = json.loads((HERE / "catalog_26.json").read_text(encoding="utf-8"))
    cat1000 = json.loads((HERE / "catalog_1000.json").read_text(encoding="utf-8"))
    slots = list(cat26["facet_names"])
    defs26 = cat26["definitions"]
    defs1000 = cat1000["definitions"]
    by_id26 = {d["id"]: d for d in defs26}

    # Collect all evaluation queries to enforce strict disjointness
    banned_norms: set[str] = set()
    for req_file in (
        "requests_orig_96.json",
        "requests_glm_174.json",
        "requests_scale_120.json",
        "requests_glm_scale.json",
    ):
        p = HERE / req_file
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["requests"]:
                banned_norms.add(norm_text(r["text"]))

    intents = build_core_intents()
    rows: list[dict] = []
    used_norms: set[str] = set()

    # Include seed examples from pool_26.json first (mapped to exact stated facets)
    pool26 = json.loads((HERE / "pool_26.json").read_text(encoding="utf-8"))
    per_intent_seed = collections.Counter()
    intent_keys = {json.dumps(st, ensure_ascii=False, sort_keys=True) for st, _ in intents}
    for ex in pool26:
        nt = norm_text(ex["text"])
        if nt in banned_norms or nt in used_norms:
            continue
        d = by_id26[ex["def"]]
        f = d["facets"]
        if ex["text"] == f"{d['name']}是多少？":
            st = {k: [v] for k, v in f.items() if k in ("channel", "category", "subject") and v}
            if f.get("profit"):
                st["profit"] = [f["profit"]]
        else:
            st = {k: [v] for k, v in f.items() if v}
        cst = canonical_stated(st)
        k = json.dumps(cst, ensure_ascii=False, sort_keys=True)
        if k in intent_keys:
            g26 = sorted(x["id"] for x in defs26 if consistent(x["facets"], cst, slots))
            rows.append({"text": ex["text"], "stated": cst, "gold": g26})
            used_norms.add(nt)
            per_intent_seed[k] += 1

    # Enumerate rule-labeled phrasings per core intent
    present_intents = 0
    absent_intents = 0
    for cst, target_n in intents:
        g26 = sorted(x["id"] for x in defs26 if consistent(x["facets"], cst, slots))
        g1000 = sorted(x["id"] for x in defs1000 if consistent(x["facets"], cst, slots))
        assert g26 == g1000, f"Core invariance broken for {cst}: {g26} vs {g1000}"
        if g26:
            present_intents += 1
        else:
            absent_intents += 1
        k = json.dumps(cst, ensure_ascii=False, sort_keys=True)
        need = max(0, target_n - per_intent_seed[k])
        for txt in render_intent_phrasings(cst, need, banned_norms | used_norms):
            used_norms.add(norm_text(txt))
            rows.append({"text": txt, "stated": cst, "gold": g26})

    # Final leak check
    for row in rows:
        assert norm_text(row["text"]) not in banned_norms, f"Leak detected: {row['text']}"

    args.out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )

    by_key = collections.Counter(json.dumps(r["stated"], ensure_ascii=False, sort_keys=True) for r in rows)
    print(
        json.dumps(
            {
                "out": str(args.out.name),
                "total_rows": len(rows),
                "intents": len(by_key),
                "present_intents": present_intents,
                "absent_intents": absent_intents,
                "median_per_intent": statistics.median(by_key.values()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
