# Paired Fixed-Catalog Maintenance Policy Replay

**Paper Reference:** §6.6 (*Q5: Maintenance Policy Comparison Across Four Schemas*, Table 6).

## Overview

This directory contains the paired four-schema maintenance policy comparison across **TPC-DS**, **TPC-H**, **SSB**, and **BIRD `financial`**, holding the admitted metric catalog fixed while applying identical database updates to compare four policies:

1. `Write invalidate` (`revoke`) — Invalidates definitions upon any write to a referenced table.
2. `Schema check only` (`schema`) — Invalidates only when table/column catalog metadata changes.
3. `Table-level data tests` (`tabletest`) — Runs generic table-level uniqueness/non-null checks without definition-specific join/filter/repair semantics.
4. `MAVRA` (`condition`) — Validates shared condition hypergraph nodes under `REPEATABLE READ` and applies bounded local repairs (`dupload`, `latekey`, `status`, `dimhist`).

*(See also [exp/maintenance-guards/](../maintenance-guards/README.md) for the 12-change replay adding `reclass` and historical bucket check `G9`.)*

## Curated Files

- [replay-policies.json](replay-policies.json) — Aggregated Correct / Served-Wrong / Withheld counts across Benign, Covered-Break, and Outside-Condition updates on all four schemas.
- [analyse.py](analyse.py) — Emits `Rp*` LaTeX macros directly from `replay-policies.json` (or recomputes from live `--reports-dir` runs).

## Reproduction

1. **Generate `Rp*` LaTeX macros offline**:
   ```bash
   python3 exp/policy-replay/analyse.py --tex results/gen/replay-policies.tex
   ```
2. **Run live four-schema policy replay** (`MAVRA_DB_URL`):
   ```bash
   for s in tpch ssb financial; do
     ./target/release/mavra --out "results/policy-replay/$s" replay-bench \
       --spec "exp/multi-schema-generality/schemas/$s.json" \
       --libs "exp/multi-schema-generality/libs/$s.json" \
       --policies revoke,schema,tabletest,condition --oracles snapshot
   done
   ```
