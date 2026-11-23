//! Opt-in Q5 PostgreSQL mechanism and scaling benchmarks (LLM-free).
//!
//! Run all Q5 benchmarks directly from HEAD:
//!   cargo test --release --locked q5_bench_tests:: -- --ignored --nocapture --test-threads=1
//! Or run a single benchmark:
//!   SV_QUICK=1 cargo test --release --locked q5_bench_tests::postgres_shared_validation_scaling -- --ignored --nocapture

use crate::db::{Db, QKind};
use crate::integration_tests::seeded_metrics;
use crate::knowledge::Metric;
use crate::metric::{self, Ask, Period};
use crate::middle::{Checkpoint, Ctx, Maint, Middle, MiddleConfig};
use crate::scenario::{self, Change};
use crate::{catalog, etl, metricbench};
use anyhow::{ensure, Context, Result};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const SV_PAIRS: usize = 4;
const SV_DEFS: usize = 16;
const SV_OFFSET: i64 = 1_000_000_000;

const DUP_INJECT: &str = "insert into store_sales select s.* from store_sales s join date_dim d on s.ss_sold_date_sk = d.d_date_sk \
                          where d.d_date between date '2002-06-01' and date '2002-09-30'";
const DUP_RESET: &str = "delete from store_sales a using store_sales b \
                         where a.ss_ticket_number = b.ss_ticket_number and a.ss_item_sk = b.ss_item_sk and a.ctid > b.ctid";
const SNAP_TABLES: [&str; 4] = ["store_sales", "store_returns", "date_dim", "item"];

async fn run_q5_report<F, Fut>(label: &str, out_prefix: &str, seconds: u64, run: F) -> Result<()>
where
    F: FnOnce(String, String) -> Fut,
    Fut: std::future::Future<Output = Result<Value>> + Send + 'static,
{
    let _ = dotenvy::dotenv();
    let url = crate::resolve_env("MAVRA_TEST_DB_URL", "AGENTDB_TEST_URL").context("MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) required")?;
    let admin = Db::connect(&url, 1, false)?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros();
    let name = format!("mavra_{label}_{}_{stamp}", std::process::id());
    let mut test_url = reqwest::Url::parse(&url)?;
    test_url.set_path(&format!("/{name}"));
    let out = format!("results/{out_prefix}-{stamp}");
    std::fs::create_dir_all(&out)?;
    admin.query(QKind::Meta, &format!("create database {name}")).await.context("failed to create isolated Q5 database")?;
    let mut task = tokio::spawn(run(test_url.to_string(), out.clone()));
    let result = tokio::time::timeout(Duration::from_secs(seconds), &mut task).await;
    if result.is_err() {
        task.abort();
        let _ = task.await;
    }
    let cleanup = admin.query(QKind::Meta, &format!("drop database {name} with (force)")).await;
    let payload = match &result {
        Ok(Ok(Ok(v))) => json!({"status": "passed", "report": v, "cleaned_up": cleanup.is_ok()}),
        Ok(Ok(Err(e))) => json!({"status": "failed", "error": format!("{e:#}"), "cleaned_up": cleanup.is_ok()}),
        Ok(Err(e)) => json!({"status": "failed", "error": format!("panicked: {e}"), "cleaned_up": cleanup.is_ok()}),
        Err(_) => json!({"status": "failed", "error": "timeout", "cleaned_up": cleanup.is_ok()}),
    };
    std::fs::write(format!("{out}/report.json"), serde_json::to_string_pretty(&payload)?)?;
    eprintln!("Q5 report written to {out}/report.json (cleaned_up={})", cleanup.is_ok());
    cleanup.context("Q5 database cleanup failed")?;
    let _ = result.context("Q5 benchmark timed out")?.context("Q5 benchmark panicked")??;
    Ok(())
}

// ───────────────────────── 1. Backup-Table Repair Ambiguity (Q5 / Section 6.6) ─────────────────────────

fn with_returns_filter(id: &str, m: &Metric, f: &str) -> Metric {
    let mut m = m.clone();
    if id == "M2" {
        m.filters.insert("store_returns".into(), f.into());
    } else if let Some(j) = m.joins.iter_mut().find(|j| j.right == "store_returns") {
        j.filters.insert("store_returns".into(), f.into());
    }
    m
}

