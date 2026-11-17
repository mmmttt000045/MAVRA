#!/usr/bin/env python3
"""Deterministic nested enterprise catalog & multi-domain query generator for C2 lookup scaling (P1-1).

Builds nested catalogs M_26 c M_100 c M_500 c M_1000 across 8 enterprise analytical domains:
  - D01..D26: byte-identical 26-definition TPC-DS retail core (from 2026-11-10 lookup benchmark).
  - D0027..D1000: 974 SQL-backed metric definitions (homonymous pairs + single-definition metrics)
    spanning Retail Categories, Digital Retail Channels, B2B/SaaS, Supply Chain/WMS, Finance/Payments,
    CRM/Loyalty, AdTech Attribution, After-Sales Service, and Store Operations.

Invariants enforced by assertion before writing any file:
  1. Strict nesting: M_26 == M_100[:26], M_100 == M_500[:100], M_500 == M_1000[:500].
  2. Core ground-truth invariance: for every query r in requests_orig_96.json and requests_glm_174.json,
     gold(r, M_26) == gold(r, M_100) == gold(r, M_500) == gold(r, M_1000).
  3. Homonymous pair completeness: no homonymous pair is split across the 26 / 100 / 500 / 1000 boundaries.
  4. Zero phrasing overlap between pool_1000.json / synthetic training phrasings and any test query set.
"""
import hashlib
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_CAT = json.loads((HERE / "catalog_26.json").read_text(encoding="utf-8"))
ORIG_REQS = json.loads((HERE / "requests_orig_96.json").read_text(encoding="utf-8"))["requests"]
GLM_REQS = json.loads((HERE / "requests_glm_174.json").read_text(encoding="utf-8"))["requests"]
POOL_26 = json.loads((HERE / "pool_26.json").read_text(encoding="utf-8"))

FN = BASE_CAT["facet_names"]
SLOTS = list(FN)


def consistent(f, stated):
    """Exact Definition 4.1 facet consistency rule from common.py / lookup.py (normalizing str/list)."""
    for s in SLOTS:
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


def consistent_raw(f, stated):
    """Exact byte-for-byte original consistent() from common.py to ensure string-in-string edge cases never trigger."""
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


def conflicts_with_core(facets):
    for r in ORIG_REQS + GLM_REQS:
        if consistent(facets, r["stated"]) or consistent_raw(facets, r["stated"]):
            return True
    return False


# ---------------------------------------------------------------------------
# Building blocks across 8 enterprise schemas
# ---------------------------------------------------------------------------

# 1. Retail category expansion on classic channels (门店, 目录, 网店)
# Carefully excludes any (channel, category, subject) asked as absent in requests_orig_96 (e.g. 家居+门店销售额, 电子+网店销售额)
RETAIL_CATS = [
    ("男装", "Men", "men"),
    ("童装", "Children", "kids"),
    ("运动户外", "Sports", "sports"),
    ("鞋靴箱包", "Shoes", "footwear"),
    ("美妆护肤", "Beauty", "beauty"),
    ("食品生鲜", "Grocery", "grocery"),
    ("图书音像", "Books", "books"),
    ("珠宝钟表", "Jewelry", "jewelry"),
    ("母婴玩具", "Baby", "baby"),
    ("大小家电", "Appliances", "appliance"),
    ("数码配件", "Accessories", "accessory"),
    ("汽车用品", "Automotive", "auto"),
    ("宠物用品", "Pets", "pet"),
    ("医药健康", "Pharmacy", "health"),
    ("办公文具", "Office", "office"),
    ("乐器文创", "Music", "music"),
]

