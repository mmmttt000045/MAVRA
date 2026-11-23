# Controlled Mechanism Studies: Representation, Overlap Sweep, and Snapshot Barrier

**Paper Reference:** §6.6 (*Q5: Systems Mechanisms and Ablations*).

## Overview

This directory isolates three core design mechanisms of MAVRA through controlled experiments:

1. **Part A — Feature-Definition vs. Full-Program Reuse** ([representation.py](representation.py), [representation-summary.json](representation-summary.json)): Factorial $2 \times 2$ comparison (`none`, `program`, `definition`, `full`) on `rel-stack` holding frozen source exploration fixed ([source-input.json](source-input.json)) across same-task temporal transfer (`user-badge` cutoff 2) and cross-task transfer (`user-engagement` cutoff 1).
2. **Part B — Fixed-Catalog Condition Overlap Sweep** ([system_tests.rs](system_tests.rs), [system-summary.json](system-summary.json)): 72-cell PostgreSQL benchmark (9,216 metric requests, zero LLM calls) holding catalog size fixed at 16 definitions while varying condition sharing $k \in \{1, 2, 4, 8\}$ across staggered and burst arrivals against a generic SQL-text check cache (`definition-cache`) and full recheck.
3. **Part C — Controlled-Barrier TOCTOU Isolation** ([system_tests.rs](system_tests.rs), [system-summary.json](system-summary.json)): 30-trial deterministic read/write barrier experiment contrasting single-snapshot `REPEATABLE READ` validation+execution (`0` inconsistent reads) against split-snapshot check-then-execute (`5 / 5` inconsistent reads when violating writes commit after validation).

## Curated Files

- [source-input.json](source-input.json) — Frozen audited `user-badge` cutoff-1 source feature input for Part A.
- [representation-summary.json](representation-summary.json) — Complete 8-cell factorial results and amortized token breakdown for Part A.
- [system-summary.json](system-summary.json) — Complete 72-cell overlap-sweep and 30-trial snapshot-barrier measurements for Parts B and C.
- [representation.py](representation.py), [seed_adapter.py](seed_adapter.py), [test_representation.py](test_representation.py) — Part A runner, entity-key adapter, and offline boundary unit tests.
- [analyze_representation.py](analyze_representation.py), [plot_mechanisms.py](plot_mechanisms.py), [analyze_systems.py](analyze_systems.py), [run_systems.py](run_systems.py), [system_tests.rs](system_tests.rs) — Analysis, plotting, and PostgreSQL system driver scripts.

## Reproduction

1. **Run offline boundary unit tests & inspect summaries** (no database or API key required):
   ```bash
   python3 -m unittest discover -s exp/mechanism-studies -p "test_*.py"
   python3 exp/mechanism-studies/analyze_representation.py
   python3 exp/mechanism-studies/analyze_systems.py
   python3 tools/figures/mechanism.py --out results/gen/mechanism.tex
   ```
2. **Run Parts B and C on PostgreSQL** (`MAVRA_TEST_DB_URL`):
   ```bash
   python3 exp/mechanism-studies/run_systems.py --out results/mechanism-systems
   ```
