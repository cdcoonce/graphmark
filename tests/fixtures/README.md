# Fixtures — the frozen differential oracle

Each fixture is a synthetic mini-vault (`<name>/vault/`) plus `<name>/expected.json` holding the
**ground-truth outputs graphmark must reproduce**. These expected values are NOT authored by hand or
by graphmark — they come from independent reference implementations, which is what makes the gate
ungameable.

## `simple/`

A 6-note vault exercising: a hub, a link chain, two orphans (an isolated note and a note whose only
link is unresolvable), an alias link (`[[Alpha|the first note]]`), and a code-span link that must be
ignored.

**Structural metrics** (`stats`, `orphans`, `hubs`, `clusters`, `bridges`, `neighborhood`) are the
verbatim JSON output of the reference engine:

```bash
BM=<my-brain>/.claude/scripts/brain_map.py
python3 "$BM" --vault-root simple/vault --stats
python3 "$BM" --vault-root simple/vault --orphans
python3 "$BM" --vault-root simple/vault --hubs
python3 "$BM" --vault-root simple/vault --clusters
python3 "$BM" --vault-root simple/vault --bridges
python3 "$BM" --vault-root simple/vault --neighborhood "brain/hub.md" [--depth 2]
```

**`pagerank`** is from networkx (the reference for that algorithm), alpha=0.85, dangling nodes
redistributed uniformly. graphmark implements PageRank itself (pure-python power iteration, no
scipy); its output must match the frozen ranking within `_tolerance` (1e-4). Reference:

```bash
uv run --with networkx --with scipy python3 -c "import networkx as nx; ..."
```

**Rule:** never edit an `expected.json` to make a test pass. If a value looks wrong, stop and flag
it — the oracle is the specification.
