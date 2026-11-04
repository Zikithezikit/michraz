# AGENTS.md: instructions for AI coding agents

You are working on **michraz** (מכרז, "tender"): a pure-Python library and CLI giving one interface to Israeli
public tenders (RMI land tenders, Beer Sheva municipal tenders). MIT licensed.

## Non-negotiables

1. **Never weaken a test to make it pass**, and never regenerate fixtures from the code under test. Fixtures are
   recorded responses and only change when a source changes (record the date in the commit message).
2. **No live network in the test suite.**
3. **Be a polite client.** Do not remove the rate limit, the User-Agent or the cache.
4. **No new runtime dependencies** without maintainer approval (runtime is `httpx` only).
5. **Keep the public API small.** Anything not exported from `michraz/__init__.py` is private.
6. **Don't claim what you didn't verify.** In PR descriptions, separate "verified (how)" from "believed".
7. Plain ASCII in PR text and commit messages. Check with `grep -nP '[^\x00-\x7F]' <file>` before posting.

## Workflow

- Branch from `main` as `<short-name>`, one focused change per PR, PR against `main`.
- Conventional Commits: `feat:`, `fix:`, `test:`, `ci:`, `docs:`, `refactor:`, `chore:`.
- Every commit builds and passes `make check` on its own (PRs are rebase-merged).
- Fix review findings in the commit that introduced them: `git commit --fixup=<sha>` then
  `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash main`; push with `--force-with-lease` to your own branch only.
- Never push to `main`, never merge, never force-push a shared branch. Never tag or publish: releasing is the
  maintainer's action.
- Add a line under "Unreleased" in `CHANGELOG.md` for every user-visible change.
