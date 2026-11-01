//! 验证检查：每种检查 = 一条 SQL + 一个判定。检查结果本身也作为知识共享。

use crate::db::Rows;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

/// 关联列对：(左表列, 右表列)
pub type On = Vec<(String, String)>;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(tag = "type")]
pub enum Check {
    /// 键唯一性：`table` 在 `cols` 上是否唯一（可带行过滤）。关联时“一侧”必须唯一，否则会膨胀。
    KeyUnique { table: String, cols: Vec<String>, filter: Option<String> },
    /// 抽样扇出：取左表若干行，按键去右表找匹配，看是否一行匹配多行。便宜，适合先查。
    SampleFanout { left: String, right: String, on: On, lf: Option<String>, rf: Option<String>, n: u32 },
    /// 行数守恒：关联后行数与左表行数对比（发现膨胀，并量化丢行）。
    RowConservation { left: String, right: String, on: On, lf: Option<String>, rf: Option<String> },
    /// 日期键连续：日期维度按（年, 月）分组后，每组的键恰好是 [min, max] 内的全部整数，且相邻月份首尾相接。
    /// 成立时任一期间的日期键集合就是一个整数区间，期间谓词可以写成事实表日期键的范围过滤，不必连接维度表。
    DateKeysContiguous { dim: String, key: String, year_col: String, month_col: String },
    /// 日期列完整性：没有日期维度时，日期列为空的行归不到任何期间；返回有日期的行占比，由调用方与准入基线比较。
    DateCoverage { table: String, col: String },
    /// 雪花型连接的完整性，按事实行计：从事实表出发、沿路径 `path`（每段为 左表, 右表, 关联列）的前几段内连接到达最后一段的
    /// 左表的事实行中，关联不上最后一段右表的行所占比例。只看中间维表的行会低估遗漏：一个热门商品失去类别，只占商品表一行，
    /// 却可能是大半事实。返回到达的事实行数与其中关联得上的行数，由调用方与准入基线比较。
    PathCoverage { fact: String, path: Vec<(String, String, On)> },
    /// 日期键两种编码下的覆盖：事实表日期键按维度键或其另一种编码 `alias`（维度列上的表达式，如 yyyymmdd）关联得上的行占比。
    /// 日期键修复后的定义以它代替维度键的覆盖条件。
    KeyAliasCoverage { fact: String, fact_col: String, dim: String, dim_col: String, alias: String },
    /// 日期键两种编码合起来仍唯一：维度键与另一种编码的取值互不重叠，各自唯一，任一事实键至多对应一个日期。
    KeyAliasUnique { dim: String, dim_col: String, alias: String },
    /// 去除完全重复的行后键唯一：`table` 中满足过滤、在 `cols` 上重复的每个键，其各行在所有列上都相同。
    /// 成立时 `select distinct *` 后每键恰好一行（去重修复后的粒度条件）；没有重复键时也成立。
    DistinctKeyUnique { table: String, cols: Vec<String>, filter: Option<String> },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Outcome {
    pub pass: bool,
    pub metrics: Value,
    pub ms: f64,
}

impl Check {
    pub fn kind(&self) -> &'static str {
        match self {
            Check::KeyUnique { .. } => "KeyUnique",
            Check::SampleFanout { .. } => "SampleFanout",
            Check::RowConservation { .. } => "RowConservation",
            Check::DateKeysContiguous { .. } => "DateKeysContiguous",
            Check::DateCoverage { .. } => "DateCoverage",
            Check::PathCoverage { .. } => "PathCoverage",
            Check::KeyAliasCoverage { .. } => "KeyAliasCoverage",
            Check::KeyAliasUnique { .. } => "KeyAliasUnique",
            Check::DistinctKeyUnique { .. } => "DistinctKeyUnique",
        }
    }

    pub fn key(&self) -> String {
        serde_json::to_string(self).unwrap_or_default()
    }

