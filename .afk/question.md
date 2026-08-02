# Issue #176 — blocked deliverable: `docs/corpus/expected/README.md`

## What shipped

`scripts/corpus/diff.py` (`diff_reports`, `load_expected`) and `tests/test_corpus_diff.py`. Both
paths appear literally in the issue body, and both are complete against their acceptance criteria.

## What is blocked, and why

The issue also asks for:

> New directory `docs/corpus/expected/` holding a short README noting that files here are generated
> by an explicit, human-invoked run of the harness ...

and the 2026-08-01 addendum adds a criterion about what that README must state (manifest
`excluded_dirs` used verbatim; the reports intentionally differ from `docs/corpus-study.md`'s
published tables; `docs/corpus-study.md` is not the oracle).

The prior attempt at this slice created `docs/corpus/expected/README.md` and was rejected:

> Out-of-scope file(s) added: `docs/corpus/expected/README.md`. Remove them and keep only changes
> the issue's acceptance criteria call for.

The scope gate matches new-file *basenames* against the issue text. The issue names the
**directory** (`docs/corpus/expected/`) but never the string `README.md`, so the file is rejected
mechanically even though two acceptance criteria require it. Per the standing convention ("if the
implementation needs a new file the issue body does not name, write the dependency to
`.afk/question.md` and stop rather than creating it speculatively and burning retries"), I removed
the README rather than re-create it and burn a second retry on the same tripwire.

## What a human needs to decide

Either is fine; I have no way to pick between them autonomously:

1. **Amend the issue body** to name `docs/corpus/expected/README.md` literally, then re-run this
   slice — the README lands with no other change.
2. **Land the README by hand.** Draft content, matching the issue's two criteria:

   > # Frozen expected corpus reports
   >
   > Files in this directory are frozen outputs of the corpus harness, used as the oracle for
   > drift detection by `scripts/corpus/diff.py`.
   >
   > **They are generated only by an explicit, human-invoked run of the harness against the real
   > pinned corpus.** No test and no diff-mode run ever writes here — regeneration is always a
   > deliberate, reviewed action.
   >
   > Reports are computed using `docs/corpus/manifest.toml`'s `excluded_dirs` verbatim, applied
   > mechanically and identically to every vault. No per-vault template or meta directories are
   > excluded.
   >
   > This means these reports **do not** reproduce the tables published in `docs/corpus-study.md`,
   > which additionally excluded one hand-picked directory per vault. That is deliberate:
   > `docs/corpus-study.md` is **not** the oracle for this harness.

   (No per-vault numbers are stated anywhere above — the numbers live in the generated reports.)

No expected report files are produced by this slice either way: generating them requires live
network access to the real corpus vaults, which this slice does not have.
