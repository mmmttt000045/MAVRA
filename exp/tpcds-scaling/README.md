# Warehouse Scale-Up (TPC-DS SF1/SF3/SF10) and Core Coverage Controls

**Paper Reference:** §6.5 and §6.6 (*Q5: Validation Scalability and Coverage*).

## Overview

This directory contains three scalability and coverage evaluations:

1. **TPC-DS SF1 $\rightarrow$ SF3 $\rightarrow$ SF10 Maintenance Scaling** ([scaling-summary.json](scaling-summary.json)): Evaluates condition validation, guard overhead, and local repair runtime as `store_sales` grows from **2.88M rows (SF1)** to **8.64M rows (SF3)** and **28.80M rows (SF10)** on PostgreSQL, verifying invariant correctness and sub-linear amortized per-definition cost.
2. **4-Call Budget-Matched RelBench Control** ([relbench-4call-truncation.json](relbench-4call-truncation.json)): Evaluates `No memory` truncated at MAVRA's reuse call budget ($\le 4$ model calls), confirming that memoryless exploration cannot match reused definitions under equal online call budgets.
3. **Static Core Template Coverage (`G3`)** ([g3-coverage.json](g3-coverage.json)): Measures the fraction of benchmark queries covered by MAVRA's single-fact $N{:}1$ star-join core across SSB, TPC-DS, TPC-H, and BIRD `financial`.

## Curated Files

- [scaling-summary.json](scaling-summary.json) — Validation, repair, and replay latency across SF1, SF3, and SF10 alongside table row counts and database sizes.
- [relbench-4call-truncation.json](relbench-4call-truncation.json) — 4-call truncated `No memory` evaluation summary on RelBench.
- [g3-coverage.json](g3-coverage.json) — Schema-by-schema `G3` core coverage breakdown.

## Reproduction

```bash
cargo build --release --locked
./target/release/mavra --pool 16 --out results/tpcds-sf10 replay-bench \
  --libs exp/population-sharing/tpcds-defs.json \
  --schema tpcds --tpcds-db tpcds_sf10 \
  --policies revoke,schema,tabletest,condition \
  --oracles snapshot --sql-timeout-secs 3600
```
