mod bench;
mod catalog;
mod checks;
mod db;
mod etl;
mod feedback;
mod flight;
#[cfg(test)]
mod integration_tests;
mod knowledge;
mod llm;
mod metric;
mod middle;
#[cfg(test)]
mod q5_bench_tests;
mod server;
mod sqlscan;
mod sqlscope;
mod timing;

pub(crate) use bench::{bindingbench, maintbench, metricbench, replaybench, scenario, specchange, tpcds, workloadbench};

use anyhow::Result;
use clap::{Parser, Subcommand};
use db::Db;
use middle::Middle;
use std::sync::Arc;

const DEFAULT_DB_URL: &str = "postgres://postgres:postgres@127.0.0.1:5432/mavra";

#[derive(Parser)]
#[command(name = "mavra", version, about = "MAVRA: Sharing and Maintaining Executable Knowledge for Data Agents")]
struct Cli {
    /// PostgreSQL connection URL (falls back to AGENTDB_URL, then localhost:5432/mavra)
    #[arg(long, env = "MAVRA_DB_URL")]
    db: Option<String>,
    /// Read-only query connection pool size
    #[arg(long, default_value_t = 16, value_parser = positive_usize)]
    pool: usize,
    /// Output directory for benchmark reports and traces
    #[arg(long, default_value = "results")]
    out: String,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// End-to-end metric extraction, cross-agent reuse, and post-update maintenance benchmark (LLM + isolated PostgreSQL DB)
    MetricBench(Box<metricbench::Options>),
    /// Controlled maintenance-policy benchmark comparing revoke, schema-only, definition-level, and condition-level validation (LLM-free)
    MaintBench(maintbench::Options),
    /// Paired policy replay over archived definition libraries and 12 data-change scenarios (LLM-free)
    ReplayBench(replaybench::Options),
    /// Admission-gate and unseen-parameter compilation accuracy benchmark across 39 periods (LLM-free)
    BindingBench(bindingbench::Options),
    /// Concurrent multi-session agent workload characterization benchmark (LLM + isolated PostgreSQL DB)
    WorkloadBench(workloadbench::Options),
    /// Initialize idempotent synthetic-retail status column and ETL batch table
    Setup,
    /// Simulate synthetic-retail ETL schema/granularity transition: apply-v2 | reset | status
    Etl {
        #[arg(value_parser = ["apply-v2", "reset", "status"])]
        action: String,
    },
    /// Start the MAVRA HTTP tool middleware service
    Serve {
        /// Listen address for HTTP tool endpoints
        #[arg(long, default_value = "127.0.0.1:8088")]
        addr: String,
        /// Runtime configuration profile (e.g., full, metric-global-full, middle-alone, relbench-mavra)
        #[arg(long, default_value = "full")]
        mode: String,
        /// Skip synthetic-retail ETL fixture initialization (use for TPC-DS, TPC-H, SSB, BIRD, or RelBench schemas)
        #[arg(long)]
        no_etl: bool,
        /// LLM provider profile for /v1/learn_features extraction (openai | deepseek | zhipu | anthropic)
        #[arg(long)]
        extractor: Option<String>,
    },
}

fn positive_usize(s: &str) -> std::result::Result<usize, String> {
    s.parse::<usize>().ok().filter(|n| *n > 0).ok_or_else(|| "must be a positive integer".into())
}

pub(crate) fn resolve_db_url(explicit: Option<String>) -> String {
    explicit
        .filter(|v| !v.trim().is_empty())
        .or_else(|| std::env::var("MAVRA_DB_URL").ok().filter(|v| !v.trim().is_empty()))
        .or_else(|| std::env::var("AGENTDB_URL").ok().filter(|v| !v.trim().is_empty()))
        .unwrap_or_else(|| DEFAULT_DB_URL.into())
}

#[cfg(test)]
pub(crate) fn resolve_env(primary: &str, legacy: &str) -> Option<String> {
    std::env::var(primary).ok().filter(|v| !v.trim().is_empty()).or_else(|| std::env::var(legacy).ok().filter(|v| !v.trim().is_empty()))
}

fn main() -> Result<()> {
    let _ = dotenvy::dotenv();
    let cli = Cli::parse();
    const STACK_BYTES: usize = 16 * 1024 * 1024;
    std::thread::Builder::new()
        .name("mavra-main".into())
        .stack_size(STACK_BYTES)
        .spawn(move || {
            let rt = tokio::runtime::Builder::new_multi_thread().thread_stack_size(STACK_BYTES).enable_all().build()?;
            rt.block_on(async_main(cli))
        })?
        .join()
        .map_err(|e| anyhow::anyhow!("mavra runtime panicked: {e:?}"))?
}