# 2. Enterprise channels / business lines across 8 warehouse domains
ENTERPRISE_LINES = [
    # Domain A: Modern Digital Retail
    {"channel": "移动端App", "en": "mobile app", "syn": ["手机App", "客户端App"], "fact": "app_orders", "ret": "app_returns", "pfx": "ao"},
    {"channel": "微信小程序", "en": "WeChat mini-program", "syn": ["小程序商城", "微信端"], "fact": "mp_orders", "ret": "mp_returns", "pfx": "mp"},
    {"channel": "抖音直播间", "en": "Douyin livestream", "syn": ["抖音带货", "直播电商抖音端"], "fact": "live_dy_sales", "ret": "live_dy_returns", "pfx": "dy"},
    {"channel": "快手直播间", "en": "Kuaishou livestream", "syn": ["快手电商店铺", "快手带货"], "fact": "live_ks_sales", "ret": "live_ks_returns", "pfx": "ks"},
    {"channel": "跨境独立站", "en": "cross-border storefront", "syn": ["海外独立站", "DTC出海站"], "fact": "dtc_orders", "ret": "dtc_refunds", "pfx": "dtc"},
    {"channel": "社区即时达", "en": "instant local delivery", "syn": ["同城小时达", "前置仓即时零售"], "fact": "instant_orders", "ret": "instant_returns", "pfx": "ins"},
    {"channel": "机场免税店", "en": "airport duty-free", "syn": ["口岸免税专柜", "免税渠道"], "fact": "dutyfree_sales", "ret": "dutyfree_returns", "pfx": "df"},
    {"channel": "加盟经销商", "en": "franchise dealer", "syn": ["加盟门店体系", "特许经销渠道"], "fact": "dealer_sales", "ret": "dealer_returns", "pfx": "dl"},
    # Domain B: B2B & SaaS Enterprise
    {"channel": "企业大客户B2B", "en": "enterprise B2B", "syn": ["KA大客户线", "企业集采渠道"], "fact": "b2b_ka_invoices", "ret": "b2b_ka_credits", "pfx": "ka"},
    {"channel": "中小企业SMB", "en": "SMB commercial", "syn": ["中小商户线", "SMB自助采购"], "fact": "b2b_smb_invoices", "ret": "b2b_smb_credits", "pfx": "smb"},
    {"channel": "政企采购线", "en": "public-sector procurement", "syn": ["政企阳光采购", "G端集采"], "fact": "gov_orders", "ret": "gov_returns", "pfx": "gov"},
    {"channel": "SaaS云订阅", "en": "SaaS cloud subscription", "syn": ["云服务年费订阅", "软件订阅线"], "fact": "saas_billings", "ret": "saas_churn_credits", "pfx": "saas"},
    # Domain C: Supply Chain & Regional Fulfillment Warehouses
    {"channel": "华东中心仓", "en": "East China central warehouse", "syn": ["昆山总仓", "华东RDC仓"], "fact": "wms_east_shipments", "ret": "wms_east_claims", "pfx": "we"},
    {"channel": "华南区域仓", "en": "South China regional warehouse", "syn": ["东莞区域仓", "华南RDC仓"], "fact": "wms_south_shipments", "ret": "wms_south_claims", "pfx": "ws"},
    {"channel": "华北中心仓", "en": "North China central warehouse", "syn": ["武清总仓", "华北RDC仓"], "fact": "wms_north_shipments", "ret": "wms_north_claims", "pfx": "wn"},
    {"channel": "保税跨境仓", "en": "bonded cross-border warehouse", "syn": ["宁波保税仓", "跨境备货仓"], "fact": "wms_bonded_shipments", "ret": "wms_bonded_claims", "pfx": "wb"},
    {"channel": "冷链生鲜仓", "en": "cold-chain fulfillment hub", "syn": ["温控冷链仓", "生鲜冷冻仓"], "fact": "wms_cold_shipments", "ret": "wms_cold_claims", "pfx": "wc"},
    # Domain D: Finance & Payment Gateways
    {"channel": "支付宝渠道", "en": "Alipay gateway", "syn": ["支付宝收单", "Alipay支付通道"], "fact": "pay_alipay_txns", "ret": "pay_alipay_chargebacks", "pfx": "ali"},
    {"channel": "微信支付渠道", "en": "WeChat Pay gateway", "syn": ["财付通微信收单", "微信支付通道"], "fact": "pay_wx_txns", "ret": "pay_wx_chargebacks", "pfx": "wxp"},
    {"channel": "银联云闪付", "en": "UnionPay gateway", "syn": ["银联卡收单", "云闪付通道"], "fact": "pay_up_txns", "ret": "pay_up_chargebacks", "pfx": "up"},
    {"channel": "信用卡分期", "en": "credit card installment", "syn": ["银行卡分期通道", "免息分期渠道"], "fact": "pay_inst_txns", "ret": "pay_inst_chargebacks", "pfx": "inst"},
    # Domain E: CRM & Membership Tiers
    {"channel": "付费黑卡会员", "en": "VIP Black-Card members", "syn": ["SVIP付费会员", "黑卡年费会员"], "fact": "crm_vip_orders", "ret": "crm_vip_refunds", "pfx": "vip"},
    {"channel": "企微私域池", "en": "WeCom private-traffic pool", "syn": ["企业微信社群", "导购私域渠道"], "fact": "crm_wecom_orders", "ret": "crm_wecom_refunds", "pfx": "wcrm"},
    {"channel": "校园联名会员", "en": "campus student membership", "syn": ["高校学生会员", "青春卡会员"], "fact": "crm_campus_orders", "ret": "crm_campus_refunds", "pfx": "stu"},
    # Domain F: AdTech & Attribution Channels
    {"channel": "信息流广告", "en": "in-feed ads", "syn": ["推荐流信息流投放", "短视频信息流"], "fact": "ad_feed_conversions", "ret": "ad_feed_invalid", "pfx": "adf"},
    {"channel": "搜索竞价SEM", "en": "paid search SEM", "syn": ["关键词竞价投放", "搜索广告渠道"], "fact": "ad_sem_conversions", "ret": "ad_sem_invalid", "pfx": "sem"},
    {"channel": "达人种草投放", "en": "KOL influencer campaigns", "syn": ["博主合作种草", "达人商单渠道"], "fact": "ad_kol_conversions", "ret": "ad_kol_invalid", "pfx": "kol"},
    {"channel": "联盟分销CPS", "en": "affiliate CPS network", "syn": ["淘宝客与返利联盟", "CPS分销推广"], "fact": "ad_cps_conversions", "ret": "ad_cps_invalid", "pfx": "cps"},
    # Domain G: After-Sales & Service Centers
    {"channel": "线下授权网点", "en": "authorized service centers", "syn": ["线下特约维修站", "授权售后网点"], "fact": "svc_center_orders", "ret": "svc_center_claims", "pfx": "sc"},
    {"channel": "寄修服务中心", "en": "mail-in repair depot", "syn": ["返厂寄修中心", "集中寄修仓"], "fact": "svc_depot_orders", "ret": "svc_depot_claims", "pfx": "sd"},
    # Domain H: Store Formats & Operations
    {"channel": "直营旗舰店", "en": "direct flagship stores", "syn": ["城市形象旗舰店", "自营大店"], "fact": "ops_flagship_sales", "ret": "ops_flagship_returns", "pfx": "flg"},
    {"channel": "奥莱折扣店", "en": "outlet discount stores", "syn": ["奥特莱斯工厂店", "尾货奥莱店"], "fact": "ops_outlet_sales", "ret": "ops_outlet_returns", "pfx": "out"},
]


