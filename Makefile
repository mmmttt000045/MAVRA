.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help check index index-check py-test db-test paper paper-pack figures

help:
	@printf '%s\n' \
	  'check         Experiment index check, Rust format, unit tests, and Clippy' \
	  'index         Regenerate exp/README.md from exp/catalog.json' \
	  'index-check   Validate exp/catalog.json coverage and file references' \
	  'py-test       Run offline Python unit tests in tools/relbench/' \
	  'db-test       Run PostgreSQL regressions (requires AGENTDB_TEST_URL)' \
	  'paper         Compile overleaf/main.tex -> overleaf/build/main.pdf' \
	  'paper-pack    Package Overleaf source closure into overleaf/build/mavra-pvldb.zip' \
	  'figures       Regenerate all paper vector figures in overleaf/figures/'

check: index-check
	cargo fmt --check
	cargo test --locked
	cargo clippy --locked --all-targets -- -D warnings

index:
	$(PYTHON) tools/experiment-index.py

index-check:
	$(PYTHON) tools/experiment-index.py --check

py-test:
	$(PYTHON) -m unittest discover -s tools/relbench -p "test_*.py"

db-test:
	RUST_MIN_STACK=16777216 cargo test --locked integration_tests:: -- --ignored --test-threads=1

paper:
	bash overleaf/build.sh en

paper-pack:
	bash overleaf/build.sh pack

figures:
	$(PYTHON) tools/figures/build.py
	$(PYTHON) tools/figures/mechanism.py
