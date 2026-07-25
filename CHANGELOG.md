# CHANGELOG

<!--
This file is maintained automatically by python-semantic-release. On each promotion of `dev`
to `main`, the release workflow regenerates it from the conventional-commit history. Do not edit
it by hand — write good `feat:` / `fix:` / `perf:` commit messages instead.
-->

## v0.2.0 (unreleased until first dev -> main promotion)

Honest-surface & hardening pass (the "0.2 API cut"):

- **Breaking:** removed the dead seeded dataclasses `model.Edge` / `model.Graph` / `model.Finding`
  (`Document` is the only model type); removed the silent no-op config knobs `wikilink_pattern`
  and `orphan_min_chars`; `graphmark gaps` now exits 2 with guidance instead of printing `[]`.
- **Robustness:** non-UTF8 notes decode with replacement instead of crashing; corrupt dismissal
  store treated as empty; `load_config` raises a clear error on a missing `root`; DOT identifiers
  escape `"`/`\`; `neighborhood()` raises on an unknown note; fenced-code stripping respects
  fence length.
- **API/typing:** `interfaces.Similarity` protocol for the injected `similar_fn`; validated gaps
  banding shipped as `metrics.GAPS_DEFAULT_*` constants.
- **Perf:** folder-style link resolution caches the flattened path list per catalog.
- **Packaging:** `__version__` single-sourced from package metadata.
