# Tools and Analysis Scripts

## Repository & Manuscript Utilities

- `experiment-index.py` — validates `exp/catalog.json` against `exp/*` directories and renders `exp/README.md` (`--check` runs in CI).
- `sync-paper-repo.py` — mirrors `overleaf/main.tex` and its exact dependency closure to `icde-2027-paper` (`--apply`, `--push`, `--prune`).
- `check-llm.py` — verifies configured LLM endpoint connectivity from `.env`.

## Database & Analytical Benchmark Scripts

- `tpcds-load.sh`, `tpcds-library.py`, `tpcds-sharing.py` — TPC-DS SF1 data loading, definition library, and cross-agent sharing driver.
- `bench-load.sh`, `bench-library.py`, `bench-support.py` — TPC-H SF1, SSB, and BIRD `financial` fixture loading and query libraries.
- `workload-stats.py` — generates `overleaf/gen/workload-example.tex` (Table 1 & Section 1 workload characterization).
- `population-stats.py` — generates `overleaf/gen/population.tex` (Section 6.3 16-agent TPC-DS study).
- `sharing-stats.py` — generates `overleaf/gen/sharing.tex` (Section 6.6 admission gate statistics).
- `review-results.py`, `replay-stats.py` — generate `overleaf/gen/review.tex` and replay summaries.

## Subdirectories

- `figures/` — deterministic vector figure generators for Figures 1–10 (`build.py`).
- `relbench/` — multi-cutoff RelBench feature-reuse harness (`harness.py`), baselines (`featpilot.py`, `gmemory_service.py`, `tecod_service.py`), data preparation (`prepare.py`), paper macro/table generator (`paper-stats.py`), and unit tests (`test_*.py`).
