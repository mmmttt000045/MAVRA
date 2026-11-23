# MAVRA Documentation

- **[Architecture & Source Map](architecture.md)** — System components (Knowledge Cache, Extractor, Semantic Lookup, Snapshot-Bound Executor, and Certified Maintenance Manager), admission/repair gates (`G1`–`G9`, `F1`–`F4`), module-by-module source map, runtime profiles, and HTTP API reference.
- **[Artifact Reproducibility Guide](reproducibility.md)** — End-to-end instructions to reproduce RQs 1–5, Tables 1–6, and Figures 1–9, including external baseline setup (`ACE`, `AWM`, `G-Memory`, `TeCoD`), neural semantic lookup (`tools/lookup/`), and self-contained PostgreSQL scalability benchmarks (`q5_bench_tests`).
- **[Development & Testing Guide](development.md)** — Build prerequisites, offline Rust/Python test suites, isolated PostgreSQL regression tests (Linux & Windows PowerShell), and codebase conventions.
- **[Datasets & Schema Fixtures](../data/README.md)** — Generating and loading Synthetic Retail, TPC-DS (SF1/SF3/SF10), TPC-H SF1, SSB, BIRD `financial`, and RelBench (`rel-stack`, `rel-trial`) databases.
- **[Tools & Analysis Scripts](../tools/README.md)** — Data loaders, RelBench multi-cutoff harness, semantic lookup service, statistics scripts, and standalone figure generators.
- **[Experiment Evidence Index](../exp/README.md)** — Catalog of benchmark inputs, evaluation scripts, and aggregated summary results across all 14 evaluation suites.