async fn repair_ambiguity(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    let rows = crate::resolve_env("MAVRA_SCENARIO_ROWS", "AGENTDB_SCENARIO_ROWS").and_then(|v| v.parse().ok()).unwrap_or(200_000);
    admin.query(QKind::Meta, &metricbench::fixture(rows)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    let v1 = scenario::fingerprint(&admin).await?;
    let ch = Change::Mirror;
    let learn = Period::month(2001, 3);
    let asks = [
        Ask::Single { period: Period::month(2002, 9) },
        Ask::Single { period: Period::month(2002, 5) },
        Ask::RankMonth { year: 2002 },
        Ask::Single { period: Period::month(2001, 6) },
    ];
    let gold = |id: &str, a: &Ask| match a {
        Ask::Single { period } => metricbench::gold_period(id, period),
        Ask::RankMonth { year } => metricbench::gold_rank(id, *year),
        _ => unreachable!(),
    };
    let returns: Vec<(&str, Metric)> = seeded_metrics().into_iter().filter(|(id, _)| matches!(*id, "M2" | "M3")).collect();
    let answer = |sql: String| {
        let admin = &admin;
        async move { Ok::<_, anyhow::Error>(admin.query(QKind::Meta, &sql).await?.cell(0, 0).unwrap_or("NULL").to_string()) }
    };
    let same = |a: &Ask, x: &str, y: &str| {
        let dec = if matches!(a, Ask::RankMonth { .. }) { 0 } else { 2 };
        metric::same_value(&metric::parse_answer(x), &metric::parse_answer(y), dec)
    };
    let mut runs = vec![];
    for maint in [Maint::Condition, Maint::Definition] {
        let db = Arc::new(Db::connect(url, 4, true)?);
        let cfg = MiddleConfig {
            name: maint.name().into(),
            version_ttl_ms: 0,
            metric_maint: maint,
            cond_reuse: maint == Maint::Condition,
            ..Default::default()
        };
        let mid = Middle::new(db, cfg).await?;
        let seed = Ctx::new("A", "seed", "seed");
        for (id, m) in &returns {
            let v = mid.seed_metric(&seed, m.clone(), Ask::Single { period: learn }, 2, &metricbench::gold_period(id, &learn)).await?;
            ensure!(v["promoted"] == true, "{id} failed admission: {v}");
        }
        ch.apply_truth(&admin).await?;
        let mut expect = BTreeMap::new();
        for (id, _) in &returns {
            for (i, a) in asks.iter().enumerate() {
                expect.insert((*id, i), answer(gold(id, a)).await?);
            }
        }
        ch.apply_hidden(&admin).await?;
        mid.invalidate_versions();
        let ctx = Ctx::new("B", ch.name(), "use");
        let mut served = vec![];
        for (id, m) in &returns {
            let v = mid.use_metric(&ctx, &format!("metric:{}", m.name)).await?;
            let mut answers = vec![];
            if v["status"] == "valid" {
                let got: Metric = serde_json::from_value(v["metric"].clone())?;
                for (i, a) in asks.iter().enumerate() {
                    let value = answer(metric::compile(&got, a)?).await?;
                    answers.push(json!({"ask": a, "value": value, "gold": expect[&(*id, i)], "ok": same(a, &value, &expect[&(*id, i)])}));
                }
                served.push(json!({"metric": id, "status": "valid", "revision": v["revision"], "filters": got.filters,
                                   "join_filters": got.joins.iter().map(|j| &j.filters).collect::<Vec<_>>(), "answers": answers}));
            } else {
                served.push(json!({"metric": id, "status": v["status"]}));
            }
        }
        runs.push(json!({"maint": maint.name(), "served": served, "events": mid.take_metric_events()}));
        ch.reset(&admin).await?;
        scenario::ensure_v1(&admin, &v1, ch.name()).await?;
    }
    ch.apply_truth(&admin).await?;
    let mut expect = BTreeMap::new();
    for (id, _) in &returns {
        for (i, a) in asks.iter().enumerate() {
            expect.insert((*id, i), answer(gold(id, a)).await?);
        }
    }
    ch.apply_hidden(&admin).await?;
    let total = answer("select count(distinct (sr_ticket_number, sr_item_sk)) from store_returns".into()).await?;
    let mut candidates = vec![];
    for v in ["primary", "backup"] {
        let f = format!("sr_source = '{v}'");
        let r = admin
            .query(QKind::Meta, &format!("select count(*), count(distinct (sr_ticket_number, sr_item_sk)) from store_returns where {f}"))
            .await?;
        let (n, k) = (r.cell(0, 0).unwrap_or("0").to_string(), r.cell(0, 1).unwrap_or("0").to_string());
        let mut per_metric = vec![];
        for (id, m) in &returns {
            let mm = with_returns_filter(id, m, &f);
            let g8_expect = answer(metricbench::gold_period(id, &learn)).await?;
            let g8_got = answer(metric::compile(&mm, &Ask::Single { period: learn })?).await?;
            let learn_ask = Ask::Single { period: learn };
            let mut new_asks = vec![];
            for (i, a) in asks.iter().enumerate() {
                let value = answer(metric::compile(&mm, a)?).await?;
                new_asks.push(json!({"ask": a, "value": value, "gold": expect[&(*id, i)], "ok": same(a, &value, &expect[&(*id, i)])}));
            }
            per_metric
                .push(json!({"metric": id, "g8": {"value": g8_got, "judge": g8_expect, "pass": same(&learn_ask, &g8_got, &g8_expect)},
                                   "asks": new_asks}));
        }
        candidates.push(json!({"filter": f, "rows": n, "keys": k, "total_keys": total, "repair_test_passes": n == k && k == total,
                               "metrics": per_metric}));
    }
    ch.reset(&admin).await?;
    scenario::ensure_v1(&admin, &v1, ch.name()).await?;
    let variant = repair_ambiguity_precolumn(url, &admin, &returns, learn, &asks).await?;
    Ok(json!({"rows": rows, "change": ch.describe(), "learn": learn, "runs": runs, "candidates": candidates,
              "precolumn_variant": variant}))
}

async fn repair_ambiguity_precolumn(url: &str, admin: &Db, returns: &[(&str, Metric)], learn: Period, asks: &[Ask]) -> Result<Value> {
    let answer =
        |sql: String| async move { Ok::<_, anyhow::Error>(admin.query(QKind::Meta, &sql).await?.cell(0, 0).unwrap_or("NULL").to_string()) };
    let same = |a: &Ask, x: &str, y: &str| {
        let dec = if matches!(a, Ask::RankMonth { .. }) { 0 } else { 2 };
        metric::same_value(&metric::parse_answer(x), &metric::parse_answer(y), dec)
    };
    let gold = |id: &str, a: &Ask| match a {
        Ask::Single { period } => metricbench::gold_period(id, period),
        Ask::RankMonth { year } => metricbench::gold_rank(id, *year),
        _ => unreachable!(),
    };
    let anticipated = |sql: String| sql.replace("r.sr_status = '完成'", "r.sr_status = '完成' and r.sr_source = 'primary'");
    admin
        .query(QKind::Meta, "alter table store_returns add column sr_source varchar(10) not null default 'primary'; analyze store_returns")
        .await?;
    let stored: BTreeMap<&str, String> = {
        let mut m = BTreeMap::new();
        for (id, _) in returns {
            m.insert(*id, answer(metricbench::gold_period(id, &learn)).await?);
        }
        m
    };
    let before =
        || async { Ok::<_, anyhow::Error>(crate::catalog::versions(admin).await?.get("store_returns").map(|v| v.dml).unwrap_or(0)) };
    let settle = |b: i64| async move {
        admin.query(QKind::Meta, "select pg_stat_force_next_flush(); analyze store_returns").await?;
        etl::wait_table_stats(admin, "store_returns", b).await
    };
    let apply = || async {
        let b = before().await?;
        admin
            .execute(
                "update store_returns set sr_return_amt = sr_return_amt - 1 where sr_ticket_number % 10 = 3 and sr_returned_date_sk >= 732",
            )
            .await?;
        settle(b).await
    };
    let hide = || async {
        let b = before().await?;
        admin
            .execute(
                "insert into store_returns (sr_returned_date_sk, sr_item_sk, sr_ticket_number, sr_return_quantity, sr_return_amt, \
                 sr_return_tax, sr_fee, sr_net_loss, sr_status, sr_source) \
                 select sr_returned_date_sk, sr_item_sk, sr_ticket_number, sr_return_quantity, \
                        sr_return_amt + case when sr_ticket_number % 10 = 3 and sr_returned_date_sk >= 732 then 1 else 0 end, \
                        sr_return_tax, sr_fee, sr_net_loss, sr_status, 'backup' from store_returns where sr_source = 'primary'",
            )
            .await?;
        settle(b).await
    };
    let undo = || async {
        let b = before().await?;
        admin.execute("delete from store_returns where sr_source = 'backup'").await?;
        admin
            .execute(
                "update store_returns set sr_return_amt = sr_return_amt + 1 where sr_ticket_number % 10 = 3 and sr_returned_date_sk >= 732",
            )
            .await?;
        settle(b).await
    };
    let mut runs = vec![];
    for ((oracle, use_anticipated), unique) in
        [("unanticipated", false), ("anticipated", true)].into_iter().flat_map(|o| [false, true].map(move |u| (o, u)))
    {
        let db = Arc::new(Db::connect(url, 4, true)?);
        let cfg = MiddleConfig {
            version_ttl_ms: 0,
            metric_maint: Maint::Condition,
            cond_reuse: true,
            repair_unique: unique,
            ..Default::default()
        };
        let mid = Middle::new(db, cfg).await?;
        let seed = Ctx::new("A", "seed", "seed");
        for (id, m) in returns {
            let judge = metricbench::gold_period(id, &learn);
            let judge = if use_anticipated { anticipated(judge) } else { judge };
            let v = mid.seed_metric(&seed, m.clone(), Ask::Single { period: learn }, 2, &judge).await?;
            ensure!(v["promoted"] == true, "{id} failed admission: {v}");
        }
        apply().await?;
        let mut expect = BTreeMap::new();
        for (id, _) in returns {
            for (i, a) in asks.iter().enumerate() {
                expect.insert((*id, i), answer(gold(id, a)).await?);
            }
        }
        hide().await?;
        mid.invalidate_versions();
        let ctx = Ctx::new("B", "mirror-pre", "use");
        let mut served = vec![];
        for (id, m) in returns {
            let v = mid.use_metric(&ctx, &format!("metric:{}", m.name)).await?;
            if v["status"] == "valid" {
                let got: Metric = serde_json::from_value(v["metric"].clone())?;
                let mut oks = vec![];
                for (i, a) in asks.iter().enumerate() {
                    let value = answer(metric::compile(&got, a)?).await?;
                    oks.push(same(a, &value, &expect[&(*id, i)]));
                }
                served.push(json!({"metric": id, "status": "valid", "revision": v["revision"], "filters": got.filters,
                                   "join_filters": got.joins.iter().map(|j| &j.filters).collect::<Vec<_>>(), "asks_ok": oks}));
            } else {
                served.push(json!({"metric": id, "status": v["status"]}));
            }
        }
        let events: Vec<Value> = mid.take_metric_events().into_iter().filter(|e| e["event"] != "maintenance").collect();
        runs.push(json!({"oracle": oracle, "repair_unique": unique, "served": served, "events": events}));
        undo().await?;
    }
    apply().await?;
    hide().await?;
    let mut candidates = vec![];
    for v in ["primary", "backup"] {
        let f = format!("sr_source = '{v}'");
        let mut per = vec![];
        for (id, m) in returns {
            let got = answer(metric::compile(&with_returns_filter(id, m, &f), &Ask::Single { period: learn })?).await?;
            let rerun = answer(metricbench::gold_period(id, &learn)).await?;
            let rerun_anticipated = answer(anticipated(metricbench::gold_period(id, &learn))).await?;
            let la = Ask::Single { period: learn };
            per.push(json!({"metric": id, "canonical": got,
                            "g8_unanticipated": same(&la, &got, &rerun), "g8_anticipated": same(&la, &got, &rerun_anticipated),
                            "g8_stored_answer": same(&la, &got, &stored[id])}));
        }
        candidates.push(json!({"filter": f, "metrics": per}));
    }
    undo().await?;
    admin.query(QKind::Meta, "alter table store_returns drop column sr_source; analyze store_returns").await?;
    Ok(json!({"runs": runs, "candidates": candidates}))
}

#[tokio::test]
#[ignore = "Q5 benchmark; requires MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_repair_ambiguity() -> Result<()> {
    run_q5_report("repair_amb", "repair-ambiguity", 3600, |url, _out| Box::pin(async move { repair_ambiguity(&url).await })).await
}

