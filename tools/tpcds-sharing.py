#!/usr/bin/env python3
"""Measure natural data-condition sharing across official TPC-DS SQL templates.

Usage: python3 tools/tpcds-sharing.py --templates DIR --schema tpcds.sql [--json OUT]
Requires: pglast (`pip install -r tools/requirements.txt`).
"""

import argparse
import collections
import json
import os
import re
import sys

try:
    from pglast import parse_sql
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency pglast: pip install -r tools/requirements.txt")

FACTS = {"store_sales", "store_returns", "catalog_sales", "catalog_returns", "web_sales", "web_returns", "inventory"}
AGGS = {"sum", "avg", "count", "min", "max", "stddev_samp", "stddev", "var_samp", "variance"}


def load_schema(path):
    """表 → (列集合, 主键)。"""
    text = open(path, encoding="utf-8").read()
    tables = {}
    for m in re.finditer(r"create table (\w+)\s*\((.*?)\n\);", text, re.S | re.I):
        name, body = m.group(1).lower(), m.group(2)
        cols = [c.lower() for c in re.findall(r"^\s*(\w+)\s+(?:integer|char|varchar|date|time|decimal|int)", body, re.M | re.I)]
        pk = re.search(r"primary key\s*\(([^)]*)\)", body, re.I)
        tables[name] = (set(cols), tuple(sorted(c.strip().lower() for c in pk.group(1).split(","))) if pk else ())
    return tables


def instantiate(tpl):
    """把模板参数换成能解析的占位值：text({...}) 取第一个选项，其余取 1；LIMIT 方言占位换成标准写法。"""
    defs = {}
    for m in re.finditer(r"define\s+(\w+)\s*=\s*(.*?);", tpl, re.I | re.S):
        name, expr = m.group(1).upper(), m.group(2)
        t = re.search(r'text\(\s*\{\s*"([^"]+)"', expr)
        defs[name] = t.group(1) if t else "1"
    body = re.sub(r"^\s*define\s+.*?;\s*$", "", tpl, flags=re.I | re.M | re.S)
    body = re.sub(r"--.*", "", body)
    body = body.replace("[_LIMITA]", "").replace("[_LIMITB]", "").replace("[_LIMITC]", "limit 100")

    def sub(m):
        key = m.group(1).upper().split(".")[0]
        return defs.get(key, "1")

    body = re.sub(r"\[([A-Za-z_][A-Za-z0-9_.]*)\]", sub, body)
    # TPC-DS 的 “+ 30 days” 不是 PostgreSQL 语法
    body = re.sub(r"(\d+)\s+days\b", r"interval '\1 days'", body, flags=re.I)
    return body


def walk(x):
    """遍历 pglast 字典树中的全部节点。"""
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from walk(v)


def walk_block(x, top=True):
    """遍历一个 SELECT 块自身的节点，不进入嵌套的 SELECT（嵌套块单独处理）。"""
    if isinstance(x, dict):
        if not top and x.get("@") == "SelectStmt":
            return
        yield x
        for v in x.values():
            yield from walk_block(v, False)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from walk_block(v, False)


def colref(node, aliases, schema_cols):
    """ColumnRef → (表, 列)；只解析到基表列。"""
    fields = [f.get("sval") for f in node.get("fields", ()) if isinstance(f, dict) and f.get("@") == "String"]
    if not fields:
        return None
    col = fields[-1].lower()
    if len(fields) >= 2:
        t = aliases.get(fields[-2].lower())
        if t and col in schema_cols.get(t, ()):
            return (t, col)
        return None
    owners = [t for t in aliases.values() if col in schema_cols.get(t, ())]
    return (owners[0], col) if len(set(owners)) == 1 else None


