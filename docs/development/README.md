# Development Guide

## Engine development

Use stable Rust with `rustfmt` and `clippy`. The default tests run without databases, network services, API keys, Python, or manuscript dependencies.

```bash
cargo fmt --check
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
```

`make check` runs these checks plus `python3 tools/experiment-index.py --check` (Python 3.10+, standard library only).

## Database regressions

Use PostgreSQL 16+ and a role allowed to create databases. Each test creates a uniquely named database and removes it after success, failure, panic, or timeout. The supplied database is only the administration connection; fixtures are loaded into the new database. Tests print their result and do not generate experiment archives.

```bash
export AGENTDB_TEST_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres
make db-test
```

On Windows PowerShell, run the equivalent directly:

```powershell
$env:AGENTDB_TEST_URL = 'postgres://postgres:postgres@127.0.0.1:5432/postgres'
$env:RUST_MIN_STACK = '16777216'
cargo test --locked integration_tests:: -- --ignored --test-threads=1
```

Use a test name in place of `integration_tests::` to run one regression. The suite covers HTTP lifecycle and query coalescing, scoped SQL admission, join orientation, feature fusion and future-row isolation, date-key repair, optimization and rollback, data-change maintenance, and concurrent snapshot binding. Large row-count and latency sweeps belong to [historical experiments](repository.md#historical-experiments).

## RelBench harness

The offline tests mock database and model calls; they need only the packages in the test dependency file:

```bash
python3 -m pip install -r tools/relbench/requirements-test.txt
make py-test
```

Without Make (also works in PowerShell with `python`):

```bash
python3 -m unittest discover -s tools/relbench -p 'test_*.py'
```

Full evaluation runs additionally need LightGBM, scikit-learn, RelBench and its data preparation dependencies. Follow the archived [RelBench protocol](../../exp/2026-10-20-relbench/README.md) for those runs; they are separate from the development checks.

## Manuscript work

`make figures` needs `tools/figures/requirements.txt`; `make paper` needs TeX Live (`latexmk` and pdfLaTeX) or Tectonic. See the [manuscript guide](../../overleaf/README.md) and [sync conventions](repository.md#paper-delivery). Normal paper delivery syncs verified sources to GitHub; packaging is only for an explicit request.