// ───────────────────────── 2. Snapshot Binding & 16-Shard Trigger Overhead (Q5 / Section 6.6) ─────────────────────────

fn classify(r: &Result<Value>) -> &'static str {
    match r {
        Err(_) => "error",
        Ok(v) if v.get("rejected").is_some() => "rejected",
        Ok(v) => match v["result"]["rows"][0][1].as_str().and_then(|d| d.parse::<i64>().ok()) {
            Some(0) => "served",
            Some(_) => "violation",
            None => "error",
        },
    }
}

fn summary(xs: &mut [f64]) -> Value {
    if xs.is_empty() {
        return json!({"n": 0});
    }
    xs.sort_by(|a, b| a.total_cmp(b));
    let q = |p: f64| xs[((xs.len() - 1) as f64 * p).round() as usize];
    json!({"n": xs.len(), "mean": xs.iter().sum::<f64>() / xs.len() as f64, "p50": q(0.5), "p95": q(0.95), "max": q(1.0)})
}

struct SnapBench {
    url: String,
    admin: Db,
    learn: Period,
}

struct SnapMid {
    mid: Middle,
    cp: Checkpoint,
    refs: Vec<(String, u32)>,
    canon: String,
    probe: String,
    probes: Vec<String>,
}

impl SnapBench {
    async fn middle(&self, snapshot: bool, pause_ms: u64) -> Result<SnapMid> {
        let db = Arc::new(Db::connect(&self.url, 8, true)?);
        let cfg = MiddleConfig {
            name: if snapshot { "snapshot" } else { "precheck" }.into(),
            metric_maint: Maint::Condition,
            cond_reuse: true,
            result_cache: false,
            snapshot_exec: snapshot,
            exec_pause_ms: pause_ms,
            ..Default::default()
        };
        let mid = Middle::new(db, cfg).await?;
        let m1 = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").map(|x| x.1).context("missing M1")?;
        let key = format!("metric:{}", m1.name);
        let v = mid
            .seed_metric(
                &Ctx::new("A", "seed", "seed"),
                m1,
                Ask::Single { period: self.learn },
                2,
                &metricbench::gold_period("M1", &self.learn),
            )
            .await?;
        ensure!(v["promoted"] == true, "M1 failed admission: {v}");
        let u = mid.use_metric(&Ctx::new("B", "snapshot", "use"), &key).await?;
        ensure!(u["status"] == "valid", "M1 unavailable: {u}");
        let m: Metric = serde_json::from_value(u["metric"].clone())?;
        let canon = metric::compile(&m, &Ask::Single { period: Period::month(2002, 7) })?;
        let wrap = |mo: u32| -> Result<String> {
            let c = metric::compile(&m, &Ask::Single { period: Period::month(2002, mo) })?;
            Ok(format!(
                "select ({}) as v, (select count(*) - count(distinct (s.ss_ticket_number, s.ss_item_sk)) from store_sales s \
                 join date_dim d on s.ss_sold_date_sk = d.d_date_sk where d.d_year = 2002 and d.d_moy = {mo}) as dup",
                c.trim().trim_end_matches(';')
            ))
        };
        let probe = wrap(7)?;
        let probes = (6..=9).map(wrap).collect::<Result<Vec<_>>>()?;
        let refs = vec![(key, u["revision"].as_u64().unwrap_or(0) as u32)];
        Ok(SnapMid { cp: mid.checkpoint(), mid, refs, canon, probe, probes })
    }

    async fn dml(&self) -> Result<i64> {
        Ok(catalog::versions(&self.admin).await?.get("store_sales").map(|v| v.dml).unwrap_or(0))
    }

    async fn inject_then_notify(&self, mid: &Middle) -> Result<()> {
        self.admin.execute(DUP_INJECT).await?;
        metricbench::log_batch(&self.admin, "store_sales", "duplicate load (snapshot benchmark)").await?;
        mid.invalidate_versions();
        Ok(())
    }

    async fn reset(&self, s: &SnapMid) -> Result<()> {
        let before = self.dml().await?;
        if self.admin.execute(DUP_RESET).await? > 0 {
            etl::wait_table_stats(&self.admin, "store_sales", before).await?;
        }
        self.admin.query(QKind::Meta, "vacuum analyze store_sales").await?;
        tokio::time::sleep(Duration::from_millis(1500)).await;
        s.mid.invalidate_versions();
        s.mid.restore(&s.cp).await?;
        let warm = s.mid.run_sql_with(&Ctx::new("W", "snapshot", "warm"), &s.probe, &s.refs).await;
        ensure!(classify(&warm) == "served", "warmup after reset must succeed on clean data: {warm:?}");
        Ok(())
    }

    async fn interleave(&self, snapshot: bool, case: &str, trials: usize) -> Result<Value> {
        let s = self.middle(snapshot, if case == "write_during_pause" { 2000 } else { 0 }).await?;
        let ctx = Ctx::new("B", "snapshot", "use");
        let mut counts: BTreeMap<&str, u32> = BTreeMap::new();
        let (mut samples, mut lat) = (vec![], vec![]);
        for i in 0..trials {
            let warm = s.mid.run_sql_with(&ctx, &s.probe, &s.refs).await;
            ensure!(classify(&warm) == "served", "trial {i} warmup must succeed on clean data: {warm:?}");
            let t = Instant::now();
            let r = match case {
                "write_during_pause" => {
                    let (r, w) = tokio::join!(s.mid.run_sql_with(&ctx, &s.probe, &s.refs), async {
                        tokio::time::sleep(Duration::from_millis(700)).await;
                        self.admin.execute(DUP_INJECT).await
                    });
                    w?;
                    r
                }
                "write_before_call" => {
                    self.admin.execute(DUP_INJECT).await?;
                    s.mid.run_sql_with(&ctx, &s.probe, &s.refs).await
                }
                _ => {
                    let before = self.dml().await?;
                    self.inject_then_notify(&s.mid).await?;
                    etl::wait_table_stats(&self.admin, "store_sales", before).await?;
                    s.mid.invalidate_versions();
                    s.mid.run_sql_with(&ctx, &s.probe, &s.refs).await
                }
            };
            lat.push(t.elapsed().as_secs_f64() * 1000.0);
            let c = classify(&r);
            *counts.entry(c).or_default() += 1;
            if i < 2 {
                let resp = match &r {
                    Ok(v) => v.clone(),
                    Err(e) => json!(format!("{e:#}")),
                };
                samples.push(json!({"class": c, "response": resp}));
            }
            self.reset(&s).await?;
        }
        Ok(json!({"mode": if snapshot { "snapshot" } else { "precheck" }, "case": case, "trials": trials, "counts": counts,
                  "latency_ms": summary(&mut lat), "stats": s.mid.stats_json(), "samples": samples}))
    }

