# System Architecture and Source Map

**MAVRA** (**M**etric-**A**ware **V**alidation and **R**euse for **A**gents) is a stateful Rust middleware between LLM data agents and PostgreSQL. Instead of replaying unverified text trajectories or static SQL snippets, MAVRA extracts executable metric and point-in-time predictive feature definitions paired with explicit data-validity checks, resolves incoming requests with calibrated abstention, executes compiled queries inside `REPEATABLE READ` snapshots, and maintains or certifiably repairs definitions when underlying tables change.

---

## 1. Core System Components

1. **Knowledge Cache (`src/knowledge.rs`, `src/checks.rs`, `src/middle/mod.rs`)**
   - Stores immutable, versioned analytical `Metric` definitions, verified `JoinPath` and negative `BadPath` records, point-in-time `EntityRef` predictive features, task programs (`program:<task>`), and a table-version-indexed check verdict cache (`snap_verdicts`).
2. **Knowledge Extractor (`src/middle/metrics.rs`, `src/middle/features.rs`, `src/sqlscan.rs`)**
   - Traces exploratory SQL executions, probes candidate joins and near-unique grain predicates, canonicalizes SQL ASTs and aliases (`sqlparser`), and enforces multi-stage admission gates before publication:
     - **Analytical metric gates (`G1`–`G7`)**: source traceability and chain verification (`G1`/`G2`/`G5`/`G6`), structural and parameter completeness (`G3`/`G4`), and deterministic recompilation equivalence on the source snapshot (`G7`).
     - **Predictive feature gates (`F1`–`F4`)**: structural grain/type validation, `2,000`-entity sample execution, and `5,000`-seed time-censored temporal leakage audits under masked PostgreSQL `search_path` schemas.
3. **Adaptive Semantic Lookup (`src/middle/metrics.rs`, `tools/lookup/`)**
   - Resolves natural-language metric requests via an alias cache, dense candidate recall (`BAAI/bge-m3`), and three 12-layer `XLM-RoBERTa` peer-difference cross-encoders (`BAAI/bge-reranker-base` backbone) with `(0.1, 0.9)` thresholds and routing checks into four outcomes:
     - `Hit` — single high-confidence match compiled directly without LLM disambiguation;
     - `Diffs` — structural parameter differences surfaced explicitly;
     - `Refer` — ambiguous/multi-formula candidates narrowed for lightweight agent confirmation;
     - `Miss` — absent metric routed cleanly to guided SQL exploration.
   - When `MAVRA_LOOKUP_URL` points to `tools/lookup/service.py`, `find_metric` uses neural resolution; when unset, it uses deterministic local name/alias resolution.
4. **Snapshot-Bound Query Executor (`src/db.rs`, `src/catalog.rs`, `src/flight.rs`, `src/metric.rs`, `src/sqlscope.rs`)**
   - Binds condition validation and compiled SQL execution inside a single `REPEATABLE READ READ ONLY` PostgreSQL transaction (`CheckAndRun`) to eliminate check-then-execute TOCTOU races under concurrent writes.
   - Tracks table mutations via 16-shard transactional triggers (`mavra_versions`, sharded by `pg_backend_pid() % 16`) and coalesces concurrent identical checks via single-flight `OnceCell` coordination (`src/flight.rs`).
   - Compiles point-in-time predictive features with `LATERAL` scan fusion (`compose_features`) and guards exploratory `run_sql` calls against known `BadPath` fan-outs and grain violations (`src/sqlscope.rs`).
5. **Maintenance Manager & Certified Repair (`src/middle/metrics.rs`, `src/middle/optimize.rs`)**
   - Evaluates only the data conditions (`KeyUnique`, `DistinctKeyUnique`, `RowConservation`, `PathCoverage`, `DateCoverage`, `NotNull`, `MeasureScale`) whose input table versions advanced, sharing check verdicts across all definitions that depend on the same condition.
   - When an integrity break invalidates a condition, searches restricted single-edit repairs (exact-row deduplication, date-key alias rebinding, low-cardinality status/type equality filters) and publishes a new revision only if a **unique** candidate passes all structural checks, source replay (`G8`), and untouched-bucket historical invariance (`G9` via retained snapshot or 128-bit multiset digest `HistorySummary`). Ambiguous repairs or out-of-scope semantic drifts escalate to guided exploration.

---

## 2. Repository Source Map

All paths are relative to the repository root.

### Core Middleware (`src/` and `src/middle/`)