    pub fn tables(&self) -> Vec<String> {
        match self {
            Check::KeyUnique { table, .. } | Check::DistinctKeyUnique { table, .. } => vec![table.clone()],
            Check::DateKeysContiguous { dim, .. } => vec![dim.clone()],
            Check::DateCoverage { table, .. } => vec![table.clone()],
            Check::PathCoverage { fact, path } => {
                let mut t = vec![fact.clone()];
                for (_, r, _) in path {
                    t.push(r.clone());
                }
                t
            }
            Check::SampleFanout { left, right, .. } | Check::RowConservation { left, right, .. } => {
                vec![left.clone(), right.clone()]
            }
            Check::KeyAliasCoverage { fact, dim, .. } => vec![fact.clone(), dim.clone()],
            Check::KeyAliasUnique { dim, .. } => vec![dim.clone()],
        }
    }

    /// 反馈统计的上下文：键唯一性看被检查的表，另两种看关联方向（左表>右表）。
    pub fn context(&self) -> String {
        match self {
            Check::KeyUnique { table, cols, .. } => format!("{table}({})", cols.join(",")),
            Check::DistinctKeyUnique { table, cols, .. } => format!("{table}({}) distinct", cols.join(",")),
            Check::DateKeysContiguous { dim, key, .. } => format!("{dim}({key})"),
            Check::DateCoverage { table, col } => format!("{table}({col})"),
            Check::PathCoverage { fact, path } => {
                format!("{fact}>{}", path.iter().map(|(_, r, on)| format!("{r}:{}", fmt_on(on))).collect::<Vec<_>>().join(">"))
            }
            Check::SampleFanout { left, right, on, .. } | Check::RowConservation { left, right, on, .. } => {
                format!("{left}>{right}:{}", fmt_on(on))
            }
            Check::KeyAliasCoverage { fact, fact_col, dim, dim_col, alias } => format!("{fact}.{fact_col}>{dim}({dim_col}|{alias})"),
            Check::KeyAliasUnique { dim, dim_col, alias } => format!("{dim}({dim_col}|{alias})"),
        }
    }

    /// 本检查大致要扫的行数（给反馈模块估代价用）。
    pub fn rows_touched(&self, rows: &dyn Fn(&str) -> f64) -> f64 {
        match self {
            Check::KeyUnique { table, cols, .. } => rows(table) * (1.0 + 0.5 * (cols.len() as f64 - 1.0)),
            Check::DistinctKeyUnique { table, cols, .. } => rows(table) * (1.5 + 0.5 * (cols.len() as f64 - 1.0)),
            Check::DateKeysContiguous { dim, .. } => rows(dim),
            Check::DateCoverage { table, .. } => rows(table),
            Check::PathCoverage { fact, path } => rows(fact) * (1.0 + path.len() as f64),
            Check::SampleFanout { right, .. } => rows(right),
            Check::RowConservation { left, right, .. } => rows(left) * 2.0 + rows(right),
            Check::KeyAliasCoverage { fact, dim, .. } => rows(fact) + 2.0 * rows(dim),
            Check::KeyAliasUnique { dim, .. } => 2.0 * rows(dim),
        }
    }

    pub fn describe(&self) -> String {
        match self {
            Check::KeyUnique { table, cols, filter } => {
                format!("{table}({}) 是否唯一{}", cols.join(", "), filter.as_ref().map(|f| format!(" [过滤 {f}]")).unwrap_or_default())
            }
            Check::DistinctKeyUnique { table, cols, filter } => format!(
                "{table}({}) 去除完全重复的行后是否唯一{}",
                cols.join(", "),
                filter.as_ref().map(|f| format!(" [过滤 {f}]")).unwrap_or_default()
            ),
            Check::DateKeysContiguous { dim, key, .. } => format!("{dim}({key}) 日期键是否按月连续"),
            Check::DateCoverage { table, col } => format!("{table}.{col} 有日期的行占比"),
            Check::PathCoverage { fact, path } => {
                format!("{fact} 的行经 {} 关联得上的占比", path.iter().map(|(_, r, _)| r.as_str()).collect::<Vec<_>>().join(" → "))
            }
            Check::SampleFanout { left, right, on, .. } => format!("抽样：{left}→{right} 按 {} 是否一对多", fmt_on(on)),
            Check::RowConservation { left, right, on, .. } => {
                format!("行数守恒：{left}⋈{right} 按 {} 后行数是否超过 {left}", fmt_on(on))
            }
            Check::KeyAliasCoverage { fact, fact_col, dim, dim_col, alias } => {
                format!("{fact}.{fact_col} 按 {dim}.{dim_col} 或 {alias} 关联得上的占比")
            }
            Check::KeyAliasUnique { dim, dim_col, alias } => format!("{dim} 的 {dim_col} 与 {alias} 合起来是否唯一"),
        }
    }

