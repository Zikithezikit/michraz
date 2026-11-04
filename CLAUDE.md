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

`src/michraz/`:

- `models.py`: frozen `Tender` and `Document`. `extra` is excluded from equality and hashing.
- `sources/`: `base.py` (the `Source` protocol and `BaseSource`, which lazily builds or is bound to an `HttpClient`
  and collects skipped records in `errors`), `rmi.py`, `beersheva.py`, and `data/rmi_settlements.json`.
- `_http.py`: `HttpClient` with per-host rate limit, disk cache, retries. The clock, sleep and wall clock are
  injectable, which is how tests avoid real waiting.
- `client.py`: `Michraz`, owns one `HttpClient` and binds it to the sources.
- `filters.py`, `export.py`, `cli.py`, `_dates.py`, `errors.py`.

Tests: fixtures in `tests/fixtures` are recorded responses (see `docs/sources.md`). `tests/conftest.py` blocks real
sockets for every test not marked `live`. `tests/live/` runs only with `pytest -m live`. HTTP is mocked with `respx`.

Source facts (what was verified, what was not) live in `docs/sources.md`. Update it when a source changes.
