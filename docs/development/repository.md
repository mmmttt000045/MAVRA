# Repository Conventions

## Directory Ownership

- `src/` and `src/middle/` contain MAVRA's core Rust middleware; `src/bench/` contains Rust benchmark harnesses.
- Runtime profiles belong in `src/middle/profiles.rs`; serving the application must not depend on a benchmark module's configuration logic.
- `tools/` holds Python/Shell data loaders, RelBench runners (`tools/relbench/`), figure builders (`tools/figures/`), `experiment-index.py`, and `sync-paper-repo.py`.
- `exp/` stores the archived evidence, protocols, and summary JSONs for experiments reported in the manuscript, indexed by `exp/catalog.json` and rendered into `exp/README.md`.
- `overleaf/` is the single source of truth for the PVLDB manuscript; `tools/sync-paper-repo.py` mirrors its compilation closure to `mmmttt000045/icde-2027-paper` (`main`) and records sync metadata in `docs/development/paper-sync.json`.

## Pre-Commit Checks

- Run `make check` (`python3 tools/experiment-index.py --check`, `cargo fmt --check`, `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings`) before committing.
- Never commit `.env`, API credentials, `target/`, `results/`, `overleaf/build/`, or local scratch directories (`ccfa-workfiles/`).

## Keeping the repository small

- Add one clear implementation of each behavior. Extend an existing helper or profile instead of copying it for every experiment version.
- Test observable behavior and failure boundaries. Use case tables for equivalent inputs; avoid tests that only restate configuration dictionaries or private implementation details.
- Keep PostgreSQL regressions focused on correctness. Reuse the common isolated-database runner; avoid per-test report writers, row-count sweeps, and throughput measurement loops.
- Store experiment evidence in `exp/` and index it in `exp/catalog.json`. Retire one-off drivers once their protocol, outputs, and source revision are recorded; do not copy their code into the runtime or test suite.
- Keep generated results, downloaded datasets, virtual environments, build output, and scratch files outside tracked source. Preserve published evidence and pinned third-party attribution.

## Historical experiments

The report-only repair-ambiguity, snapshot performance, shared-validation scaling, and sustained-write drivers are preserved in revision `5104ad593b0953f5f2a3e49f07d96116404cde72`. Their reports and analysis remain in `exp/2026-10-02-cache-baseline-tpcds/`, `exp/2026-11-01-shared-validation/`, and `exp/2026-11-11-maint-hardening/`. The current `postgres_snapshot_binding` is a short correctness regression, with a different output format from the historical performance driver.

Reproduce historical commands in a separate checkout of that revision:

```bash
git worktree add --detach ../agent4db-history 5104ad593b0953f5f2a3e49f07d96116404cde72
cd ../agent4db-history
# Set AGENTDB_TEST_URL, then use the command and environment in the archived README.
cargo test --release --locked postgres_shared_validation_scaling -- --ignored --nocapture
```

`exp/2026-10-29-mechanism-pilot/prepare_systems.py` injects helpers into the old snapshot experiment module. Run that archived preparation against its recorded source checkout, where those helpers exist.

## Paper delivery

`overleaf/` is the only manuscript source. After paper changes compile and pass verification, use `tools/sync-paper-repo.py` to sync, commit, and push the dependency closure to `mmmttt000045/icde-2027-paper` on `main`. Check and merge remote edits first, retain remote-owned files, then update `docs/development/paper-sync.json` and verify the remote commit. Do not push the main project repository under this authorization. Generate an Overleaf ZIP only when explicitly requested.