    #[allow(clippy::too_many_arguments)]
    async fn stress(
        &self,
        snapshot: bool,
        notify: bool,
        distinct: bool,
        trials: usize,
        readers: usize,
        window_ms: u64,
        think_ms: u64,
        seed: u64,
    ) -> Result<Value> {
        use rand::{Rng, SeedableRng};
        let s = self.middle(snapshot, 0).await?;
        let mut rng = rand::rngs::StdRng::seed_from_u64(seed);
        let mut counts: BTreeMap<&str, u32> = BTreeMap::new();
        let (mut lat, mut after_commit, mut per_trial) = (vec![], vec![], vec![]);
        for _ in 0..trials {
            let at = rng.gen_range(300..window_ms - 300);
            let start = Instant::now();
            let reader = |k: usize| {
                let s = &s;
                async move {
                    let ctx = Ctx::new(&format!("R{k}"), "snapshot", "use");
                    let mut out = vec![];
                    while start.elapsed() < Duration::from_millis(window_ms) {
                        let t0 = start.elapsed().as_secs_f64() * 1000.0;
                        let probe = if distinct { &s.probes[k % s.probes.len()] } else { &s.probe };
                        let r = s.mid.run_sql_with(&ctx, probe, &s.refs).await;
                        out.push((classify(&r), t0, start.elapsed().as_secs_f64() * 1000.0));
                        tokio::time::sleep(Duration::from_millis(think_ms)).await;
                    }
                    out
                }
            };
            let writer = async {
                tokio::time::sleep(Duration::from_millis(at)).await;
                self.admin.execute(DUP_INJECT).await?;
                let committed = start.elapsed().as_secs_f64() * 1000.0;
                if notify {
                    metricbench::log_batch(&self.admin, "store_sales", "duplicate load (snapshot benchmark)").await?;
                    s.mid.invalidate_versions();
                }
                Ok::<_, anyhow::Error>((committed, start.elapsed().as_secs_f64() * 1000.0))
            };
            let (calls, w) = tokio::join!(futures::future::join_all((0..readers).map(reader)), writer);
            let (committed, notified) = w?;
            let mut trial: BTreeMap<&str, u32> = BTreeMap::new();
            for (c, t0, t1) in calls.into_iter().flatten() {
                *counts.entry(c).or_default() += 1;
                *trial.entry(c).or_default() += 1;
                lat.push(t1 - t0);
                if c == "violation" {
                    after_commit.push(t0 - committed);
                }
            }
            per_trial.push(json!({"commit_ms": committed, "notify_ms": notified, "counts": trial}));
            self.reset(&s).await?;
        }
        Ok(
            json!({"mode": if snapshot { "snapshot" } else { "precheck" }, "notify": notify, "distinct": distinct, "trials": trials, "readers": readers,
                  "window_ms": window_ms, "think_ms": think_ms, "counts": counts, "latency_ms": summary(&mut lat),
                  "violation_start_minus_commit_ms": summary(&mut after_commit), "per_trial": per_trial, "stats": s.mid.stats_json()}),
        )
    }

    async fn reader_overhead(&self, snapshot: bool, calls: usize, writes: usize) -> Result<Value> {
        self.admin.query(QKind::Meta, "vacuum analyze store_sales").await?;
        let s = self.middle(snapshot, 0).await?;
        let ctx = Ctx::new("B", "snapshot", "use");
        let ok = |r: &Result<Value>| r.as_ref().is_ok_and(|v| v.get("rejected").is_none() && v.get("result").is_some());
        for _ in 0..3 {
            let r = s.mid.run_sql_with(&ctx, &s.canon, &s.refs).await;
            ensure!(ok(&r), "warmup failed: {r:?}");
        }
        let mut steady = vec![];
        for _ in 0..calls {
            let t = Instant::now();
            let r = s.mid.run_sql_with(&ctx, &s.canon, &s.refs).await;
            ensure!(ok(&r), "steady-state call failed: {r:?}");
            steady.push(t.elapsed().as_secs_f64() * 1000.0);
        }
        let (mut first, mut second) = (vec![], vec![]);
        for _ in 0..writes {
            let before = self.dml().await?;
            self.admin
                .execute(
                    "update store_sales set ss_net_paid = ss_net_paid where (ss_ticket_number, ss_item_sk) = \
                     (select ss_ticket_number, ss_item_sk from store_sales order by ss_ticket_number, ss_item_sk limit 1)",
                )
                .await?;
            metricbench::log_batch(&self.admin, "store_sales", "benign write (snapshot benchmark)").await?;
            etl::wait_table_stats(&self.admin, "store_sales", before).await?;
            s.mid.invalidate_versions();
            for out in [&mut first, &mut second] {
                let t = Instant::now();
                let r = s.mid.run_sql_with(&ctx, &s.canon, &s.refs).await;
                ensure!(ok(&r), "post-write call failed: {r:?}");
                out.push(t.elapsed().as_secs_f64() * 1000.0);
            }
        }
        Ok(json!({"mode": if snapshot { "snapshot" } else { "precheck" }, "steady_ms": summary(&mut steady),
                  "first_after_write_ms": summary(&mut first), "second_after_write_ms": summary(&mut second), "stats": s.mid.stats_json()}))
    }

    async fn writer_overhead(&self, per_worker: usize) -> Result<Value> {
        let pool = Db::connect(&self.url, 32, false)?;
        pool.query(
            QKind::Meta,
            "drop table if exists bench_w; create table bench_w (id int primary key, x int not null default 0); \
             insert into bench_w (id) select g from generate_series(0, 31999) g",
        )
        .await?;
        let run = |workers: usize| {
            let pool = &pool;
            async move {
                let t = Instant::now();
                let jobs = (0..workers).map(|w| async move {
                    for i in 0..per_worker {
                        pool.execute(&format!("update bench_w set x = x + 1 where id = {}", w * 1000 + i % 1000)).await?;
                    }
                    Ok::<_, anyhow::Error>(())
                });
                for r in futures::future::join_all(jobs).await {
                    r?;
                }
                Ok::<_, anyhow::Error>((workers * per_worker) as f64 / t.elapsed().as_secs_f64())
            }
        };
        let mut out = vec![];
        for round in 0..3 {
            for shards in [0, 1, catalog::TX_SHARDS] {
                let trig = shards > 0;
                if trig {
                    catalog::install_tx_versions_sharded(&pool, &["bench_w"], shards).await?;
                } else {
                    pool.query(QKind::Meta, "drop trigger if exists mavra_bump on bench_w").await?;
                }
                let seq = run(1).await?;
                let conc = run(8).await?;
                let conc32 = run(32).await?;
                let t = Instant::now();
                for b in 0..20 {
                    pool.execute(&format!("update bench_w set x = x + 1 where id between {} and {}", (b % 8) * 1000, (b % 8) * 1000 + 999))
                        .await?;
                    pool.execute(&format!(
                        "insert into bench_w (id) select g from generate_series({lo}, {hi}) g; delete from bench_w where id between {lo} and {hi}",
                        lo = 100_000 + b * 10_000,
                        hi = 100_000 + b * 10_000 + 9_999
                    ))
                    .await?;
                }
                let bulk = t.elapsed().as_secs_f64() * 1000.0 / 60.0;
                out.push(json!({"round": round, "trigger": trig, "shards": shards, "sequential_stmt_per_s": seq,
                                "concurrent8_stmt_per_s": conc, "concurrent32_stmt_per_s": conc32, "bulk_ms_per_stmt": bulk}));
            }
        }
        pool.query(QKind::Meta, "drop table bench_w; delete from mavra_versions where table_name = 'bench_w'").await?;
        Ok(json!(out))
    }
}