    pub fn sql(&self) -> String {
        match self {
            Check::KeyUnique { table, cols, filter } => {
                // 按键分组计数：与 count(distinct (键列)) 等价（键列都不为空），可以用哈希聚合，大表上快得多
                format!(
                    "select coalesce(sum(c), 0)::bigint as n_rows, count(*) as n_keys from \
                     (select count(*) as c from {table} where {} group by {}) g",
                    key_conds(cols, filter),
                    cols.join(", ")
                )
            }
            Check::DistinctKeyUnique { table, cols, filter } => {
                // 只看重复的键：这些键上去除完全相同的行之后的行数，与重复键数比较
                let keys = cols.join(", ");
                let wf = filter.as_ref().map(|f| format!(" where ({f})")).unwrap_or_default();
                format!(
                    "with d as (select {keys} from {table} where {} group by {keys} having count(*) > 1) \
                     select (select count(*) from (select distinct {table}.* from {table} join d using ({keys}){wf}) x) as n_rows, \
                            (select count(*) from d) as n_keys",
                    key_conds(cols, filter)
                )
            }
            Check::DateKeysContiguous { dim, key, year_col, month_col } => format!(
                "with m as (select {year_col} as y, {month_col} as mo, count(*) as c, min({key}) as mn, max({key}) as mx \
                 from {dim} where {key} is not null group by 1, 2), \
                 s as (select c, mn, mx, lag(mx) over (order by y, mo) as prev_mx from m) \
                 select count(*) filter (where c <> mx - mn + 1 or (prev_mx is not null and mn <> prev_mx + 1)) as n_bad, \
                        count(*) as n_months from s"
            ),
            Check::DateCoverage { table, col } => format!("select count(*) as n_rows, count({col}) as n_dated from {table}"),
            Check::PathCoverage { fact, path } => {
                // 前几段内连接到达最后一段的左表，最后一段左连接；右表在关联列上唯一（连接基数条件），每个事实行至多一行
                let mut from = fact.clone();
                for (k, (l, r, on)) in path.iter().enumerate() {
                    let kw = if k + 1 == path.len() { "left join" } else { "join" };
                    let conds: Vec<String> = on.iter().map(|(a, b)| format!("{l}.{a} = {r}.{b}")).collect();
                    from.push_str(&format!(" {kw} {r} on {}", conds.join(" and ")));
                }
                let (_, last, on) = path.last().expect("路径至少一段");
                let probe = on.first().map(|(_, b)| format!("{last}.{b}")).unwrap_or_else(|| "null".into());
                format!("select count(*) as n_left, count({probe}) as n_join from {from}")
            }
            Check::SampleFanout { left, right, on, lf, rf, n } => {
                let lcols: Vec<&str> = on.iter().map(|(l, _)| l.as_str()).collect();
                let mut lconds: Vec<String> = lcols.iter().map(|c| format!("{c} is not null")).collect();
                if let Some(f) = lf {
                    lconds.push(format!("({f})"));
                }
                let mut jconds: Vec<String> = on.iter().map(|(l, r)| format!("{right}.{r} = s.{l}")).collect();
                if let Some(f) = rf {
                    jconds.push(format!("({f})"));
                }
                format!(
                    "with s as (select {cols} from {left} where {lc} limit {n}) \
                     select count(*) as n_sample, coalesce(max(m), 0) as max_mult, coalesce(avg(m), 0) as avg_mult, \
                            count(*) filter (where m > 1) as n_fanned \
                     from s cross join lateral (select count(*) as m from {right} where {jc}) t",
                    cols = lcols.join(", "),
                    lc = lconds.join(" and "),
                    jc = jconds.join(" and "),
                )
            }
            Check::RowConservation { left, right, on, lf, rf } => {
                // 过滤在各自表的子查询里求值，过滤可以写成 表.列，也可以引用两表重名的列
                let wl = lf.as_ref().map(|f| format!(" where {f}")).unwrap_or_default();
                let wr = rf.as_ref().map(|f| format!(" where {f}")).unwrap_or_default();
                let side = |t: &str, w: &str| if w.is_empty() { t.to_string() } else { format!("(select * from {t}{w})") };
                let conds: Vec<String> = on.iter().map(|(l, r)| format!("l.{l} = r.{r}")).collect();
                format!(
                    "select (select count(*) from {left}{wl}) as n_left, (select count(*) from {right}{wr}) as n_right, \
                            (select count(*) from {} l join {} r on {}) as n_join",
                    side(left, &wl),
                    side(right, &wr),
                    conds.join(" and ")
                )
            }
            Check::KeyAliasCoverage { fact, fact_col, dim, dim_col, alias } => format!(
                "select count(*) as n_left, count(k.k) as n_join from {fact} \
                 left join (select {dim}.{dim_col} as k from {dim} union select {alias} as k from {dim}) k on {fact}.{fact_col} = k.k"
            ),
            Check::KeyAliasUnique { dim, dim_col, alias } => format!(
                "select count(*) as n_rows, count(distinct k) as n_keys from \
                 (select {dim}.{dim_col} as k from {dim} union all select {alias} as k from {dim}) u where k is not null"
            ),
        }
    }

