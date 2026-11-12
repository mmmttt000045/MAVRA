# Repository Conventions

## Directory Ownership

- `src/` and `src/middle/` contain MAVRA's core Rust middleware; `src/bench/` contains Rust benchmark harnesses.
- `tools/` holds Python/Shell data loaders, RelBench runners (`tools/relbench/`), figure builders (`tools/figures/`), `experiment-index.py`, and `sync-paper-repo.py`.
- `exp/` stores the archived evidence, protocols, and summary JSONs for experiments reported in the manuscript, indexed by `exp/catalog.json` and rendered into `exp/README.md`.
- `overleaf/` is the single source of truth for the PVLDB manuscript; `tools/sync-paper-repo.py` mirrors its compilation closure to `mmmttt000045/icde-2027-paper` (`main`) and records sync metadata in `docs/development/paper-sync.json`.

## Pre-Commit Checks

- Run `make check` (`python3 tools/experiment-index.py --check`, `cargo fmt --check`, `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings`) before committing.
- Never commit `.env`, API credentials, `target/`, `results/`, `overleaf/build/`, or local scratch directories (`ccfa-workfiles/`).
