# graphmark

[![PyPI](https://img.shields.io/pypi/v/graphmark.svg)](https://pypi.org/project/graphmark/)
[![Python versions](https://img.shields.io/pypi/pyversions/graphmark.svg)](https://pypi.org/project/graphmark/)
[![License](https://img.shields.io/pypi/l/graphmark.svg)](https://github.com/cdcoonce/graphmark/blob/main/LICENSE)

Deterministic knowledge-graph analysis for markdown / `[[wikilink]]` vaults — orphans, hubs,
clusters, bridges, siloed notes, neighborhoods, PageRank, and link-gap suggestions over your notes,
driven by a small config so it works on any Obsidian-family vault.

Structural outputs are pinned by a frozen differential oracle: they reproduce a proven reference
implementation exactly, down to ordering and tie-breaking. See
[CLAUDE.md](https://github.com/cdcoonce/graphmark/blob/main/CLAUDE.md) for the architecture and the
reference-parity contract.

## Install

```bash
pip install graphmark        # or: uv pip install graphmark
```

Runtime dependency: `networkx` only. The package ships a `py.typed` marker, so mypy and pyright
see its annotations.

## Quickstart

```python
import graphmark

graph = graphmark.build("/path/to/vault")

print(graphmark.stats(graph))            # {'notes': 6, 'edges': 5, 'orphans': 2, ...}
print(graphmark.hubs(graph, n=10))       # [['brain/hub.md', 3], ...]
print(graphmark.orphans(graph, graphmark.VaultConfig(root="/path/to/vault")))
```

`build()` accepts a vault root (`str` or `Path`) or a fully configured `VaultConfig`. To drive it
from a TOML file, pair it with `load_config`:

```python
graph = graphmark.build(graphmark.load_config("vault.toml"))
```

## CLI

Every command takes `--config PATH` (TOML) and/or `--root PATH` (vault root; overrides the config's
root). Output is deterministic JSON on stdout (DOT for `export dot`); errors and warnings go to
stderr, so stdout is always safe to pipe.

```bash
graphmark stats                          --root /path/to/vault
graphmark orphans                        --config vault.toml
graphmark hubs --n 10                    --root /path/to/vault
graphmark clusters                       --root /path/to/vault
graphmark bridges                        --root /path/to/vault
graphmark siloed                         --root /path/to/vault
graphmark neighborhood --note a/b.md --depth 2  --root /path/to/vault
graphmark pagerank --n 10 --alpha 0.85   --root /path/to/vault
graphmark export dot                     --root /path/to/vault > graph.dot
graphmark check                          --config vault.toml
```

Exit codes: `0` success, `1` a `check` threshold breach, `2` a usage or config error. Nothing else
uses `1`, so CI can trust it.

## `graphmark check` — vault health as a CI gate

Declare thresholds in the config's `[check]` table, then run `graphmark check` as a build step. It
exits non-zero when the vault drifts past them.

```toml
root = "."

[check]
max_orphans = 10
max_unresolved_links = 0
max_siloed = 3
```

```console
$ graphmark check --config vault.toml
max_orphans: 14 exceeds limit 10
{"pass": false, "checks": [{"name": "max_orphans", "limit": 10, "actual": 14, "pass": false}, {"name": "max_unresolved_links", "limit": 0, "actual": 0, "pass": true}]}
$ echo $?
1
```

The JSON report is byte-stable — key order is fixed and checks appear in policy-declaration order —
so two runs over an unchanged vault diff to nothing. Thresholds are inclusive (`actual == limit`
passes), and only thresholds you set are reported.

Unknown keys inside `[check]` are a hard error rather than being ignored, and a config with no
thresholds at all exits `2` instead of reporting a meaningless green: a gate that can't fail is
worse than no gate.

## `gaps` — link suggestions with injected similarity

`gaps` is **library-first**. graphmark owns the deterministic ranking and filtering — already-linked
pairs, self-pairs, thresholds, prefix exclusions, dismissed pairs, reciprocal dedup, novelty-first
ordering — while _you_ supply the similarity source. No embeddings ship in this package, and the
test gate stays free of them.

```python
import graphmark

graph = graphmark.build("/path/to/vault")

def my_similarity(rel_path: str, k: int) -> list[tuple[str, float]]:
    """Return up to k (rel_path, score) pairs. Any embedding backend you like."""
    ...

# The band validated on a live ~340-note vault, as one keyword bundle.
suggestions = graphmark.gaps(graph, my_similarity, **graphmark.GAPS_DEFAULT_BAND)
```

`GAPS_DEFAULT_BAND` bundles `threshold=0.6`, `max_score=0.92`, `k=8`, `hub_degree=40` (also
available individually as `GAPS_DEFAULT_THRESHOLD` and friends). The `Similarity` protocol in
`graphmark.interfaces` types the callable you inject.

Because the CLI has no similarity source to inject, `graphmark gaps` prints guidance to stderr and
exits `2` rather than silently returning `[]`.

### Dismissing a suggestion

`dismiss` is a content-hash store: a dismissed pair stays suppressed only while both notes still
exist with unchanged content, so a rewrite re-opens the question.

| Function                                    | Purpose                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------- |
| `weaklink_sig(a, b)`                        | Stable, order-independent signature for a pair — the same one `gaps()` emits as `sig` |
| `record_dismissal(root, a, b, *, path=...)` | Persist a dismissal, hashing both notes' current content                              |
| `active_dismissed_sigs(root, *, path=...)`  | The signatures still valid (both notes present, unchanged)                            |
| `load_dismissed(root, *, path=...)`         | Raw store contents; a corrupt store reads as empty, never raises                      |

```python
graphmark.record_dismissal(root, "a/one.md", "b/two.md")

# Feed the live set back in, and that pair stops being suggested.
suggestions = graphmark.gaps(
    graph, my_similarity,
    dismissed=graphmark.active_dismissed_sigs(root),
    **graphmark.GAPS_DEFAULT_BAND,
)
```

The store lives under the vault root at `.claude/data/connect-dismissed.json`; pass `path=` to put
it elsewhere.

## Other metrics

```python
graphmark.pagerank(graph, n=10, alpha=0.85)   # importance ranking; matches networkx
graphmark.clusters(graph)                     # connected components, largest first
graphmark.bridges(graph)                      # articulation points
graphmark.siloed_notes(graph)                 # reachable only through a single bridge
graphmark.neighborhood(graph, "a/b.md", depth=2)
graphmark.to_dot(graph)                       # Graphviz DOT
graph.unresolved                              # {rel_path: [broken link displays]}
graph.catalog                                 # {normalized stem: [rel_paths]} — 2+ means ambiguous
graph.out_of_scope                            # same, for markdown outside the configured scope
```

`catalog` and `out_of_scope` are the resolution state the build consulted. They are what you need to
explain a link rather than just resolve it — which notes a bare `[[link]]` collided with, or whether
a link that failed to resolve points at a real file you deliberately excluded. Value lists are
sorted by rel_path.

## `diagnose` — why a link failed, not just that it did

`graph.unresolved` conflates two different problems. A link that matched _nothing_ needs its target
created or deleted; a link that matched _too much_ needs disambiguating against the notes it
collided with. `diagnose` separates them, and names the three cases that are not broken at all.

```python
d = graphmark.diagnose(graph, "2026-W27-tasks|W27 tasks")

d.reason      # 'ambiguous'
d.candidates  # ('personal/archive/tasks/2026-W27-tasks.md', 'work/archive/2026/tasks/2026-W27-tasks.md')
d.target      # None — set only when reason == 'resolved'
d.display     # echoed verbatim: what a human has to go and fix
```

| `reason`            | meaning                                                        | `candidates`        |
| ------------------- | -------------------------------------------------------------- | ------------------- |
| `resolved`          | names exactly one note; `target` is its rel_path               | —                   |
| `ambiguous`         | names several notes, so the resolver refused to pick           | the colliding notes |
| `non-note-file`     | targets a `.canvas` / `.base` / image / PDF — not indexed here | —                   |
| `out-of-scope-note` | targets real markdown outside the configured scope             | the unindexed paths |
| `missing`           | names nothing that exists — a genuine broken link              | —                   |
| `intra-note`        | `[[#Heading]]` / `[[#^block]]` — a same-note reference         | —                   |

`DIAGNOSIS_REASONS` holds that set in decision order, so a consumer can switch on it exhaustively.
Alias, anchor and `.md` forms all diagnose identically to the bare form.

`VaultGraph.build` classifies its own links through this same function, so a diagnosis can never
contradict the graph it describes: `unresolved` is exactly the displays diagnosing as `ambiguous` or
`missing`, and the edges are exactly the `resolved` non-self targets.

### Near-miss suggestions

Pass `suggest=k` to turn a `missing` verdict into an actionable one. Suggestions are computed only
for `missing` — every other reason already carries the rel_paths in play — so the default of `0`
costs nothing on the `check` hot path.

```python
graphmark.diagnose(graph, "Jordan", suggest=5).candidates
# ('people/Jordan Ellis.md',)
```

Matching is **directional**, which is what separates a suggestion from a wrong answer:

- a display inside a candidate name is an abbreviation — `[[Jordan]]` → `Jordan Ellis`, or
  `[[Mood Tracker]]` → `2026-04-11-mood-tracker` (pure-digit tokens are filing metadata, not
  content);
- a candidate inside a display is offered only when it covers at least `SUGGEST_MIN_COVERAGE` of it
  — `[[fable-prompt-technique-reference]]` → `fable-prompt-technique` is the answer, while
  `[[Dagster PJM InSchedules]]` → `Dagster` is a real note that is _not_ the target;
- partial overlap in neither direction is rejected;
- a display matching more than `SUGGEST_MAX_MATCHES` notes names a topic, not a typo, and gets
  nothing at all.

Notes whose stem is generic (`SKILL.md`, `README.md`) are matched on their **parent folder**, where
their name actually lives.

Both constants were calibrated against a human-annotated baseline of a real vault's broken links
rather than chosen by taste — see [`tests/fixtures/suggest/README.md`](tests/fixtures/suggest/README.md)
for the method and the measured result.

## Configuration

```toml
root = "."                                    # required unless --root is passed
scoped_folders = ["brain", "work"]            # limit the vault to these top-level folders
excluded_dirs = [".git", "templates"]         # skip notes under these directories
rules_files = ["CLAUDE.md", "CLAUDE.local.md"]  # agent-rules files, not vault content
transient_prefixes = ["daily/"]               # excluded from orphan reports
```

Unknown top-level keys are ignored; unknown keys inside `[check]` are an error.

## Development & releases

Two long-lived branches: **`dev`** is the integration branch (open PRs against it); **`main`** is
the release branch. Both are gated by CI — `ruff check` + `ruff format --check` + `pytest -q` on
Ubuntu and macOS across Python 3.11, 3.12, and 3.13.

```bash
uv pip install -e ".[dev]"
uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pytest -q
```

Releases are automated by conventional commits. When `dev` is promoted to `main`,
`.github/workflows/release.yml` runs [python-semantic-release](https://python-semantic-release.readthedocs.io):
it reads the commit history since the last tag, bumps the version, updates `CHANGELOG.md`, tags
`v<version>`, cuts a GitHub release, and publishes to PyPI via OIDC Trusted Publishing. So the
version is a function of your commit messages — `feat:` bumps the minor, `fix:`/`perf:` the patch
(pre-1.0, breaking changes bump the minor, not the major). No manual version edits, no tokens.
