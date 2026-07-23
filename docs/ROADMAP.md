# Roadmap — graphmark (for `afk-driver --expand`)

> Read **verbatim** by `afk-driver --expand` and injected into the feature-proposing agent's prompt
> alongside the live code. Write at the altitude of **intent** — name directions and gaps; let the
> expander (and the code it reads) propose specifics. **Every proposal must state which Track it
> advances** — that is how a human decides whether a green gate is sufficient.

## Vision

A general, deterministic **knowledge-graph analysis library + CLI** for markdown / `[[wikilink]]`
vaults — orphans, hubs, clusters, bridges, siloed notes, neighborhoods, PageRank, and link-gap
suggestions — driven by a small config so it works on **any** Obsidian-family vault. Published on
PyPI; generalized from a proven vault-specific engine (`brain_map.py`).

The central fact of this repo: **correctness is pinned by a frozen differential oracle.** Structural
outputs are the verbatim results of the reference engine, PageRank is checked against networkx, and
live-vault parity diffing backs the fixtures. The executor cannot regenerate the oracle — so a
**green gate proves correctness**, and Track A/C work is autonomous-safe.

Identity (settled 2026-07-19): graphmark is **personal infrastructure with a public correctness
story** — the priority consumer is the owner's vault seam (`graph_cli.py`), not external adoption.

## What's shipped (baseline — do not re-propose)

- **The full engine, v0.1.1 on PyPI**: `parse.py` (wikilink extraction, code-span skipping),
  `graph.py` (catalog + `NormalizeResolver` + `VaultGraph.build`), `metrics.py` (stats, orphans,
  hubs, clusters, bridges, siloed_notes, neighborhood, pure-python pagerank, gaps),
  `export.py` (JSON/DOT), `cli.py`, `config.py` (`VaultConfig` + `load_config`), and
  `dismiss.py` (content-hash weaklink dismissal store).
- **Six frozen differential fixtures** — simple, alt, scoped, selflink, gaps (+ out-of-graph),
  dismiss — plus live-vault parity diffs against the reference engine.
- **`gaps()` with injected similarity** — graphmark owns the deterministic ranking/filtering
  (already-linked / self / threshold / max-score / prefix / dismissed filters; reciprocal dedup;
  novelty-first ordering); the embedding source is injected by the caller. The gate stays
  fastembed-free.
- **Packaging** — PyPI Trusted Publishing on `v*` tags; networkx-only runtime dependency.
- **Reintegration** — the-vault's `graph_cli.py` consumes the package and injects the vault's
  similarity function; /connect and /garden run on it.

## Direction

### Track A — Engine parity (CLOSED at v0.1.1 — do not re-propose engine work)

### Track C — Hardening & honest surface (gate-verifiable; autonomous-safe)

_Where we are:_ v0.1.1 is correct on its parity paths but carries correctness debt and dead
surface no consumer exercises.
_Where we're going:_ **v0.2.0 — every error path tested, every public knob real.**

- Version single-sourcing (pyproject / `__init__.__version__` / smoke-test drift).
- Robustness: non-UTF8 note handling in `parse_document`; JSON-corruption guards in
  `dismiss.load_dismissed` / `active_dismissed_sigs`; `load_config` clear error on missing keys;
  DOT identifier escaping in `to_dot`; defined behavior for `neighborhood` on an unknown note.
- Cut or wire dead surface: `model.Edge/Graph/Finding` (never consumed); the CLI `gaps` stub
  (null `similar_fn` — always `[]`); make the dismissal-store path injectable instead
  of hardcoding `.claude/data/connect-dismissed.json`.
- Move the validated gaps banding policy (threshold / max-score / k / hub-degree defaults) from the
  consumer's argparse into the package so any consumer gets the proven band.
- A `Similarity` Protocol in `interfaces.py` typing the injected `similar_fn`.

_The principle:_ each slice is single-purpose with its asserting test **pre-frozen by the
conductor before dispatch** — the oracle-first discipline that closed the zero-test hole.

### Track D — `graphmark check`: the deterministic CI gate (feature track)

The one unserved niche the ecosystem offers: **headless vault-health gating**. Obsidian's official
CLI requires the desktop app; the dormant Python incumbent has no CLI; link checkers do no graph
metrics.

- `graphmark check --config ...` — thresholds (max orphans, max unresolved links, max siloed
  notes, ...), non-zero exit on breach, byte-stable JSON report for diffing across runs.
- Config-driven policy block (`[check]` in the TOML) so the gate is declarative.
- Later: a thin GitHub Action wrapper. The owner's vault dogfoods the gate first.

### Track B — Judgment the oracle can't cover (human-validated)

- New fixtures on a **different schema** than my-brain have hand-authored expected values → a human
  confirms them. Public API naming, packaging/release, and documentation voice are Track B.

## Principles every proposal must respect

- **The oracle is the spec.** Never edit an `expected.json` to pass a test. Match it; if it looks
  wrong, flag it.
- **Pre-frozen asserting tests.** New modules/behaviors ship only when the conductor has committed
  the failing test before the slice runs — a green gate must prove the new code, not just tolerate it.
- **The gaps contract:** graphmark owns deterministic ranking/filtering; similarity is **injected**;
  the package and its gate stay embedding-free (no fastembed/numpy/scipy in deps).
- **Implement within the seeded interfaces.** Do not redesign `model`/`interfaces`/`config`
  boundaries.
- **Dependency-light.** Shipped runtime dep is `networkx` only.
- **Keep the layers separate** — engine (vault-agnostic) / config (the domain seam) / surface
  (JSON, DOT, CLI) / dismissal store. See `CLAUDE.md`.
- **TDD, tracer-bullet slices.** `afk-sized` = single-purpose, independently testable; larger is
  `needs-decomposition`.

## Non-goals (CLOSED as dropped 2026-07-19 — do not propose)

Evaluated against the ecosystem and dropped for zero consumer pull; do not re-litigate:

- Embeddings / semantic search / any similarity backend **inside** the package.
- Betweenness centrality, Louvain/Leiden community detection.
- CSV/GML/Cypher export; incremental/cached builds; any LLM "propose" pass.
- MCP server or retrieval/search surface.
- Alternate link-syntax adapters (Logseq, `[](.)` markdown) — the pluggable interfaces exist so
  these _can_ be added on demand; do not build them speculatively.
- Re-platforming (no swapping networkx; no async/parallel rewrites).
- Performance work without a benchmark showing pain (the live consumer is a ~340-note vault). The
  known ceilings — O(L·N) path-suffix resolution, O(A·(V+E)) `siloed_notes`, per-metric graph
  rebuilds — are documented, accepted, and not to be optimized speculatively.
