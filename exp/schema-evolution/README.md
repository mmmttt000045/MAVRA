# End-to-End Maintenance Under 11 Database Updates

**Paper Reference:** §6.4 (*Q3: Robustness and Cost Under Database Evolution*), Table 4 and Figure 7.

## Overview

This directory evaluates end-to-end answer accuracy, wrong-answer rate, token consumption, and latency across **11 database update scenarios** spanning four categories on **Synthetic Retail (1M rows)** and **TPC-H SF1** over 3 independent runs:

- **Held-out baseline (`holdout`)** and **4 non-breaking updates (`non_breaking`)**: `append`, `backfill`, `correct`, `addcol`.
- **5 condition-covered breaking updates (`covered_breaks`)**: `status`, `revision`, `dupload`, `dimhist`, `latekey`.
- **2 outside-condition shifts (`outside_conditions`)**: `unit`, `mirror`.

### Evaluated Arms

- Published agent-memory systems: `ACE`, `AWM`, `G-Memory`, `TeCoD`
- Controlled SQL/definition baselines: `Shared recheck`, `Template + schema check`, `Template + write invalidate`
- `MAVRA` (condition hypergraph $(\mathcal{H}, \Gamma)$ + SQL value guards + targeted local repair)

## Curated Files

- [bank-synthetic.json](bank-synthetic.json), [bank-tpch.json](bank-tpch.json) — Frozen question banks (`P1` single-month and `T1` period-difference tasks) shared across all arms and runs.
- [study-stats.json](study-stats.json) — Aggregated per-cell, per-group, and per-change accuracy, wrong-answer rate, clarification rate, token usage, and wall-clock latency.
- [analyse.py](analyse.py), [run-study.py](run-study.py), [budget-proxy.py](budget-proxy.py), [memory-service.py](memory-service.py), [select-bank.py](select-bank.py) — Study runner, loopback accounting relay, external memory service adapter, and macro aggregator.

## Reproduction

1. **Generate Table 4 (`Cs*`) macros and Figure 7 offline** from `study-stats.json`:
   ```bash
   python3 exp/schema-evolution/analyse.py --tex results/gen/change-study.tex
   python3 tools/figures/build.py change-study
   ```
2. **Execute live multi-arm benchmark runs** (`MAVRA_DB_URL` + `DEEPSEEK_API_KEY`):
   ```bash
   cargo build --release --locked
   python3 exp/schema-evolution/run-study.py --runs 1,2,3 --results results/schema-evolution
   python3 exp/schema-evolution/analyse.py --results results/schema-evolution --tex results/gen/change-study.tex
   ```
