# CLAUDE.md

@AGENTS.md

## What this is

michraz: a pure-Python library and CLI for Israeli public tenders. One normalized `Tender` model (stdlib frozen
dataclasses), sources for RMI (Israel Land Authority JSON API) and Beer Sheva (data.gov.il CKAN). Runtime
dependency is `httpx` only.

## Commands

```bash
make venv        # create .venv and install with dev tools
make check       # ruff, mypy --strict, pytest: exactly what CI runs
make test        # pytest only
.venv/bin/pytest tests/test_x.py::test_y   # one test
make build       # sdist + wheel, twine check
```

## Architecture

`src/michraz/`: `models.py` (Tender, Document), `sources/` (one file per source, each yields `Tender`s),
`_http.py` (polite client: rate limit, cache, retries), `filters.py`, `export.py`, `cli.py`. The milestone plan is
in the maintainer's spec; the package is built up milestone by milestone, so modules may not exist yet.
