# CHANGELOG


## v0.2.0 (2026-07-25)

### Bug Fixes

- **ci**: Let release.yml build with uv; skip semantic-release's own build
  ([`6989689`](https://github.com/cdcoonce/graphmark/commit/6989689a0672d79df143eee68a31ce6493573209))

The python-semantic-release action runs in a container without uv, so build_command='uv build'
  failed with exit 127 and aborted the release before any tag/publish. Set build_command='' so
  semantic-release only versions/tags/changelogs, and the workflow's own uv-based step (running on
  the runner host where uv is installed) builds and publishes.

- **cli**: Gaps subcommand exits 2 with guidance instead of printing []
  ([#59](https://github.com/cdcoonce/graphmark/pull/59),
  [`81b5fc1`](https://github.com/cdcoonce/graphmark/commit/81b5fc1dfb82c727ddd07e84c76d01598886b60a))

The gaps subcommand hardwired an empty similarity source and always printed [], so the package's
  most distinctive metric looked broken from its own command line. gaps needs a caller-injected
  similarity source the CLI can't supply, so 'graphmark gaps' now prints 'gaps requires an injected
  similarity source; use the library API (graphmark.metrics.gaps) — see README' to stderr and exits
  2 (honest signpost, chosen option). Stdout stays clean. README updated to match; drops the dead
  gaps import.

Closes #31

- **config**: Clear error when required 'root' key is missing
  ([#49](https://github.com/cdcoonce/graphmark/pull/49),
  [`70b275d`](https://github.com/cdcoonce/graphmark/commit/70b275d0173f9f229caa1e9e047f561843a781d1))

load_config indexed data['root'] unguarded, so a TOML without the only required key failed with a
  bare KeyError naming neither the file nor what was expected. Raise ValueError(f"config {path}:
  missing required key 'root'") instead, and document root as required / all other keys as optional
  in the docstring.

Closes #26

- **config**: Remove silent no-op knobs wikilink_pattern and orphan_min_chars
  ([#55](https://github.com/cdcoonce/graphmark/pull/55),
  [`98590ef`](https://github.com/cdcoonce/graphmark/commit/98590ef0ec7525d2eeab21987f8f311cb460bfb4))

Both fields were loaded from TOML and never consulted: _WIKILINK_RE is hardcoded in parse.py and
  orphans() consults only transient_prefixes. A config that set them lied to its author. Remove them
  from VaultConfig, load_config, and the reference configs/my-brain.toml. Removal is the
  behavior-preserving option (wiring orphan_min_chars=300 would change orphans() against the frozen
  oracles; wiring wikilink_pattern re-opens link-extraction parity). Unknown TOML keys are now
  documented as silently ignored. Human-approved config-schema break.

Closes #30

- **dismiss**: Treat a corrupt store as empty in load_dismissed
  ([#52](https://github.com/cdcoonce/graphmark/pull/52),
  [`6b5bdd1`](https://github.com/cdcoonce/graphmark/commit/6b5bdd140736c11e7872d3e54fac9f6e0aad8eaf))

load_dismissed indexed json.loads unguarded while record_dismissal already fell back to {} on
  (JSONDecodeError, OSError) — the two halves of the same store disagreed about failure, so a
  corrupt store crashed gap filtering. Mirror the existing guard: invalid JSON, an unreadable file,
  or a non-dict payload all return {}, so active_dismissed_sigs returns an empty set. A corrupt
  store means 'no active dismissals', never a crash.

Closes #24

- **export**: Escape quotes and backslashes in DOT output
  ([#48](https://github.com/cdcoonce/graphmark/pull/48),
  [`bbaab3c`](https://github.com/cdcoonce/graphmark/commit/bbaab3c8b5fa56d5ff643dd1a59679bd0f3de2c9))

to_dot interpolated raw note paths into quoted DOT identifiers with no escaping, so a filename
  containing " or \ produced invalid DOT that Graphviz rejects. Add a _dot_quote helper (backslash
  first, then quote) applied to every emitted identifier. Output for paths without special
  characters is byte-identical to before.

Closes #25

- **neighborhood**: Defined error for an unknown note
  ([#50](https://github.com/cdcoonce/graphmark/pull/50),
  [`eceb4c5`](https://github.com/cdcoonce/graphmark/commit/eceb4c5c5b3ae7b6612ed08f69744f8c00ab1bbb))

neighborhood() on a nonexistent note silently returned empty out/back lists, so a typo in --note was
  indistinguishable from a genuinely isolated note. metrics.neighborhood now raises
  ValueError('unknown note: <note>') when the note is not in graph.nodes; the CLI catches it, prints
  to stderr, and exits 2 (stdout stays JSON-only). Known-note output is byte-identical.

Closes #27

- **parse**: Decode non-UTF8 notes with replacement instead of crashing
  ([#51](https://github.com/cdcoonce/graphmark/pull/51),
  [`f42ad7b`](https://github.com/cdcoonce/graphmark/commit/f42ad7b23e0dbfac0681f775f37a2a489519ca16))

parse_document read notes with a bare read_text(encoding='utf-8'), so a single non-UTF8 file
  anywhere in the vault propagated UnicodeDecodeError and killed every graphmark command with a
  traceback. Read bytes and decode with errors='replace' on failure, keeping the note in the graph
  (node counts stay truthful) and emitting exactly one warning line per affected file to stderr —
  never stdout, so the JSON surface stays clean. Valid vaults are byte-identical and silent.

Closes #23

- **parse**: Fenced-code stripping respects fence length, not just char
  ([#53](https://github.com/cdcoonce/graphmark/pull/53),
  [`4b375fe`](https://github.com/cdcoonce/graphmark/commit/4b375fe151800df49d868bdfe4c063c7f1bf858f))

_strip_fenced_blocks tracked only which character opened a fence, so a shorter nested fence of the
  same character (a 3-backtick example inside a 4-backtick outer fence) closed the fence prematurely
  and leaked wikilinks inside code as real links — violating the documented 'ignore links inside
  code spans' invariant. Track the opening fence's character AND length; only close on the same
  character with length >= the opening length (CommonMark's fence-closing rule).

Closes #33

- **version**: Single-source __version__ from package metadata
  ([#47](https://github.com/cdcoonce/graphmark/pull/47),
  [`1db7e8d`](https://github.com/cdcoonce/graphmark/commit/1db7e8d2cfd89c91cdd1f75dd5a586a46064a063))

Derive __version__ via importlib.metadata.version('graphmark') with a PackageNotFoundError fallback
  of 0.0.0+unknown for un-installed source checkouts. Smoke test now compares against
  importlib.metadata instead of a hardcoded literal, so the wheel can never again self-report a
  stale version (published 0.1.1 wheel reported 0.1.0).

Closes #22

### Chores

- Commit dev-cycle telemetry and post-release uv.lock
  ([`9379914`](https://github.com/cdcoonce/graphmark/commit/937991436e7db0d74d58f35811b72f9e43f26253))

docs/dev-cycle/ is the build-#1 afk telemetry dataset (42 attestation rows, quarantine log,
  last-run) — tracked, not ignored, per the dogfood directive. uv.lock carries the 0.1.0->0.1.1 bump
  left behind by the release commit.

- Sync uv.lock for 0.2.0
  ([`4232227`](https://github.com/cdcoonce/graphmark/commit/4232227f9176e0576327d9642f811642bbcf0320))

- **afk**: Add missing [model] tier map to config
  ([`458762f`](https://github.com/cdcoonce/graphmark/commit/458762f701a18549d8a325d9454938aa312ab3ff))

The driver requires model.cheap when default_tier resolves to 'cheap' (its default). The config had
  no [model] section, so every scheduled cycle aborted at config load with ConfigError, blocking the
  entire promoted backlog (#23-#32, all afk:cheap). Mirror afk-cockpit's tier map: cheap=sonnet,
  frontier=opus.

### Continuous Integration

- Add per-PR gate on ubuntu+macos; gate before build in publish
  ([`0d76209`](https://github.com/cdcoonce/graphmark/commit/0d76209252df1562a0681b6e622ed713e66b1bb3))

The afk gate runs Linux-only, so OS-specific escapes only surfaced at release. ci.yml mirrors the
  gate command exactly on both OSes for every push/PR. publish.yml now gates before building the
  artifact it publishes.

- Automate releases on dev->main with semantic-release; bump to 0.2.0
  ([`d6c2c04`](https://github.com/cdcoonce/graphmark/commit/d6c2c045517dbe4c69aec5495a61ec2010764aa6))

Adopt a dev/main branch model with deploy-on-promotion. dev is the integration branch; promoting dev
  to main triggers release.yml, which runs the gate, then python-semantic-release reads the
  conventional-commit history to bump the version, update CHANGELOG.md, tag v<version>, cut a GitHub
  release, and publish to PyPI via OIDC Trusted Publishing.

- pyproject: baseline version 0.2.0 (the honest-surface API cut) + a [tool.semantic_release] config
  (major_on_zero=false so pre-1.0 breaking changes bump the minor; version single-sourced in
  pyproject). - ci.yml: gate main and dev (plus PRs). - release.yml: new; replaces the tag-triggered
  publish.yml (its trusted publish now runs inline only when a release is actually cut). -
  CHANGELOG.md: seeded; henceforth generated by semantic-release. - README: document the branch
  model + automated release flow.

### Documentation

- Seeded-interface rule yields to human-triaged issue direction
  ([`a88bc28`](https://github.com/cdcoonce/graphmark/commit/a88bc28501be7f08a1a9ee8467919b764bba5c31))

Issues #29/#30 are triaged decisions that change the seeded surface (remove dead model dataclasses,
  remove no-op config knobs). The standing CLAUDE.md non-negotiable and the afk agent_prompt both
  said 'do not redesign the seeded interfaces' unconditionally, which would put the executor in a
  contract conflict on those slices. The rule now names the exception: an issue that explicitly
  directs a seeded-surface change (a recorded human triage) wins.

- Truth-up contract docs post-0.1.1
  ([`6ff2c48`](https://github.com/cdcoonce/graphmark/commit/6ff2c48a083f31de5516892f9f32b183c376587b))

README/ROADMAP/CLAUDE.md described a pre-ship repo: engine 'being built', 5/10 CLI commands with
  wrong syntax, load_config 'unimplemented', dismiss.py and siloed absent from the contract. ROADMAP
  is the afk --expand grounding doc, so the stale copy would have proposed already-built work.

- README: v0.1.1 status, all 10 subcommands with real flags, library usage, gaps CLI-stub caveat -
  ROADMAP: Track A closed; Track C (hardening -> 0.2) and Track D (graphmark check CI gate) added;
  non-goals closed as dropped - CLAUDE.md: dismiss.py added as the fourth part, siloed added to the
  parity list, the gaps injected-similarity contract codified - config.py: docstring no longer
  claims load_config is unimplemented

### Features

- **gaps**: Ship validated banding policy as package-level constants
  ([#60](https://github.com/cdcoonce/graphmark/pull/60),
  [`2d01499`](https://github.com/cdcoonce/graphmark/commit/2d014997eea239bd1823bef25529cacf08e62a84))

The validated gaps band (threshold 0.6, max_score 0.92, k 8, hub_degree 40) — proven in daily
  /connect + /garden use on the owner's live vault — lived only in the consumer's argparse defaults,
  so any second consumer re-derived policy from scratch and gaps()'s own defaults are unvalidated.
  Ship the band in-package as named constants (GAPS_DEFAULT_*) with provenance recorded in a
  comment. Chosen the non-breaking shape: gaps()'s signature defaults are untouched, so the frozen
  gaps fixtures (which pass explicit params) stay byte-identical; consumers opt in.

Closes #32

- **interfaces**: Add Similarity Protocol typing the injected similar_fn
  ([#54](https://github.com/cdcoonce/graphmark/pull/54),
  [`eefd039`](https://github.com/cdcoonce/graphmark/commit/eefd0393dcfefa16165391db82457d1115fca0f2))

gaps()'s injected similar_fn is the package's similarity seam but was untyped — its contract was
  only discoverable by reading metrics.py. Add a Similarity Protocol to interfaces.py (where
  LinkExtractor/Resolver already live) codifying the (rel_path, k) -> list[(rel_path, score)] shape,
  annotate metrics.gaps' parameter, and reference the contract in its docstring. Additive typing
  only; no runtime behavior change.

Closes #28

### Performance Improvements

- **graph**: Cache flattened path list for folder-style link resolution
  ([#56](https://github.com/cdcoonce/graphmark/pull/56),
  [`958c642`](https://github.com/cdcoonce/graphmark/commit/958c6426be4c033b3c8ef379f9eae50dac84573e))

NormalizeResolver.resolve rebuilt the full flattened path list ([p for paths in catalog.values() for
  p in paths]) on every folder-style link, making resolution O(notes x folder-links). catalog is
  invariant for a whole VaultGraph.build(), so cache the flattened list keyed on id(catalog)
  (single-slot: a new catalog evicts the previous). Signature and Resolver Protocol unchanged;
  results are behavior-preserving.

Closes #34

### Refactoring

- **model**: Remove dead seeded dataclasses Edge/Graph/Finding (0.2 API cut)
  ([#58](https://github.com/cdcoonce/graphmark/pull/58),
  [`3f32d3a`](https://github.com/cdcoonce/graphmark/commit/3f32d3af692b49497aee53cd52811b7c4c8d7490))

model.Edge, model.Graph, and model.Finding were dead public surface — nothing in the package or any
  consumer constructed or imported them (the engine uses graph.VaultGraph; Document is the only
  model type in use). Dead 'seeded boundary' types misled library users about the real API. Remove
  all three as the 0.2 honest-surface cut; Document stays. Add model.__all__ = ['Document'] and a
  public-surface test so the dead types can't silently reappear. Sync CLAUDE.md ('a Graph' -> 'a
  VaultGraph') and docs/ROADMAP.md. Human-approved public-API break.

Closes #29

### Testing

- **siloed**: Pin equal-size component tie-break; make it explicit
  ([#57](https://github.com/cdcoonce/graphmark/pull/57),
  [`cde5ecd`](https://github.com/cdcoonce/graphmark/commit/cde5ecd20f0dc692ecf19afb0ae74717510404cb))

siloed_notes picked the largest post-bridge-removal component as mainland; when two components tied
  for largest, which became mainland depended silently on nx.connected_components' traversal order.
  No frozen fixture exercises a tie, so it was unverified. Break ties explicitly by member order
  (lexicographically-smallest-membered component is mainland) and add an inline test constructing a
  single articulation point whose removal yields two equal-size components, asserting deterministic
  output. Non-tie cases (all frozen oracles) are byte-identical since size dominates the sort key.

Closes #35


## v0.1.1 (2026-07-01)

### Chores

- Package metadata + MIT license for PyPI publish
  ([`ef30b45`](https://github.com/cdcoonce/graphmark/commit/ef30b45f7a5f92727a3fca5d34c920c7bb7a6e0e))

Add license (MIT), authors, keywords, classifiers, project URLs; add LICENSE file; constrain the
  sdist to real package contents (was bundling .afk agent transcripts → 1.2MB, now 26KB). Wheel
  verified installing in a clean env with the graphmark console script working end-to-end.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Continuous Integration

- Add PyPI trusted-publishing workflow (tag v* -> publish, no token)
  ([`c46ec3b`](https://github.com/cdcoonce/graphmark/commit/c46ec3b012fbe285a92e334318e171786bd7ae69))

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- Drop environment requirement from publish workflow for zero-config trusted publishing
  ([`485a784`](https://github.com/cdcoonce/graphmark/commit/485a784bcc2c932223cf4b4632db450fbb855ab5))

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Testing

- **fixtures**: Freeze alt `siloed` oracle for afk #6 (issue #11)
  ([`563aa61`](https://github.com/cdcoonce/graphmark/commit/563aa617f703dad386bf73e9506ee6727454ba01))

Computed by running brain_map.py's OWN siloed_notes() on the alt graph (the reference engine IS the
  spec). It deliberately includes pre-existing orphans (daily/orphan/stub) alongside the nodes cut
  off behind articulation point echo (delta/foxtrot); graphmark must reproduce this verbatim
  (parity, quirk included). Guessing the "intuitive" [delta,foxtrot] would have frozen a wrong
  oracle — compute from the reference, never guess (afk-agent-system#654).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Freeze alt-fixture pagerank oracle for afk #4
  ([`803e6f1`](https://github.com/cdcoonce/graphmark/commit/803e6f1ec4e1a37914509b4b44c94807d07b172f))

Generated via networkx's pure-python reference (_pagerank_python, alpha=0.85) and cross-checked to
  reproduce simple/expected.json's pagerank exactly, so the same trusted method backs both oracles.
  A correct pure-python power-iteration impl must now match BOTH fixtures — closing the
  single-fixture overfitting gap where #4's pagerank could otherwise be hardcoded to simple's six
  values.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Pre-freeze alt vault oracle + config.toml for afk #3
  ([`d889dcf`](https://github.com/cdcoonce/graphmark/commit/d889dcfe3efc5905c0f3879284f67186273af903))

Hand-authored, human-conductor-frozen BEFORE afk dispatch so the executor asserts against oracles it
  cannot write — the same trust model as the brain_map-generated simple/expected.json. brain_map.py
  is hardcoded to my-brain and cannot generate an oracle for a foreign vault, so slice #3
  (generalization) had no ungameable oracle; the executor's first attempt manufactured its own
  expected.json and was correctly quarantined.

- tests/fixtures/alt/: 10-note vault with different folder names (docs/refs/misc/daily) and distinct
  topology (2 clusters sized 4 & 3, an articulation point, a transient daily note, an
  unresolved-link orphan) to prove graphmark is not hardcoded to my-brain. -
  tests/fixtures/alt/expected.json: structural keys only; verified byte-for-byte against the trusted
  engine. pagerank deferred to #4 (networkx is its independent oracle, runnable on any vault). -
  tests/fixtures/simple/config.toml: drives the engine through load_config over the original
  oracle's vault, so #3 can assert config-path == hardcoded-path.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Pre-freeze dismiss/ oracle for afk #7 (issue #12)
  ([`3ab046c`](https://github.com/cdcoonce/graphmark/commit/3ab046c28cacf462102367353981154076cb8ba1))

Active-sig set computed by brain_map.py's OWN active_dismissed_sigs() (reference engine = spec), per
  afk-agent-system#654. connect-dismissed.json records three weaklink dismissals: alpha|beta
  (correct hashes → ACTIVE), alpha|gamma (stale gamma hash → STALE), alpha|delta (delta.md missing →
  STALE). Reference output: active = ['weaklink|alpha.md|beta.md'].

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Pre-freeze gaps/ oracle + fake similar_fn for afk #8 (issue #13)
  ([`28b4e2f`](https://github.com/cdcoonce/graphmark/commit/28b4e2f99a33005240f1dc55c8755e140f199d0a))

Oracle computed by feeding graphmark's OWN built graph into brain_map.py's gaps() (reference engine
  = spec), per afk-agent-system#654. similar.json is a deterministic fake similar_fn (NO embeddings
  — the embedding source is injected; graphmark owns the ranking/filter algorithm). Exercises every
  branch: already-linked, threshold, max_score, dismiss, reciprocal dedup, cross-folder ranking, and
  hub demotion (hub<->d 0.80 ranks below d<->a 0.75 because docs/hub.md is a hub).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Pre-freeze out-of-graph gaps oracle for afk #10 (defensive degree)
  ([`27be377`](https://github.com/cdcoonce/graphmark/commit/27be377e88547b7eb4b6d7a0952656c47d54469b))

A live vault run of the graph_cli adapter crashed graphmark's gaps(): _hub() calls G.degree(r),
  which raises for a note returned by similar_fn that is NOT a graph node (semantic index scope >
  graph scope). brain_map treats unknown nodes as degree 0 (non-hub). Oracle computed via brain_map;
  graphmark must match.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Pre-freeze scoped/ include-list oracle for afk #5 (issue #10)
  ([`bb02fc8`](https://github.com/cdcoonce/graphmark/commit/bb02fc859822511602bd07fefb92ff60bafdfa3c))

Human-conductor-frozen before dispatch, per the oracle-pre-freeze discipline (afk-agent-system#654).
  scoped_folders=['docs','refs'] include-list: only docs/one.md + refs/two.md are in the graph;
  misc/ and junk/ notes (and the link originating in misc/) must vanish. Verified against the
  trusted engine by simulating the include-list via excluded_dirs (equivalent). Fails on current
  main (scans all → notes=4), passes once scoped_folders is honored.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **fixtures**: Pre-freeze selflink/ oracle for afk #9 (self-edge parity fix)
  ([`fb6c014`](https://github.com/cdcoonce/graphmark/commit/fb6c014ed71e76b41176b90bd22756705b6a56a1))

A live-vault diff of graphmark vs brain_map found graphmark's ONLY structural divergence: it creates
  a self-loop for a note that links to itself ([[Key Decisions]] inside Key Decisions.md), while
  brain_map drops self-links. This fixture pins the correct behavior: a.md links to [[a]] and [[b]]
  -> exactly one edge a->b, no self-loop. Frozen before dispatch (afk-agent-system#654).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
