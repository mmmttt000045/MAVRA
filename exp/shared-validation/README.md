# Shared Validation Scaling Across 1 to 32 Concurrent Agents

**Paper Reference:** §6.6 (*Q5: Shared Validation Scaling*, Figure 9).

## Overview

This directory evaluates post-update validation query counts and database execution time across **16 shared metric definitions** and **$N \in \{1, 2, 4, 8, 16, 32\}$ consumer agents** under both **staggered** and **simultaneous** arrival patterns (3 randomized blocks = 108 cells, zero LLM calls):

- `Per-agent validation` (`per-agent`) — Each agent validates its own definitions independently ($O(N)$ validation cost).
- `Shared definition recheck` (`full-recheck`) — Shares definition-level status across agents without cross-definition condition deduplication or single-flight coalescing.
- `MAVRA` (`mavra`) — Deduplicates shared conditions across definitions and coalesces concurrent in-flight checks across simultaneous arrivals.

## Curated Files

- [stats.json](stats.json) — Median, minimum, and maximum validation query counts and database execution times (`db_s`) across all 108 cells.
- [analyse.py](analyse.py) — Emits all 25 `Sv*` LaTeX macros offline from `stats.json` (or recomputes from `--results-dir`).

## Reproduction

1. **Generate `Sv*` LaTeX macros and Figure 9 offline**:
   ```bash
   python3 exp/shared-validation/analyse.py --tex results/gen/shared-validation.tex
   python3 tools/figures/build.py shared-validation
   ```
2. **Run the PostgreSQL scaling benchmark from scratch** (`MAVRA_TEST_DB_URL`):
   ```bash
   cargo test --release --locked q5_bench_tests::postgres_shared_validation_scaling \
     -- --ignored --nocapture --test-threads=1
   ```