async fn snapshot_binding_scaling(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    let rows = crate::resolve_env("MAVRA_SCENARIO_ROWS", "AGENTDB_SCENARIO_ROWS").and_then(|v| v.parse().ok()).unwrap_or(200_000);
    admin.query(QKind::Meta, &metricbench::fixture(rows)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    catalog::install_tx_versions(&admin, &SNAP_TABLES).await?;
    admin.query(QKind::Meta, "analyze").await?;
    let b = SnapBench { url: url.to_string(), admin, learn: Period::month(2001, 3) };
    let trials = crate::resolve_env("MAVRA_SNAP_TRIALS", "AGENTDB_SNAP_TRIALS").and_then(|v| v.parse().ok()).unwrap_or(10);
    let parts = crate::resolve_env("MAVRA_SNAP_PARTS", "AGENTDB_SNAP_PARTS").unwrap_or_else(|| "readers,writers,interleave,stress".into());
    let on = |p: &str| parts.split(',').any(|x| x.trim() == p);
    let mut readers = vec![];
    if on("readers") {
        for _ in 0..2 {
            for snapshot in [false, true] {
                readers.push(b.reader_overhead(snapshot, 40, trials).await?);
            }
        }
    }
    let writers = if on("writers") { b.writer_overhead(500).await? } else { json!([]) };
    let mut interleavings = vec![];
    if on("interleave") {
        for case in ["write_during_pause", "write_before_call", "write_notified"] {
            for snapshot in [false, true] {
                interleavings.push(b.interleave(snapshot, case, trials).await?);
            }
        }
    }
    let mut stress = vec![];
    if on("stress") {
        for distinct in [false, true] {
            for notify in [true, false] {
                for snapshot in [false, true] {
                    stress.push(b.stress(snapshot, notify, distinct, 2 * trials, 4, 3000, 10, 1002).await?);
                }
            }
        }
    }
    Ok(json!({"rows": rows, "trials": trials, "interleavings": interleavings, "stress": stress,
              "reader_overhead": readers, "writer_overhead": writers}))
}

#[tokio::test]
#[ignore = "Q5 benchmark; requires MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_snapshot_binding_scaling() -> Result<()> {
    run_q5_report("snap_scale", "snapshot-binding", 5400, |url, _out| Box::pin(async move { snapshot_binding_scaling(&url).await })).await
}

// ───────────────────────── 3. Shared Validation Scaling Across 1–32 Agents (Q5 / Fig. 9) ─────────────────────────

async fn sv_uses(mid: &Middle, keys: &[String], agent: usize, seed: u64) -> Result<usize> {
    use rand::{seq::SliceRandom, SeedableRng};
    let mut order = keys.to_vec();
    order.shuffle(&mut rand::rngs::StdRng::seed_from_u64(seed * 1000 + agent as u64));
    let ctx = Ctx::new(&format!("R{agent}"), "shared-validation", "use");
    let mut unavailable = 0;
    for key in order {
        if mid.use_metric(&ctx, &key).await?["status"] != "valid" {
            unavailable += 1;
        }
    }
    Ok(unavailable)
}

async fn sv_seed(mid: &Middle, base: &Metric) -> Result<Vec<String>> {
    let ctx = Ctx::new("admin", "shared-validation", "seed");
    let ask = Ask::Single { period: Period::month(2001, 3) };
    let mut keys = vec![];
    for i in 0..SV_DEFS {
        let p = i % SV_PAIRS;
        let mut m = base.clone();
        m.name = format!("net_paid_unit_{i}");
        m.definition = m.name.clone();
        m.fact = format!("sv_fact{p}");
        m.time.as_mut().expect("M1 has time spec").dim = format!("sv_date{p}");
        m.measure = format!("sum(ss_net_paid) * {}", i + 1);
        let gold = format!(
            "select ({}) * {}",
            metricbench::gold_period("M1", &Period::month(2001, 3))
                .replace("store_sales", &m.fact)
                .replace("date_dim", &format!("sv_date{p}"))
                .trim()
                .trim_end_matches(';'),
            i + 1
        );
        let r = mid.seed_metric(&ctx, m, ask.clone(), 2, &gold).await?;
        ensure!(r["promoted"] == true, "definition failed admission: {r}");
        keys.push(r["key"].as_str().unwrap_or_default().to_string());
    }
    sv_uses(mid, &keys, 0, 0).await?;
    Ok(keys)
}

async fn shared_validation(url: &str, out: &str) -> Result<Value> {
    use rand::{seq::SliceRandom, SeedableRng};
    let admin = Db::connect(url, 2, false)?;
    admin.query(QKind::Meta, &metricbench::fixture(200_000)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    for p in 0..SV_PAIRS {
        admin
            .query(
                QKind::Meta,
                &format!("create table sv_fact{p} as table store_sales; create table sv_date{p} as table date_dim; analyze sv_fact{p}; analyze sv_date{p}"),
            )
            .await?;
    }
    let base = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").context("missing M1")?.1;
    let quick = std::env::var_os("SV_QUICK").is_some();
    let agents_axis: Vec<usize> = if quick { vec![1, 4] } else { vec![1, 2, 4, 8, 16, 32] };
    let mut order = vec![];
    for rep in 0..(if quick { 1u64 } else { 3 }) {
        let mut block = vec![];
        for &n in agents_axis.iter() {
            for policy in ["per-agent", "full-recheck", "mavra"] {
                for arrival in ["staggered", "simultaneous"] {
                    block.push((rep, n, policy, arrival));
                }
            }
        }
        block.shuffle(&mut rand::rngs::StdRng::seed_from_u64(1101 + rep));
        order.extend(block);
    }
    std::fs::write(format!("{out}/order.json"), serde_json::to_string_pretty(&order)?)?;
    let sv_cols: Vec<String> = {
        let r = admin
            .query(
                QKind::Meta,
                "select column_name from information_schema.columns where table_name = 'store_sales' order by ordinal_position",
            )
            .await?;
        (0..r.rows.len()).filter_map(|i| r.cell(i, 0).map(str::to_string)).collect()
    };
    let mut cells = vec![];
    for (rep, n, policy, arrival) in order {
        for p in 0..SV_PAIRS {
            admin
                .query(
                    QKind::Meta,
                    &format!("delete from sv_fact{p} where ss_ticket_number >= {SV_OFFSET}; select pg_stat_force_next_flush()"),
                )
                .await?;
            admin.query(QKind::Meta, &format!("vacuum analyze sv_fact{p}")).await?;
        }
        tokio::time::sleep(Duration::from_millis(1200)).await;
        let db = Arc::new(Db::connect(url, 8, true)?);
        let cfg = MiddleConfig {
            name: policy.into(),
            metric_maint: if policy == "full-recheck" { Maint::Definition } else { Maint::Condition },
            cond_reuse: policy != "full-recheck",
            result_cache: false,
            version_ttl_ms: 0,
            ..Default::default()
        };
        let copies = if policy == "per-agent" { n } else { 1 };
        let mut mids = vec![];
        let mut keys = vec![];
        for _ in 0..copies {
            let mid = Middle::new(db.clone(), cfg.clone()).await?;
            keys = sv_seed(&mid, &base).await?;
            mids.push(mid);
        }
        for p in 0..SV_PAIRS {
            admin
                .query(
                    QKind::Meta,
                    &format!(
                        "insert into sv_fact{p} ({cols}) select {sel} from store_sales where ss_ticket_number % 100 = 7; \
                         select pg_stat_force_next_flush()",
                        cols = sv_cols.join(", "),
                        sel = sv_cols
                            .iter()
                            .map(|c| if c == "ss_ticket_number" { format!("{c} + {SV_OFFSET}") } else { c.clone() })
                            .collect::<Vec<_>>()
                            .join(", ")
                    ),
                )
                .await?;
            metricbench::log_batch(&admin, &format!("sv_fact{p}"), "shared-validation append").await?;
        }
        admin.query(QKind::Meta, "select pg_stat_force_next_flush()").await?;
        tokio::time::sleep(Duration::from_millis(1200)).await;
        for m in &mids {
            m.invalidate_versions();
            m.take_metric_events();
        }
        let mid_of = |agent: usize| &mids[if copies == 1 { 0 } else { agent }];
        let before = db.meter.snap();
        let start = Instant::now();
        let mut unavailable = 0;
        if arrival == "simultaneous" {
            for r in futures::future::join_all((0..n).map(|a| sv_uses(mid_of(a), &keys, a, rep + 1))).await {
                unavailable += r?;
            }
        } else {
            for a in 0..n {
                unavailable += sv_uses(mid_of(a), &keys, a, rep + 1).await?;
            }
        }
        let wall = start.elapsed().as_secs_f64();
        let meter = crate::db::diff(&before, &db.meter.snap());
        let mut actions: BTreeMap<String, u64> = BTreeMap::new();
        for m in &mids {
            for c in m
                .take_metric_events()
                .iter()
                .filter(|e| e["event"] == "maintenance")
                .flat_map(|e| e["conditions"].as_array().cloned().unwrap_or_default())
            {
                *actions.entry(c["action"].as_str().unwrap_or("unknown").into()).or_default() += 1;
            }
        }
        let row = json!({"repeat": rep, "agents": n, "policy": policy, "arrival": arrival, "definitions": SV_DEFS,
                         "table_pairs": SV_PAIRS, "rows_per_fact": 200_000, "wall_seconds": wall, "db": meter,
                         "unavailable": unavailable, "condition_actions": actions});
        eprintln!(
            "shared-validation r{rep} n{n} {policy} {arrival}: {:.0} ms DB, {} queries, unavailable {unavailable}",
            row["db"]["db_ms"].as_f64().unwrap_or(0.0),
            row["db"]["queries"]
        );
        std::fs::write(format!("{out}/cell-r{rep}-n{n}-{policy}-{arrival}.json"), serde_json::to_string_pretty(&row)?)?;
        cells.push(row);
    }
    Ok(json!({"cells": cells, "design": "16 definitions on 4 fact/date pairs (sharing factor 4), 200k rows per fact, \
               append of new business keys to every fact table, date tables unchanged; 1-32 agents each use all 16 \
               definitions once after the update; three randomized blocks"}))
}

#[tokio::test]
#[ignore = "Q5 benchmark; requires MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_shared_validation_scaling() -> Result<()> {
    run_q5_report("sharedval", "shared-validation", 4 * 3600, |url, out| Box::pin(async move { shared_validation(&url, &out).await })).await
}