| Path | Responsibility |
| --- | --- |
| [`src/main.rs`](../src/main.rs) | CLI entry point (`mavra`): `serve`, `setup`, `etl`, and benchmark subcommands |
| [`src/server.rs`](../src/server.rs) | Asynchronous `axum` HTTP/JSON middleware endpoints (`/v1/*`) |
| [`src/db.rs`](../src/db.rs), [`src/etl.rs`](../src/etl.rs) | PostgreSQL connection pool, `REPEATABLE READ` snapshot binding, 16-shard `mavra_versions` triggers, and synthetic retail ETL transitions |
| [`src/flight.rs`](../src/flight.rs), [`src/timing.rs`](../src/timing.rs) | Single-flight concurrent check coalescing and task-local latency/SQL attribution |
| [`src/catalog.rs`](../src/catalog.rs), [`src/checks.rs`](../src/checks.rs) | Schema/join/grain catalog, table version stamps, and data-condition SQL generation |
| [`src/sqlscan.rs`](../src/sqlscan.rs), [`src/sqlscope.rs`](../src/sqlscope.rs) | `sqlparser` AST canonicalization, alias normalization, and query-scoped grain uniqueness proofs |
| [`src/metric.rs`](../src/metric.rs), [`src/knowledge.rs`](../src/knowledge.rs) | Executable metric/feature ASTs, `HistorySummary` digests, deterministic SQL & `LATERAL` feature compilation, and versioned knowledge store |
| [`src/feedback.rs`](../src/feedback.rs) | Repair candidate pruning and structured check-failure diagnostics |
| [`src/llm.rs`](../src/llm.rs) | Multi-provider LLM client (`openai`, `deepseek`, `zhipu`, `anthropic`) with tool-calling loop and token accounting |
| [`src/middle/mod.rs`](../src/middle/mod.rs) | Middleware coordinator, shared check cache, and agent tool dispatch |
| [`src/middle/profiles.rs`](../src/middle/profiles.rs) | Named runtime profiles shared by `mavra serve --mode` and evaluation runners |
| [`src/middle/metrics.rs`](../src/middle/metrics.rs) | Admission gates (`G1`–`G7`), semantic lookup hook, condition-level lazy validation, and certified repair (`G8`–`G9`) |
| [`src/middle/features.rs`](../src/middle/features.rs) | Point-in-time predictive feature admission (`F1`–`F4`), `LATERAL` fusion, and temporal leakage audits |
| [`src/middle/optimize.rs`](../src/middle/optimize.rs) | Equivalent query optimization verification and revision publication |
| [`src/integration_tests.rs`](../src/integration_tests.rs) | Isolated PostgreSQL & HTTP correctness regressions (`make db-test`) |
| [`src/q5_bench_tests.rs`](../src/q5_bench_tests.rs) | Self-contained Q5 scalability, concurrency, TOCTOU snapshot-binding, sustained-write trigger, and repair-ambiguity benchmarks |

### Benchmark Harnesses & Tooling (`src/bench/` and `tools/`)

| Path | Responsibility |
| --- | --- |
| [`src/bench/metricbench.rs`](../src/bench/metricbench.rs) | End-to-end multi-agent analytical sharing (Q1) and 11-update evaluation (Q3) (`metric-bench`) |
| [`src/bench/maintbench.rs`](../src/bench/maintbench.rs) | Controlled maintenance policy comparison without LLM calls (`maint-bench`) |
| [`src/bench/replaybench.rs`](../src/bench/replaybench.rs) | Paired 4-schema, 12-update maintenance policy & repair ablation replay (`replay-bench`) |
| [`src/bench/bindingbench.rs`](../src/bench/bindingbench.rs) | Unseen parameter-binding compilation accuracy & gate ablation (`binding-bench`) |
| [`src/bench/workloadbench.rs`](../src/bench/workloadbench.rs) | Memoryless agent exploration profiler (`workload-bench`) |
| [`src/bench/scenario.rs`](../src/bench/scenario.rs), [`src/bench/specchange.rs`](../src/bench/specchange.rs), [`src/bench/tpcds.rs`](../src/bench/tpcds.rs) | Synthetic retail, TPC-DS, TPC-H, SSB, and BIRD `financial` workload definitions and 12-class data mutations |
| [`tools/lookup/`](../tools/lookup/README.md) | Neural semantic lookup HTTP service (`BAAI/bge-m3` + 3-model `XLM-RoBERTa` peer-difference cross-encoders) |
| [`tools/relbench/`](../tools/README.md) | Multi-cutoff RelBench predictive feature reuse harness, external baseline adapters, and offline unit tests |
| [`tools/figures/`](../tools/README.md) | Standalone vector figure and summary table generators (`make figures`) |

---

## 3. HTTP Middleware Interface (`mavra serve`)

`mavra serve` exposes six JSON endpoints on `--addr` (default `127.0.0.1:8088`):

| Method & Path | Description |
| --- | --- |
| `GET /v1/tools` | Returns JSON Schemas for tools exposed under the active `--mode` profile (`list_tables`, `describe_table`, `run_sql`, `join_path`, `check_join`, `find_metric`, `run_metric`). |
| `POST /v1/tools/:name` | Executes tool `:name` inside an agent context `{"agent": "...", "session": "...", "task": "...", "tables": [...], "args": {...}}`. |
| `GET /v1/knowledge` | Exports active and historical metric definitions, join paths, negative `BadPath` entries, and revision metadata. |
| `GET /v1/stats` | Returns cumulative check counts, cache hit rates, coalesced flight counts, and database/validation latencies. |
| `POST /v1/learn_features` | Extracts, leak-audits (`F1`–`F4`), and publishes point-in-time predictive features from a completed exploration trace (requires `--extractor <profile>` and a feature-enabled `--mode` such as `relbench-mavra`). |
| `GET /v1/features` | Lists admitted point-in-time `EntityRef` feature definitions and task programs. |

### Key Runtime Profiles (`--mode`)

| Profile | Capabilities Enabled |
| --- | --- |
| `full` / `metric-global-full` | Full MAVRA stack: shared metric catalog, admission gates `G1`–`G7`, condition-level validation cache, certified repair `G8`–`G9`, equivalence optimization, and `REPEATABLE READ` snapshot-bound execution (`mavra_versions`). |
| `relbench-mavra` | Predictive feature catalog (`F1`–`F4`), temporal leakage audit, `LATERAL` feature fusion, and task-program reuse for RelBench. |
| `metric-global-recheck` | Ablation baseline: shared definitions with per-definition full recheck and no automatic repair (`Shared recheck`). |
| `metric-global-schema` / `metric-global-revoke` | Ablation baselines: `Schema check only` and `Write invalidate`. |
| `metric-private` | Ablation baseline: per-agent isolated metric memory (`Single-agent memory`). |
| `middle-alone` / `direct` | SQL exploration guardrails without metric memory (`middle-alone`) or raw SQL pass-through (`direct`). |
