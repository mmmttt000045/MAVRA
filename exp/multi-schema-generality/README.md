# Multi-Schema Generality: TPC-H, SSB, and BIRD Financial

**Paper Reference:** §6.1 (*Experimental Setup*) and §6.6 (*Q5: Multi-Schema Policy Replay*, Table 6).

## Overview

This directory holds declarative schema specifications, extracted and verified metric libraries, SQL reference queries, and multi-schema evaluation summaries across **TPC-H SF1**, **Star Schema Benchmark (SSB) SF1**, **BIRD `financial`**, and **TPC-DS SF1**.

## Curated Files

- `schemas/` ([tpch.json](schemas/tpch.json), [ssb.json](schemas/ssb.json), [financial.json](schemas/financial.json), [tpcds.json](schemas/tpcds.json)) — Declarative fact/dimension keys, calendar mappings, and schema-neutral update specifications (tested offline by `cargo test --locked specchange`).
- `libs/` ([tpch.json](libs/tpch.json), [ssb.json](libs/ssb.json), [financial.json](libs/financial.json), plus `*-kept.json`, `*-summary.json`, `*-notes.json`) — Verified metric definition libraries.
- `queries/` ([financial.json](queries/financial.json), `ssb/*.sql`, `tpch/*.sql`) — Benchmark reference SQL queries.
- [generality-stats.json](generality-stats.json), [replay-safety-summary.json](replay-safety-summary.json), [ssb-contiguity.json](ssb-contiguity.json), [e2e/scen-stats.json](e2e/scen-stats.json), [e2e/tpch-defs.json](e2e/tpch-defs.json) — Aggregated multi-schema sharing and maintenance safety summaries.
- [libcheck.py](libcheck.py) — PostgreSQL grain and compiled-definition sanity checker.

## Reproduction

1. **Offline schema & update-generator unit tests** (no database required):
   ```bash
   cargo test --locked specchange
   ```
2. **Extract a metric library and run paired policy replay** (`MAVRA_DB_URL`):
   ```bash
   bash tools/bench-load.sh tpch
   python3 tools/bench-library.py \
     --spec exp/multi-schema-generality/schemas/tpch.json \
     --queries exp/multi-schema-generality/queries/tpch \
     --db "$MAVRA_DB_URL" --out results/tpch-lib.json
   ./target/release/mavra --out results/replay-tpch replay-bench \
     --spec exp/multi-schema-generality/schemas/tpch.json \
     --libs exp/multi-schema-generality/libs/tpch.json
   ```
