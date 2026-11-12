//! 已发布定义在未见参数上的准确率（C1，不调用 LLM）。取场景评测各 MAVRA 族组的 `metric_report`，按定义内容去重后，
//! 在初始数据上把每个定义编译到 2000–2002 年的 36 个单月与 3 个全年（39 个参数），与基准手写的标准答案比较。
//! G7 拒绝的草稿同样评估：没有 G7 时它们会被发布，这里量出它们会在多少参数上答错（反事实）。
//! G7 只检验学习题的一个参数；本评测回答“通过门槛的定义在其他参数上还会错多少”。

use crate::db::{Db, QKind};
use crate::etl;
use crate::knowledge::Metric;
use crate::metric::{self, parse_answer, same_value, Ask, Period};
use crate::metricbench;
use crate::scenario;
use anyhow::{Context, Result};
use futures::StreamExt;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug, clap::Args, Serialize)]
pub struct Options {
    /// 场景评测的结果目录（递归查找 mode 以 metric-global 开头的 cell-*.json）
    #[arg(long, value_delimiter = ',', required = true)]
    cells: Vec<String>,
    /// 门店销售行数（与场景评测相同）
    #[arg(long, default_value_t = 1_000_000)]
    rows: u32,
    /// 并发查询数
    #[arg(long, default_value_t = 8)]
    parallel: usize,
}

fn find(path: &Path, out: &mut Vec<String>) -> Result<()> {
    if path.is_dir() {
        let mut items: Vec<_> = std::fs::read_dir(path)?.filter_map(|e| e.ok().map(|e| e.path())).collect();
        items.sort();
        for p in items {
            if p.is_dir() {
                find(&p, out)?;
            } else if p.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.starts_with("cell-") && n.ends_with(".json")) {
                out.push(p.to_string_lossy().into_owned());
            }
        }
    }
    Ok(())
}

/// 定义的计算内容（去掉名称、说明、示例与基线），用于去重。
fn content_key(m: &Metric) -> String {
    let mut v = serde_json::to_value(m).unwrap_or_default();
    if let Some(o) = v.as_object_mut() {
        for k in ["name", "aliases", "definition", "caveats", "examples", "basis", "null_base", "scale_base"] {
            o.remove(k);
        }
        if let Some(t) = o.get_mut("time").and_then(Value::as_object_mut) {
            t.remove("loss_ratio");
            t.remove("role");
        }
        if let Some(js) = o.get_mut("joins").and_then(Value::as_array_mut) {
            for j in js.iter_mut().filter_map(Value::as_object_mut) {
                for k in ["key", "cardinality", "loss_ratio", "orphan_ratio", "revision"] {
                    j.remove(k);
                }
            }
        }
    }
    v.to_string()
}

struct Item {
    def: String,
    class: &'static str,
    metric: Metric,
    sessions: usize,
    cells: Vec<String>,
    reasons: Vec<String>,
}

