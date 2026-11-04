# Contributing

Thanks for helping out.

## Setup

```bash
make venv
make check
```

`make help` lists every command. `make check` runs what CI runs: ruff, mypy (strict) and pytest.

## Ground rules

- **Never weaken a test to make it pass.** Fixtures are recorded responses; they change only when a source changes.
- **No live network in the test suite.** Use fixtures and `respx`.
- **Be a polite client.** Keep the rate limit, the honest User-Agent and the cache.
- **No new runtime dependencies** without maintainer approval. Dev extras are fine.
- Keep public API small. Anything not exported from `michraz/__init__.py` is private.

## Tests

- `make test` runs everything offline. A guard fails any test that opens a socket.
- `pytest -m live` calls each real service once. It is manual (`Live smoke` workflow) and never a required check.
  If it fails, a source changed: re-record the fixture in its own commit and note the date in the message.

## Pull requests

1. Branch from `main` as `<short-name>`, one focused change per PR, PR against `main`.
2. Conventional Commits: `feat:`, `fix:`, `test:`, `ci:`, `docs:`, `refactor:`, `chore:`.
3. Every commit builds and passes `make check` on its own (PRs are rebase-merged).
4. Fix review findings in the commit that introduced them: `git commit --fixup=<sha>`, then
   `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash main`, and push with `--force-with-lease` to your own branch.
5. Add a line under "Unreleased" in `CHANGELOG.md` for every user-visible change.
6. Run `make check`.

## Releasing (maintainers)

1. Move "Unreleased" entries in `CHANGELOG.md` under the new version and bump `version` in `pyproject.toml`.
2. Commit and push to `main`, then tag the same version: `git tag v0.1.0 && git push origin v0.1.0`.
3. The `Release` workflow runs CI, builds the sdist and wheel, checks that the tag matches `pyproject.toml`,
   attests the artifacts and publishes to PyPI. It needs the `PYPI_API_TOKEN` repository secret.