// ───────────────────────── 4. Sustained Multi-Session Writes & Trigger Overhead (Q5 / Section 6.6) ─────────────────────────

async fn sustained_writes(url: &str, out: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    admin.query(QKind::Meta, &metricbench::fixture(200_000)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    let sv_cols: Vec<String> = {
        let r = admin
            .query(
                QKind::Meta,
                "select column_name from information_schema.columns where table_name = 'store_sales' order by ordinal_position",
            )
            .await?;
        (0..r.rows.len()).filter_map(|i| r.cell(i, 0).map(str::to_string)).collect()
    };
    let insert = |table: &str, batch: i64| {
        format!(
            "insert into {table} ({cols}) select {sel} from store_sales where ss_ticket_number % 1000 = {k}",
            cols = sv_cols.join(", "),
            sel = sv_cols
                .iter()
                .map(|c| if c == "ss_ticket_number" { format!("{c} + {}", SV_OFFSET + batch * 1_000_000) } else { c.clone() })
                .collect::<Vec<_>>()
                .join(", "),
            k = batch % 1000
        )
    };
    let base = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").context("missing M1")?.1;
    let rates: Vec<(u32, u32)> = if std::env::var_os("SW_OVERHEAD_ONLY").is_some() { vec![] } else { vec![(0, 1), (1, 8), (1, 2), (2, 1)] };
    let (agents, rounds) = (8usize, 8usize);
    let mut cells = vec![];
    for (num, den) in rates {
        for policy in ["full-recheck", "mavra"] {
            for p in 0..SV_PAIRS {
                admin
                    .query(
                        QKind::Meta,
                        &format!(
                            "drop table if exists sv_fact{p}; drop table if exists sv_date{p}; \
                             create table sv_fact{p} as table store_sales; create table sv_date{p} as table date_dim; \
                             analyze sv_fact{p}; analyze sv_date{p}; select pg_stat_force_next_flush()"
                        ),
                    )
                    .await?;
            }
            tokio::time::sleep(Duration::from_millis(1200)).await;
            let db = Arc::new(Db::connect(url, 8, true)?);
            let cfg = MiddleConfig {
                name: policy.into(),
                metric_maint: if policy == "full-recheck" { Maint::Definition } else { Maint::Condition },
                cond_reuse: policy != "full-recheck",
                result_cache: false,
                version_ttl_ms: 0,
                ..Default::default()
            };
            let mid = Middle::new(db.clone(), cfg).await?;
            let keys = sv_seed(&mid, &base).await?;
            mid.take_metric_events();
            let before = db.meter.snap();
            let (mut writes, mut write_ms, mut unavailable, mut uses) = (0i64, 0f64, 0usize, 0usize);
            let start = Instant::now();
            for session in 0..agents * rounds {
                unavailable += sv_uses(&mid, &keys, session % agents, 100 + session as u64).await?;
                uses += keys.len();
                let due = ((session as u32 + 1) * num / den) as i64 - (session as u32 * num / den) as i64;
                for _ in 0..due {
                    let t = format!("sv_fact{}", writes as usize % SV_PAIRS);
                    let w0 = Instant::now();
                    admin.query(QKind::Meta, &format!("{}; select pg_stat_force_next_flush()", insert(&t, writes + 1))).await?;
                    write_ms += w0.elapsed().as_secs_f64() * 1000.0;
                    metricbench::log_batch(&admin, &t, "sustained append").await?;
                    writes += 1;
                }
                if due > 0 {
                    tokio::time::sleep(Duration::from_millis(1200)).await;
                    mid.invalidate_versions();
                }
            }
            let wall = start.elapsed().as_secs_f64();
            let meter = crate::db::diff(&before, &db.meter.snap());
            let mut actions: BTreeMap<String, u64> = BTreeMap::new();
            for c in mid
                .take_metric_events()
                .iter()
                .filter(|e| e["event"] == "maintenance")
                .flat_map(|e| e["conditions"].as_array().cloned().unwrap_or_default())
            {
                *actions.entry(c["action"].as_str().unwrap_or("unknown").into()).or_default() += 1;
            }
            let row = json!({"policy": policy, "rate": format!("{num}/{den}"), "rate_value": num as f64 / den as f64,
                             "sessions": agents * rounds, "uses": uses, "writes": writes, "write_ms": write_ms,
                             "wall_seconds": wall, "db": meter, "unavailable": unavailable, "condition_actions": actions});
            eprintln!(
                "sustained {policy} lambda={num}/{den}: writes {writes}, {:.0} ms DB, actions {:?}",
                meter.db_ms, row["condition_actions"]
            );
            std::fs::write(format!("{out}/cell-{policy}-{num}-{den}.json"), serde_json::to_string_pretty(&row)?)?;
            cells.push(row);
        }
    }
    admin.query(QKind::Meta, "drop table if exists sv_wt; create table sv_wt as table store_sales with no data").await?;
    let (mut with, mut without) = (vec![], vec![]);
    for i in 0..120i64 {
        let trig = i % 2 == 0;
        if trig {
            catalog::install_tx_versions(&admin, &["sv_wt"]).await?;
        } else {
            admin.query(QKind::Meta, "drop trigger if exists mavra_bump on sv_wt").await?;
        }
        let t0 = Instant::now();
        admin.query(QKind::Meta, &insert("sv_wt", 300 + i)).await?;
        let ms = t0.elapsed().as_secs_f64() * 1000.0;
        if trig {
            with.push(ms);
        } else {
            without.push(ms);
        }
    }
    let med = |v: &mut Vec<f64>| {
        v.sort_by(|a, b| a.total_cmp(b));
        v[v.len() / 2]
    };
    let overhead = json!({"inserts_each": with.len(), "rows_per_insert": 200,
                          "median_ms_with_trigger": med(&mut with), "median_ms_without": med(&mut without)});
    eprintln!("trigger overhead: {overhead}");
    Ok(json!({"cells": cells, "trigger_overhead": overhead,
              "design": "16 shared definitions on 4 fact/date pairs, 200k rows per fact; 64 sessions (8 agents x 8 rounds) each use all 16 definitions; after each session lambda appends (0, 1/8, 1/2, 2) of ~200 new-key rows to the fact tables in turn"}))
}

#[tokio::test]
#[ignore = "Q5 benchmark; requires MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_sustained_writes() -> Result<()> {
    run_q5_report("sustained", "sustained-writes", 4 * 3600, |url, out| Box::pin(async move { sustained_writes(&url, &out).await })).await
}