pub async fn run(url: &str, out: &str, o: Options) -> Result<()> {
    let mut files = vec![];
    for c in &o.cells {
        find(Path::new(c), &mut files)?;
    }
    let mut items: BTreeMap<(String, String), Item> = BTreeMap::new();
    let mut cells = 0;
    for f in &files {
        let d: Value = serde_json::from_str(&std::fs::read_to_string(f)?).with_context(|| format!("读取 {f}"))?;
        if !d["mode"].as_str().is_some_and(|m| m.starts_with("metric-global")) {
            continue;
        }
        cells += 1;
        for e in d["metric_report"]["entries"].as_array().into_iter().flatten() {
            let class = match &e["status"] {
                Value::String(s) if s == "Valid" => "published",
                Value::Object(c) if c.get("Candidate").and_then(Value::as_str).is_some_and(|r| r.starts_with("G7")) => "g7_rejected",
                _ => continue,
            };
            let Some(def) = e["evidence"]["task"].as_str().and_then(|t| t.split('-').next()).map(str::to_string) else { continue };
            let Ok(m) = serde_json::from_value::<Metric>(e["metric"].clone()) else { continue };
            let key = (class.to_string(), format!("{def}|{}", content_key(&m)));
            let it = items.entry(key).or_insert_with(|| Item { def, class, metric: m, sessions: 0, cells: vec![], reasons: vec![] });
            it.sessions += 1;
            it.cells.push(f.clone());
            if let Some(r) = e["status"]["Candidate"].as_str() {
                it.reasons.push(r.to_string());
            }
        }
    }
    eprintln!(
        "组 {cells} 个；不同定义：发布 {}，G7 拒绝 {}",
        items.keys().filter(|k| k.0 == "published").count(),
        items.keys().filter(|k| k.0 == "g7_rejected").count()
    );

    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros();
    let name = format!("agentdb_binding_{}_{stamp}", std::process::id());
    let root = Db::connect(url, 1, false)?;
    let mut isolated = reqwest::Url::parse(url)?;
    isolated.set_path(&format!("/{name}"));
    root.query(QKind::Meta, &format!("create database {name}")).await?;
    let result: Result<Value> = async {
        let admin = Db::connect(isolated.as_str(), 2, false)?;
        eprintln!("生成合成零售数据：门店销售 {} 行", o.rows);
        admin.query(QKind::Meta, &metricbench::fixture(o.rows)).await?;
        etl::setup(&admin).await?;
        scenario::setup(&admin).await?;
        let probe = Db::connect(isolated.as_str(), o.parallel.max(1), true)?;
        let bindings: Vec<Period> = (2000..=2002)
            .flat_map(|y| (1..=12).map(move |m| Period::month(y, m)).chain(std::iter::once(Period { year: y, m1: 1, m2: 12 })))
            .collect();
        let defs: Vec<String> = {
            let mut v: Vec<String> = items.values().map(|i| i.def.clone()).collect();
            v.sort();
            v.dedup();
            v
        };
        let run = |sql: String| {
            let probe = &probe;
            async move {
                match probe.query(QKind::Meta, &sql).await {
                    Ok(r) => r.cell(0, 0).unwrap_or("NULL").to_string(),
                    Err(e) => format!("ERROR: {e:#}"),
                }
            }
        };
        let mut gold: BTreeMap<(String, usize), String> = BTreeMap::new();
        for d in &defs {
            for (bi, p) in bindings.iter().enumerate() {
                gold.insert((d.clone(), bi), run(metricbench::gold_period(d, p)).await);
            }
        }
        let mut per_item = vec![];
        for it in items.values() {
            let jobs = bindings.iter().enumerate().map(|(bi, p)| {
                let ask = Ask::Single { period: *p };
                let sql = metric::compile(&it.metric, &ask);
                let run = &run;
                async move {
                    let v = match sql {
                        Ok(s) => run(s).await,
                        Err(e) => format!("ERROR: {e:#}"),
                    };
                    (bi, v)
                }
            });
            let values: Vec<(usize, String)> = futures::stream::iter(jobs).buffer_unordered(o.parallel.max(1)).collect().await;
            let mut wrong = vec![];
            for (bi, v) in &values {
                let g = &gold[&(it.def.clone(), *bi)];
                let ask = Ask::Single { period: bindings[*bi] };
                if !same_value(&parse_answer(v), &parse_answer(g), metricbench::decimals(&ask)) {
                    wrong.push(json!({"period": bindings[*bi], "value": v, "gold": g}));
                }
            }
            per_item.push(json!({
                "def": it.def, "class": it.class, "sessions": it.sessions, "bindings": bindings.len(), "wrong": wrong.len(),
                "wrong_examples": wrong.iter().take(4).collect::<Vec<_>>(), "reasons": it.reasons, "metric": it.metric,
                "cells": it.cells,
            }));
        }
        let summary = |class: &str| {
            let xs: Vec<&Value> = per_item.iter().filter(|x| x["class"] == class).collect();
            let n = xs.len();
            let exact = xs.iter().filter(|x| x["wrong"] == 0).count();
            let sessions: u64 = xs.iter().map(|x| x["sessions"].as_u64().unwrap_or(0)).sum();
            let exact_sessions: u64 = xs.iter().filter(|x| x["wrong"] == 0).map(|x| x["sessions"].as_u64().unwrap_or(0)).sum();
            let wrong_b: u64 = xs.iter().map(|x| x["wrong"].as_u64().unwrap_or(0)).sum();
            json!({"definitions": n, "exact_all_bindings": exact, "sessions": sessions, "sessions_exact": exact_sessions,
                   "binding_checks": n * bindings.len(), "binding_wrong": wrong_b})
        };
        Ok(json!({"cells": cells, "rows": o.rows, "bindings": bindings, "published": summary("published"),
                  "g7_rejected": summary("g7_rejected"), "items": per_item}))
    }
    .await;
    let cleanup = root.query(QKind::Meta, &format!("drop database {name} with (force)")).await;
    let report = result?;
    cleanup?;
    std::fs::create_dir_all(out)?;
    let path = format!("{out}/binding-{stamp}.json");
    std::fs::write(&path, serde_json::to_string_pretty(&report)?)?;
    eprintln!("发布：{}；G7 拒绝：{}；报告 {path}", report["published"], report["g7_rejected"]);
    Ok(())
}
