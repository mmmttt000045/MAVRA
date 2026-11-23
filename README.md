# MAVRA: Sharing and Maintaining Executable Knowledge for Data Agents

[![CI](https://github.com/mmmttt000045/MAVRA/actions/workflows/ci.yml/badge.svg)](https://github.com/mmmttt000045/MAVRA/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/Rust-1.75%2B-orange.svg)](Cargo.toml)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B-336791.svg)](https://www.postgresql.org/)

**MAVRA** (**M**etric-**A**ware **V**alidation and **R**euse for **A**gents) is a stateful Rust middleware between LLM data agents and PostgreSQL that turns ad-hoc agent SQL exploration into shared, snapshot-validated, and self-maintaining executable definitions. Rather than caching brittle natural-language trajectories or unverified SQL strings, MAVRA admits structured analytical metrics and point-in-time predictive features together with explicit data invariants, resolves new requests with calibrated selective abstention, executes compiled queries inside `REPEATABLE READ` database snapshots, and certifiably repairs definitions when underlying tables change.

---

## System Overview

MAVRA sits on the tool path between heterogeneous data agents and PostgreSQL through five coordinated mechanisms (detailed in [`docs/architecture.md`](docs/architecture.md)):

1. **Knowledge Cache (`src/knowledge.rs`, `src/checks.rs`)** — Stores immutable, versioned analytical `Metric` definitions, verified `JoinPath` and negative `BadPath` records, point-in-time `EntityRef` predictive features, task programs, and a table-version-indexed check verdict cache shared across concurrent sessions.
2. **Gate-Verified Knowledge Extractor (`src/middle/metrics.rs`, `src/middle/features.rs`, `src/sqlscan.rs`)** — Probes candidate joins and grain predicates, canonicalizes SQL ASTs (`sqlparser`), and enforces multi-stage admission gates before any definition enters the catalog:
   - *Analytical gates (`G1`–`G7`)*: source traceability and arithmetic chain verification (`G1`/`G2`/`G5`/`G6`), structural and parameter completeness (`G3`/`G4`), and deterministic recompilation equivalence on the source snapshot (`G7`).
   - *Predictive feature gates (`F1`–`F4`)*: entity-grain validation, `2,000`-entity sample execution, and `5,000`-seed time-censored temporal leakage audits under masked PostgreSQL `search_path` schemas.
3. **Adaptive Semantic Lookup (`src/middle/metrics.rs`, `tools/lookup/`)** — Combines an exact/alias cache, dense candidate recall (`BAAI/bge-m3`), and three 12-layer `XLM-RoBERTa` peer-difference cross-encoders with `(0.1, 0.9)` thresholds and routing checks to classify each request into `Hit` (direct SQL compilation), `Diffs` (explicit parameter adaptation), `Refer` (narrowed multi-formula disambiguation), or `Miss` (clean abstention to guided exploration).
4. **Snapshot-Bound Executor (`src/db.rs`, `src/catalog.rs`, `src/flight.rs`, `src/metric.rs`)** — Evaluates pending data checks and executes compiled SQL inside one `REPEATABLE READ READ ONLY` transaction (`CheckAndRun`) backed by 16-shard transactional version triggers (`mavra_versions`), eliminating check-then-execute TOCTOU races, coalescing concurrent checks via single-flight coordination, and fusing point-in-time predictive features via `LATERAL` joins.
5. **Condition-Level Maintenance & Certified Repair (`src/middle/metrics.rs`, `src/middle/optimize.rs`)** — Lazily re-evaluates only the data conditions (`KeyUnique`, `DistinctKeyUnique`, `RowConservation`, `PathCoverage`, `DateCoverage`, `NotNull`, `MeasureScale`) whose input table versions advanced, sharing check verdicts across definitions. On integrity breaks, MAVRA searches restricted single-edit repairs (deduplication, date-key alias rebinding, low-cardinality filters) and publishes a new revision only when a **unique** candidate passes all invariants, source replay (`G8`), and untouched-bucket historical invariance (`G9` via retained snapshot or 128-bit multiset digest `HistorySummary`).

---

## Repository Structure

| Path | Contents |
| --- | --- |
| [`src/`](src/), [`src/middle/`](src/middle/) | Core Rust middleware, HTTP server (`mavra serve`), admission/repair gates, SQL compiler, and runtime profiles |
| [`src/bench/`](src/bench/) | Analytical sharing, maintenance policy, 4-schema replay, unseen parameter-binding, and workload characterization harnesses |
| [`src/integration_tests.rs`](src/integration_tests.rs), [`src/q5_bench_tests.rs`](src/q5_bench_tests.rs) | Isolated PostgreSQL regressions (`make db-test`) and self-contained Q5 scalability/concurrency benchmarks |
| [`tools/lookup/`](tools/lookup/README.md) | Neural semantic lookup service (`BAAI/bge-m3` recall + 3-model `XLM-RoBERTa` peer-difference cross-encoders) |
| [`tools/relbench/`](tools/README.md) | Multi-cutoff RelBench predictive feature reuse harness, external baseline bridges (`ACE`, `AWM`, `G-Memory`, `TeCoD`, `FeatPilot*`), and offline tests |
| [`tools/figures/`](tools/README.md), [`tools/`](tools/README.md) | Standalone vector figure builders (`make figures`), statistics scripts, and PostgreSQL schema loaders |
| [`data/`](data/README.md) | Integration test SQL fixture ([`mock_fixture.sql`](data/mock_fixture.sql)) and dataset preparation instructions |
| [`exp/`](exp/README.md) | Curated benchmark catalogs, evaluation scripts, and aggregated summary results indexed by [`exp/catalog.json`](exp/catalog.json) |
| [`third_party/`](third_party/) | Vendored Apache-2.0 baseline components ([`ace/`](third_party/ace/README.md) and [`awm/`](third_party/awm/README.md)) |
| [`docs/`](docs/README.md) | [Architecture & Source Map](docs/architecture.md), [Reproducibility Guide](docs/reproducibility.md), and [Development Guide](docs/development.md) |

---

## Prerequisites & Build

- **Rust**: Stable toolchain (`1.75+`) with `rustfmt` and `clippy`
- **PostgreSQL**: `16+` (for database tests, middleware serving, and relational benchmarks)
- **Python**: `3.10+` (`3.12` recommended for RelBench, figure generation, and neural lookup scripts)

```bash
# 1. Build the release binary (./target/release/mavra)
cargo build --release --locked

# 2. (Optional) Start a local PostgreSQL 16 instance via Docker
docker run -d --name mavra-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16

# 3. Configure environment variables
cp .env.example .env
```

---

## 5-Minute Verification (Zero API Keys Required)

Every command below runs locally without external LLM API keys or paid services:

```bash
# 1. Offline Rust unit tests (64 offline unit tests; DB/Q5 tests gated behind --ignored), formatting, Clippy, and catalog check
cargo test --locked
python3 tools/experiment-index.py --check

# 2. Offline Python unit tests
python3 -m pip install -r tools/relbench/requirements-test.txt
python3 -m unittest discover -s tools/relbench -p "test_*.py"
python3 -m unittest discover -s exp/mechanism-studies

# 3. Isolated PostgreSQL 16+ integration regressions (creates & drops temporary DBs automatically)
export MAVRA_TEST_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres
make db-test

# 4. Deterministic maintenance policy benchmark on built-in synthetic retail data (no LLM calls)
export MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres
./target/release/mavra --db "$MAVRA_DB_URL" maint-bench --rows 50000 --agents 8

# 5. Regenerate paper vector figures & summary macros from benchmark summaries into results/
#    (Runs out-of-the-box with standard Matplotlib fonts; uses TeX Live libertine/inconsolata automatically if installed)
python3 -m pip install -r tools/figures/requirements.txt
make figures
```

---

## Reproducing Paper Results (Tables 1–6 & Figures 1–9)

Full dataset loading (`tpcds-load.sh`, `bench-load.sh`, `tools/relbench/prepare.py`) and external baseline setup (`G-Memory`, `TeCoD`) are documented step-by-step in [`data/README.md`](data/README.md) and [`docs/reproducibility.md`](docs/reproducibility.md).

| Paper Target | Evaluation Scope & Schemas | Runner / Analysis Command | LLM API? | Evaluation Suite |
| --- | --- | --- | :---: | --- |
| **Table 1**, **Fig. 1** (§1) | Workload characterization: Redset + 100 memoryless agent sessions | `./target/release/mavra workload-bench` · `python3 tools/workload-stats.py` | Live run only | [`exp/workload-characterization/`](exp/workload-characterization/README.md) |
| **Table 2**, **Figs. 2–5** (§2–§4) | Capability comparison & architecture, extraction, lookup, and repair walkthroughs | System implementation in `src/middle/{metrics,features,optimize}.rs` · `make figures` | No | [`exp/premise-optimization/`](exp/premise-optimization/README.md) |
| **Fig. 6** (Q1, §6.2) | 16 sequential agents on TPC-DS SF1 (5 runs) + append-only sales restatement | `./target/release/mavra metric-bench --population` · `python3 tools/population-stats.py --out results/gen` | Live run only | [`exp/population-sharing/`](exp/population-sharing/README.md) |
| **Table 3**, **Fig. 8** (Q2, §6.3) | Semantic lookup scaling (`26`→`1,000` definitions across 8 domains; `390` main + `92` repeated + `204` unseen requests) | `python3 exp/semantic-lookup/analyse.py` · `python3 tools/figures/lookup_scale.py` (GPU training in [`exp/semantic-lookup/`](exp/semantic-lookup/README.md)) | Optional (`Top-8+LLM`) | [`exp/semantic-lookup/`](exp/semantic-lookup/README.md), [`exp/maintenance-guards/`](exp/maintenance-guards/README.md) |
| **Fig. 7**, **Table 4** (Q3, §6.4) | 11 database updates on Synthetic Retail (1M) & TPC-H SF1 across 8 baselines/policies | `python3 exp/schema-evolution/run-study.py` · `python3 exp/maintenance-guards/served-split.py` | Live run only | [`exp/schema-evolution/`](exp/schema-evolution/README.md), [`exp/maintenance-guards/`](exp/maintenance-guards/README.md) |
| **Table 5** (Q4, §6.5) | Cross-cutoff predictive feature reuse across 6 RelBench tasks × 5 cutoffs (`rel-stack`, `rel-trial`) | `python3 tools/relbench/harness.py --arm mavra-retry` · `python3 tools/relbench/paper-stats.py --out results/gen` | Live run only (`FeatPilot*` is LLM-free) | [`exp/relbench-predictive/`](exp/relbench-predictive/README.md), [`exp/relbench-attribution/`](exp/relbench-attribution/README.md) |
| **Table 6** (Q5, §6.6) | Paired policy replay & `G8`/`G9` repair ablations across 4 schemas (`TPC-DS`, `TPC-H`, `SSB`, `financial`) × 12 update classes (`1,806` instances) + SF1/SF3/SF10 scaling | `./target/release/mavra replay-bench --libs ...` · `./target/release/mavra binding-bench --defs ...` | **No** | [`exp/policy-replay/`](exp/policy-replay/README.md), [`exp/tpcds-scaling/`](exp/tpcds-scaling/README.md), [`exp/multi-schema-generality/`](exp/multi-schema-generality/README.md) |
| **Fig. 9** & **Q5 Systems** (§6.6) | 1–32 agent shared validation scaling, `REPEATABLE READ` TOCTOU isolation, 16-shard sustained-write trigger overhead, and backup repair ambiguity | `cargo test --release --locked q5_bench_tests:: -- --ignored --nocapture --test-threads=1` | **No** | [`exp/shared-validation/`](exp/shared-validation/README.md), [`exp/cache-baseline-tpcds/`](exp/cache-baseline-tpcds/README.md), [`exp/mechanism-studies/`](exp/mechanism-studies/README.md) |

---

## Running the MAVRA HTTP Middleware Server

Launch MAVRA as a standalone HTTP tool server in front of any PostgreSQL 16+ database:

```bash
# Optional: start the neural semantic lookup sidecar (BAAI/bge-m3 + XLM-RoBERTa cross-encoders)
python3 tools/lookup/service.py --catalog exp/semantic-lookup/catalog_26.json --port 8090 &

# Start MAVRA with full snapshot-bound validation, shared condition caching, and certified repair
MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/tpcds_sf1 \
MAVRA_LOOKUP_URL=http://127.0.0.1:8090 \
  ./target/release/mavra serve --addr 127.0.0.1:8088 --mode full --no-etl
```

*(Omit `--no-etl` only when serving the synthetic retail demo schema managed by `mavra setup` / `mavra etl`. Pass `--extractor deepseek` or `--extractor openai` to enable model-backed `/v1/learn_features` extraction.)*

### HTTP Endpoints

- `GET  /v1/tools` — List active agent tool schemas (`list_tables`, `describe_table`, `run_sql`, `join_path`, `check_join`, `find_metric`, `run_metric`)
- `POST /v1/tools/:name` — Invoke a tool within an agent session context:
  ```bash
  curl -s http://127.0.0.1:8088/v1/tools/list_tables \
    -H "Content-Type: application/json" \
    -d '{"agent": "analyst-1", "session": "s1", "args": {}}'
  ```
- `GET  /v1/knowledge` — Inspect admitted metric definitions, revisions, join paths, and negative `BadPath` guards
- `GET  /v1/stats` — Inspect validation check counts, shared cache hits, single-flight coalescing, and DBMS latencies
- `POST /v1/learn_features` — Admit and leak-audit (`F1`–`F4`) point-in-time predictive features from exploration traces
- `GET  /v1/features` — List published point-in-time `EntityRef` features and task programs

---

## Citation

If you use MAVRA or its evaluation benchmarks in your research, please cite ([`CITATION.bib`](CITATION.bib)):

```bibtex
@misc{mavra,
  title        = {{MAVRA}: Sharing and Maintaining Executable Knowledge for Data Agents},
  author       = {Ming, Tai and Zhao, Zhanhao},
  howpublished = {\url{https://github.com/mmmttt000045/MAVRA}},
  url          = {https://github.com/mmmttt000045/MAVRA}
}
```

---

## License

MAVRA is released under the [Apache License, Version 2.0](LICENSE). Vendored baseline components in [`third_party/ace/`](third_party/ace/LICENSE) and [`third_party/awm/`](third_party/awm/LICENSE) are distributed under their respective Apache-2.0 licenses (see [`LICENSE`](LICENSE) for third-party notices).
