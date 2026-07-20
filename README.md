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
embeddings. The CLI subcommand currently runs with an empty similarity source and returns `[]`;
wiring a real similarity provider into the CLI is planned for 0.2.

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
