# MAVRA: Sharing and Maintaining Executable Knowledge for Data Agents

MAVRA (**M**etric-**A**ware **V**alidation and **R**euse for **A**gents) is a stateless middleware layer between LLM data agents and PostgreSQL. Instead of sharing unverified text summaries or slice-bound SQL examples, MAVRA distills verified agent explorations into compact, self-maintaining executable definitions (`~0.6 KB`) for analytical metrics and point-in-time predictive features.

- **Example-blind relational distillation**: verifies zero-row server-side arithmetic provenance, enforces SQL AST join/grain/parameter gates, and compiles fresh SQL from the structured definition alone to confirm exact answer reproduction before publication.
- **Set-valued semantic lookup**: projects explicit business choices from each definition to synthesize rule-labeled phrasings offline and train a lightweight cross-encoder matcher that handles paraphrases, shared names, ambiguity, and absent metrics without online LLM calls.
- **Incremental validity maintenance**: tracks sharded transactional table stamps aligned with `REPEATABLE READ` snapshots, shares check verdicts across definitions and concurrent agents, admits single-edit repairs only when untouched historical buckets stay unchanged, and executes validation and query compilation inside one snapshot.

## Quick Start

```bash
cargo build --release --locked
cp .env.example .env          # configure PostgreSQL URL and optional LLM API keys
make check                    # experiment index check, rustfmt, unit tests, and Clippy
```

| Command | Description |
| --- | --- |
| `cargo run --release -- setup` | Install sharded `mavra_versions` triggers and `etl_batch_log` on PostgreSQL |
| `cargo run --release -- serve --addr 127.0.0.1:8088` | Start the MCP-compatible HTTP JSON tool server (`agentdb-mid`) |
| `make py-test` | Run offline Python unit tests for the RelBench feature-reuse harness |
| `make paper` | Compile the PVLDB manuscript (`overleaf/main.tex` -> `overleaf/build/main.pdf`) |
| `make figures` | Regenerate all vector figures (`overleaf/figures/*.pdf`) from archived stats |

## Repository Structure

| Path | Responsibility |
| --- | --- |
| `src/` | Core Rust engine (`catalog`, `checks`, `sqlscan`, `sqlscope`, `metric`, `knowledge`, `db`, `etl`, `flight`, `server`, `llm`) |
| `src/middle/` | Middleware orchestration (`mod.rs`), metric lifecycle (`metrics.rs`), predictive features (`features.rs`), and candidate optimization (`optimize.rs`) |
| `src/bench/` | Analytical, replay, parameter-binding, maintenance, and workload evaluation harnesses (`metric-bench`, `maint-bench`, `replay-bench`, `binding-bench`, `workload-bench`) |
| `tools/` | Experiment index validator, paper-repo sync script, TPC-DS/TPC-H/SSB/BIRD loaders, RelBench harness (`tools/relbench/`), and figure generators (`tools/figures/`) |
| `exp/` | Authoritative archived experimental evidence, protocols, and summary JSONs indexed by [exp/README.md](exp/README.md) |
| `overleaf/` | PVLDB manuscript sources, macros (`overleaf/gen/`), vector figures, and tables |
| `third_party/` | Pinned external baseline components (`ace`, `awm`) |
| `data/` | Minimal PostgreSQL fixture (`mock_fixture.sql`) for offline/CI integration tests |
| `docs/` | Architecture map, development conventions, and literature notes ([docs/README.md](docs/README.md)) |