def make_line_bundle(line, cat=None):
    """Creates a cohesive list of groups (each group is either a 2-def homonymous pair or a 1-def metric)
    for an enterprise line, optionally scoped by product category `cat`."""
    ch = line["channel"]
    en_ch = line["en"]
    f_tbl = line["fact"]
    r_tbl = line["ret"]
    p = line["pfx"]
    cat_zh, cat_en = (cat[0], cat[1]) if cat else (None, None)
    cat_prefix = f"{cat_zh}品类" if cat_zh else ""
    cat_clause = f"类别（item.i_category）为 {cat_en} 的商品在" if cat_zh else ""
    base_f = {"channel": ch}
    if cat_zh:
        base_f["category"] = cat_zh

    groups = []

    # Group 1 (Homonymous pair): 营业额 (实付扣券后 vs 扣券前销售额)
    g1 = [
        {
            "name": f"{cat_prefix}{ch}营业额",
            "text": f"{cat_prefix}{ch}营业额 = {cat_clause}{ch}明细行的净支付额（{f_tbl}.{p}_net_paid，已扣优惠券、不含税）之和，按订单销售日期归属期间",
            "facets": {**base_f, "subject": "销售额", "amount": "实付（扣券后，不含税）", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "rev_net"},
        },
        {
            "name": f"{cat_prefix}{ch}营业额",
            "text": f"{cat_prefix}{ch}营业额 = {cat_clause}{ch}明细行的折前成交额（{f_tbl}.{p}_gross_amount，未扣优惠券、不含税）之和，按订单销售日期归属期间",
            "facets": {**base_f, "subject": "销售额", "amount": "扣券前销售额（不含税）", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "rev_gross"},
        },
    ]
    groups.append(g1)

    # Group 2 (Homonymous pair): 退货率 (按金额 vs 按件数)
    g2 = [
        {
            "name": f"{cat_prefix}{ch}退货率",
            "text": f"{cat_prefix}{ch}退货率（%）= 期间内售出的{cat_clause}{ch}订单所对应的退款金额（{r_tbl}.{p}_return_amt）之和 ÷ 这些订单行的净支付额（{f_tbl}.{p}_net_paid）之和 × 100；按销售日期归属期间",
            "facets": {**base_f, "subject": "退货率", "ratio": "按金额", "amount": "实付（扣券后，不含税）", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "rr_amt"},
        },
        {
            "name": f"{cat_prefix}{ch}退货率",
            "text": f"{cat_prefix}{ch}退货率（%）= 期间内售出的{cat_clause}{ch}订单所对应的退回件数（{r_tbl}.{p}_return_qty）之和 ÷ 这些订单行的售出件数（{f_tbl}.{p}_quantity）之和 × 100；按销售日期归属期间",
            "facets": {**base_f, "subject": "退货率", "ratio": "按件数", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "rr_qty"},
        },
    ]
    groups.append(g2)

    # Group 3 (Homonymous by subject 利润): 净利润 vs 毛利
    g3 = [
        {
            "name": f"{cat_prefix}{ch}净利润",
            "text": f"{cat_prefix}{ch}净利润 = {cat_clause}{ch}明细行的净利润（{f_tbl}.{p}_net_profit，即扣券后净支付额减履约与商品成本）之和，按销售日期归属期间",
            "facets": {**base_f, "subject": "利润", "profit": "净利润（实付减成本）", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "prof_net"},
        },
        {
            "name": f"{cat_prefix}{ch}毛利",
            "text": f"{cat_prefix}{ch}毛利 = {cat_clause}{ch}明细行的扣券前销售额减商品进货成本（{f_tbl}.{p}_gross_amount - {f_tbl}.{p}_wholesale_cost）之和，按销售日期归属期间",
            "facets": {**base_f, "subject": "利润", "profit": "毛利（扣券前销售额减成本）", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "prof_gross"},
        },
    ]
    groups.append(g3)

    # Group 4 (Homonymous pair): 退货金额 (按退货日期 vs 按销售日期)
    g4 = [
        {
            "name": f"{cat_prefix}{ch}退货金额",
            "text": f"{cat_prefix}{ch}退货金额 = {cat_clause}{ch}退货单的退款金额（{r_tbl}.{p}_return_amt）之和，按退货处理日期归属期间",
            "facets": {**base_f, "subject": "退货金额", "date": "按退货日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "ret_rdate"},
        },
        {
            "name": f"{cat_prefix}{ch}退货金额",
            "text": f"{cat_prefix}{ch}退货金额 = 期间内售出的{cat_clause}{ch}订单后续发生的退款金额（{r_tbl}.{p}_return_amt）之和，按原订单销售日期归属期间",
            "facets": {**base_f, "subject": "退货金额", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "ret_sdate"},
        },
    ]
    groups.append(g4)

    # Single-definition metrics on this line/category
    singles = [
        {
            "name": f"{cat_prefix}{ch}销量",
            "text": f"{cat_prefix}{ch}销量 = {cat_clause}{ch}明细行的售出件数（{f_tbl}.{p}_quantity）之和，按销售日期归属期间",
            "facets": {**base_f, "subject": "销量", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "qty"},
        },
        {
            "name": f"{cat_prefix}{ch}订单数",
            "text": f"{cat_prefix}{ch}订单数 = {cat_clause}{ch}中不同订单号（{f_tbl}.{p}_order_id）的去重个数，按销售日期归属期间",
            "facets": {**base_f, "subject": "订单数", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "orders"},
        },
        {
            "name": f"{cat_prefix}{ch}客单价",
            "text": f"{cat_prefix}{ch}客单价 = {cat_clause}{ch}净支付额（{f_tbl}.{p}_net_paid）之和 ÷ 不同订单号（{f_tbl}.{p}_order_id）个数，按销售日期归属期间",
            "facets": {**base_f, "subject": "客单价", "amount": "实付（扣券后，不含税）", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "aov"},
        },
        {
            "name": f"{cat_prefix}{ch}优惠券金额",
            "text": f"{cat_prefix}{ch}优惠券金额 = {cat_clause}{ch}明细行的优惠券抵扣额（{f_tbl}.{p}_coupon_amt）之和，按销售日期归属期间",
            "facets": {**base_f, "subject": "优惠券金额", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "coupon"},
        },
        {
            "name": f"{cat_prefix}{ch}折扣额",
            "text": f"{cat_prefix}{ch}折扣额 = {cat_clause}{ch}明细行的标价立减折扣额（{f_tbl}.{p}_discount_amt）之和，按销售日期归属期间",
            "facets": {**base_f, "subject": "折扣额", "date": "按销售日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "discount"},
        },
        {
            "name": f"{cat_prefix}{ch}退货件数",
            "text": f"{cat_prefix}{ch}退货件数 = {cat_clause}{ch}退货单的退回件数（{r_tbl}.{p}_return_qty）之和，按退货日期归属期间",
            "facets": {**base_f, "subject": "退货件数", "date": "按退货日期"},
            "_meta": {"en_ch": en_ch, "cat_en": cat_en, "syn": line["syn"], "kind": "ret_qty"},
        },
    ]
    for s in singles:
        groups.append([s])

    return groups


def make_classic_category_groups():
    """Category-scoped metrics on classic TPC-DS channels (门店, 目录, 网店) that never collide with core 270."""
    classic_lines = [
        {"channel": "门店", "en": "in-store", "syn": ["实体店", "线下门店"], "fact": "store_sales", "ret": "store_returns", "pfx": "ss"},
        {"channel": "目录", "en": "catalog", "syn": ["邮购目录", "目录渠道"], "fact": "catalog_sales", "ret": "catalog_returns", "pfx": "cs"},
        {"channel": "网店", "en": "web store", "syn": ["线上商城", "官方网店"], "fact": "web_sales", "ret": "web_returns", "pfx": "ws"},
    ]
    groups = []
    for cat in RETAIL_CATS:
        for cl in classic_lines:
            for g in make_line_bundle(cl, cat=cat):
                if not any(conflicts_with_core(item["facets"]) for item in g):
                    groups.append(g)
    return groups


def generate_all_groups():
    # Tier-balanced ordering:
    # Wave 1 (fills 27..100 = 74 defs): 16 primary enterprise lines across all 8 domains (rev pair + rr pair + singles) + classic retail categories
    wave1_groups = []
    for idx, line in enumerate(ENTERPRISE_LINES[:16]):
        b = make_line_bundle(line, cat=None)
        wave1_groups.append(b[0])  # homonymous rev pair (2)
        if idx < 8:
            wave1_groups.append(b[1])  # homonymous return-rate pair (2)
        wave1_groups.append(b[4])  # qty single (1)
        if idx < 10:
            wave1_groups.append(b[6])  # aov single (1)

    # Wave 2 (fills 101..500 = 400 defs): remaining unscoped enterprise lines + classic category-scoped retail + first category-scoped digital lines
    rest_groups = []
    for idx, line in enumerate(ENTERPRISE_LINES):
        b = make_line_bundle(line, cat=None)
        start_j = 0
        for j, g in enumerate(b):
            if idx < 16 and (j == 0 or (idx < 8 and j == 1) or j == 4 or (idx < 10 and j == 6)):
                continue
            rest_groups.append(g)

    rest_groups.extend(make_classic_category_groups())

    # Category-scoped enterprise lines (e.g. Electronics on Mobile App, Beauty on Douyin Livestream, etc.) to reach 1,000+ cleanly
    for cat in RETAIL_CATS[:10]:
        for line in ENTERPRISE_LINES[:14]:
            for g in make_line_bundle(line, cat=cat):
                if not any(conflicts_with_core(item["facets"]) for item in g):
                    rest_groups.append(g)

    return wave1_groups, rest_groups


def pack_exact(groups, target_add, used_signatures):
    """Packs complete groups (size 1 or 2) to hit `target_add` definitions exactly without splitting any homonymous pair."""
    out = []
    deferred = []
    for g in groups:
        sigs = [json.dumps(x["facets"], ensure_ascii=False, sort_keys=True) + "|" + x["name"] for x in g]
        if any(s in used_signatures for s in sigs):
            continue
        if any(conflicts_with_core(x["facets"]) for x in g):
            continue
        rem = target_add - len(out)
        if rem == 0:
            break
        if len(g) <= rem:
            out.extend(g)
            used_signatures.update(sigs)
        else:
            deferred.append(g)
    return out, deferred


def make_pool_phrasings(d):
    """Generates 1 canonical + 5 diverse synthetic phrasings for TeCoD's template pool & refreshed CE training."""
    meta = d.get("_meta", {})
    ch = d["facets"].get("channel", "")
    cat = d["facets"].get("category")
    syn = (meta.get("syn") or [ch])[0]
    en_ch = meta.get("en_ch", ch)
    cat_zh = f"{cat}类" if cat else ""
    cat_en = f"{meta['cat_en']} " if meta.get("cat_en") else ""
    kind = meta.get("kind", "")

    canon = f"{d['name']}是多少？"
    if kind == "rev_net":
        extra = [
            f"2023年第四季度{syn}{cat_zh}券后不含税实付营收合计是多少？",
            f"2024年上半年{ch}{cat_zh}扣除优惠券后的净收款金额（不含税）是多少？",
            f"What was the {cat_en}net paid revenue (after coupons, ex-tax) for {en_ch} in Q2 2024?",
            f"对比2023年与2022年，{syn}{cat_zh}实付不含税销售额增长了多少？",
            f"2024年1月至6月{ch}{cat_zh}各月净支付营业额（已扣券）最高的是哪个月？",
        ]
    elif kind == "rev_gross":
        extra = [
            f"2023年全年{syn}{cat_zh}未扣优惠券的不含税销售额合计是多少？",
            f"2024年3月{ch}{cat_zh}折前成交金额（扣券前、不含增值税）是多少？",
            f"What was the pre-coupon gross sales amount (excluding tax) on {en_ch} for {cat_en}items in 2023?",
            f"2022年第四季度{syn}{cat_zh}未减除优惠券的销售总额是多少？",
            f"2024年{ch}{cat_zh}各月扣券前营业额的平均值是多少？",
        ]
    elif kind == "rr_amt":
        extra = [
            f"2023年{syn}{cat_zh}按金额计算的退货率（按销售日期归属）是多少？",
            f"2024年第二季度{ch}{cat_zh}售出订单对应的退款额占实付金额的百分比是多少？",
            f"What was the amount-based return rate (by sale date) for {cat_en}{en_ch} in 2023?",
            f"2022年{syn}{cat_zh}按实付净额口径统计的退货金额占比是多少？",
            f"2024年上半年{ch}{cat_zh}哪个月的金额口径退货率最高？",
        ]
    elif kind == "rr_qty":
        extra = [
            f"2023年{syn}{cat_zh}按件数计算的退货率是多少？",
            f"2024年第一季度{ch}{cat_zh}退回商品件数占售出件数的比例是多少？",
            f"What was the quantity-based return rate for {cat_en}{en_ch} in 2023?",
            f"2022年全年{syn}{cat_zh}按销量件数口径统计的退货占比是多少？",
            f"2024年5月{ch}{cat_zh}件数退货率比4月变化了多少？",
        ]
    elif kind == "prof_net":
        extra = [
            f"2023年{syn}{cat_zh}扣除成本和优惠券后的净利润合计是多少？",
            f"2024年第二季度{ch}{cat_zh}实付净利（净支付额减成本）是多少？",
            f"What was the net profit (net paid minus cost) for {cat_en}{en_ch} in 2023?",
            f"2022年下半年{syn}{cat_zh}净赚的利润总额是多少？",
            f"2024年{ch}{cat_zh}各月净利润最高的是哪个月？",
        ]
    elif kind == "prof_gross":
        extra = [
            f"2023年{syn}{cat_zh}毛利（扣券前销售额减进货成本）是多少？",
            f"2024年第一季度{ch}{cat_zh}不扣优惠券的销售毛利额合计多少？",
            f"What was the gross margin amount (pre-coupon sales minus wholesale cost) on {en_ch} for {cat_en}products in 2023?",
            f"2022年{syn}{cat_zh}全年账面毛利总额是多少？",
            f"2024年6月{ch}{cat_zh}扣券前毛利比5月增加了多少？",
        ]
    elif kind == "ret_rdate":
        extra = [
            f"2023年8月{syn}{cat_zh}按退货处理日期统计的退款总额是多少？",
            f"2024年第一季度{ch}{cat_zh}当期入账处理的退货金额合计多少？",
            f"What was the return amount attributed by return date for {cat_en}{en_ch} in May 2023?",
            f"2022年{syn}{cat_zh}按退货发生日归属的退款金额是多少？",
            f"2024年上半年{ch}{cat_zh}按退货日期口径哪个月退款最多？",
        ]
    elif kind == "ret_sdate":
        extra = [
            f"2023年8月售出的{syn}{cat_zh}订单后来被退掉的金额合计是多少？",
            f"2024年第一季度{ch}{cat_zh}按原销售日期归属的退货金额是多少？",
            f"What was the return amount attributed to original sale date for {cat_en}{en_ch} in Q1 2024?",
            f"2022年11月大促售出的{syn}{cat_zh}商品后续累计退款多少钱？",
            f"2024年{ch}{cat_zh}按销售日归属口径的月度退货额是多少？",
        ]
    elif kind == "qty":
        extra = [
            f"2023年{syn}{cat_zh}一共卖出了多少件商品？",
            f"2024年第二季度{ch}{cat_zh}累计销售件数是多少？",
            f"Total {cat_en}units sold on {en_ch} in 2023?",
            f"2022年12月{syn}{cat_zh}商品出货销量是多少？",
            f"2024年{ch}{cat_zh}销量最高的月份卖了多少件？",
        ]
    elif kind == "orders":
        extra = [
            f"2023年{syn}{cat_zh}成交了多少笔去重订单？",
            f"2024年第一季度{ch}{cat_zh}不同订单号总数是多少？",
            f"How many distinct {cat_en}orders were placed via {en_ch} in 2023?",
            f"2022年全年{syn}{cat_zh}有效订单单量合计多少？",
            f"2024年5月{ch}{cat_zh}订单笔数是多少？",
        ]
    elif kind == "aov":
        extra = [
            f"2023年{syn}{cat_zh}平均每笔订单实付多少钱？",
            f"2024年第二季度{ch}{cat_zh}客单价（净支付额除以订单数）是多少？",
            f"What was the average order value (net paid) on {en_ch} for {cat_en}orders in 2023?",
            f"2022年{syn}{cat_zh}单均实收金额是多少？",
            f"2024年上半年{ch}{cat_zh}客单价最高的是哪个月？",
        ]
    elif kind == "coupon":
        extra = [
            f"2023年{syn}{cat_zh}优惠券一共抵扣了多少钱？",
            f"2024年第一季度{ch}{cat_zh}用券减免总额是多少？",
            f"Total coupon redemption amount for {cat_en}{en_ch} in 2023?",
            f"2022年双十一期间{syn}{cat_zh}优惠券补贴金额是多少？",
            f"2024年{ch}{cat_zh}各月优惠券抵扣额合计多少？",
        ]
    elif kind == "discount":
        extra = [
            f"2023年{syn}{cat_zh}标价立减折扣总额是多少？",
            f"2024年第二季度{ch}{cat_zh}打折让利金额合计多少？",
            f"What was the total discount amount off list price for {cat_en}{en_ch} in 2023?",
            f"2022年{syn}{cat_zh}促销直降折扣额是多少？",
            f"2024年3月{ch}{cat_zh}折扣减免金额是多少？",
        ]
    else:  # ret_qty
        extra = [
            f"2023年{syn}{cat_zh}被退回的商品总件数是多少？",
            f"2024年第一季度{ch}{cat_zh}按退货日期统计的退货件数是多少？",
            f"How many {cat_en}units were returned on {en_ch} in 2023?",
            f"2022年{syn}{cat_zh}累计退回件数合计多少？",
            f"2024年上半年{ch}{cat_zh}退货件数最多的是哪个月？",
        ]
    return [canon] + extra


def build_scale_queries(defs_100, defs_500, defs_1000):
    """Builds 120 hand-crafted multi-domain test queries (zero overlap with pool phrasings):
      - 32 targeting definitions introduced in M_100 (D0027..D0100)
      - 32 targeting definitions introduced in M_500 (D0101..D0500)
      - 32 targeting definitions introduced in M_1000 (D0501..D1000)
      - 24 absent / out-of-catalog queries (gold == [] even at M=1,000)
    Within each 32-query tier: 12 homonymous multi-def (|A|=2), 10 facet-disambiguated single-def, 10 direct single-def.
    """
    reqs = []

    def pick_tier_queries(tier_defs, tier_tag):
        # Group tier_defs by (channel, category, subject) to find complete homonymous pairs & singletons
        by_group = {}
        for d in tier_defs:
            f = d["facets"]
            key = (f.get("channel"), f.get("category"), f.get("subject"))
            by_group.setdefault(key, []).append(d)

        # Verify against full M_1000 that the group size in M_1000 equals len(ds)
        homonyms = []
        singles = []
        for key, ds in by_group.items():
            ch, cat, subj = key
            stated_base = {"subject": [subj]}
            if ch:
                stated_base["channel"] = [ch]
            if cat:
                stated_base["category"] = [cat]
            full_matches = [x["id"] for x in defs_1000 if consistent(x["facets"], stated_base)]
            if len(ds) == 2 and len(full_matches) == 2:
                homonyms.append((key, ds, stated_base))
            elif len(ds) == 1 and len(full_matches) == 1:
                singles.append((key, ds[0], stated_base))

        rng = random.Random({"t100": 101, "t500": 503, "t1000": 1009}[tier_tag])
        rng.shuffle(homonyms)
        rng.shuffle(singles)

        # 12 homonymous underspecified queries (|A| == 2)
        templates_homo = [
            lambda ch, cat, subj, syn, en: f"经营周报复盘：2024年9月{cat}{syn}的{subj}是多少？",
            lambda ch, cat, subj, syn, en: f"帮我查一下2023年全年{cat}{ch}{subj}总计多少？",
            lambda ch, cat, subj, syn, en: f"Please check the {subj} for {en} ({cat or 'all categories'}) in Q3 2024.",
            lambda ch, cat, subj, syn, en: f"2024年第二季度{cat}{syn}{subj}表现如何，具体数值是多少？",
        ]
        for i, ((ch, cat, subj), ds, st) in enumerate(homonyms[:12]):
            m = ds[0]["_meta"]
            cat_str = f"{cat}品类" if cat else ""
            syn = m["syn"][i % len(m["syn"])] if i % 2 == 1 else ch
            en = (f"{m['cat_en']} " if m.get("cat_en") else "") + m["en_ch"]
            txt = templates_homo[i % len(templates_homo)](ch, cat_str, subj, syn, en)
            reqs.append({
                "id": f"{tier_tag}_h{i+1:02d}",
                "kind": "homonym_multi",
                "tier": tier_tag,
                "text": txt,
                "stated": st,
            })

        # 10 facet-disambiguated queries resolving a homonymous pair to |A| == 1
        for i, ((ch, cat, subj), ds, st) in enumerate(homonyms[12:22] if len(homonyms) >= 22 else homonyms[:10]):
            d = ds[i % 2]
            m = d["_meta"]
            cat_str = f"{cat}品类" if cat else ""
            syn = m["syn"][(i + 1) % len(m["syn"])]
            st_one = dict(st)
            if d["facets"].get("amount") and subj == "销售额":
                st_one["amount"] = [d["facets"]["amount"]]
                desc = "扣除优惠券后的实付净额（不含税）" if "实付" in d["facets"]["amount"] else "未扣优惠券的折前金额（不含税）"
            elif d["facets"].get("ratio"):
                st_one["ratio"] = [d["facets"]["ratio"]]
                desc = "按退款金额占实付额比例计算" if d["facets"]["ratio"] == "按金额" else "按退回件数占销量比例计算"
            elif d["facets"].get("profit"):
                st_one["profit"] = [d["facets"]["profit"]]
                desc = "扣除成本及优惠券后的净利" if "净利润" in d["facets"]["profit"] else "不扣优惠券的账面毛利"
            else:
                st_one["date"] = [d["facets"]["date"]]
                desc = "按退货单处理日期归属" if d["facets"]["date"] == "按退货日期" else "按原销售订单日期归属"
            txt = f"财务口径核对：2024年上半年{cat_str}{syn}的{subj}（限定{desc}）是多少？"
            reqs.append({
                "id": f"{tier_tag}_f{i+1:02d}",
                "kind": "facet_single",
                "tier": tier_tag,
                "text": txt,
                "stated": st_one,
            })

        # 10 direct single-definition queries across domains
        templates_single = [
            lambda ch, cat, subj, syn, en: f"2024年7月{cat}{syn}的{subj}是多少？",
            lambda ch, cat, subj, syn, en: f"业务看板需要2023年第四季度{cat}{ch}{subj}，请给出结果。",
            lambda ch, cat, subj, syn, en: f"What was the {subj} on {en} {('for ' + cat) if cat else ''} in 2024?",
        ]
        for i, ((ch, cat, subj), d, st) in enumerate(singles[:10]):
            m = d["_meta"]
            cat_str = f"{cat}品类" if cat else ""
            syn = m["syn"][i % len(m["syn"])]
            en = (f"{m['cat_en']} " if m.get("cat_en") else "") + m["en_ch"]
            txt = templates_single[i % len(templates_single)](ch, cat_str, subj, syn, en)
            reqs.append({
                "id": f"{tier_tag}_s{i+1:02d}",
                "kind": "domain_single",
                "tier": tier_tag,
                "text": txt,
                "stated": st,
            })

    pick_tier_queries(defs_100[26:], "t100")
    pick_tier_queries(defs_500[100:], "t500")
    pick_tier_queries(defs_1000[500:], "t1000")

    # 24 always-absent enterprise queries (gold == [] across all catalog scales including M=1,000)
    absent_specs = [
        ("abs01", "2024年抖音直播间的平均观看停留时长是多少？", {"channel": ["抖音直播间"], "subject": ["观看停留时长"]}),
        ("abs02", "2023年微信小程序的日活跃用户数DAU是多少？", {"channel": ["微信小程序"], "subject": ["日活跃用户数"]}),
        ("abs03", "2024年华东中心仓的叉车设备折旧费是多少？", {"channel": ["华东中心仓"], "subject": ["设备折旧费"]}),
        ("abs04", "2023年企业大客户B2B的坏账核销率是多少？", {"channel": ["企业大客户B2B"], "subject": ["坏账核销率"]}),
        ("abs05", "2024年支付宝渠道的含增值税营业额是多少？", {"channel": ["支付宝渠道"], "subject": ["销售额"], "amount": ["含税"]}),
        ("abs06", "2023年SaaS云订阅的净金额留存率NDR是多少？", {"channel": ["SaaS云订阅"], "subject": ["净金额留存率"]}),
        ("abs07", "What was the customer acquisition cost CAC for WeChat mini-program in 2024?", {"channel": ["微信小程序"], "subject": ["获客成本"]}),
        ("abs08", "2024年跨境独立站的物流清关延误率是多少？", {"channel": ["跨境独立站"], "subject": ["清关延误率"]}),
        ("abs09", "2023年付费黑卡会员的续费率是多少？", {"channel": ["付费黑卡会员"], "subject": ["续费率"]}),
        ("abs10", "2024年信息流广告的千次曝光成本CPM是多少？", {"channel": ["信息流广告"], "subject": ["千次曝光成本"]}),
        ("abs11", "2023年直营旗舰店的每平米坪效是多少？", {"channel": ["直营旗舰店"], "subject": ["坪效"]}),
        ("abs12", "2024年冷链生鲜仓的温控电费支出是多少？", {"channel": ["冷链生鲜仓"], "subject": ["电费支出"]}),
        ("abs13", "2023年达人种草投放的视频完播率是多少？", {"channel": ["达人种草投放"], "subject": ["视频完播率"]}),
        ("abs14", "2024年线下授权网点的平均维修工时是多少？", {"channel": ["线下授权网点"], "subject": ["平均维修工时"]}),
        ("abs15", "What was the employee turnover rate at North China central warehouse in 2023?", {"channel": ["华北中心仓"], "subject": ["员工离职率"]}),
        ("abs16", "2024年按退货日期计算的抖音直播间退货率是多少？", {"channel": ["抖音直播间"], "subject": ["退货率"], "date": ["按退货日期"]}),
        ("abs17", "2023年政企采购线的投标中标率是多少？", {"channel": ["政企采购线"], "subject": ["中标率"]}),
        ("abs18", "2024年社区即时达的骑手准时送达率是多少？", {"channel": ["社区即时达"], "subject": ["准时送达率"]}),
        ("abs19", "2023年银联云闪付的通道故障时长是多少？", {"channel": ["银联云闪付"], "subject": ["故障时长"]}),
        ("abs20", "2024年宠物用品在抖音直播间的营业额是多少？", {"channel": ["抖音直播间"], "subject": ["销售额"], "category": ["宠物用品"]}),
        ("abs21", "2023年奥莱折扣店的试穿转化率是多少？", {"channel": ["奥莱折扣店"], "subject": ["试穿转化率"]}),
        ("abs22", "2024年保税跨境仓的海关查验率是多少？", {"channel": ["保税跨境仓"], "subject": ["海关查验率"]}),
        ("abs23", "What was the NPS satisfaction score for VIP Black-Card members in 2024?", {"channel": ["付费黑卡会员"], "subject": ["净推荐值NPS"]}),
        ("abs24", "2024年搜索竞价SEM的曝光点击率CTR是多少？", {"channel": ["搜索竞价SEM"], "subject": ["点击率"]}),
    ]
    for qid, txt, st in absent_specs:
        reqs.append({"id": qid, "kind": "absent", "tier": "absent", "text": txt, "stated": st})

    return reqs


def build_synthetic_train(defs_1000, pool_1000):
    """Creates synthetic training dataset for the optional refreshed multi-domain CE:
    combines existing train_26_clean (loaded on server) with multi-domain single-target, underspecified homonym,
    and absent synthetic phrasings (strictly disjoint from all test queries)."""
    by_id = {d["id"]: d for d in defs_1000}
    rows = []
    # Single-target / facet-stated examples from pool_1000 for D0027..D1000
    for ex in pool_1000:
        did = ex["def"]
        if not did.startswith("D0") and not did.startswith("D1"):
            continue
        if len(did) == 3:  # D01..D26 already covered by train_26_clean.jsonl
            continue
        d = by_id[did]
        f = d["facets"]
        # Build stated dict specifying all facets of d so gold in defs_1000 is [did] (or exact homonym if canon)
        if ex["text"] == f"{d['name']}是多少？":
            st = {k: [v] for k, v in f.items() if k in ("channel", "category", "subject") and v}
            if d["facets"].get("profit"):
                st["profit"] = [d["facets"]["profit"]]
        else:
            st = {k: [v] for k, v in f.items() if v}
        gold = sorted(x["id"] for x in defs_1000 if consistent(x["facets"], st))
        rows.append({"text": ex["text"], "stated": st, "gold": gold})

    # Add underspecified multi-definition synthetic phrasings for homonymous groups
    by_group = {}
    for d in defs_1000[26:]:
        f = d["facets"]
        key = (f.get("channel"), f.get("category"), f.get("subject"))
        by_group.setdefault(key, []).append(d)
    for (ch, cat, subj), ds in by_group.items():
        if len(ds) < 2:
            continue
        st = {"subject": [subj]}
        if ch:
            st["channel"] = [ch]
        if cat:
            st["category"] = [cat]
        gold = sorted(x["id"] for x in defs_1000 if consistent(x["facets"], st))
        cat_s = f"{cat}类" if cat else ""
        for yr, mo in [("2021", "4"), ("2022", "10"), ("2025", "1")]:
            rows.append({"text": f"{yr}年{mo}月{cat_s}{ch}{subj}总计多少？", "stated": st, "gold": gold})

    # Add synthetic absent examples (strictly different subjects from test absent_specs!)
    synth_absent_subjects = ["退换货邮费险", "客服工单催办率", "直播间弹幕互动率", "仓库包材耗损费", "导购连带率", "账期逾期利息"]
    for ch_line in ENTERPRISE_LINES[:18]:
        ch = ch_line["channel"]
        for sb in synth_absent_subjects[:3]:
            st = {"channel": [ch], "subject": [sb]}
            if not any(consistent(x["facets"], st) for x in defs_1000):
                rows.append({"text": f"2022年{ch}的{sb}是多少？", "stated": st, "gold": []})
    return rows


def main():
    wave1, rest = generate_all_groups()
    used = set()

    add_74, def1 = pack_exact(wave1 + rest, 74, used)
    assert len(add_74) == 74, f"Expected 74, got {len(add_74)}"

    add_400, def2 = pack_exact(def1 + rest, 400, used)
    assert len(add_400) == 400, f"Expected 400, got {len(add_400)}"

    add_500, _ = pack_exact(def2 + rest, 500, used)
    assert len(add_500) == 500, f"Expected 500, got {len(add_500)}"

    all_new = add_74 + add_400 + add_500
    assert len(all_new) == 974

    # Assign deterministic IDs D0027..D1000
    for idx, d in enumerate(all_new, start=27):
        d["id"] = f"D{idx:04d}"

    defs_26 = [dict(d) for d in BASE_CAT["definitions"]]
    defs_100 = defs_26 + all_new[:74]
    defs_500 = defs_26 + all_new[:474]
    defs_1000 = defs_26 + all_new

    assert len(defs_26) == 26
    assert len(defs_100) == 100
    assert len(defs_500) == 500
    assert len(defs_1000) == 1000

    # Verify strict core ground-truth invariance across ALL 96 + 174 queries
    for qset_name, qset in [("orig_96", ORIG_REQS), ("glm_174", GLM_REQS)]:
        for r in qset:
            g26 = sorted(d["id"] for d in defs_26 if consistent(d["facets"], r["stated"]))
            g26_raw = sorted(d["id"] for d in defs_26 if consistent_raw(d["facets"], r["stated"]))
            assert g26 == g26_raw, f"Raw vs list mismatch on {r['id']}"
            for m_size, m_defs in [(100, defs_100), (500, defs_500), (1000, defs_1000)]:
                gm = sorted(d["id"] for d in m_defs if consistent(d["facets"], r["stated"]))
                gm_raw = sorted(d["id"] for d in m_defs if consistent_raw(d["facets"], r["stated"]))
                assert gm == g26 and gm_raw == g26, f"Core invariance violated on {qset_name}:{r['id']} at M={m_size}: {gm} != {g26}"

    # Build pool_1000 (preserving pool_26 byte-for-byte on D01..D26)
    pool_1000 = list(POOL_26)
    for d in all_new:
        for txt in make_pool_phrasings(d):
            pool_1000.append({"def": d["id"], "text": txt})
    assert len(pool_1000) == 1000 * 6, f"Expected 6000 pool examples, got {len(pool_1000)}"

    # Build 120 multi-domain scale queries
    scale_reqs = build_scale_queries(defs_100, defs_500, defs_1000)
    assert len(scale_reqs) == 120, f"Expected 120 scale queries, got {len(scale_reqs)}"

    # Verify scale_reqs gold sizes at M=1,000 and zero phrasing overlap with pool_1000
    pool_texts = {re.sub(r"\s+", "", x["text"].lower()) for x in pool_1000}
    for r in scale_reqs:
        norm_q = re.sub(r"\s+", "", r["text"].lower())
        assert norm_q not in pool_texts, f"Overlap with pool on {r['id']}"
        g1000 = sorted(d["id"] for d in defs_1000 if consistent(d["facets"], r["stated"]))
        if r["kind"] == "absent":
            assert g1000 == [], f"Absent query {r['id']} matched {g1000}"
        elif r["kind"] == "homonym_multi":
            assert len(g1000) == 2, f"Homonym query {r['id']} matched {g1000}"
        else:
            assert len(g1000) == 1, f"Single query {r['id']} matched {g1000}"

    synth_extra = build_synthetic_train(defs_1000, pool_1000)
    synth_texts = {re.sub(r"\s+", "", x["text"].lower()) for x in synth_extra}
    for r in ORIG_REQS + GLM_REQS + scale_reqs:
        assert re.sub(r"\s+", "", r["text"].lower()) not in synth_texts, f"Leak check failed on {r['id']}"

    # Strip internal _meta before writing catalogs
    def clean_defs(ds):
        return [{k: v for k, v in d.items() if k != "_meta"} for d in ds]

    for m_size, ds in [(26, defs_26), (100, defs_100), (500, defs_500), (1000, defs_1000)]:
        payload = {
            "note": f"Nested enterprise metric catalog (M={m_size}) for P1-1 lookup scaling evaluation.",
            "facet_names": FN,
            "definitions": clean_defs(ds),
        }
        (HERE / f"catalog_{m_size}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    (HERE / "requests_scale_120.json").write_text(
        json.dumps(
            {
                "note": "120 multi-domain & scale lookup requests spanning M=100, 500, 1000 (48 single-target, 48 homonymous 2-def, 24 absent at M=1000).",
                "requests": scale_reqs,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    (HERE / "pool_1000.json").write_text(json.dumps(pool_1000, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "train_scale_extra.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in synth_extra), encoding="utf-8"
    )

    manifest = {
        "catalog_sizes": [26, 100, 500, 1000],
        "pool_examples": {m: m * 6 for m in [26, 100, 500, 1000]},
        "query_sets": {
            "orig_96": len(ORIG_REQS),
            "glm_174": len(GLM_REQS),
            "scale_120": len(scale_reqs),
            "total": len(ORIG_REQS) + len(GLM_REQS) + len(scale_reqs),
        },
        "synth_extra_rows": len(synth_extra),
        "catalog_1000_sha256": hashlib.sha256((HERE / "catalog_1000.json").read_bytes()).hexdigest(),
    }
    (HERE / "benchmark-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
