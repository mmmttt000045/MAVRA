# Evaluation, Lookup, and Analysis Tools

Auxiliary Python scripts, schema loaders, neural lookup services, and vector figure builders for **MAVRA**.

## Root Utilities (`tools/`)

Install core SQL AST and DuckDB data-generation dependencies with:

```bash
python3 -m pip install -r tools/requirements.txt
```

- `experiment-index.py` — Validates `exp/catalog.json` against `exp/*/` directories (`--check`) and regenerates `exp/README.md`.
- `check-llm.py` — Official-API connectivity and tool-calling smoke check (`deepseek`, `openai`, `zhipu`).
- `tpcds-load.sh`, `tpcds-library.py`, `tpcds-sharing.py` — Load `dsdgen` TPC-DS data into PostgreSQL (`MAVRA_DB_URL`), extract structured metric libraries from official TPC-DS templates, and measure natural condition sharing across queries.
- `bench-load.sh`, `bench-library.py`, `bench-support.py` — Load TPC-H SF1 (via DuckDB `tpch`), Star Schema Benchmark (`ssb`), and BIRD `financial` into PostgreSQL (`MAVRA_DB_URL`), and build filtered metric definition libraries (`exp/multi-schema-generality/`).
- `workload-stats.py` — Classifies agent tool traces via `pglast` AST fingerprinting and compares memoryless agent workloads against parameterized application SQL (Section 1, Table 1).
- `population-stats.py` — Aggregates 16-agent sequential analytical sharing and post-restatement accuracy/cost statistics into Markdown and `results/gen/population.tex` (Section 6.2, Figure 6).
- `sharing-stats.py` — Summarizes admission-gate funnels (`G1`–`G7`), consumer speedup, and optimization rules into `results/gen/sharing.tex` (Section 6.6).
- `replay-stats.py`, `review-results.py` — Compute paired maintenance-policy replay outcomes (`95%` cluster-bootstrap CIs), snapshot-isolation stress tables, and condition-sharing macros in `results/gen/` (Section 6.6, Table 6).

## Subdirectories

- [`tools/lookup/`](lookup/README.md) — Standalone HTTP service (`POST /resolve`, `GET /health`) implementing `BAAI/bge-m3` dense candidate recall, 3-model `XLM-RoBERTa` (`BAAI/bge-reranker-base`) peer-difference scoring, and `(0.10, 0.90)` selective `Hit / Diffs / Refer / Miss` routing (`MAVRA_LOOKUP_URL`).
- `tools/relbench/` — Multi-cutoff RelBench predictive feature reuse harness (`harness.py`, `prepare.py`, `run-queue.py`, `paper-stats.py`, `frozen-summary.py`), external baseline bridges (`featpilot.py`, `gmemory_service.py`, `tecod_service.py`, plus `third_party/ace` and `third_party/awm`), and offline unit tests (`make py-test`, `requirements-test.txt`, `requirements.txt`).
- [`tools/figures/`](figures/README.md) — Deterministic vector PDF generators (`make figures` -> `results/figures/*.pdf` and `results/gen/mechanism.tex`) reading archived experiment JSONs in `exp/`.

## Self-Contained PostgreSQL System Benchmarks

Self-contained Q5 PostgreSQL mechanism drivers (shared validation scaling from 1 to 32 concurrent agents, `REPEATABLE READ` snapshot-bound TOCTOU isolation, 16-shard `mavra_versions` sustained-write throughput, and backup-table repair ambiguity) live in [`src/q5_bench_tests.rs`](../src/q5_bench_tests.rs) and run with zero LLM API keys via `make q5-bench`.
