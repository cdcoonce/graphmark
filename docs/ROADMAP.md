# Roadmap — graphmark (for `afk-driver --expand`)

> Read **verbatim** by `afk-driver --expand` and injected into the feature-proposing agent's prompt
> alongside the live code. Write at the altitude of **intent** — name directions and gaps; let the
> expander (and the code it reads) propose specifics. **Every proposal must state which Track it
> advances** — that is how a human decides whether a green gate is sufficient.

## Vision

A general, deterministic **knowledge-graph analysis library + CLI** for markdown / `[[wikilink]]`
vaults — orphans, hubs, clusters, bridges, neighborhoods, and PageRank — driven by a small config so
it works on **any** Obsidian-family vault. It generalizes a proven vault-specific engine
(`brain_map.py`) into a standalone, pip-installable, publishable package.

The central fact of this repo: **correctness is pinned by a frozen differential oracle.** Structural
outputs are the verbatim results of the reference engine (`brain_map.py --vault-root`), and PageRank
is checked against networkx. Both are independent of anything the executor writes, and the executor
cannot regenerate them — so a **green gate proves correctness**, and nearly all work is Track A.

## What's shipped (baseline — do not re-propose)

- **The seed (Phase 0).** Package scaffold, `.afk` gate, `CLAUDE.md` contract.
- **Seeded boundaries** — `model.py` (Document/Edge/Graph/Finding), `interfaces.py`
  (`LinkExtractor`/`Resolver` Protocols), `config.py` (`VaultConfig`; `load_config` is a stub).
- **`configs/my-brain.toml`** — the reference config instance.
- **The frozen oracle** — `tests/fixtures/simple/`: a synthetic vault + `expected.json` holding
  `brain_map`'s verbatim structural output plus networkx PageRank.
- The engine itself — `parse.py`, `graph.py`, `metrics.py`, `export.py`, `cli.py` — **does not exist
  yet.** That is the work.

## Direction

### Track A — Engine, correctness & packaging (gate-verifiable; autonomous-safe)

_The frozen oracle can verify these. Safe to promote on a green gate._

- _Where we are:_ boundaries and the oracle exist; no engine. The current bottleneck is
  **parse + graph + link resolution** (issue #1) — nothing else can be verified until the graph builds.
- _Where we're going:_ a config-driven engine whose structural metrics reproduce `brain_map` **exactly**
  (shape, ordering, tie-breaking), a `load_config` that makes every vault-specific behavior parametric,
  net-new **pure-python PageRank**, DOT export, and a CLI. All checked against frozen fixtures.
- _The principle:_ every correctness property is pinned by a fixture derived from an independent
  reference; matching the fixture IS the contract that lets afk build unsupervised.

### Track B — Judgment the oracle can't cover (human-validated)

_The gate confirms "matches the frozen fixture"; it cannot confirm a **new** fixture's expected values
are right, nor adjudicate API taste._

- New fixtures on the **my-brain schema** derive expected values from `brain_map` → still Track A.
  New fixtures on a **different schema** (e.g. the generalization fixture in issue #3) have
  hand-authored expected values → **Track B**: a human confirms them.
- Public API naming, packaging/release, and documentation voice are Track B.

## Principles every proposal must respect

- **The oracle is the spec.** Never edit an `expected.json` to pass a test. Match it; if it looks
  wrong, flag it.
- **Implement within the seeded interfaces.** Do not redesign `model`/`interfaces`/`config` boundaries.
- **Dependency-light.** Shipped deps are `networkx` only — **no scipy/numpy** in the package;
  PageRank is pure-python power iteration.
- **Keep the three layers separate** — engine (vault-agnostic) / config (the domain seam) / surface
  (JSON, DOT, CLI). See `CLAUDE.md`.
- **TDD, tracer-bullet slices.** `afk-sized` = single-purpose, independently testable; larger is
  `needs-decomposition`.

## Non-goals (out of scope — do not propose)

- Semantic "gaps" / embeddings (keep the gate fastembed-free), betweenness centrality, Louvain/Leiden
  community detection, CSV/GML/Cypher export, incremental/cached builds, any LLM "propose" pass.
- Alternate link-syntax adapters (Logseq, markdown `[](.)` links) — the pluggable interfaces exist so
  these *can* be added later; do not build the implementations now.
- Re-platforming — no swapping networkx for another graph backend; no async/parallel rewrites.
