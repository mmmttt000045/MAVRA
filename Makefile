.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help check index index-check py-test paper paper-en paper-pack figures

help:
	@printf '%s\n' \
	  'check         Experiment index check, Rust format, unit tests, and Clippy' \
	  'index         Regenerate exp/README.md from exp/catalog.json' \
	  'index-check   Validate exp/catalog.json coverage and file references' \
	  'py-test       Run offline Python unit tests in tools/relbench/' \
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
	PYTHONPATH=tools/relbench $(PYTHON) -m unittest discover -s tools/relbench -p "test_*.py"

paper paper-en:
	bash overleaf/build.sh en

paper-pack:
	bash overleaf/build.sh pack

figures:
	$(PYTHON) tools/figures/build.py
	$(PYTHON) tools/figures/mechanism.py
