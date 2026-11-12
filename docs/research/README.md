# Research Evidence Overview

MAVRA's empirical evaluation in the PVLDB manuscript (`overleaf/sections/05-evaluation.tex`) spans five research questions, each backed by archived evidence in `exp/` and macros in `overleaf/gen/`:

- **Workload Motivation (Section 2.1, Table 1, Fig. 1)**: `exp/2026-10-01-workload-characterization` (`overleaf/gen/workload-example.tex`).
- **Q1 — Predictive Feature Reuse across Cutoffs (Section 6.2, Table 3, Figs. 6–7)**: `exp/2026-10-20-relbench` and `exp/2026-11-12-relbench-quality` (`overleaf/gen/relbench.tex`, `overleaf/gen/relbench-table.tex`).
- **Q2 — Cross-Agent Analytical Sharing (Section 6.3, Table 4, Fig. 8)**: `exp/2026-10-12-population` (`overleaf/gen/population.tex`).
- **Q3 — Ambiguity-Aware Semantic Lookup (Section 6.4, Table 5)**: `exp/2026-11-11-maint-hardening` and `overleaf/tables/lookup.tex`.
- **Q4 — Validity Maintenance under Updates (Section 6.5, Fig. 9)**: `exp/2026-11-01-change-study` and `exp/2026-11-11-maint-hardening` (`overleaf/gen/change-study.tex`, `overleaf/gen/served-split.tex`).
- **Q5 — Mechanism Ablations, Concurrency & Overhead (Section 6.6, Table 6, Fig. 10)**: `exp/2026-11-01-replay-rerun`, `exp/2026-11-01-shared-validation`, `exp/2026-11-11-maint-hardening`, `exp/2026-10-02-cache-baseline-tpcds`, `exp/2026-10-08-optimize`, `exp/2026-10-11-generality`, and `exp/2026-10-29-mechanism-pilot`.

See [exp/README.md](../../exp/README.md) for full per-experiment file links and [related-work.md](related-work.md) for literature positioning.
