# Publication Gates, Equivalence Optimization, and Premise Rollback

**Paper Reference:** §4.2 (*Publication Gates and Equivalence-Preserving Optimization*) and §6.6 (*Q5: Systems Mechanisms*).

## Overview

This directory evaluates MAVRA's offline publication pipeline (`G1`–`G7` admission gates), equivalence-preserving SQL rewrite optimization (`O1`–`O6` gates producing optimized revision `r1` guarded by explicit premises such as `KeyRange` and `DateKeysContiguous`), and automatic fallback from `r1` to canonical revision `r0` when out-of-order date keys (`latekey`) invalidate an optimization premise without invalidating the underlying business definition.

## Curated Files

- [premise-report.json](premise-report.json) — Structured execution report verifying optimization promotion (`r0` $\rightarrow$ `r1`), premise invalidation under `latekey`, zero-error fallback to `r0`, and reinstatement after key repair.
- [opt-stats.md](opt-stats.md) — Summary table of optimization gate pass rates, candidate test wall-clock cost, and per-execution query latency savings.

## Reproduction

1. **Emit publication and optimization summary macros offline**:
   ```bash
   python3 tools/sharing-stats.py --out results/gen
   ```
2. **Run a live publication + premise-rollback benchmark** (`MAVRA_DB_URL` + `DEEPSEEK_API_KEY`):
   ```bash
   cargo build --release --locked
   ./target/release/mavra --out results/premise-opt metric-bench \
     --rows 500000 --modes metric-global-full --changes append,latekey --trace
   ```