def block_definitions(sel, schema, qid, bid):
    schema_cols = {t: c for t, (c, _) in schema.items()}
    aliases = {}
    for n in walk_block(sel.get("fromClause", ())):
        if n.get("@") == "RangeVar" and n.get("relname", "").lower() in schema:
            t = n["relname"].lower()
            a = (n.get("alias") or {}).get("aliasname", t).lower()
            aliases[a] = t
    if not aliases:
        return []
    facts = sorted({t for t in aliases.values() if t in FACTS})
    if not facts:
        return []
    # 等值连接：WHERE 与 JOIN ... ON
    pairs = collections.defaultdict(set)  # (F, T) -> {(fcol, tcol)}
    for n in walk_block([sel.get("whereClause"), sel.get("fromClause", ())]):
        if n.get("@") != "A_Expr":
            continue
        op = [x.get("sval") for x in n.get("name", ()) if isinstance(x, dict)]
        l, r = n.get("lexpr"), n.get("rexpr")
        if op != ["="] or not (isinstance(l, dict) and isinstance(r, dict)) or l.get("@") != "ColumnRef" or r.get("@") != "ColumnRef":
            continue
        a, b = colref(l, aliases, schema_cols), colref(r, aliases, schema_cols)
        if not a or not b or a[0] == b[0]:
            continue
        for (ft, fc), (tt, tc) in ((a, b), (b, a)):
            if ft in FACTS:
                pairs[(ft, tt)].add((fc, tc))
    # 聚合所读的事实表列
    agg_facts = set()
    star = False
    for n in walk_block([sel.get("targetList", ()), sel.get("havingClause"), sel.get("sortClause", ())]):
        if n.get("@") != "FuncCall":
            continue
        name = [x.get("sval") for x in n.get("funcname", ()) if isinstance(x, dict)][-1:]
        if not name or name[0].lower() not in AGGS:
            continue
        if n.get("agg_star"):
            star = True
        for m in walk(n.get("args", ())):
            if m.get("@") == "ColumnRef":
                c = colref(m, aliases, schema_cols)
                if c and c[0] in FACTS:
                    agg_facts.add(c[0])
    if star and len(facts) == 1:
        agg_facts.add(facts[0])
    out = []
    for f in sorted(agg_facts):
        conds = {("grain", (f,), schema[f][1])}
        for (ft, tt), cols in pairs.items():
            if ft != f:
                continue
            cols = tuple(sorted(cols))
            if tt == "date_dim":
                for fc, _ in cols:
                    conds.add(("time", (f, "date_dim"), (fc,)))
            elif tt in FACTS:
                key = tuple(sorted({tuple(sorted(p)) for p in cols}))
                conds.add(("factjoin", tuple(sorted((f, tt))), key))
            else:
                conds.add(("join", (f, tt), cols))
        out.append({"query": qid, "block": bid, "fact": f, "conditions": sorted(conds)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--json", default=None)
    o = ap.parse_args()
    schema = load_schema(o.schema)
    defs, failed = [], []
    files = sorted((f for f in os.listdir(o.templates) if f.endswith(".tpl")), key=lambda f: int(re.sub(r"\D", "", f)))
    for f in files:
        qid = f[:-4]
        sql = instantiate(open(os.path.join(o.templates, f), encoding="utf-8", errors="replace").read())
        try:
            stmts = parse_sql(sql)
        except Exception as e:  # 记录无法解析的模板，不静默丢弃
            failed.append({"query": qid, "error": str(e)[:200]})
            continue
        bid = 0
        for st in stmts:
            tree = st.stmt(skip_none=True)
            for n in walk(tree):
                if n.get("@") == "SelectStmt" and n.get("fromClause"):
                    defs += block_definitions(n, schema, qid, bid)
                    bid += 1
    inst = [c for d in defs for c in d["conditions"]]
    distinct = sorted(set(inst))
    uses = collections.Counter(inst)
    per_table = {}
    for x in sorted({t for c in distinct for t in c[1]}):
        affected = [d for d in defs if any(x in c[1] for c in d["conditions"])]
        per_table[x] = {
            "affected_definitions": len(affected),
            "definition_level_checks": sum(len(d["conditions"]) for d in affected),
            "condition_level_checks": len({c for c in distinct if x in c[1]}),
        }
    shared = sum(1 for c in distinct if uses[c] >= 2)
    res = {
        "templates": len(files),
        "parse_failures": failed,
        "queries_with_definitions": len({d["query"] for d in defs}),
        "definitions": len(defs),
        "condition_instances": len(inst),
        "distinct_conditions": len(distinct),
        "instances_per_distinct": round(len(inst) / len(distinct), 2) if distinct else None,
        "distinct_shared_by_2plus": shared,
        "instances_on_shared_conditions_pct": round(100 * sum(uses[c] for c in distinct if uses[c] >= 2) / len(inst), 1) if inst else None,
        "by_type": {t: {"instances": sum(1 for c in inst if c[0] == t), "distinct": sum(1 for c in distinct if c[0] == t)}
                    for t in ("grain", "time", "join", "factjoin")},
        "top_conditions": [{"condition": list(map(str, c)), "definitions": n} for c, n in uses.most_common(12)],
        "per_table_update": per_table,
        "definitions_list": [{"query": d["query"], "block": d["block"], "fact": d["fact"], "conditions": [list(map(str, c)) for c in d["conditions"]]} for d in defs],
    }
    if o.json:
        json.dump(res, open(o.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    show = {k: v for k, v in res.items() if k not in ("definitions_list",)}
    print(json.dumps(show, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
