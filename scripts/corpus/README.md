# scripts/corpus/ conventions

Harness scripts for the corpus study -- not part of the graphmark engine or its public package
surface (see each module's own docstring).

## Confirm repo identity before mutating git commands

Any script under `scripts/corpus/` that shells out to `git` against a config- or caller-supplied
directory (a cache entry, a checkout target, anything not created fresh in the same call) must
confirm that directory is actually the root of its own git repository *before* running any
mutating command against it (`fetch`, `checkout`, `reset`, etc.).

Why: git resolves `.git` by walking **up** the directory tree from `cwd`. If the supplied directory
exists but is not itself a git repo -- a stray leftover from an interrupted clone, or any other
non-repo directory that happens to be nested inside an unrelated, enclosing repository -- a command
run with `cwd=<that directory>` does not fail. It silently resolves against the **enclosing** repo
instead, and a mutating command (`checkout`, `reset --hard`, etc.) then acts on that enclosing
repo's working tree, not the intended target.

The check: run `git rev-parse --show-toplevel` with `cwd` set to the target directory, and compare
its output against the target -- **resolve both sides** (`Path.resolve()`) before comparing.
`--show-toplevel`'s output can differ from the target by symlink normalization alone (e.g. macOS
`/tmp` is a symlink to `/private/tmp`, and a caller-supplied path may not already be normalized to
match), which would false-positive a plain string comparison. If the command fails, or the resolved
paths don't match, the directory is not the target's own repo root -- raise `ValueError` naming
both the artifact/vault and the path; do not proceed to any fetch/checkout, and do not auto-delete
or auto-reclone the directory (removal policy for a disposable-but-untrusted cache entry is a
separate decision, not implied by this check).

Reference implementation: `_is_repo_root` / `fetch_vault` in `fetch.py`.