    pub fn eval(&self, rows: &Rows, ms: f64) -> Outcome {
        match self {
            Check::KeyUnique { .. } | Check::KeyAliasUnique { .. } | Check::DistinctKeyUnique { .. } => {
                let (n_rows, n_keys) = (rows.i64(0, 0).unwrap_or(0), rows.i64(0, 1).unwrap_or(0));
                let avg = if n_keys > 0 { n_rows as f64 / n_keys as f64 } else { 0.0 };
                Outcome { pass: n_rows == n_keys, metrics: json!({"n_rows": n_rows, "n_keys": n_keys, "avg_mult": avg}), ms }
            }
            Check::DateKeysContiguous { .. } => {
                let (n_bad, n_months) = (rows.i64(0, 0).unwrap_or(0), rows.i64(0, 1).unwrap_or(0));
                Outcome { pass: n_bad == 0, metrics: json!({"n_bad": n_bad, "n_months": n_months}), ms }
            }
            Check::PathCoverage { .. } | Check::KeyAliasCoverage { .. } => {
                let (n_left, n_join) = (rows.i64(0, 0).unwrap_or(0), rows.i64(0, 1).unwrap_or(0));
                let ratio = if n_left > 0 { n_join as f64 / n_left as f64 } else { 1.0 };
                Outcome { pass: true, metrics: json!({"n_left": n_left, "n_join": n_join, "join_ratio": ratio}), ms }
            }
            Check::DateCoverage { .. } => {
                let (n_rows, n_dated) = (rows.i64(0, 0).unwrap_or(0), rows.i64(0, 1).unwrap_or(0));
                let ratio = if n_rows > 0 { n_dated as f64 / n_rows as f64 } else { 1.0 };
                Outcome { pass: true, metrics: json!({"n_rows": n_rows, "n_dated": n_dated, "join_ratio": ratio}), ms }
            }
            Check::SampleFanout { .. } => {
                let max_mult = rows.i64(0, 1).unwrap_or(0);
                Outcome {
                    pass: max_mult <= 1,
                    metrics: json!({
                        "n_sample": rows.i64(0, 0).unwrap_or(0),
                        "max_mult": max_mult,
                        "avg_mult": rows.f64(0, 2).unwrap_or(0.0),
                        "n_fanned": rows.i64(0, 3).unwrap_or(0),
                    }),
                    ms,
                }
            }
            Check::RowConservation { .. } => {
                let (n_left, n_right, n_join) = (rows.i64(0, 0).unwrap_or(0), rows.i64(0, 1).unwrap_or(0), rows.i64(0, 2).unwrap_or(0));
                let ratio = if n_left > 0 { n_join as f64 / n_left as f64 } else { 0.0 };
                Outcome {
                    pass: n_join <= n_left,
                    metrics: json!({"n_left": n_left, "n_right": n_right, "n_join": n_join, "join_ratio": ratio}),
                    ms,
                }
            }
        }
    }
}

