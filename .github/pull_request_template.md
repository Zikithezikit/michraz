<!--
One focused change per PR against `main`. Title in Conventional Commits style
(feat:|fix:|test:|ci:|docs:|refactor:|chore:). Fold review fixes into the commit that introduced the problem
(--fixup + autosquash). ASCII only.
-->

## What does this PR do?

## How was it tested?

<!-- Record what you ran and the results. Every commit must pass `make check` on its own. -->

## Verified vs believed

<!-- Separate what you checked (and how) from what you assume. -->

## Checklist (from AGENTS.md)

- [ ] No live network in tests; fixtures not regenerated from the code under test
- [ ] Rate limit, User-Agent and cache untouched (or n.a.)
- [ ] No new runtime deps
- [ ] Public API change limited to `michraz/__init__.py` exports (or n.a.)
- [ ] `make check` green on every commit
- [ ] CHANGELOG updated (if user-visible)
