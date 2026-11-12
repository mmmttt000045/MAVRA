# Source Map

All paths are relative to the repository root.

## Core System (`src/` and `src/middle/`)

| Path | Responsibility |
| --- | --- |
| `src/main.rs` | CLI entry point (`agentdb-mid`): `serve`, `setup`, `etl`, and benchmark subcommands |
| `src/server.rs` | Asynchronous `axum` HTTP/JSON tool interface |
| `src/db.rs`, `src/etl.rs` | PostgreSQL connection pool, `REPEATABLE READ` snapshot binding, sharded `mavra_versions` triggers, and `etl_batch_log` |
| `src/flight.rs`, `src/timing.rs` | Single-flight concurrent check coalescing and task-local latency/SQL attribution |
| `src/catalog.rs`, `src/checks.rs` | Schema/join/grain catalog, table version stamps, and structural/value check SQL generation |
| `src/sqlscan.rs`, `src/sqlscope.rs` | `sqlparser` AST canonicalization, alias normalization, and query-scoped grain uniqueness proofs |
| `src/metric.rs`, `src/knowledge.rs` | Executable definition representation $m^r = (B,I,C,E,r)$, deterministic SQL compilation, and persistent store $(M, \mathcal{H})$ |
| `src/feedback.rs` | Candidate pruning and check failure feedback |
| `src/llm.rs`, `src/agentmem.rs` | OpenAI/DeepSeek-compatible LLM client and per-agent/shared text-memory baseline adapters |
| `src/middle/mod.rs` | Stateless middleware coordinator and agent tool dispatch |
| `src/middle/metrics.rs` | Admission gates (G1–G7), version-coalesced validation, history-preserving repair, and snapshot execution |
| `src/middle/features.rs` | Point-in-time predictive feature admission, `LATERAL` fusion, and time-censored leakage audits |
| `src/middle/optimize.rs` | Equivalent candidate verification and revision publication |
| `src/integration_tests.rs` | End-to-end PostgreSQL and HTTP lifecycle, concurrency, and repair regression tests |

## Evaluation Suite (`src/bench/`)

| Path | Responsibility |
| --- | --- |
| `src/bench/metricbench.rs` | End-to-end multi-agent analytical sharing and post-update evaluation (`metric-bench`) |
| `src/bench/maintbench.rs` | Controlled maintenance policy comparison (`maint-bench`) |
| `src/bench/replaybench.rs` | Paired four-schema, twelve-update maintenance policy replay (`replay-bench`) |
| `src/bench/bindingbench.rs` | Unseen parameter-binding compilation accuracy benchmark (`binding-bench`) |
| `src/bench/workloadbench.rs` | Memoryless agent exploration and probe-target workload profiler (`workload-bench`) |
| `src/bench/scenario.rs`, `specchange.rs`, `tpcds.rs` | Synthetic retail, TPC-DS, TPC-H, SSB, and BIRD `financial` workload definitions and data mutations |
