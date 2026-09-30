# Common development tasks. Run `make` or `make help` to list them.

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
IMAGE ?= robo-evals:dev

.DEFAULT_GOAL := help

.PHONY: help
help: ## List the available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)

.PHONY: setup
setup: $(BIN)/python ## Create .venv, install the dev and docs extras, and the Git hooks
	$(BIN)/python -m pip install -U pip
	$(BIN)/python -m pip install -e ".[dev,docs]"
	$(BIN)/pre-commit install

.PHONY: lint
lint: ## Run ruff lint and the format check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

.PHONY: fmt
fmt: ## Format the code and apply safe lint fixes
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

.PHONY: typecheck
typecheck: ## Run mypy in strict mode
	$(BIN)/mypy

.PHONY: test
test: ## Run the test suite
	$(BIN)/pytest

.PHONY: check
check: lint typecheck test ## Run lint, typecheck, and tests

.PHONY: bench
bench: ## Run the benchmarks and apply the regression gate
	$(BIN)/pytest benchmarks --benchmark-only --benchmark-json=bench.json
	$(BIN)/python scripts/bench_gate.py bench.json

.PHONY: mutation
mutation: ## Run mutation testing on the statistics and report modules
	$(BIN)/mutmut run --max-children 4
	$(BIN)/mutmut results

.PHONY: demo
demo: ## Run the smoke suite and write reports and a video to results/
	$(BIN)/robo-evals run --policy scripted --suite smoke --episodes 5 --video first

.PHONY: docs
docs: ## Build the documentation site into site/
	$(BIN)/mkdocs build --strict

.PHONY: docs-serve
docs-serve: ## Serve the documentation site with live reload
	$(BIN)/mkdocs serve

.PHONY: build
build: ## Build the wheel and sdist into dist/
	$(BIN)/python -m pip install build
	$(BIN)/python -m build

.PHONY: binary
binary: ## Build the standalone executable into dist-bin/
	$(BIN)/python -m pip install pyinstaller ".[video,ws]"
	$(BIN)/python scripts/build_binary.py

.PHONY: docker
docker: ## Build the container image and run the smoke suite in it
	docker build -t $(IMAGE) .
	mkdir -p out
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$$PWD/out:/out" $(IMAGE) \
		run --policy scripted --suite smoke --episodes 2

.PHONY: clean
clean: ## Remove build output and caches
	rm -rf build dist dist-bin site out results bench.json mutants .benchmarks .hypothesis \
		.pytest_cache .mypy_cache .ruff_cache
