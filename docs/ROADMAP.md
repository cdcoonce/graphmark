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

- **The full engine, v0.6.0 on PyPI**: `parse.py` (wikilink extraction, code-span skipping,
  frontmatter incl. block lists), `graph.py` (catalog + `NormalizeResolver` + `VaultGraph.build` +
  `unresolved` + `diagnose`/`LinkDiagnosis` + frontmatter aliases), `metrics.py` (stats, orphans,
  hubs, clusters, bridges, siloed_notes, neighborhood, pure-python pagerank, gaps), `check.py`
  (policy evaluation), `export.py` (JSON/DOT), `cli.py`, `config.py` (`VaultConfig` +
  `CheckPolicy` + `load_config`), and `dismiss.py` (content-hash weaklink dismissal store).
  Tracks A, C, D and E are all closed — read their sections before proposing anything in those
  areas.
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

### Track C — Hardening & honest surface (CLOSED at v0.2.0 — do not re-propose)

Every item shipped: version single-sourcing, non-UTF8 notes, dismiss-store JSON guards,
`load_config` errors, DOT escaping, `neighborhood` on an unknown note, the dead-surface cut
(`model.Edge/Graph/Finding` gone — `Document` is the only model type; the no-op `wikilink_pattern`
/ `orphan_min_chars` knobs gone; the CLI `gaps` stub exits 2), the `GAPS_DEFAULT_*` banding
constants, and the `Similarity` Protocol. `py.typed`, the 3.11–3.13 CI matrix, `--version`, and
unified exit-code 2 for usage errors came with it.

### Track D — `graphmark check`: the deterministic CI gate (SHIPPED at v0.3.0)

The one unserved niche the ecosystem offers: **headless vault-health gating**. Obsidian's official
CLI requires the desktop app; the dormant Python incumbent has no CLI; link checkers do no graph
metrics.

Shipped: `graph.unresolved`, the `[check]` policy block (`max_orphans` /
`max_unresolved_links` / `max_siloed`, strict on unknown keys), `graphmark check` with exit 1
reserved for breach and a byte-stable JSON report, `graphmark.build()` + curated top-level
re-exports, and a README rewritten around the real surface.

_Where we are (0.3.4):_ the gate works and the vault dogfoods it. The remaining risk is the
**credibility of its flagship number**. Four false-positive classes have been found and fixed by
triaging a real vault against the metric — same-note anchors (#98, 19% of the count),
non-markdown targets (#101, 10%), the `.md` extension (#104), and links to notes that exist but
are out of graph scope (#107, 7%). A threshold nobody trusts is not a gate.

_Where we're going:_ keep truthing the metric against live vaults, then the thin GitHub Action
wrapper — but only once the count is trustworthy enough to fail someone's build.

### Track E — One resolver: absorb the consumer's second link stack (feature track)

_The problem:_ the-vault's `graph_gardener.py` (Lane A) carries its **own** parse / catalog /
normalize / resolve stack, independent of this package's. The two drift, and drift here is
user-visible: the gardener spent weeks proposing repairs for working links that graphmark had
already learned were fine. #107 is the fourth fix that had to be applied in two places.

The gardener's stack survives because it answers questions graphmark cannot yet answer. graphmark
says _whether_ a link resolves; Lane A needs to know **why it failed and what to do about it** —
the ambiguity set, the near-miss candidates behind a "did you mean", and the canonical title of
the note a display resolves to (so `[[jordan ellis]]` can be repaired to `[[Jordan Ellis]]`).

_Where we're going:_ a documented, typed **link-diagnosis** surface that makes the consumer a
formatter over graphmark's answers instead of a second resolver. The classification is already
implicit in `build` — resolved / ambiguous / out-of-scope note / non-note file / intra-note
reference / missing — it is simply thrown away. Candidate suggestion is the one genuinely new
behavior, and it is the piece a human must confirm: freeze a differential oracle from the current
gardener's hints on a real vault before changing anything.

Sliced as #110 (retain the catalogs), #111 (`LinkDiagnosis` + `diagnose()`), #112 (near-miss
suggestions — **not autonomous-safe past freezing the baseline**; the human annotation gate is the
point of it). The consumer-side deletion is hand-coded in the vault; the package side is afk-able.

_Constraint:_ this is additive. Nothing here may change what resolves or what an edge is.

**CLOSED at v0.6.0.** #110/#111/#112 shipped, and frontmatter aliases moved in-package (#119) —
the last piece of the consumer's parallel stack. the-workshop#474 deletes the consumer side.

### Track F — Auditable link accounting (the current epic)

_The problem is not any individual bug; it is how they get found._ Every correctness bug in this
package's history was found the same way: a human reading link lists from **one** vault. Seven so
far — #98 same-note anchors, #101 non-markdown targets, #104 the `.md` extension, #107 out-of-scope
notes, #119 frontmatter aliases, #123 Unicode NFD/NFC, plus the whitespace-padded displays fixed
alongside #107. Six of those seven landed in a single day of hand-triage.

The frozen differential oracle is a **ratchet, not a detector.** It prevents regression superbly and
has never once surfaced something new. Worse, the single consumer's seam actively _conceals_
package defects: its `AliasResolver` hid a 23-link error for six releases, because the only vault
that could have exposed the gap had already patched around it.

_Why the bugs hide:_ the buckets are silent. `build` sorts every extracted display into one of the
six `DIAGNOSIS_REASONS`, then reports **one** of them. A vault owner sees `N unresolved` and nothing
about what was suppressed — and six of the seven bugs were _mis-bucketing_, a link filed as
`unresolved` that belonged in `resolved` or the reverse. Had graphmark printed

```
3677 edges · 23 unresolved · 0 alias-resolved · 12 out-of-scope · 8 non-note-file · 19 intra-note
```

the alias gap would have been obvious at a glance: zero alias-resolved beside 23 unresolved is
visibly wrong. Nobody could see it, so nobody saw it for six releases.

_Where we're going:_ **every extracted display lands in exactly one named bucket; the buckets are
counted, reported, and bound by a property-tested conservation law.** The aim is not another metric
— it is to make the package's own answers auditable, so an implausible distribution is visible to
its owner without a day of triage. That is the mechanism that scales past one vault and one human,
and it is the strongest possible expression of the "public correctness story" identity.

Sliced as #124 (per-reason counts + the conservation law), #125 (`graphmark links` surfaces the
distribution), #126 (property-based vault generation — **the detector**; expect it to fail on first
run, and file what it finds), #127 (implausibility heuristics — advisory only, **not
autonomous-safe past the exact checks**, since the statistical thresholds need the same human
calibration gate #112 used).

Track F's own success measure is not slices merged: it is **bugs found by machinery rather than by
a human reading link lists.** #126's catch rate is the evidence.

_Deliberately deferred behind this:_ the Track D GitHub Action. It is an adoption play, and adoption
is not this repo's game; more to the point, shipping a gate that fails other people's builds while
the tool's own accounting is unauditable is backwards ordering. Generality work (Windows paths,
markdown-style `[text](note.md)` links for wikilink-disabled vaults, non-my-brain schemas) is real
but is a feature list, not an epic — and this track is what will tell us which parts of it matter.

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
