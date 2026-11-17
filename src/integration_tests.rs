//! Opt-in PostgreSQL + HTTP integration test.
//! Creates a uniquely named database, never loads fixtures into the supplied database.

use crate::db::{Db, QKind};
use crate::knowledge::{Basis, EmptyRule, JoinKind, JoinRef, Metric, TimeSpec, TimeStrategy};
use crate::metric::{self, Ask, Period};
use crate::middle::{Ctx, Maint, Middle, MiddleConfig};
use crate::scenario::{self, Change};
use crate::{catalog, etl, metricbench, server};
use anyhow::{ensure, Context, Result};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

// Every case owns its database; timeout and assertion failures still reach cleanup.
async fn database_case<F, Fut>(label: &str, seconds: u64, run: F) -> Result<()>
where
    F: FnOnce(String) -> Fut,
    Fut: std::future::Future<Output = Result<Value>> + Send + 'static,
{
    let _ = dotenvy::dotenv();
    let url = std::env::var("AGENTDB_TEST_URL").context("AGENTDB_TEST_URL required")?;
    let admin = Db::connect(&url, 1, false)?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros();
    let name = format!("agentdb_{label}_{}_{stamp}", std::process::id());
    let mut test_url = reqwest::Url::parse(&url)?;
    test_url.set_path(&format!("/{name}"));
    admin.query(QKind::Meta, &format!("create database {name}")).await?;
    let mut task = tokio::spawn(run(test_url.to_string()));
    let result = tokio::time::timeout(Duration::from_secs(seconds), &mut task).await;
    if result.is_err() {
        task.abort();
        let _ = task.await;
    }
    admin.query(QKind::Meta, &format!("drop database {name} with (force)")).await.context("test database cleanup failed")?;
    let report = result.context("database test timed out")?.context("database test panicked")??;
    println!("{label}: {report}");
    Ok(())
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_snapshot_binding() -> Result<()> {
    database_case("snapshot", 90, |url| Box::pin(async move { snapshot_binding(&url).await })).await
}

// One controlled write proves snapshot isolation; throughput studies live in Git history.
async fn snapshot_binding(url: &str) -> Result<Value> {
    use std::sync::atomic::{AtomicBool, Ordering};

    let admin = Db::connect(url, 2, false)?;
    admin
        .query(
            QKind::Meta,
            "create table snapshot_sales (id int, amount numeric, occurred date); \
        insert into snapshot_sales values (1,10,'2001-03-01'),(2,20,'2001-03-02'); \
        create table etl_batch_log (table_name text, batch_id bigint)",
        )
        .await?;
    catalog::install_tx_versions(&admin, &["snapshot_sales"]).await?;
    let mid = Middle::new(
        Arc::new(Db::connect(url, 4, true)?),
        MiddleConfig {
            snapshot_exec: true,
            cond_reuse: true,
            result_cache: false,
            version_ttl_ms: 0,
            exec_pause_ms: 1000,
            repair: false,
            ..Default::default()
        },
    )
    .await?;
    let ctx = Ctx::new("reader", "snapshot", "query");
    let m: Metric = serde_json::from_value(json!({"name":"sales", "definition":"total sales",
        "fact":"snapshot_sales", "measure":"sum(amount)", "grain":["id"], "empty":"zero",
        "time":{"role":"sale","fact_col":"occurred","strategy":"column","grain":"day"}}))?;
    let seeded =
        mid.seed_metric(&ctx, m, Ask::Single { period: Period::month(2001, 3) }, 2, "select sum(amount) from snapshot_sales").await?;
    ensure!(seeded["promoted"] == true, "snapshot definition must be admitted: {seeded}");
    let refs = vec![(seeded["key"].as_str().context("missing metric key")?.to_string(), 0)];
    let committed = AtomicBool::new(false);
    let sql = "select sum(amount), count(*) - count(distinct id) from snapshot_sales";
    let (read, write) = tokio::join!(
        async {
            let result = mid.run_sql_with(&ctx, sql, &refs).await?;
            ensure!(committed.load(Ordering::SeqCst), "writer must commit before the reader finishes");
            Ok::<_, anyhow::Error>(result)
        },
        async {
            // Wait for an actual snapshot check, rather than guessing how long admission takes.
            tokio::time::timeout(Duration::from_secs(10), async {
                loop {
                    let stats = mid.stats_json();
                    let snap = &stats["snapshot_exec"];
                    if snap["checks_run"].as_u64().unwrap_or(0) + snap["checks_reused"].as_u64().unwrap_or(0) > 0 {
                        break;
                    }
                    tokio::time::sleep(Duration::from_millis(5)).await;
                }
            })
            .await
            .context("reader never opened its validation snapshot")?;
            admin.query(QKind::Meta, "insert into snapshot_sales select * from snapshot_sales").await?;
            committed.store(true, Ordering::SeqCst);
            Ok::<_, anyhow::Error>(())
        }
    );
    write?;
    let result = read?;
    ensure!(
        result["source"] == "snapshot" && result["result"]["rows"][0] == json!(["30", "0"]),
        "validation and answer must use the pre-write snapshot: {result}"
    );
    let current = admin.query(QKind::Meta, sql).await?;
    ensure!(current.cell(0, 0) == Some("60") && current.cell(0, 1) == Some("2"), "writer must change the live data");
    mid.invalidate_versions();
    let next = mid.run_sql_with(&ctx, sql, &refs).await?;
    ensure!(next["rejected"] == true, "the next snapshot must reject the broken grain: {next}");
    Ok(json!({"snapshot_total":30,"live_total":60,"next_request_rejected":true}))
}

async fn feature_scan_fusion(url: &str) -> Result<Value> {
    let db = Db::connect(url, 2, false)?;
    db.query(
        QKind::Meta,
        "create table events (id int, entity_id int, occurred timestamp, amount numeric, kind text); \
         create table seeds (id int, seed_time timestamp); \
         insert into events values (1,1,'2020-01-01',10,'a'),(2,1,'2020-01-20',null,'b'), \
         (3,1,'2020-01-25',20,'a'),(4,2,'2019-01-01',7,'a'),(5,1,'2021-01-01',999,'a'); \
         insert into seeds values (1,'2020-02-01'),(2,'2020-02-01'),(3,'2020-02-01'),(1,'2020-01-15')",
    )
    .await?;
    let base: Metric = serde_json::from_value(json!({"name":"count", "definition":"event count", "fact":"events",
        "measure":"count(*)", "grain":["id"], "time":{"role":"event time","fact_col":"occurred","strategy":"column","grain":"day"},
        "entity":{"table":"entities","key":"id","via":"entity_id"}, "empty":"zero"}))?;
    let mut defs = vec![base.clone()];
    for (name, measure) in [
        ("sum", "sum(amount)"),
        ("avg", "avg(amount)"),
        ("distinct", "count(distinct kind)"),
        ("recency", "extract(epoch from (seed_time - max(occurred))) / 86400"),
        ("ratio", "sum(amount) / nullif(count(*),0)"),
    ] {
        let mut m = base.clone();
        m.name = name.into();
        m.measure = measure.into();
        m.empty = EmptyRule::Null;
        defs.push(m);
    }
    let mut recent = base.clone();
    recent.name = "recent".into();
    recent.entity.as_mut().unwrap().window_days = Some(31);
    defs.push(recent);
    let mut filtered = base;
    filtered.name = "only_a".into();
    filtered.filters.insert("events".into(), "kind = 'a'".into());
    defs.push(filtered);
    let refs: Vec<&Metric> = defs.iter().collect();
    let (fused, columns) = metric::compose_features(&refs, "id")?;
    let mut projection = vec!["s.id".to_string(), "s.seed_time".to_string()];
    let mut joins = vec![];
    for (i, m) in defs.iter().enumerate() {
        projection.push(format!("f{i}.v as {}", columns[i]));
        joins.push(metric::feature_lateral(m, &format!("f{i}"), "id")?);
    }
    let independent = format!("select {} from seeds s {} order by s.id,s.seed_time", projection.join(","), joins.join(" "));
    let compiled = format!("{} order by s.id,s.seed_time", fused.replace("{seeds}", "seeds"));
    let expected = db.query(QKind::Meta, &independent).await?.to_json(20);
    let actual = db.query(QKind::Meta, &compiled).await?.to_json(20);
    ensure!(actual == expected, "fused SQL must preserve nulls, ratios, windows, and duplicate-entity seed times: {actual} vs {expected}");
    ensure!(actual["rows"][1][2] == "3", "the February seed must count three past events: {actual}");
    ensure!(actual["rows"][3][3].is_null(), "an empty nullable sum must remain NULL: {actual}");
    db.query(QKind::Meta, "insert into events values (6,1,'2022-01-01',1000000,'b')").await?;
    let after = db.query(QKind::Meta, &compiled).await?.to_json(20);
    ensure!(after == actual, "future rows must not affect any fused feature");
    Ok(json!({"status":"passed","features":columns.len(),"independent_scans":defs.len(),
              "fused_scans":fused.matches("left join lateral").count(),"rows":actual["row_count"]}))
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_feature_scan_fusion() -> Result<()> {
    database_case("featurefusion", 90, |url| Box::pin(async move { feature_scan_fusion(&url).await })).await
}

async fn tool(http: &reqwest::Client, base: &str, name: &str, args: Value) -> Result<Value> {
    let response = http
        .post(format!("{base}/v1/tools/{name}"))
        .json(&json!({"agent": "mock-integration", "session": "test", "args": args}))
        .send()
        .await?;
    let status = response.status();
    let body: Value = response.json().await?;
    ensure!(status.is_success(), "{name}: {status}: {body}");
    Ok(body)
}

async fn scoped_admission(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    admin
        .query(
            QKind::Meta,
            "create table sales (s_key int, s_paid numeric); \
        create table returns (r_key int, r_amt numeric); \
        create table etl_batch_log (table_name text, batch_id bigint); \
        insert into sales values (1,100),(1,100),(2,200),(2,200); \
        insert into returns values (1,30),(2,45); \
        analyze sales; analyze returns",
        )
        .await?;
    let mid = Middle::new(Arc::new(Db::connect(url, 4, true)?), MiddleConfig { version_ttl_ms: 0, ..Default::default() }).await?;
    admin
        .query(
            QKind::Meta,
            "alter table returns add column r_source text not null default 'primary'; \
        insert into returns values (1,31,'backup'),(2,46,'backup'); analyze returns",
        )
        .await?;
    mid.invalidate_versions();
    let ctx = Ctx::new("A", "scoped-admission", "queries");
    let unsafe_sql = "select sum(r_amt) from sales s join returns r on s.s_key=r.r_key";
    let blocked = mid.run_sql_with(&ctx, unsafe_sql, &[]).await?;
    ensure!(blocked["rejected"] == true, "unfiltered duplicate join must remain rejected: {blocked}");
    let fixed_sql = "with s as (select distinct s_key,s_paid from sales), \
        r as (select r_key,sum(r_amt) r_amt from returns where r_source='primary' group by r_key) \
        select round(100*sum(r.r_amt)/sum(s.s_paid),2) from s left join r on s.s_key=r.r_key";
    let fixed = mid.run_sql_with(&ctx, fixed_sql, &[]).await?;
    ensure!(fixed["result"]["rows"][0][0] == "25.00", "filtered and aggregated inputs must be admitted: {fixed}");
    let on_filtered = mid
        .run_sql_with(
            &ctx,
            "with s as (select distinct s_key,s_paid from sales) \
        select round(100*sum(r.r_amt)/sum(s.s_paid),2) from s left join returns r \
        on s.s_key=r.r_key and r.r_source='primary'",
            &[],
        )
        .await?;
    ensure!(on_filtered["result"]["rows"][0][0] == "25.00", "right-side ON filter must be respected: {on_filtered}");
    let self_joined = mid
        .run_sql_with(
            &ctx,
            "with s as (select distinct s_key,s_paid from sales), \
        p as (select * from returns where r_source='primary'), b as (select * from returns where r_source='backup') \
        select sum(p.r_amt) from p join b on p.r_key=b.r_key join s on s.s_key=p.r_key where p.r_amt<>b.r_amt",
            &[],
        )
        .await?;
    ensure!(self_joined["result"]["rows"][0][0] == "75", "filtered self-join must not poison other scopes: {self_joined}");
    let scalar = mid
        .run_sql_with(
            &ctx,
            "with s as (select distinct s_key,s_paid from sales), \
        p as (select * from returns where r_source='primary'), b as (select * from returns where r_source='backup') \
        select sum((select x.s_paid from s x where x.s_key=p.r_key limit 1)) from p join b on p.r_key=b.r_key",
            &[],
        )
        .await?;
    ensure!(scalar["result"]["rows"][0][0] == "300", "scalar correlation must not be treated as a multiplying join: {scalar}");
    let exists =
        mid.run_sql_with(&ctx, "select count(*) from sales s where exists (select 1 from returns r where r.r_key=s.s_key)", &[]).await?;
    ensure!(exists["result"]["rows"][0][0] == "4", "EXISTS must not be rejected as row multiplication: {exists}");
    let still_blocked = mid.run_sql_with(&ctx, unsafe_sql, &[]).await?;
    ensure!(still_blocked["rejected"] == true, "query-local proof must not validate the unfiltered base relation");
    admin
        .query(
            QKind::Meta,
            "create table promo_sales (ticket int, item int, paid numeric, shipped date, is_current int); \
        create table promo_part (item int, category text, is_current text); \
        insert into promo_sales values (1,10,80,'1997-09-05',1),(2,11,30,'1997-09-05',1),(1,10,90,'1997-09-05',0); \
        insert into promo_part values (10,'PROMO','Y'),(10,'OLD','N'),(11,'STANDARD','Y')",
        )
        .await?;
    let ambiguous = admin.query(QKind::Meta, "select sum(paid) from promo_sales join promo_part using(item) where is_current=1").await;
    ensure!(ambiguous.is_err(), "the original shared-column ambiguity must be reproduced");
    let promo: Metric = serde_json::from_value(json!({"name":"promo", "definition":"current promotional sales",
        "fact":"promo_sales", "measure":"sum(case when promo_part.category='PROMO' then promo_sales.paid else 0 end)",
        "grain":["ticket","item"], "time":{"role":"shipment","fact_col":"shipped","grain":"day","strategy":"column"},
        "joins":[{"left":"promo_sales","right":"promo_part","on":[["item","item"]]}],
        "filters":{"promo_sales":"is_current = 1","promo_part":"is_current = 'Y'"}}))?;
    let compiled = metric::compile(&promo, &Ask::Single { period: Period::month(1997, 9) })?;
    let owned = admin.query(QKind::Meta, &compiled).await?;
    ensure!(owned.cell(0, 0) == Some("80"), "table-owned filters must compile to the intended current rows: {compiled}");
    admin.query(QKind::Meta, "delete from promo_part where is_current='N'").await?;
    catalog::install_tx_versions(&admin, &["promo_sales", "promo_part"]).await?;
    let executor = Middle::new(
        Arc::new(Db::connect(url, 4, true)?),
        MiddleConfig { record: true, snapshot_exec: true, result_cache: false, version_ttl_ms: 0, ..Default::default() },
    )
    .await?;
    let exec_ctx = Ctx::new("A", "compiled-metric", "execute");
    let ask = Ask::Single { period: Period::month(1997, 9) };
    let seeded = executor.seed_metric(&exec_ctx, promo, ask.clone(), 2, &compiled).await?;
    ensure!(seeded["promoted"] == true, "shared-column metric must pass publication: {seeded}");
    let request = json!({"key":seeded["key"],"revision":seeded["revision"],"ask":ask});
    let initial = executor.call_tool(&exec_ctx, "run_metric", &request).await?;
    ensure!(initial["result"]["rows"][0][0] == "80", "compiled metric initial value: {initial}");
    admin.query(QKind::Meta, "insert into promo_sales values (3,10,80,'1997-09-05',1)").await?;
    executor.invalidate_versions();
    let appended = executor.call_tool(&exec_ctx, "run_metric", &request).await?;
    ensure!(appended["result"]["rows"][0][0] == "160", "distinct business keys with identical payload must count: {appended}");
    let mut stale = request.clone();
    stale["revision"] = json!(seeded["revision"].as_u64().unwrap() + 1);
    let denied = executor.call_tool(&exec_ctx, "run_metric", &stale).await?;
    ensure!(denied["rejected"] == true && denied.get("ref").is_none(), "stale revisions must not execute: {denied}");
    admin.query(QKind::Meta, "insert into promo_sales values (3,10,80,'1997-09-05',1)").await?;
    executor.invalidate_versions();
    let duplicated = executor.call_tool(&exec_ctx, "run_metric", &request).await?;
    ensure!(duplicated["rejected"] == true && duplicated.get("ref").is_none(), "invalidated metrics must not execute: {duplicated}");
    Ok(json!({"unfiltered_rejected":true,"filtered_preaggregate_value":fixed["result"]["rows"][0][0],
        "exists_count":exists["result"]["rows"][0][0],"on_filter_value":on_filtered["result"]["rows"][0][0],
        "self_join_value":self_joined["result"]["rows"][0][0],"scalar_value":scalar["result"]["rows"][0][0],
        "owned_filter_promo_value":owned.cell(0,0),"compiled_append_value":appended["result"]["rows"][0][0],
        "stale_and_invalid_execution_denied":true,"base_verdict_unchanged":true}))
}

/// 日期键换编码：一批事实的日期键改用 yyyymmdd 后，覆盖条件失败，受限修复采用唯一能恢复覆盖的编码并通过回归；
/// 修复后的修订按两种编码计入全部事实，旧修订不能再执行。
async fn date_key_repair(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    admin
        .query(
            QKind::Meta,
            "create table ds (d_date_sk int primary key, d_date date, d_year int, d_moy int); \
             insert into ds select row_number() over (order by d)::int, d::date, extract(year from d)::int, extract(month from d)::int \
               from generate_series(date '2002-08-01', date '2002-09-30', interval '1 day') d; \
             create table fs (f_ticket int, f_item int, f_date_sk int, f_paid numeric(12,2)); \
             insert into fs select d_date_sk, 1, d_date_sk, 10 from ds; \
             create table etl_batch_log (table_name text, batch_id bigint); \
             analyze ds; analyze fs",
        )
        .await?;
    catalog::install_tx_versions(&admin, &["ds", "fs"]).await?;
    let mid = Middle::new(
        Arc::new(Db::connect(url, 4, true)?),
        MiddleConfig {
            record: true,
            snapshot_exec: true,
            cond_reuse: true,
            result_cache: false,
            version_ttl_ms: 0,
            metric_maint: Maint::Condition,
            ..Default::default()
        },
    )
    .await?;
    let ctx = Ctx::new("A", "date-key-repair", "execute");
    let m: Metric = serde_json::from_value(json!({"name":"rev", "definition":"net paid by sale date", "fact":"fs",
        "measure":"sum(fs.f_paid)", "grain":["f_ticket","f_item"],
        "time":{"role":"sale","fact_col":"f_date_sk","dim":"ds","dim_col":"d_date_sk","grain":"day"}}))?;
    let learn = Ask::Single { period: Period::month(2002, 8) };
    let judge = metric::compile(&m, &learn)?;
    let seeded = mid.seed_metric(&ctx, m, learn.clone(), 2, &judge).await?;
    ensure!(seeded["promoted"] == true, "metric must pass publication: {seeded}");
    let sep = Ask::Single { period: Period::month(2002, 9) };
    let request = json!({"key":seeded["key"],"revision":seeded["revision"],"ask":sep});
    let before = mid.call_tool(&ctx, "run_metric", &request).await?;
    ensure!(before["result"]["rows"][0][0] == "300.00", "September before the late batch: {before}");
    admin
        .query(
            QKind::Meta,
            "insert into fs select f_ticket + 1000, f_item, to_char(d_date, 'YYYYMMDD')::int, f_paid \
             from fs join ds on f_date_sk = d_date_sk where d_moy = 9; \
             select pg_stat_force_next_flush(); insert into etl_batch_log values ('fs', 2); analyze fs",
        )
        .await?;
    tokio::time::sleep(Duration::from_millis(1500)).await;
    mid.invalidate_versions();
    let old = mid.call_tool(&ctx, "run_metric", &request).await?;
    ensure!(old["rejected"] == true && old.get("result").is_none(), "the pre-repair revision must not execute: {old}");
    let view = mid.use_metric(&ctx, seeded["key"].as_str().unwrap_or_default()).await?;
    ensure!(view["status"] == "valid", "the date-key repair must be published: {view}");
    let alias = view["metric"]["time"]["key_alias"].as_str().unwrap_or_default().to_string();
    ensure!(alias.contains("YYYYMMDD"), "the repair must adopt the yyyymmdd encoding: {view}");
    let repaired = json!({"key":seeded["key"],"revision":view["revision"],"ask":sep});
    let after = mid.call_tool(&ctx, "run_metric", &repaired).await?;
    ensure!(after["result"]["rows"][0][0] == "600.00", "September must count both encodings: {after}");
    let aug = mid.call_tool(&ctx, "run_metric", &json!({"key":seeded["key"],"revision":view["revision"],"ask":learn})).await?;
    ensure!(aug["result"]["rows"][0][0] == "310.00", "unaffected August must keep its value: {aug}");
    Ok(json!({"alias": alias, "revision": view["revision"], "before": before["result"]["rows"][0][0],
              "after": after["result"]["rows"][0][0], "august": aug["result"]["rows"][0][0]}))
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_date_key_repair() -> Result<()> {
    database_case("datekey", 90, |url| Box::pin(async move { date_key_repair(&url).await })).await
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_scoped_sql_admission() -> Result<()> {
    database_case("scope", 90, |url| Box::pin(async move { scoped_admission(&url).await })).await
}

async fn exercise(url: &str) -> Result<Value> {
    let admin = Arc::new(Db::connect(url, 2, false)?);
    admin.query(QKind::Meta, include_str!("../data/mock_fixture.sql")).await?;
    etl::setup(&admin).await?;
    let db = Arc::new(Db::connect(url, 4, true)?);
    let mid = Arc::new(Middle::new(db.clone(), MiddleConfig { version_ttl_ms: 0, ..Default::default() }).await?);
    // Reserve an ephemeral address briefly; report a binding failure through readiness timeout.
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let addr = listener.local_addr()?;
    drop(listener);
    let server_mid = mid.clone();
    let server_task = tokio::spawn(async move { server::serve(server_mid, None, &addr.to_string()).await });
    let base = format!("http://{addr}");
    let http = reqwest::Client::builder().no_proxy().timeout(Duration::from_secs(10)).build()?;
    let result = async {
        tokio::time::timeout(Duration::from_secs(10), async {
            loop {
                if http.get(format!("{base}/v1/tools")).send().await.is_ok() { break; }
                tokio::time::sleep(Duration::from_millis(50)).await;
            }
        }).await.context("HTTP 服务未启动")?;
        let listed: Value = http.get(format!("{base}/v1/tools")).send().await?.json().await?;
        let listed = listed.as_array().context("工具清单应为数组")?;
        ensure!(listed.iter().any(|t| t["name"] == "find_metric"), "工具清单应包含 find_metric");
        ensure!(
            listed.iter().any(|t| t["name"] == "run_sql" && t["schema"]["properties"].get("metrics").is_some()),
            "工具清单里的 run_sql 应带 metrics 声明"
        );
        ensure!(db.query(QKind::Meta, "show default_transaction_read_only").await?.cell(0, 0) == Some("on"), "查询池应只读");

        let empty = tool(&http, &base, "run_sql", json!({"sql":"select ss_item_sk from store_sales where false"})).await?;
        ensure!(empty["result"]["columns"] == json!(["ss_item_sk"]), "空结果必须保留列名");
        let upper = tool(&http, &base, "run_sql", json!({"sql":"select 'ABC' as value"})).await?;
        let lower = tool(&http, &base, "run_sql", json!({"sql":"select 'abc' as value"})).await?;
        ensure!(upper["result"]["rows"] != lower["result"]["rows"], "不同字面量不能混用缓存");
        let repeated = tool(&http, &base, "run_sql", json!({"sql":"select 'abc' as value"})).await?;
        ensure!(repeated["source"] == "reused", "相同查询应复用缓存");
        let concurrent = futures::future::join_all((0..8).map(|_| tool(
            &http, &base, "run_sql", json!({"sql":"select pg_sleep(0.1), 'concurrent' as marker"})
        ))).await;
        for response in concurrent { ensure!(response?["result"]["rows"][0][1] == "concurrent", "并发查询结果错误"); }
        ensure!(mid.stats_json()["inflight_merged"].as_u64().unwrap_or(0) > 0, "并发请求应合并");

        for (table, left_col, right_col) in [
            ("item", "ss_item_sk", "i_item_sk"),
            ("customer", "ss_customer_sk", "c_customer_sk"),
            ("warehouse", "ss_warehouse_sk", "w_warehouse_sk"),
        ] {
            let v = tool(&http, &base, "check_join", json!({"left":"store_sales","right":table,"on":[[left_col,right_col]]})).await?;
            ensure!(v["valid"] == true, "合法关联失败：{v}");
        }
        let many_to_one = tool(&http, &base, "check_join", json!({"left":"store_sales","right":"date_dim","on":[["ss_sold_date_sk","d_date_sk"]]})).await?;
        ensure!(many_to_one["valid"] == true, "重复左键的一对多侧关联不应被误判：{many_to_one}");

        let pair = json!({"left":"store_returns","right":"store_sales","on":[["sr_ticket_number","ss_ticket_number"],["sr_item_sk","ss_item_sk"]]});
        let before = tool(&http, &base, "check_join", pair.clone()).await?;
        ensure!(before["valid"] == true, "v1 复合键关联应通过");
        let inserted = etl::apply_v2(&admin).await?;
        ensure!(inserted == 2, "ETL 应新增两条状态行，实际 {inserted}");
        mid.invalidate_versions();
        let repaired = tool(&http, &base, "check_join", pair).await?;
        ensure!(repaired["valid"] == true, "v2 应修复关联粒度：{repaired}");
        ensure!(repaired["path"]["filters"]["store_returns"].as_str().is_some_and(|f| f.contains("完成")), "应恢复完成状态粒度：{repaired}");
        let rejected = tool(&http, &base, "run_sql", json!({"sql":"select sum(sr_return_amt) from store_returns"})).await?;
        ensure!(rejected["rejected"] == true, "缺少状态过滤的汇总必须被拦截");
        let sum = tool(&http, &base, "run_sql", json!({"sql":"select sum(sr_return_amt) from store_returns where sr_status = '完成'"})).await?;
        ensure!(sum["result"]["rows"][0][0] == "100.00", "修复后的汇总应为 100：{sum}");
        let stats = mid.stats_json();
        ensure!(stats["guard_fails"].as_u64().unwrap_or(0) >= 1, "应观测到守卫失败");
        ensure!(stats["repairs"].as_u64().unwrap_or(0) >= 1, "应观测到粒度修复");
        Ok(json!({"status":"passed","many_to_one":many_to_one,"etl_inserted":inserted,"repaired_join":repaired,"correct_sum":sum,"stats":stats}))
    }.await;
    server_task.abort();
    let _ = server_task.await;
    result
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_http_mock_lifecycle() -> Result<()> {
    database_case("mock", 90, |url| Box::pin(async move { exercise(&url).await })).await
}

async fn orientation_counterexample(url: &str) -> Result<Value> {
    let admin = Arc::new(Db::connect(url, 2, false)?);
    admin
        .query(
            QKind::Meta,
            "create table facts (f_id bigint, f_link bigint, f_amount numeric, f_date bigint, f_scope text);\
             create table details (de_id bigint, de_fact bigint);\
             create table date_dim (d_date_sk bigint, d_year integer, d_moy integer);\
             create table etl_batch_log (table_name text, batch_id integer, note text, applied_at timestamptz default now());\
             insert into facts values (1, 10, 100, 1, 'A B');\
             insert into details values (1, 10);\
             insert into date_dim values (1, 2002, 9)",
        )
        .await?;
    let raw = "select sum(f_amount) from facts join details on f_link = de_fact \
               join date_dim on f_date = d_date_sk where d_year = 2002 and d_moy = 9";
    let before = admin.query(QKind::Meta, raw).await?;
    ensure!(before.cell(0, 0) == Some("100"), "反例初始值应为 100");
    let db = Arc::new(Db::connect(url, 4, true)?);
    let mid = Middle::new(db, MiddleConfig { version_ttl_ms: 0, cond_reuse: true, ..Default::default() }).await?;
    let ctx = Ctx::new("A", "orientation", "seed");
    let on = vec![("de_fact".into(), "f_link".into())];
    let m: Metric = serde_json::from_value(json!({
        "name": "fact_amount", "definition": "每条事实的金额恰好累计一次", "fact": "facts",
        "measure": "sum(f_amount)", "grain": ["f_id"],
        "time": {"role": "event date", "fact_col": "f_date", "dim": "date_dim", "dim_col": "d_date_sk", "grain": "day"},
        "joins": [{"left": "details", "right": "facts", "on": on, "kind": "inner"}],
        "examples": [{"question": "2002-09 amount", "sql": raw}]
    }))?;
    let ask = Ask::Single { period: Period::month(2002, 9) };
    ensure!(metric::compile(&m, &ask).is_err(), "反向引用必须被规范编译拒绝");
    // The seeding harness compiles before its gates; production extraction checks the same
    // orientation in G3 before canonical compilation. Both paths must refuse publication.
    let rejection = mid.seed_metric(&ctx, m, ask.clone(), 2, "select sum(f_amount) from facts").await.unwrap_err();
    ensure!(rejection.to_string().contains("反向"), "反向引用必须被拒绝：{rejection}");
    let admission = json!({"rejected": true, "stage": "seed compilation", "reason": rejection.to_string()});
    admin.query(QKind::Meta, "insert into details values (2, 10)").await?;
    mid.invalidate_versions();
    let path = mid.check_join(&ctx, "details", "facts", &on).await?;
    ensure!(path["valid"] == true, "details→facts 的右键仍唯一，关系检查本身应通过：{path}");
    let after = admin.query(QKind::Meta, raw).await?;
    let gold = admin.query(QKind::Meta, "select sum(f_amount) from facts").await?;
    ensure!(after.cell(0, 0) == Some("200") && gold.cell(0, 0) == Some("100"), "反向关系导致事实金额翻倍");
    admin
        .query(
            QKind::Meta,
            "insert into facts values (2,20,100,1,'AB'),(2,21,100,1,'AB'),\
             (3,30,100,1,'ABC'),(4,40,100,1,'abc'),(4,41,100,1,'abc')",
        )
        .await?;
    mid.invalidate_versions();
    let mut filter_identity = vec![];
    for (i, filter, should_promote) in
        [(0, "f_scope = 'A B'", true), (1, "f_scope = 'AB'", false), (2, "f_scope = 'ABC'", true), (3, "f_scope = 'abc'", false)]
    {
        let candidate: Metric = serde_json::from_value(json!({
            "name": format!("literal_{i}"), "definition": "过滤后的事实金额", "fact": "facts",
            "measure": "sum(f_amount)", "grain": ["f_id"], "filters": {"facts": filter},
            "time": {"role": "event date", "fact_col": "f_date", "dim": "date_dim", "dim_col": "d_date_sk", "grain": "day"}
        }))?;
        let v = mid.seed_metric(&ctx, candidate, ask.clone(), 2, &format!("select sum(f_amount) from facts where {filter}")).await?;
        ensure!(v["promoted"] == should_promote, "不同字面量不能复用另一总体的唯一性结论：{v}");
        if !should_promote {
            ensure!(v["failed_gate"] == "G4", "重复键必须由 G4 拒绝：{v}");
        }
        filter_identity.push(json!({"filter": filter, "expected_promoted": should_promote, "result": v}));
    }
    Ok(json!({"status": "passed", "before": before.cell(0, 0), "after": after.cell(0, 0),
              "gold": gold.cell(0, 0), "reverse_path": path, "admission": admission, "filter_identity": filter_identity}))
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_metric_join_orientation() -> Result<()> {
    database_case("orientation", 90, |url| Box::pin(async move { orientation_counterexample(&url).await })).await
}

/// 优化修订：对已发布的门店营业额尝试规则改写（期间谓词改为日期键范围），记录各门槛与配对代价证据；
/// 发布后新修订的示例 SQL 不再连接日期维度，声明旧修订的查询宽限可用并收到通知。
async fn optimization_revision(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    let rows = std::env::var("AGENTDB_SCENARIO_ROWS").ok().and_then(|v| v.parse().ok()).unwrap_or(20_000);
    admin.query(QKind::Meta, &metricbench::fixture(rows)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    let db = Arc::new(Db::connect(url, 4, true)?);
    let cfg = MiddleConfig {
        name: "optimize".into(),
        version_ttl_ms: 0,
        metric_maint: Maint::Condition,
        cond_reuse: true,
        optimize: true,
        ..Default::default()
    };
    let mid = Middle::new(db, cfg).await?;
    let seed = Ctx::new("A", "seed", "seed");
    let learn = Period::month(2001, 3);
    let (id, m) = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").context("没有 M1")?;
    let v = mid.seed_metric(&seed, m, Ask::Single { period: learn }, 2, &metricbench::gold_period(id, &learn)).await?;
    ensure!(v["promoted"] == true, "M1 未晋升：{v}");
    let key = "metric:门店营业额";
    let user = Ctx::new("B", "use", "use");
    let before = mid.use_metric(&user, key).await?;
    ensure!(before["status"] == "valid" && before["revision"] == 0, "{before}");
    let octx = Ctx::new("O", "optimize", "optimize");
    let rounds = mid.optimize_sweep(&octx, None, 1).await?;
    let round = rounds.iter().find(|r| r["key"] == key).context("没有 M1 的优化轮")?;
    let tried = round["tried"].as_array().context("tried")?;
    let first = tried.first().context("没有候选")?;
    ensure!(first["candidate"].as_str().unwrap_or("").contains("日期键范围"), "{first}");
    let gates = first["gates"].as_array().context("gates")?;
    for g in ["O1", "G3", "G4", "O2", "O3", "G5", "O5"] {
        ensure!(gates.iter().any(|x| x["gate"] == g && x["pass"] == true), "门槛 {g} 未通过：{first}");
    }
    let o6 = gates.iter().find(|x| x["gate"] == "O6").context("没有 O6")?.clone();
    let promoted = first["event"] == "optimize_promoted";
    let after = mid.use_metric(&user, key).await?;
    let mut grace = Value::Null;
    if promoted {
        ensure!(after["revision"] == 1, "{after}");
        let sql = after["metric"]["examples"][0]["sql"].as_str().context("示例 SQL")?.to_string();
        ensure!(!sql.contains("join date_dim"), "新修订的示例 SQL 仍连接 date_dim：{sql}");
        let r = mid.run_sql_with(&user, "select 1 as value", &[(key.to_string(), 0)]).await?;
        ensure!(r.get("rejected").is_none(), "旧修订应宽限可用：{r}");
        let notices = mid.take_notices("B");
        ensure!(notices.iter().any(|n| n.contains("等价且更省")), "缺少通知：{notices:?}");
        grace = json!({"old_revision_accepted": true, "notices": notices});
    } else {
        ensure!(after["revision"] == 0, "{after}");
    }
    Ok(json!({"rows": rows, "promoted": promoted, "candidate": first["candidate"], "o6": o6, "cost": first["cost"],
              "revision_after": after["revision"], "grace": grace, "stats": mid.stats_json()}))
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_optimization_revision() -> Result<()> {
    database_case("optimize", 900, |url| Box::pin(async move { optimization_revision(&url).await })).await
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_premise_break() -> Result<()> {
    database_case("premise", 3600, |url| Box::pin(async move { premise_break(&url).await })).await
}

/// 规范 SQL 在当前数据上的取值。
async fn value_of(db: &Db, sql: &str) -> Result<metric::Answer> {
    Ok(metric::parse_answer(db.query(QKind::Meta, sql).await?.cell(0, 0).unwrap_or("NULL")))
}

/// 被引用的修订是否被执行端接受（只看引用检查，执行的 SQL 无关紧要）。
async fn accepted(mid: &Middle, ctx: &Ctx, key: &str, rev: u32) -> Result<(bool, Value)> {
    let r = mid.run_sql_with(ctx, "select 1 as value", &[(key.to_string(), rev)]).await?;
    Ok((r.get("rejected").is_none(), r))
}

/// 优化修订的前提被破坏，以及三种被替代的修订。种子定义（M1 / M2 / M3 / M5）经一轮规则优化得到日期键范围修订后：
/// (1) 日期键重编号：2002-02 的日期换成新的代理键并让事实表改指向它。所有日期键仍存在、关联仍唯一、完整性不变，
///     只有日期键按月连续不再成立。预期日期键范围修订失效、前一修订（连接日期维度）恢复为当前修订，按它回答的各期间
///     都正确；不维护这一前提时，日期键范围修订在跨月期间上漏掉被重编号的月份。声明失效修订的查询被拒绝，声明恢复的修订被接受。
/// (2) 另一个实例中，门店退货金额优化后施加状态流水：退货粒度失效并被修复。被修复替代的修订与它的前一修订都被拒绝。
/// (3) 补录的销售中一半的商品键关联不上商品维度：内连接商品维度的电子品类营业额被完整性条件判为失效，不连接商品维度的门店营业额不受影响。
async fn premise_break(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    let rows = std::env::var("AGENTDB_SCENARIO_ROWS").ok().and_then(|v| v.parse().ok()).unwrap_or(200_000);
    admin.query(QKind::Meta, &metricbench::fixture(rows)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    let v1 = scenario::fingerprint(&admin).await?;
    let db = Arc::new(Db::connect(url, 4, true)?);
    let cfg = MiddleConfig {
        name: "premise".into(),
        version_ttl_ms: 0,
        metric_maint: Maint::Condition,
        cond_reuse: true,
        optimize: true,
        ..Default::default()
    };
    let mid = Middle::new(db, cfg.clone()).await?;
    let seed = Ctx::new("A", "seed", "seed");
    let user = Ctx::new("B", "use", "use");
    let octx = Ctx::new("O", "optimize", "optimize");
    let learn = Period::month(2001, 3);
    let defs = seeded_metrics();
    let key_of = |m: &Metric| format!("metric:{}", m.name);
    for (id, m) in &defs {
        let v = mid.seed_metric(&seed, m.clone(), Ask::Single { period: learn }, 2, &metricbench::gold_period(id, &learn)).await?;
        ensure!(v["promoted"] == true, "{id} 未晋升：{v}");
        let u = mid.use_metric(&user, &key_of(m)).await?;
        ensure!(u["status"] == "valid" && u["revision"] == 0, "{id}：{u}");
    }

    // (1) 一轮规则优化，然后日期键重编号
    let t = Instant::now();
    let rounds = mid.optimize_sweep(&octx, None, 1).await?;
    let sweep_s = t.elapsed().as_secs_f64();
    let mut optimized: BTreeMap<&str, Metric> = BTreeMap::new();
    for (id, m) in &defs {
        let u = mid.use_metric(&user, &key_of(m)).await?;
        if u["revision"] == 1 {
            optimized.insert(*id, serde_json::from_value(u["metric"].clone())?);
        }
    }
    ensure!(!optimized.is_empty(), "没有定义得到优化修订：{rounds:?}");
    // (2) 被修复替代：另一个实例只放门店退货金额，优化后施加状态流水，退货粒度失效并被修复
    let mid2 = Middle::new(Arc::new(Db::connect(url, 4, true)?), cfg.clone()).await?;
    let (m2_id, m2) = defs.iter().find(|(id, _)| *id == "M2").context("没有 M2")?;
    let m2_key = key_of(m2);
    let v = mid2.seed_metric(&seed, m2.clone(), Ask::Single { period: learn }, 2, &metricbench::gold_period(m2_id, &learn)).await?;
    ensure!(v["promoted"] == true, "{m2_id} 未晋升：{v}");
    let rounds2 = mid2.optimize_sweep(&octx, None, 1).await?;
    let before2 = mid2.use_metric(&user, &m2_key).await?;
    let st = Change::Status;
    st.apply_truth(&admin).await?;
    st.apply_hidden(&admin).await?;
    mid2.invalidate_versions();
    let after2 = mid2.use_metric(&user, &m2_key).await?;
    let mut status_refs = json!({"skipped": "门店退货金额没有得到优化修订", "rounds": rounds2, "before": before2});
    if before2["revision"] == 1 {
        ensure!(after2["status"] == "valid" && after2["revision"] == 2, "{m2_id}：状态流水后应修复为 r2：{after2}");
        let mut seen = serde_json::Map::new();
        for rev in [0u32, 1, 2] {
            let (a, r) = accepted(&mid2, &user, &m2_key, rev).await?;
            ensure!(a == (rev == 2), "{m2_id}：r{rev} 的接受情况不对：{r}");
            seen.insert(format!("r{rev}"), json!({"accepted": a, "response": r}));
        }
        // 修复之后不再保留前一修订；此时日期键重编号只破坏日期键连续，回退方式是撤销改写规则：同一结构改回连接日期维度
        let rk = Change::Rekey;
        rk.apply_truth(&admin).await?;
        rk.apply_hidden(&admin).await?;
        mid2.invalidate_versions();
        let undone = mid2.use_metric(&user, &m2_key).await?;
        ensure!(
            undone["status"] == "valid" && undone["revision"] == 3 && undone["metric"]["time"]["strategy"] == "dim_join",
            "{m2_id}：重编号后应撤销日期键范围规则，发布连接日期维度的 r3：{undone}"
        );
        let q1 = Period { year: 2002, m1: 1, m2: 3 };
        let served: Metric = serde_json::from_value(undone["metric"].clone())?;
        let got = value_of(&admin, &metric::compile(&served, &Ask::Single { period: q1 })?).await?;
        let gold = value_of(&admin, &metricbench::gold_period(m2_id, &q1)).await?;
        ensure!(metric::same_value(&got, &gold, 2), "{m2_id}：撤销规则后的 Q1 答案 {got:?}，标准 {gold:?}");
        rk.reset(&admin).await?;
        status_refs = json!({"before": before2["revision"], "after": after2["revision"], "references": seen,
                             "rekey_after_repair": {"revision": undone["revision"], "strategy": undone["metric"]["time"]["strategy"]}});
    }
    st.reset(&admin).await?;
    scenario::ensure_v1(&admin, &v1, "状态流水回滚").await?;
    mid.invalidate_versions();

    let periods = [
        ("2002-02", Period::month(2002, 2)),
        ("2002-Q1", Period { year: 2002, m1: 1, m2: 3 }),
        ("2002-H1", Period { year: 2002, m1: 1, m2: 6 }),
        ("2002", Period { year: 2002, m1: 1, m2: 12 }),
        ("2002-09", Period::month(2002, 9)),
    ];
    let mut gold_before = BTreeMap::new();
    for (id, _) in &defs {
        for (pn, p) in &periods {
            gold_before.insert((*id, *pn), value_of(&admin, &metricbench::gold_period(id, p)).await?);
        }
    }
    mid.take_metric_events();
    let ch = Change::Rekey;
    ch.apply_truth(&admin).await?;
    ch.apply_hidden(&admin).await?;
    mid.invalidate_versions();
    let mut per_def = vec![];
    let (mut served_wrong, mut unmaintained_wrong, mut answers) = (0, 0, 0);
    for (id, m) in &defs {
        let key = key_of(m);
        let u = mid.use_metric(&user, &key).await?;
        ensure!(u["status"] == "valid", "{id} 重编号后不可用：{u}");
        let served: Metric = serde_json::from_value(u["metric"].clone())?;
        let mut rows_out = vec![];
        for (pn, p) in &periods {
            let gold = value_of(&admin, &metricbench::gold_period(id, p)).await?;
            ensure!(metric::same_value(&gold, &gold_before[&(*id, *pn)], 2), "{id} {pn}：重编号改变了业务事实");
            let ask = Ask::Single { period: *p };
            let s = value_of(&admin, &metric::compile(&served, &ask)?).await?;
            let ok = metric::same_value(&s, &gold, 2);
            answers += 1;
            served_wrong += usize::from(!ok);
            let stale = match optimized.get(id) {
                Some(om) => {
                    let v = value_of(&admin, &metric::compile(om, &ask)?).await?;
                    let ok = metric::same_value(&v, &gold, 2);
                    unmaintained_wrong += usize::from(!ok);
                    json!({"value": v, "correct": ok})
                }
                None => Value::Null,
            };
            rows_out.push(json!({"period": pn, "gold": gold, "served": s, "served_correct": ok, "key_range_unmaintained": stale}));
        }
        let mut refs = json!(null);
        if optimized.contains_key(id) {
            ensure!(u["revision"] == 0, "{id}：日期键范围修订失效后应恢复前一修订 r0：{u}");
            let (a1, r1) = accepted(&mid, &user, &key, 1).await?;
            let (a0, r0) = accepted(&mid, &user, &key, 0).await?;
            ensure!(!a1 && r1["reason"].as_str().unwrap_or("").contains("日期键"), "{id}：声明失效的 r1 应被拒绝并说明原因：{r1}");
            ensure!(a0, "{id}：声明恢复的 r0 应被接受：{r0}");
            refs = json!({"r1": r1, "r0_accepted": a0});
        }
        per_def.push(json!({"id": id, "key": key, "optimized": optimized.contains_key(id), "revision_served": u["revision"],
                            "answers": rows_out, "references": refs}));
    }
    ensure!(served_wrong == 0, "恢复前一修订后仍有 {served_wrong} 个错误答案：{per_def:?}");
    ensure!(unmaintained_wrong > 0, "不维护前提时日期键范围修订应在跨月期间上出错：{per_def:?}");
    let rekey_events: Vec<Value> = mid
        .take_metric_events()
        .into_iter()
        .filter(|e| matches!(e["event"].as_str(), Some("maintenance" | "reinstated" | "predecessor_checked" | "revoked")))
        .collect();
    let rekey_notices = mid.take_notices("B");
    ch.reset(&admin).await?;
    scenario::ensure_v1(&admin, &v1, "日期键重编号回滚").await?;
    mid.invalidate_versions();

    // (3) 关联不上商品维度的销售：内连接的完整性条件
    metricbench::apply_growth(&admin).await?;
    let before = catalog::versions(&admin).await?.get("store_sales").map(|v| v.dml).unwrap_or(0);
    let n = admin
        .execute(&format!(
            "update store_sales set ss_item_sk = ss_item_sk + 1000000 \
             where ss_ticket_number > {} and ss_ticket_number % 2 = 0",
            metricbench::GROWTH_OFFSET
        ))
        .await?;
    admin.query(QKind::Meta, "select pg_stat_force_next_flush()").await?;
    metricbench::log_batch(&admin, "store_sales", "补录销售中一半的商品键关联不上商品维度").await?;
    admin.query(QKind::Meta, "analyze store_sales").await?;
    etl::wait_table_stats(&admin, "store_sales", before).await?;
    mid.invalidate_versions();
    let (_, m5) = defs.iter().find(|(id, _)| *id == "M5").context("没有 M5")?;
    let (_, m1) = defs.iter().find(|(id, _)| *id == "M1").context("没有 M1")?;
    let e5 = mid.use_metric(&user, &key_of(m5)).await?;
    let e1 = mid.use_metric(&user, &key_of(m1)).await?;
    ensure!(e5["status"] == "unavailable" && e5["reason"].as_str().unwrap_or("").contains("内连接排除"), "M5 应被完整性条件判为失效：{e5}");
    ensure!(e1["status"] == "valid", "M1 不连接商品维度，应不受影响：{e1}");
    metricbench::reset_growth(&admin).await?;
    scenario::ensure_v1(&admin, &v1, "孤儿商品键回滚").await?;

    Ok(json!({
        "status": "passed", "rows": rows, "sweep_s": sweep_s, "rounds": rounds,
        "rekey": {"definitions": per_def, "answers": answers, "served_wrong": served_wrong,
                  "key_range_unmaintained_wrong": unmaintained_wrong, "events": rekey_events, "notices": rekey_notices},
        "status_change": status_refs,
        "orphan_items": {"rows_updated": n, "m5": e5, "m1": e1},
        "stats": mid.stats_json(),
    }))
}

// ───────────────────────── 数据变化场景：不调用 LLM 的维护预期 ─────────────────────────

fn seeded_metrics() -> Vec<(&'static str, Metric)> {
    let time = |col: &str, role: &str| {
        Some(TimeSpec {
            role: role.into(),
            fact_col: col.into(),
            dim: "date_dim".into(),
            dim_col: "d_date_sk".into(),
            grain: "month".into(),
            loss_ratio: 0.0,
            strategy: TimeStrategy::DimJoin,
            year_col: "d_year".into(),
            month_col: "d_moy".into(),
            key_alias: None,
        })
    };
    let join = |right: &str, on: &[(&str, &str)], kind: JoinKind| JoinRef {
        key: String::new(),
        left: "store_sales".into(),
        right: right.into(),
        on: on.iter().map(|(l, r)| (l.to_string(), r.to_string())).collect(),
        kind,
        filters: BTreeMap::new(),
        cardinality: String::new(),
        loss_ratio: 0.0,
        orphan_ratio: 0.0,
        revision: 0,
    };
    let base = |name: &str, fact: &str, measure: &str, grain: &[&str]| Metric {
        name: name.into(),
        aliases: vec![],
        definition: name.into(),
        fact: fact.into(),
        measure: measure.into(),
        grain: grain.iter().map(|c| c.to_string()).collect(),
        time: None,
        joins: vec![],
        filters: BTreeMap::new(),
        empty: EmptyRule::Unspecified,
        caveats: vec![],
        examples: vec![],
        basis: Basis::None,
        entity: None,
        dedup: false,
        null_base: Default::default(),
        scale_base: Default::default(),
    };
    let sales = ["ss_ticket_number", "ss_item_sk"];
    let mut m1 = base("门店营业额", "store_sales", "sum(ss_net_paid)", &sales);
    m1.time = time("ss_sold_date_sk", "销售日");
    let mut m2 = base("门店退货金额", "store_returns", "sum(sr_return_amt)", &["sr_ticket_number", "sr_item_sk"]);
    m2.time = time("sr_returned_date_sk", "退货日");
    let mut m3 = base("门店退货率", "store_sales", "100.0 * sum(sr_return_amt) / sum(ss_net_paid)", &sales);
    m3.time = time("ss_sold_date_sk", "销售日");
    m3.joins = vec![join("store_returns", &[("ss_ticket_number", "sr_ticket_number"), ("ss_item_sk", "sr_item_sk")], JoinKind::Left)];
    let mut m5 = base("电子品类门店营业额", "store_sales", "sum(ss_net_paid)", &sales);
    m5.time = time("ss_sold_date_sk", "销售日");
    m5.joins = vec![join("item", &[("ss_item_sk", "i_item_sk")], JoinKind::Inner)];
    m5.filters.insert("item".into(), "i_category = '电子'".into());
    vec![("M1", m1), ("M2", m2), ("M3", m3), ("M5", m5)]
}

/// 条件级与定义级维护下，每个场景对 M1 / M2 / M3 / M5 的预期：valid0 = 刷新后原修订可用，valid1 = 修复后新修订可用，
/// unavailable = 撤销且不在修复范围或修复失败。金额单位变化由度量尺度条件发现。
fn expected(c: Change) -> [&'static str; 4] {
    const V0: &str = "valid0";
    const V1: &str = "valid1";
    match c {
        Change::Append | Change::Backfill | Change::Correct | Change::AddColumn => [V0, V0, V0, V0],
        // 金额改以分记录：读门店销售金额的三个定义月中位数跳变 100 倍，度量尺度条件不成立，暂停提供（需业务确认）
        Change::Unit => ["unavailable", V0, "unavailable", "unavailable"],
        Change::Status => [V0, V1, V1, V0],
        Change::Revision => [V1, V0, V1, V1],
        // 重复装载的行与原行完全相同：去重修复，三个读门店销售的定义发布新修订
        Change::Duplicate => [V1, V0, V1, V1],
        // 补录批次的日期键换成 yyyymmdd：日期键修复按两种编码关联，三个按销售日的定义发布新修订
        Change::LateKey => [V1, V0, V1, V1],
        Change::DimHistory => [V0, V0, V0, V1],
        Change::Mirror => [V0, V1, V1, V0],
        // 未优化的定义不依赖日期键连续：各条件都成立
        Change::Rekey => [V0, V0, V0, V0],
        // 改类：M5 的商品关联不再唯一，候选修复取当前行，但会改变事实未变日期上的历史答案（G9），不自动发布
        Change::Reclass => [V0, V0, V0, "unavailable"],
    }
}

async fn scenarios(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    // 默认 2 万行；AGENTDB_SCENARIO_ROWS 可改为评测规模（如 1000000）检查阈值、回滚与耗时
    let rows = std::env::var("AGENTDB_SCENARIO_ROWS").ok().and_then(|v| v.parse().ok()).unwrap_or(20_000);
    admin.query(QKind::Meta, &metricbench::fixture(rows)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    admin.query(QKind::Meta, "create schema mavra_learn").await?;
    for t in ["date_dim", "item", "store_sales", "store_returns", "catalog_sales"] {
        admin.query(QKind::Meta, &format!("create table mavra_learn.{t} as table public.{t}; analyze mavra_learn.{t}")).await?;
    }
    let v1 = scenario::fingerprint(&admin).await?;
    let learn = Period::month(2001, 3);
    let asks = [Ask::Single { period: Period::month(2002, 9) }, Ask::RankMonth { year: 2002 }];
    let gold = |id: &str, a: &Ask| match a {
        Ask::Single { period } => metricbench::gold_period(id, period),
        Ask::RankMonth { year } => metricbench::gold_rank(id, *year),
        _ => unreachable!(),
    };
    let mut out = vec![];
    let mut problems = vec![];
    for maint in [Maint::Condition, Maint::Definition] {
        let db = Arc::new(Db::connect(url, 4, true)?);
        let cfg = MiddleConfig {
            name: maint.name().into(),
            version_ttl_ms: 0,
            metric_maint: maint,
            cond_reuse: maint == Maint::Condition,
            g8_snapshot: Some("mavra_learn".into()),
            ..Default::default()
        };
        let mid = Middle::new(db, cfg).await?;
        let seed = Ctx::new("A", "seed", "seed");
        for (id, m) in seeded_metrics() {
            let v = mid.seed_metric(&seed, m, Ask::Single { period: learn }, 2, &metricbench::gold_period(id, &learn)).await?;
            ensure!(v["promoted"] == true, "{} 下 {id} 未晋升：{v}", maint.name());
        }
        let checkpoint = mid.checkpoint();
        for ch in scenario::ALL.into_iter().chain([Change::Reclass]) {
            let truth = ch.apply_truth(&admin).await?;
            // 标准答案在只改变数据表示的部分之前计算
            let mut expect = BTreeMap::new();
            for (id, _) in seeded_metrics() {
                for (i, a) in asks.iter().enumerate() {
                    expect.insert((id, i), admin.query(QKind::Meta, &gold(id, a)).await?.cell(0, 0).unwrap_or("NULL").to_string());
                }
            }
            let hidden = ch.apply_hidden(&admin).await?;
            mid.invalidate_versions();
            let ctx = Ctx::new("B", ch.name(), "use");
            let mut got = vec![];
            let mut served = vec![];
            for (id, m) in seeded_metrics() {
                let v = mid.use_metric(&ctx, &format!("metric:{}", m.name)).await?;
                let status = match v["status"].as_str() {
                    Some("valid") => format!("valid{}", v["revision"]),
                    Some(s) => s.to_string(),
                    None => "?".into(),
                };
                if status.starts_with("valid") {
                    let m: Metric = serde_json::from_value(v["metric"].clone())?;
                    for (i, a) in asks.iter().enumerate() {
                        let sql = metric::compile(&m, a)?;
                        let value = admin.query(QKind::Meta, &sql).await?.cell(0, 0).unwrap_or("NULL").to_string();
                        let dec = if matches!(a, Ask::RankMonth { .. }) { 0 } else { 2 };
                        let ok = metric::same_value(&metric::parse_answer(&value), &metric::parse_answer(&expect[&(id, i)]), dec);
                        served.push(json!({"metric": id, "ask": i, "value": value, "gold": expect[&(id, i)], "ok": ok}));
                        // 金额单位变化是漏检边界：此时口径仍被提供且答错是预期结果
                        if !ok && ch != Change::Unit {
                            problems.push(format!("{} {} {id}：提供的口径答错 {value} ≠ {}", maint.name(), ch.name(), expect[&(id, i)]));
                        }
                    }
                }
                got.push(status);
            }
            let want = expected(ch);
            if got != want {
                problems.push(format!("{} {}：维护结果 {got:?}，预期 {want:?}", maint.name(), ch.name()));
            }
            let events = mid.take_metric_events();
            let t = std::time::Instant::now();
            ch.reset(&admin).await?;
            scenario::ensure_v1(&admin, &v1, ch.name()).await?;
            mid.restore(&checkpoint).await?;
            out.push(json!({"maint": maint.name(), "change": ch.name(), "rows": [truth, hidden], "got": got, "want": want,
                            "served": served, "events": events, "reset_seconds": t.elapsed().as_secs_f64()}));
        }
    }
    let report = json!({"status": if problems.is_empty() { "passed" } else { "failed" }, "problems": problems, "runs": out});
    ensure!(problems.is_empty(), "场景预期不符：{problems:#?}\n{}", serde_json::to_string_pretty(&report)?);
    Ok(report)
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_change_scenarios() -> Result<()> {
    database_case("scenario", 3600, |url| Box::pin(async move { scenarios(&url).await })).await
}

/// P0-1 与 P0-2 契约回归：
/// 1. 无保留学习快照（summary-only）下：源期间未变动的合法维表拉链修复通过物化摘要准入，篡改未触及历史答案的改类被 G9 拦截，
///    源期间自身发生重述或摘要证据缺失时拒绝自动发布（Fail-Closed，绝不跳过 HistInv 或退化到当前数据）；
/// 2. 同一快照版本下并发执行不同请求期间：已覆盖的 2025 与 2026 年共享表级约束结论并返回精确值，未覆盖的 2028 年被期间覆盖检查拒绝，
///    即使开启 EmptyRule::Zero 也不会误用 2025 年的缓存结论静默返回 0。
async fn repair_and_period_contracts(url: &str) -> Result<Value> {
    let admin = Db::connect(url, 2, false)?;
    admin.query(QKind::Meta, &metricbench::fixture(10_000)).await?;
    etl::setup(&admin).await?;
    scenario::setup(&admin).await?;
    catalog::install_tx_versions(&admin, &["date_dim", "item", "store_sales", "store_returns"]).await?;
    let v1 = scenario::fingerprint(&admin).await?;
    let learn = Period::month(2001, 3);
    let db = Arc::new(Db::connect(url, 6, true)?);
    let cfg = MiddleConfig {
        name: "contracts".into(),
        snapshot_exec: true,
        cond_reuse: true,
        result_cache: false,
        version_ttl_ms: 0,
        metric_maint: Maint::Condition,
        ..Default::default()
    };
    let mid = Middle::new(db, cfg).await?;
    let seed = Ctx::new("A", "contracts", "seed");
    let user = Ctx::new("B", "contracts", "use");
    let (_, mut m1) = seeded_metrics().into_iter().find(|(id, _)| *id == "M1").context("missing M1")?;
    m1.empty = EmptyRule::Zero;
    let (_, m5) = seeded_metrics().into_iter().find(|(id, _)| *id == "M5").context("missing M5")?;
    let s1 = mid.seed_metric(&seed, m1.clone(), Ask::Single { period: learn }, 2, &metricbench::gold_period("M1", &learn)).await?;
    let s5 = mid.seed_metric(&seed, m5.clone(), Ask::Single { period: learn }, 2, &metricbench::gold_period("M5", &learn)).await?;
    ensure!(s1["promoted"] == true && s5["promoted"] == true, "initial seed failed: {s1} / {s5}");
    let checkpoint = mid.checkpoint();

    // (P0-2) 同快照并发不同期间：date_dim 覆盖 2000..2002，不覆盖 2028
    let ask_2001 = json!({"key": s1["key"], "revision": 0, "ask": Ask::Single { period: Period { year: 2001, m1: 1, m2: 12 } }});
    let ask_2002 = json!({"key": s1["key"], "revision": 0, "ask": Ask::Single { period: Period { year: 2002, m1: 1, m2: 12 } }});
    let ask_2028 = json!({"key": s1["key"], "revision": 0, "ask": Ask::Single { period: Period { year: 2028, m1: 1, m2: 12 } }});
    let (r2001, r2002, r2028) = tokio::join!(
        mid.call_tool(&user, "run_metric", &ask_2001),
        mid.call_tool(&user, "run_metric", &ask_2002),
        mid.call_tool(&user, "run_metric", &ask_2028),
    );
    let (r2001, r2002, r2028) = (r2001?, r2002?, r2028?);
    ensure!(r2001.get("rejected").is_none() && r2002.get("rejected").is_none(), "covered years must succeed: {r2001} / {r2002}");
    ensure!(
        r2028["rejected"] == true && r2028["reason"].as_str().unwrap_or("").contains("2028"),
        "uncovered year 2028 must be rejected instead of returning 0: {r2028}"
    );
    ensure!(mid.stats_json()["snapshot_exec"]["checks_reused"].as_u64().unwrap_or(0) > 0, "table checks must still share across periods");

    // (P0-1a) 无保留学习快照：维表拉链（源期间未变、历史一致）通过物化摘要自动修复
    mid.take_metric_events();
    Change::DimHistory.apply_truth(&admin).await?;
    Change::DimHistory.apply_hidden(&admin).await?;
    mid.invalidate_versions();
    let dim_ok = mid.use_metric(&user, &format!("metric:{}", m5.name)).await?;
    let events_dim = mid.take_metric_events();
    ensure!(dim_ok["status"] == "valid" && dim_ok["revision"] == 1, "summary-backed DimHistory repair must promote: {dim_ok}");
    ensure!(
        events_dim.iter().any(|e| e["event"] == "history_checked" && e["source"] == "summary")
            && !events_dim.iter().any(|e| e["event"] == "history_skipped"),
        "HistInv must run from persisted summary and never skip: {events_dim:?}"
    );
    Change::DimHistory.reset(&admin).await?;
    scenario::ensure_v1(&admin, &v1, "contracts_dimhist").await?;
    mid.restore(&checkpoint).await?;

    // (P0-1b) 无保留学习快照：仅对 2001-03 未售出的商品改类，使修复候选在源期间 2001-03 上完全复现源答案（G8 通过），
    // 但篡改后续未变动事实桶的历史答案，专门验证物化摘要上的 G9（HistInv）独立拦截该错误修复
    mid.take_metric_events();
    let post_learn_items = "i_item_sk % 3 = 0 and i_is_current = 'Y' and i_item_sk not in \
        (select ss_item_sk from store_sales join date_dim on ss_sold_date_sk = d_date_sk where d_year = 2001 and d_moy = 3)";
    admin
        .query(
            QKind::Meta,
            &format!(
                "insert into item (i_item_sk, i_category, i_current_price, i_is_current) \
                 select i_item_sk, i_category, i_current_price, 'N' from item where {post_learn_items}; \
                 update item set i_category = (array['家居','服装','电子','食品','运动'])[1 + (i_item_sk + 1) % 5] \
                 where {post_learn_items}; \
                 select pg_stat_force_next_flush(); insert into etl_batch_log values ('item', 99); analyze item"
            ),
        )
        .await?;
    mid.invalidate_versions();
    let reclass_rej = mid.use_metric(&user, &format!("metric:{}", m5.name)).await?;
    let events_reclass = mid.take_metric_events();
    ensure!(reclass_rej["status"] == "unavailable", "summary-backed post-learn Reclass must be blocked: {reclass_rej}");
    ensure!(
        events_reclass.iter().any(|e| {
            e["event"] == "repair_rejected"
                && e["failed_gate"] == "G9"
                && e["gates"].as_array().is_some_and(|gs| gs.iter().any(|g| g["gate"] == "G8" && g["pass"] == true))
        }),
        "post-learn Reclass must pass G8 yet fail at G9 (HistInv) via summary: {events_reclass:?}"
    );
    admin
        .query(
            QKind::Meta,
            "update item cur set i_category = old.i_category from item old \
             where cur.i_item_sk = old.i_item_sk and cur.i_is_current = 'Y' and old.i_is_current = 'N'; \
             delete from item where i_is_current = 'N'; \
             delete from etl_batch_log where batch_id = 99; analyze item",
        )
        .await?;
    scenario::ensure_v1(&admin, &v1, "contracts_reclass").await?;
    mid.restore(&checkpoint).await?;

    // (P0-1c) 无保留学习快照：源期间 2001-03 自身被重述（Change::Revision）时拒绝自动发布（Fail-Closed）
    mid.take_metric_events();
    Change::Revision.apply_truth(&admin).await?;
    Change::Revision.apply_hidden(&admin).await?;
    mid.invalidate_versions();
    let rev_rej = mid.use_metric(&user, &format!("metric:{}", m1.name)).await?;
    let events_rev = mid.take_metric_events();
    ensure!(rev_rej["status"] == "unavailable", "mutated source period without snapshot must fail closed: {rev_rej}");
    ensure!(
        events_rev.iter().any(|e| e["event"] == "repair_rejected" && e["failed_gate"] == "G8"),
        "mutated source period must fail closed at G8: {events_rev:?}"
    );
    Change::Revision.reset(&admin).await?;
    scenario::ensure_v1(&admin, &v1, "contracts_revision").await?;

    Ok(json!({
        "status": "passed",
        "period_2028_rejected": r2028["reason"],
        "summary_dimhist_revision": dim_ok["revision"],
        "summary_reclass_blocked": true,
        "mutated_source_fail_closed": true,
    }))
}

#[tokio::test]
#[ignore = "requires AGENTDB_TEST_URL and PostgreSQL 16+ with CREATE DATABASE permission"]
async fn postgres_repair_and_period_contracts() -> Result<()> {
    database_case("contracts", 180, |url| Box::pin(async move { repair_and_period_contracts(&url).await })).await
}