/// 键唯一性检查统计的行：键列都不为空且满足过滤。
fn key_conds(cols: &[String], filter: &Option<String>) -> String {
    let mut conds: Vec<String> = cols.iter().map(|c| format!("{c} is not null")).collect();
    if let Some(f) = filter {
        conds.push(format!("({f})"));
    }
    conds.join(" and ")
}

pub fn fmt_on(on: &On) -> String {
    let s: Vec<String> = on.iter().map(|(l, r)| format!("{l}={r}")).collect();
    format!("({})", s.join(", "))
}

/// 按列集合（不看顺序与方向）比较两个关联是否相同。
pub fn same_on(a: &On, b: &On) -> bool {
    let norm = |o: &On| {
        let mut v: Vec<(String, String)> =
            o.iter().map(|(l, r)| if l <= r { (l.clone(), r.clone()) } else { (r.clone(), l.clone()) }).collect();
        v.sort();
        v
    };
    norm(a) == norm(b)
}

pub fn flip(on: &On) -> On {
    on.iter().map(|(l, r)| (r.clone(), l.clone())).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_coverage_counts_fact_rows_along_the_chain() {
        let c = Check::PathCoverage {
            fact: "lineitem".into(),
            path: vec![
                ("lineitem".into(), "orders".into(), vec![("l_orderkey".into(), "o_orderkey".into())]),
                ("orders".into(), "customer".into(), vec![("o_custkey".into(), "c_custkey".into())]),
            ],
        };
        let sql = c.sql();
        assert_eq!(
            sql,
            "select count(*) as n_left, count(customer.c_custkey) as n_join from lineitem \
             join orders on lineitem.l_orderkey = orders.o_orderkey left join customer on orders.o_custkey = customer.c_custkey"
        );
        assert_eq!(c.tables(), vec!["lineitem".to_string(), "orders".to_string(), "customer".to_string()]);
    }

    #[test]
    fn key_uniqueness_counts_groups_of_non_null_filtered_rows() {
        let cols = vec!["l_linenumber".to_string(), "l_orderkey".to_string()];
        let k = Check::KeyUnique { table: "lineitem".into(), cols: cols.clone(), filter: Some("is_current = 1".into()) };
        assert_eq!(
            k.sql(),
            "select coalesce(sum(c), 0)::bigint as n_rows, count(*) as n_keys from \
             (select count(*) as c from lineitem where l_linenumber is not null and l_orderkey is not null and (is_current = 1) \
             group by l_linenumber, l_orderkey) g"
        );
        let d = Check::DistinctKeyUnique { table: "lineitem".into(), cols, filter: None };
        assert_eq!(
            d.sql(),
            "with d as (select l_linenumber, l_orderkey from lineitem where l_linenumber is not null and l_orderkey is not null \
             group by l_linenumber, l_orderkey having count(*) > 1) \
             select (select count(*) from (select distinct lineitem.* from lineitem join d using (l_linenumber, l_orderkey)) x) as n_rows, \
                    (select count(*) from d) as n_keys"
        );
        assert_eq!(d.tables(), vec!["lineitem".to_string()]);
    }
}
