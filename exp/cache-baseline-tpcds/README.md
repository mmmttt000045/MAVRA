# Condition Sharing, Snapshot Binding, and TPC-DS Replay

**Paper Reference:** §6.2 (*Q1: Sharing Efficiency*) and §6.6 (*Q5: Systems Mechanisms and Ablations*, Table 6).

## Overview

This directory contains the aggregated TPC-DS SF1 systems benchmark summaries and paired maintenance-policy replay statistics:

1. **Condition Sharing vs. SQL-Text Check Cache** ([cb-1m-share-stats.json](cb-1m-share-stats.json), [cb-1m-zero-stats.json](cb-1m-zero-stats.json), [cb-4m-stats.json](cb-4m-stats.json), [e1-scaling-stats.json](e1-scaling-stats.json), [e1b-4m-a32-stats.json](e1b-4m-a32-stats.json)): Compares MAVRA's shared condition hypergraph $(\mathcal{H}, \Gamma)$ against per-definition validation and a generic SQL-text check cache across 1M–16M fact rows and 8–32 agents.
2. **Snapshot-Bound Validation & Sharded Version Tracking** ([snapshot-binding-stats.json](snapshot-binding-stats.json), [snapshot-binding-report.json](snapshot-binding-report.json), [snapshot-binding-shards-stats.json](snapshot-binding-shards-stats.json), [snapshot-binding-shards-report.json](snapshot-binding-shards-report.json)): Evaluates `REPEATABLE READ` snapshot binding under concurrent writes (`0 / 11,297` mismatched reads vs. `261` TOCTOU anomalies under check-then-execute) and 16-shard `mavra_versions` trigger throughput.
3. **Ambiguity Safety, Wait-for-Repair & TPC-DS Policy Replay** ([repair-ambiguity-report.json](repair-ambiguity-report.json), [repair-ambiguity-unique-report.json](repair-ambiguity-unique-report.json), [wait-repair-stats.json](wait-repair-stats.json), [declared-use.json](declared-use.json), [replay-stats.json](replay-stats.json), [tpcds-replay-stats.json](tpcds-replay-stats.json), [tpcds-library.json](tpcds-library.json), [tpcds-library-notes.json](tpcds-library-notes.json), [tpcds-sharing.json](tpcds-sharing.json)): Evaluates `repair_unique` safety when backup tables create candidate-key ambiguity, concurrent wait-for-repair coalescing, and paired 4-policy replay on TPC-DS SF1.

## Reproduction

- **Run the PostgreSQL Q5 systems benchmarks** (`MAVRA_TEST_DB_URL`):
  ```bash
  cargo test --release --locked q5_bench_tests:: -- --ignored --nocapture --test-threads=1
  ```
- **Generate Q5 review macros and snapshot-isolation table**:
  ```bash
  python3 tools/review-results.py --out results/gen
  ```
- **Run live TPC-DS policy replay** (`MAVRA_DB_URL`):
  ```bash
  ./target/release/mavra --out results/tpcds-replay replay-bench \
    --libs exp/population-sharing/tpcds-defs.json --schema tpcds
  python3 tools/replay-stats.py results/tpcds-replay/replay.json --json results/tpcds-replay-stats.json
  ```
