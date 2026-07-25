# graphmark

Deterministic knowledge-graph analysis for markdown / `[[wikilink]]` vaults — orphans, hubs,
clusters, bridges, siloed notes, neighborhoods, PageRank, and link-gap suggestions over your notes,
driven by a small config so it works on any Obsidian-family vault.

> Status: **v0.1.1 on PyPI.** The engine is complete and pinned by a frozen differential oracle —
> structural outputs reproduce a proven reference implementation exactly (shape, ordering,
> tie-breaking). See `CLAUDE.md` for the architecture and the reference-parity contract.

## Install

```bash
pip install graphmark        # or: uv pip install graphmark
```

Dev setup:

```bash
uv pip install -e ".[dev]"
```

## Test

```bash
uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pytest -q
```

## CLI

Every command takes `--config PATH` (TOML) and/or `--root PATH` (vault root; overrides the config's
root). Output is deterministic JSON (DOT for `export dot`).

```bash
graphmark stats                          --root /path/to/vault
graphmark orphans                        --config configs/my-brain.toml
graphmark hubs --n 10                    --root /path/to/vault
graphmark clusters                       --root /path/to/vault
graphmark bridges                        --root /path/to/vault
graphmark siloed                         --root /path/to/vault
graphmark neighborhood --note a/b.md --depth 2  --root /path/to/vault
graphmark pagerank --n 10 --alpha 0.85   --root /path/to/vault
graphmark export dot                     --root /path/to/vault > graph.dot
graphmark gaps                           --root /path/to/vault
```

Note: `gaps` is a **library-first** metric — it ranks and filters link-gap candidates over a
similarity function you inject (`metrics.gaps(graph, similar_fn, ...)`); the package itself ships no
embeddings. The CLI subcommand has no similarity source to inject, so `graphmark gaps` prints
guidance to stderr and exits 2 rather than silently returning `[]`; use the library API (below).

## Library

```python
from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import gaps, hubs, stats
from graphmark.parse import WikilinkExtractor

config = VaultConfig(root=Path("/path/to/vault"))
graph = VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())

print(stats(graph))
print(hubs(graph, n=10))

# gaps: you supply similarity — graphmark owns the deterministic ranking/filtering.
print(gaps(graph, similar_fn=my_similarity, threshold=0.6, k=8))
```

`dismiss.py` provides a content-hash dismissal store for gap suggestions: a dismissed pair stays
suppressed only while both notes exist with unchanged content.

## Development & releases

Two long-lived branches: **`dev`** is the integration branch (open PRs against it); **`main`** is
the release branch. Both are gated by CI (`ruff check` + `ruff format --check` + `pytest -q` on
Ubuntu and macOS).

Releases are automated by conventional commits. When `dev` is promoted to `main`,
`.github/workflows/release.yml` runs [python-semantic-release](https://python-semantic-release.readthedocs.io):
it reads the commit history since the last tag, bumps the version, updates `CHANGELOG.md`, tags
`v<version>`, cuts a GitHub release, and publishes to PyPI via OIDC Trusted Publishing. So the
version is a function of your commit messages — `feat:` bumps the minor, `fix:`/`perf:` the patch
(pre-1.0, breaking changes bump the minor, not the major). No manual version edits, no tokens.
