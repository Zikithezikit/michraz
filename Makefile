VENV ?= .venv
BIN  := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help venv test cov lint format typecheck check build clean

help:  ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

venv:  ## Create .venv and install the package with dev tools
	python3 -m venv $(VENV)
	$(BIN)/pip install -e '.[dev]'

test:  ## Run the test suite
	$(BIN)/pytest

cov:  ## Run tests with a coverage report
	$(BIN)/pytest --cov=michraz --cov-report=term-missing

lint:  ## Lint and check formatting
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## Auto-fix lint issues and format code
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

typecheck:  ## Run mypy (strict)
	$(BIN)/mypy

check: lint typecheck test  ## Everything CI runs

build:  ## Build sdist + wheel and validate them
	rm -rf dist
	$(BIN)/python -m build
	$(BIN)/twine check dist/*

clean:  ## Remove build and cache files
	rm -rf dist build *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage
	find . -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} +
