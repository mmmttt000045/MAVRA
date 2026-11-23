# Multi-Agent Population Sharing on TPC-DS SF1

**Paper Reference:** §6.2 (*Q1: Sharing Across a Population of Data Agents*), Figure 6.

## Overview

This directory evaluates cumulative exploration amortization when 16 sequential data agents answer recurring analytical questions over TPC-DS SF1 across 5 independent runs, followed by an append-only sales restatement update. Compared methods:

- `No memory` (`direct`) — Each agent explores the database independently.
- `Single-agent memory` (`metric-private`) — Validated definitions remain private to the authoring agent.
- `Example retrieval` (`metric-global-exref`) — Past verified SQL trajectories are retrieved as in-context examples without executable validation or shared conditions.
- `MAVRA` (`metric-global-full`) — Shared validated metric definitions backed by the condition hypergraph $(\mathcal{H}, \Gamma)$ and snapshot-bound execution.

## Curated Files

- [population-stats.json](population-stats.json) — Aggregated per-step token, SQL-call, database-time, and accuracy trajectories across all 5 runs.
- [tpcds-defs.json](tpcds-defs.json) — TPC-DS metric definition manifest referencing [tpcds-library.json](../cache-baseline-tpcds/tpcds-library.json).

## Reproduction

1. **Run the 16-agent population benchmark** (`MAVRA_DB_URL`):
   ```bash
   cargo build --release --locked
   ./target/release/mavra --out results/population metric-bench \
     --population --defs exp/population-sharing/tpcds-defs.json \
     --modes direct,metric-private,metric-global-exref,metric-global-full \
     --repeats 5
   ```
2. **Generate LaTeX macros and Figure 6** directly from archived `population-stats.json`:
   ```bash
   python3 tools/population-stats.py --out results/gen
   python3 tools/figures/build.py population
   ```