async fn async_main(cli: Cli) -> Result<()> {
    let db_url = resolve_db_url(cli.db);
    let db = Arc::new(Db::connect(&db_url, cli.pool, true)?);
    let admin = Arc::new(Db::connect(&db_url, 2, false)?);
    match cli.cmd {
        Cmd::MetricBench(options) => metricbench::run(&db_url, cli.pool, &cli.out, *options).await?,
        Cmd::MaintBench(options) => maintbench::run(&db_url, cli.pool, &cli.out, options).await?,
        Cmd::ReplayBench(options) => replaybench::run(&db_url, cli.pool, &cli.out, options).await?,
        Cmd::BindingBench(options) => bindingbench::run(&db_url, &cli.out, options).await?,
        Cmd::WorkloadBench(options) => workloadbench::run(&db_url, cli.pool, &cli.out, options).await?,
        Cmd::Setup => {
            etl::setup(&admin).await?;
            eprintln!("Setup complete.");
        }
        Cmd::Etl { action } => {
            etl::setup(&admin).await?;
            match action.as_str() {
                "apply-v2" => eprintln!("Applied ETL v2 ({} status rows inserted).", etl::apply_v2(&admin).await?),
                "reset" => {
                    etl::reset(&admin).await?;
                    eprintln!("Reset to ETL v1.");
                }
                "status" => eprintln!("Current ETL state: {}", if etl::is_v2(&admin).await? { "v2 (status log)" } else { "v1" }),
                _ => anyhow::bail!("unknown action {action} (expected apply-v2 | reset | status)"),
            }
        }
        Cmd::Serve { addr, mode, no_etl, extractor } => {
            if !no_etl {
                etl::setup(&admin).await?;
            }
            let mut cfg = middle::profile(&mode).0;
            cfg.verbose = true;
            if cfg.snapshot_exec {
                match catalog::Catalog::load(&admin).await {
                    Ok(cat) => {
                        let names: Vec<&str> = cat.tables.keys().map(String::as_str).collect();
                        if let Err(err) = catalog::install_tx_versions(&admin, &names).await {
                            eprintln!(
                                "warning: failed to install mavra_versions triggers ({err:#}); disabling snapshot_exec for this session"
                            );
                            cfg.snapshot_exec = false;
                        }
                    }
                    Err(err) => {
                        eprintln!("warning: catalog load for trigger setup failed ({err:#}); disabling snapshot_exec");
                        cfg.snapshot_exec = false;
                    }
                }
            }
            let mid = Arc::new(Middle::new(db, cfg).await?);
            let extractor = extractor.map(|k| llm::Provider::from_env(&k)).transpose()?;
            server::serve(mid, extractor, &addr).await?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn invalid_options_fail_before_database_access() {
        for args in [
            vec!["mavra", "--pool", "0", "serve"],
            vec!["mavra", "etl", "typo"],
            vec!["mavra", "maint-bench", "--agents", "0"],
            vec!["mavra", "llm"],
        ] {
            assert!(Cli::try_parse_from(&args).is_err(), "{args:?}");
        }
    }

    #[test]
    fn defaults_are_valid() {
        for cmd in ["setup", "serve", "metric-bench", "maint-bench", "workload-bench"] {
            assert!(Cli::try_parse_from(["mavra", cmd]).is_ok(), "{cmd}");
        }
        for args in [
            vec!["mavra", "replay-bench", "--libs", "a.json"],
            vec![
                "mavra",
                "replay-bench",
                "--defs",
                "exp/population-sharing/tpcds-defs.json",
                "--schema",
                "tpcds",
                "--tpcds-db",
                "tpcds_sf1",
            ],
            vec!["mavra", "binding-bench", "--cells", "results/scen"],
            vec!["mavra", "binding-bench", "--defs", "exp/population-sharing/tpcds-defs.json", "--rows", "200000"],
            vec!["mavra", "workload-bench", "--agent", "deepseek", "--concurrency", "3", "--rounds", "2"],
            vec!["mavra", "metric-bench", "--population", "--pop-agents", "16", "--pop-questions", "7"],
        ] {
            assert!(Cli::try_parse_from(&args).is_ok(), "{args:?}");
        }
    }
}
