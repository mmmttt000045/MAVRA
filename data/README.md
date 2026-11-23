# Datasets and Schema Fixtures

MAVRA evaluates analytical sharing, semantic resolution, certified definition repair, and predictive feature reuse across five relational analytical schemas and two temporal RelBench databases. To keep the repository lightweight, only the compact integration-test fixture is tracked directly; larger benchmarks are generated deterministically or loaded via scripts in [`tools/`](../tools/README.md).

---

## 1. Bundled Integration Fixture (`data/mock_fixture.sql`)

- [`mock_fixture.sql`](mock_fixture.sql) is a self-contained 31-line synthetic retail star schema (`date_dim`, `item`, `customer`, `warehouse`, `store_sales`, `store_returns`) compiled into the test binary for isolated PostgreSQL regressions (`src/integration_tests.rs`).
- Do not load `mock_fixture.sql` into a shared database manually; `make db-test` automatically provisions and drops per-test temporary databases.

---

## 2. Built-In Synthetic Retail Workload (No External Download)

The Rust benchmark subcommands (`maint-bench`, `metric-bench`, `replay-bench --schema synthetic`, `binding-bench`, and `workload-bench`) include a deterministic in-process generator (`src/bench/scenario.rs`) that populates the synthetic retail warehouse (`1,000,000` `store_sales` rows, `396,000` `store_returns` rows, and `500,000` `catalog_sales` rows at default scale) directly inside an isolated PostgreSQL database.

Set `MAVRA_DB_URL` (or pass `--db`) and run any synthetic benchmark directly—no external `.dat` or `.tbl` files are required:

```bash
export MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/mavra
cargo run --release -- maint-bench --rows 100000 --agents 8
```

---

## 3. TPC-DS (SF1, SF3, and SF10)

Used in **Q1** (16-agent sequential sharing on SF1), **Q2** (core 26-definition catalog), and **Q5** (policy replay on SF1 and validation scaling across SF1/SF3/SF10, `2.9M`–`28.8M` `store_sales` rows).

1. Build `dsdgen` from the official `tpcds-kit` distribution and generate pipe-delimited files without trailing delimiters (`-terminate n`):
   ```bash
   ./dsdgen -scale 1 -dir /tmp/tpcds-sf1 -terminate n
   ```
   *(Use `-scale 3` or `-scale 10` for Q5 scaling experiments.)*

2. Load into a PostgreSQL template database using [`tools/tpcds-load.sh`](../tools/tpcds-load.sh):
   ```bash
   MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres \
     bash tools/tpcds-load.sh /tmp/tpcds-sf1 /path/to/tpcds-kit/tools/tpcds.sql tpcds_sf1
   ```
   **Representation notes**: `tools/tpcds-load.sh` applies two representation-only adjustments required by the 12-class data-mutation benchmark while preserving standard query semantics:
   - Replaces primary-key constraints on the six sales/returns fact tables with non-unique B-tree indexes on grain and date columns so integrity-break workloads (duplicate loads, status logs, backup copies) can insert duplicate keys; dimension primary keys remain intact.
   - Widens `decimal(7,2)` columns to `numeric(12,2)` so semantic unit-shift mutations (`×100`) do not overflow.

---

## 4. TPC-H SF1, Star Schema Benchmark (SSB), and BIRD `financial`

Used in **Q3** (11-update end-to-end study on TPC-H SF1) and **Q5** (4-schema, 12-update policy replay and static core-coverage analysis). All three schemas are loaded via [`tools/bench-load.sh`](../tools/bench-load.sh):

### A. TPC-H SF1 (`tpch_sf1`)
If `*.tbl` files are not already present in the target directory, `tools/bench-load.sh` automatically generates TPC-H SF1 via DuckDB's built-in `tpch` extension (`pip install -r tools/requirements.txt`):

```bash
MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres \
  bash tools/bench-load.sh tpch /tmp/tpch-sf1 tpch_sf1
```

### B. Star Schema Benchmark SF1 (`ssb_sf1`)
Generate `*.tbl` files with `ssb-dbgen` (`dbgen -s 1`), then load:

```bash
MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres \
  bash tools/bench-load.sh ssb /tmp/ssb-sf1 ssb_sf1
```
*(Adds a typed `d_fulldate DATE` column derived from `d_datekey` alongside SSB's text `d_date` column.)*

### C. BIRD `financial` (`financial`)
Download the BIRD `dev` database bundle and place `financial.sqlite` (PKDD'99 Czech bank relational database) inside `/tmp/bird-financial`, then load:

```bash
MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres \
  bash tools/bench-load.sh financial /tmp/bird-financial financial
```
*(Renames SQLite's reserved-word table `order` to `orders`, normalizes identifiers to lowercase, and widens fact monetary columns to `numeric(18,2)` for reversible unit-shift tests.)*

---

## 5. RelBench Temporal Cutoff Databases (`rel-stack` and `rel-trial`)

Used in **Q4** (cross-cutoff predictive feature reuse across 6 tasks and 5 temporal cutoffs: 91-day spacing on `rel-stack` and 365-day spacing on `rel-trial`).

Install the RelBench dependencies (`pip install -r tools/relbench/requirements.txt`) and run [`tools/relbench/prepare.py`](../tools/relbench/prepare.py) to materialize the five temporal cutoffs (`tasks/<task>/k1..k5/{train,val,test}.parquet`, `timeline.json`) and load the cutoff-1 PostgreSQL template database (`time <= test_1`; test labels never enter PostgreSQL):

```bash
export MAVRA_DB_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres

# Stack Exchange (`rel-stack`: post-votes, user-badge, user-engagement)
python3 tools/relbench/prepare.py \
  --data results/relbench-data/rel-stack \
  --out results/relbench-data/rel-stack-prep \
  --cutoffs 5 \
  --pg "$MAVRA_DB_URL" \
  --dbname relbench_stack_t1

# Clinical Trials (`rel-trial`: site-success, study-adverse, study-outcome)
python3 tools/relbench/prepare.py \
  --data results/relbench-data/rel-trial \
  --out results/relbench-data/rel-trial-prep \
  --cutoffs 5 \
  --pg "$MAVRA_DB_URL" \
  --dbname relbench_trial_t1
```

`prepare.py` verifies row-by-row equality between cutoff `k = 5` and the official hosted RelBench split before completing.

---

## 6. Benchmark Catalogs & Summary Results (`exp/`)

Curated metric catalogs, synthetic multi-domain definitions (`catalog_26.json` through `catalog_1000.json`), request sets (`390` main requests, `92` repeated period requests, `204` unseen paraphrases), schema metadata (`exp/multi-schema-generality/{schemas,libs}/`), and aggregated summary results are tracked directly under [`exp/`](../exp/README.md).
