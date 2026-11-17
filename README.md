# MAVRA: Sharing and Maintaining Executable Knowledge for Data Agents

MAVRA is an early-stage Rust middleware between data agents and PostgreSQL. It validates SQL joins and grain, shares verified metric and predictive-feature definitions, and checks those definitions when their input tables change. Knowledge and cached results live in the server process; restarting the server clears them.

## Start developing

Rust development needs the stable toolchain with `rustfmt` and `clippy`. Running the service or database tests also needs PostgreSQL 16+. Python and LaTeX are optional for engine development.

```bash
cargo build --locked
cargo test --locked            # fast tests; no PostgreSQL, API keys, or model calls
cp .env.example .env           # set AGENTDB_URL to your development database
cargo run -- serve --no-etl    # HTTP tools at http://127.0.0.1:8088/v1/tools
```

`--no-etl` skips the retail demo's schema updates. Use `setup` and the default `serve` only with the retail schema. `--mode` selects a shared runtime profile; `--extractor` enables the optional model-backed feature-learning endpoint. Existing benchmark subcommands are listed by `cargo run -- --help`.

| Task | Command |
| --- | --- |
| Format, Rust tests, lint, experiment index | `make check` |
| PostgreSQL regressions on isolated databases | `make db-test` (set `AGENTDB_TEST_URL`) |
| Offline RelBench harness tests | `make py-test` (install `tools/relbench/requirements-test.txt`) |
| Compile the manuscript | `make paper` |
| Regenerate paper figures from archived evidence | `make figures` |

Windows commands, dependencies, and test scope are in the [development guide](docs/development/README.md).

## Where to work

| Path | Responsibility |
| --- | --- |
| `src/`, `src/middle/` | Runtime engine, HTTP tools, metric lifecycle, feature compilation, and shared profiles |
| `src/bench/` | Analytical and maintenance evaluation workloads; separate from runtime configuration |
| `src/integration_tests.rs`, `data/mock_fixture.sql` | Focused PostgreSQL and HTTP regressions and their small fixture |
| `tools/relbench/` | RelBench evaluation harness and offline tests |
| `tools/` | Database loaders, evidence analysis, figure generation, and repository utilities |
| `exp/` | Archived protocols, reports, and evidence, indexed by [exp/README.md](exp/README.md) |
| `overleaf/` | Authoritative manuscript source; verified paper changes sync to the independent paper repository |
| `third_party/` | Pinned ACE and AWM baseline components |
| `docs/` | [Source map](docs/development/source-map.md), [repository conventions](docs/development/repository.md), and research notes |

Report-only performance experiments have been retired from the test suite. Their evidence is preserved in `exp/`; the [historical reproduction instructions](docs/development/repository.md#historical-experiments) identify the source revision and commands.
