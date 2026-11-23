# Workload Characterization: Memoryless Data Agents vs. Production BI Queries

**Paper Reference:** §2.1 (*Motivation and Problem Statement*), Table 1, and Figure 1.

## Overview

This directory contains the empirical workload characterization contrasting production analytical warehouse workloads (Amazon Redset) against 100 memoryless LLM data-agent sessions answering recurring business metric questions over a shared 1M-row retail star schema (`store_sales`, `store_returns`, `catalog_sales`, `date_dim`, `item`, `etl_batch_log`).

Across the 100 independent sessions (5 metrics $\times$ 10 tasks $\times$ 2 phrasings), 80.5% of database tool calls inspect schema catalogs, explore value distributions, or validate join/uniqueness assumptions rather than computing the requested period answer, motivating shared, maintained executable definitions.

## Curated Files

- [workload-stats.json](workload-stats.json), [workload-stats.md](workload-stats.md) — Aggregated SQL template fingerprints (`pglast`), tool-call category breakdown (`schema`, `explore`, `validate`, `attempt`, `answer`, `compute`, `error`), and equivalence statistics across sessions.
- [redset/redset_stats.json](redset/redset_stats.json), [redset/README.md](redset/README.md) — Amazon Redset production warehouse query repetition and template statistics.

## Reproduction

1. **Run a fresh workload benchmark** against PostgreSQL (`MAVRA_DB_URL`):
   ```bash
   cargo build --release --locked
   ./target/release/mavra --out results/workload-characterization workload-bench \
     --rows 1000000 --agent openai --concurrency 6
   ```
2. **Analyze session logs and generate Figure 1**:
   ```bash
   python3 tools/workload-stats.py results/workload-characterization --out results/workload-stats
   python3 tools/figures/build.py metric-record
   ```