// ───────────────────────── 5. Mechanism Supplement: Compiler Subsets & Matched B/C (Section 6.6) ─────────────────────────

#[test]
#[ignore = "export frozen source subsets with the unchanged Rust compiler; no database or model calls"]
fn mechanism_compile_frozen_source() -> Result<()> {
    let source = std::env::var("MECHANISM_SOURCE")?;
    let out = std::env::var("MECHANISM_COMPILED_OUT")?;
    let data: Value = serde_json::from_str(&std::fs::read_to_string(format!("{source}/source-features.json"))?)?;
    let frozen: Value = serde_json::from_str(&std::fs::read_to_string(format!("{source}/frozen-definitions.json"))?)?;
    let mut defs = data["features"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|x| x["status"] == "Valid")
        .map(|x| Ok((x["entry"]["key"].as_str().unwrap().to_string(), serde_json::from_value::<Metric>(x["entry"].clone())?)))
        .collect::<Result<Vec<_>>>()?;
    defs.sort_by(|a, b| a.0.cmp(&b.0));
    ensure!(defs.len() == 7, "source changed: expected seven frozen definitions");
    let mut entries = serde_json::Map::new();
    for mask in 1..(1 << defs.len()) {
        let chosen = defs.iter().enumerate().filter(|(i, _)| mask & (1 << i) != 0).map(|(_, d)| d).collect::<Vec<_>>();
        let metrics = chosen.iter().map(|d| &d.1).collect::<Vec<_>>();
        let (sql, cols) = metric::compose_features(&metrics, "userid")?;
        let keys = chosen.iter().map(|d| d.0.clone()).collect::<Vec<_>>();
        let columns = keys.iter().zip(cols).map(|(k, c)| json!({"key": k, "revision": 0, "column": c})).collect::<Vec<_>>();
        if mask == (1 << defs.len()) - 1 {
            ensure!(sql == frozen["sql"].as_str().unwrap(), "full-source compiler equivalence failed");
        }
        entries.insert(keys.join("|"), json!({"sql": sql, "columns": columns}));
    }
    std::fs::write(out, serde_json::to_string_pretty(&json!({"subsets": entries, "full_sql_exact_match": true}))?)?;
    Ok(())
}

async fn mech_c_middle(b: &SnapBench, detach: bool) -> Result<SnapMid> {
    let cfg = MiddleConfig {
        name: if detach { "tx-precheck" } else { "tx-bound" }.into(),
        metric_maint: Maint::Condition,
        cond_reuse: true,
        result_cache: false,
        snapshot_exec: true,
        experiment_detach: detach,
        experiment_barrier: Some(Arc::new((
            std::sync::atomic::AtomicBool::new(false),
            tokio::sync::Notify::new(),
            tokio::sync::Notify::new(),
        ))),
        ..Default::default()
    };
    let mid = Middle::new(Arc::new(Db::connect(&b.url, 8, true)?), cfg).await?;
    let m = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").unwrap().1;
    let key = format!("metric:{}", m.name);
    let seeded = mid
        .seed_metric(&Ctx::new("A", "seed", "seed"), m, Ask::Single { period: b.learn }, 2, &metricbench::gold_period("M1", &b.learn))
        .await?;
    ensure!(seeded["promoted"] == true, "matched-C admission failed: {seeded}");
    let u = mid.use_metric(&Ctx::new("B", "matched", "use"), &key).await?;
    let m: Metric = serde_json::from_value(u["metric"].clone())?;
    let canon = metric::compile(&m, &Ask::Single { period: Period::month(2002, 7) })?;
    let probe = format!(
        "select ({}) as v, (select count(*)-count(distinct (s.ss_ticket_number,s.ss_item_sk)) \
        from store_sales s join date_dim d on s.ss_sold_date_sk=d.d_date_sk \
        where d.d_year=2002 and d.d_moy=7) as dup",
        canon.trim().trim_end_matches(';')
    );
    let refs = vec![(key, u["revision"].as_u64().unwrap() as u32)];
    Ok(SnapMid { cp: mid.checkpoint(), mid, refs, canon, probe, probes: vec![] })
}

