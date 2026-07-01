# graphmark

Deterministic knowledge-graph analysis for markdown / `[[wikilink]]` vaults — orphans, hubs,
clusters, bridges, neighborhoods, and PageRank over your notes, driven by a small config so it works
on any Obsidian-family vault.

> Status: **early**. Engine modules are being built against a differential oracle (a proven
> reference implementation's frozen outputs). See `CLAUDE.md` for the architecture and the
> reference-parity contract.

## Install (dev)

```bash
uv pip install -e ".[dev]"
```

## Test

```bash
uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pytest -q
```

## Usage (once built)

```bash
graphmark stats     --config configs/my-brain.toml --root /path/to/vault
graphmark orphans   --config configs/my-brain.toml --root /path/to/vault
graphmark hubs 10   --config configs/my-brain.toml --root /path/to/vault
graphmark pagerank  --config configs/my-brain.toml --root /path/to/vault
graphmark export dot --config configs/my-brain.toml --root /path/to/vault > graph.dot
```