async fn mechanism_c(url: &str, out: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    admin.query(QKind::Meta, &metricbench::fixture(200_000)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    catalog::install_tx_versions(&admin, &SNAP_TABLES).await?;
    admin.query(QKind::Meta, "analyze").await?;
    let b = SnapBench { url: url.into(), admin, learn: Period::month(2001, 3) };
    let mut rows = vec![];
    for trial in 0..5 {
        for case in ["benign_after_check", "violation_after_check", "violation_before_call"] {
            for index in 0..2 {
                let detach = (index + trial) % 2 == 0;
                let s = mech_c_middle(&b, detach).await?;
                let ctx = Ctx::new("B", "matched", "execute");
                let warm = s.mid.run_sql_with(&ctx, &s.probe, &s.refs).await;
                ensure!(classify(&warm) == "served", "matched-C warm failed");
                let barrier = s.mid.cfg.experiment_barrier.as_ref().unwrap().clone();
                let r = if case == "violation_before_call" {
                    b.admin.execute(DUP_INJECT).await?;
                    s.mid.run_sql_with(&ctx, &s.probe, &s.refs).await
                } else {
                    barrier.0.store(true, std::sync::atomic::Ordering::SeqCst);
                    let writer = async {
                        tokio::time::timeout(Duration::from_secs(60), barrier.1.notified())
                            .await
                            .context("validation barrier was not reached")?;
                        let w = if case == "benign_after_check" {
                            b.admin
                                .execute("update store_sales set ss_net_paid=ss_net_paid where ctid=(select ctid from store_sales limit 1)")
                                .await
                        } else {
                            b.admin.execute(DUP_INJECT).await
                        };
                        barrier.2.notify_one();
                        w
                    };
                    let (r, w) = tokio::join!(s.mid.run_sql_with(&ctx, &s.probe, &s.refs), writer);
                    w?;
                    barrier.0.store(false, std::sync::atomic::Ordering::SeqCst);
                    r
                };
                let row = json!({
                    "trial": trial,
                    "case": case,
                    "mode": if detach { "tx-precheck" } else { "tx-bound" },
                    "outcome": classify(&r),
                    "response": match r { Ok(v) => v, Err(e) => json!({"error": format!("{e:#}")}) },
                    "stats": s.mid.stats_json(),
                    "artificial_interleaving": case != "violation_before_call",
                });
                eprintln!("matched-C: {} {} trial {} -> {}", row["mode"], case, trial, row["outcome"]);
                rows.push(row);
                std::fs::write(format!("{out}/c-progress.json"), serde_json::to_string_pretty(&rows)?)?;
                b.reset(&s).await?;
            }
        }
    }
    Ok(json!({"rows": rows, "version_source": "transactional in both modes", "performance_measurement": false}))
}

async fn mech_b_uses(mid: &Middle, keys: &[String], agent: usize, seed: u64) -> Result<Vec<Value>> {
    use rand::{seq::SliceRandom, SeedableRng};
    let mut order = keys.to_vec();
    order.shuffle(&mut rand::rngs::StdRng::seed_from_u64(seed + agent as u64));
    let ctx = Ctx::new(&format!("R{agent}"), "fixed-sharing", "use");
    let mut out = vec![];
    for key in order {
        let start = Instant::now();
        let r = mid.use_metric(&ctx, &key).await?;
        out.push(json!({"key": key, "status": r["status"], "ms": start.elapsed().as_secs_f64() * 1000.0}));
    }
    Ok(out)
}

async fn mechanism_b(url: &str, out: &str) -> Result<Value> {
    use rand::{seq::SliceRandom, SeedableRng};
    let admin = Db::connect(url, 2, false)?;
    admin.query(QKind::Meta, &metricbench::fixture(100_000)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    for i in 0..16 {
        admin
            .query(
                QKind::Meta,
                &format!(
                    "create table mb_fact{i} as table store_sales; \
                     create table mb_date{i} as table date_dim; analyze mb_fact{i}; analyze mb_date{i}"
                ),
            )
            .await?;
    }
    let base = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").unwrap().1;
    let mut cells = vec![];
    let mut order = vec![];
    for rep in 0..3 {
        let mut block = vec![];
        for reuse in [1, 2, 4, 8] {
            for policy in ["definition", "definition-cache", "condition"] {
                for arrival in ["staggered", "burst"] {
                    block.push((rep, reuse, policy, arrival));
                }
            }
        }
        block.shuffle(&mut rand::rngs::StdRng::seed_from_u64(1029 + rep as u64));
        order.extend(block);
    }
    std::fs::write(format!("{out}/b-order.json"), serde_json::to_string_pretty(&order)?)?;
    for (rep, reuse, policy, arrival) in order {
        let db = Arc::new(Db::connect(url, 8, true)?);
        let cfg = MiddleConfig {
            name: policy.into(),
            metric_maint: if policy == "condition" { Maint::Condition } else { Maint::Definition },
            cond_reuse: policy == "condition",
            sql_cache: policy == "definition-cache",
            result_cache: false,
            version_ttl_ms: 0,
            ..Default::default()
        };
        let mid = Middle::new(db.clone(), cfg).await?;
        let ctx = Ctx::new("admin", "fixed-sharing", "seed");
        let mut keys = vec![];
        let mut definitions = vec![];
        for i in 0..16 {
            let mut m = base.clone();
            m.name = format!("unit_conversion_{i}");
            m.definition = m.name.clone();
            m.fact = format!("mb_fact{}", i / reuse);
            m.time.as_mut().unwrap().dim = format!("mb_date{}", i / reuse);
            m.measure = format!("sum(ss_net_paid) * {}", i + 1);
            let base_gold = metricbench::gold_period("M1", &Period::month(2001, 3))
                .replace("store_sales", &m.fact)
                .replace("date_dim", &m.time.as_ref().unwrap().dim);
            let gold = format!("select ({}) * {}", base_gold.trim().trim_end_matches(';'), i + 1);
            let r = mid.seed_metric(&ctx, m.clone(), Ask::Single { period: Period::month(2001, 3) }, 2, &gold).await?;
            ensure!(r["promoted"] == true, "B admission failed: {r}");
            keys.push(r["key"].as_str().unwrap().to_string());
            definitions.push(m);
        }
        mech_b_uses(&mid, &keys, 0, 0).await?;
        for i in 0..16 {
            admin.query(QKind::Meta, &format!("select sum(ss_net_paid) from mb_fact{i}; select count(*) from mb_date{i}")).await?;
            admin
                .execute(&format!("update mb_fact{i} set ss_net_paid=ss_net_paid where ctid=(select ctid from mb_fact{i} limit 1)"))
                .await?;
            metricbench::log_batch(&admin, &format!("mb_fact{i}"), "fixed-sharing benign write").await?;
            admin.execute(&format!("update mb_date{i} set d_date_sk=d_date_sk where ctid=(select ctid from mb_date{i} limit 1)")).await?;
            metricbench::log_batch(&admin, &format!("mb_date{i}"), "fixed-sharing benign write").await?;
        }
        mid.invalidate_versions();
        mid.take_metric_events();
        let start = Instant::now();
        let before = db.meter.snap();
        let mut uses = vec![];
        if arrival == "burst" {
            for r in futures::future::join_all((0..8).map(|agent| mech_b_uses(&mid, &keys, agent, rep as u64 * 1000))).await {
                uses.extend(r?);
            }
        } else {
            for agent in 0..8 {
                uses.extend(mech_b_uses(&mid, &keys, agent, rep as u64 * 1000).await?);
            }
        }
        let elapsed = start.elapsed().as_secs_f64();
        let meter = crate::db::diff(&before, &db.meter.snap());
        let events = mid.take_metric_events();
        let unavailable = uses.iter().filter(|u| u["status"] != "valid").count();
        let mut actions: BTreeMap<String, u64> = BTreeMap::new();
        for c in events.iter().filter(|e| e["event"] == "maintenance").flat_map(|e| e["conditions"].as_array().into_iter().flatten()) {
            *actions.entry(c["action"].as_str().unwrap_or("unknown").into()).or_default() += 1;
        }
        let row = json!({
            "repeat": rep,
            "reuse_factor": reuse,
            "policy": policy,
            "arrival": arrival,
            "definitions": 16,
            "groups": 16 / reuse,
            "rows_per_fact": 100_000,
            "agents": 8,
            "wall_seconds": elapsed,
            "db": meter,
            "unavailable": unavailable,
            "uses": uses,
            "condition_actions": actions,
            "events": events,
            "definition_inputs": definitions,
        });
        eprintln!("fixed-B: r{rep} reuse{reuse} {policy} {arrival}: {} ms, unavailable {unavailable}", row["db"]["db_ms"]);
        std::fs::write(format!("{out}/b-r{rep}-k{reuse}-{policy}-{arrival}.json"), serde_json::to_string_pretty(&row)?)?;
        cells.push(row);
    }
    Ok(json!({"cells": cells, "design": "fixed 16 definitions, exact shared conditions, warmed fixed physical dataset"}))
}

#[tokio::test]
#[ignore = "Q5 mechanism supplement; requires MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_mechanism_supplement() -> Result<()> {
    let _ = dotenvy::dotenv();
    let url = crate::resolve_env("MAVRA_TEST_DB_URL", "AGENTDB_TEST_URL").context("MAVRA_TEST_DB_URL (or AGENTDB_TEST_URL) required")?;
    let part = std::env::var("MECHANISM_PART").unwrap_or_else(|_| "C".into());
    ensure!(part == "B" || part == "C", "unknown supplement part {part} (expected B or C)");
    let admin = Db::connect(&url, 1, false)?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros();
    let name = format!("mavra_mech_{}_{stamp}", std::process::id());
    let mut test_url = reqwest::Url::parse(&url)?;
    test_url.set_path(&format!("/{name}"));
    let out = format!("results/mechanism-systems/{part}-{stamp}");
    std::fs::create_dir_all(&out)?;
    admin.query(QKind::Meta, &format!("create database {name}")).await?;
    let result = tokio::time::timeout(Duration::from_secs(3600), async {
        if part == "B" {
            mechanism_b(test_url.as_str(), &out).await
        } else {
            mechanism_c(test_url.as_str(), &out).await
        }
    })
    .await;
    let cleanup = admin.query(QKind::Meta, &format!("drop database {name} with (force)")).await;
    let report = match &result {
        Ok(Ok(r)) => r.clone(),
        Ok(Err(e)) => json!({"error": format!("{e:#}")}),
        Err(_) => json!({"error": "timeout"}),
    };
    std::fs::write(format!("{out}/report.json"), serde_json::to_string_pretty(&json!({"report": report, "cleaned_up": cleanup.is_ok()}))?)?;
    eprintln!("saved {out}/report.json");
    cleanup?;
    result.context("supplement timeout")??;
    Ok(())
}
