# CHANGELOG


## v0.7.1 (2026-07-25)

### Bug Fixes

- **graph**: Match path-suffix links on component boundaries (#136)
  ([#140](https://github.com/cdcoonce/graphmark/pull/140),
  [`3c23b1a`](https://github.com/cdcoonce/graphmark/commit/3c23b1a04a86cdf1c482075c976ed5db86f4e18e))

`[[work/Tasks]]` resolved to `homework/Tasks.md`. Path-suffix resolution tested a raw string suffix,
  so nothing required the character before the match to be `/`.

This is the first defect class in this package that fabricates an *edge* rather than moving a link
  between reported buckets, and it is invisible by construction: the link counts `resolved`, so no
  bucket looks implausible, while orphans, hubs, clusters, bridges, siloed_notes and PageRank all
  read a graph that does not describe the vault. The mirror case is equally wrong — when the real
  folder also exists, the spurious second match makes the resolver decline a correct link and report
  it ambiguous.

`_matches_path_suffix` requires the match to consume the whole rel_path or be preceded by `/`, and
  both the resolver and `candidates_for` go through it, so the ambiguity set a consumer is shown can
  never contain a path the resolver would not have considered.

Measured on the reference vault: 0 occurrences, graph byte-identical. Latent, not absent — it needs
  one folder whose name ends with another's (`work`/`homework`, `ops`/`devops`,
  `<x>`/`archive-<x>`), which is ordinary.

- **parse**: Strip a leading UTF-8 BOM before the frontmatter split (#137)
  ([#141](https://github.com/cdcoonce/graphmark/pull/141),
  [`e92afd6`](https://github.com/cdcoonce/graphmark/commit/e92afd6484d4d8b966122df1db858cd791b33e0a))

`_FM_RE` is anchored with `.match` and decoding leaves U+FEFF at index 0, so a BOM'd note had no
  frontmatter at all. One cause, two opposite symptoms: its `aliases:` never registered, so links
  written against them were phantom breaks (#119's class, reintroduced through the parser); and its
  frontmatter wikilinks stayed in the body and became phantom edges — the exact failure `_FM_RE`'s
  own docstring says it exists to prevent. That regex was hardened for CRLF and for a block ending
  at EOF, but not for the byte that can precede the block.

Stripped on the decoded text, so the frontmatter split, the body and the extractor all see the same
  string on both decode paths. Leading only: elsewhere U+FEFF is a zero-width no-break space and is
  legitimate content.

Reference vault: 0 BOM'd notes. Latent, not absent — Windows editors, PowerShell's default Out-File
  and some git filters emit BOMs.

### Documentation

- **roadmap**: Record Track F's interim finding-method result
  ([#142](https://github.com/cdcoonce/graphmark/pull/142),
  [`2e6c368`](https://github.com/cdcoonce/graphmark/commit/2e6c368aa16cd3b0cd5dbf4fe6912dcbe7bb1427))

Four defects (#136 #137 #138 #139) found in one pass after #124-#126 shipped — none by reading link
  lists, none by the property generator. The method that worked was adversarial reading of the
  resolver and parser, confirmed by probe. All four measure 0 occurrences on the reference vault.

Names two limits this exposes: the counts cannot surface a wrong answer INSIDE a bucket (#136 files
  as `resolved`, #138 hides a break in `non-note-file`), and #126's generator draws from an alphabet
  that never reaches these input classes. Also records the hand audit of both suppressed buckets: 0
  false suppressions.


## v0.7.0 (2026-07-25)

### Documentation

- Record the nine-vault corpus study ([#134](https://github.com/cdcoonce/graphmark/pull/134),
  [`7495934`](https://github.com/cdcoonce/graphmark/commit/749593468e3d57913d89fc00942179786f5f5128))

graphmark has had exactly one real vault, and a coverage run showed the problem is worse than n=1:
  that vault now has zero broken links, so it never executes the error handling at all —
  suggest_notes entirely, the ambiguous / missing / out-of-scope verdicts, unresolved recording, and
  diagnose(). 54% of the package is unexercised by it. The healthier it gets, the less it validates.

Nine third-party vaults, zero crashes — the first evidence for the README's 'any Obsidian-family
  vault' claim. kepano's vault is 74% .base links, which independently justifies #101 and shows the
  reference vault understated that class by 7x. Third-party vaults sit at 1.8-27% missing against
  the reference vault's 0%.

That range confirms #127's closure against real data rather than argument: the largest
  false-positive class this package has had moved missing by 0.4%, which no threshold can separate
  from ordinary variation.

No new defects. Two suspicious distributions were both graphmark being right, and the second was my
  own scoping error — I excluded English template directory names but not the Spanish 'Plantillas',
  which is the methodological lesson worth recording for anyone repeating this.

- **roadmap**: Close Track E, open Track F — auditable link accounting
  ([#128](https://github.com/cdcoonce/graphmark/pull/128),
  [`4ca84de`](https://github.com/cdcoonce/graphmark/commit/4ca84de110dd288cd2778ccdc48a3b558367b269))

* docs(roadmap): close Track E, open Track F — auditable link accounting (#124-#127)

afk-driver --expand reads this file verbatim, so it has to describe where the work actually is.
  Track E is closed at 0.6.0 (aliases were its last piece), and the baseline line still claimed
  0.3.4.

Track F names the real problem, which is not any individual bug but how bugs get found: all seven
  correctness defects in this package's history came from a human reading link lists on the single
  reference vault, six of them in one day. The frozen oracle is a ratchet, not a detector — it has
  never surfaced anything new — and the one consumer's seam actively conceals package defects,
  having hidden a 23-link alias error for six releases.

The mechanism of the hiding is that the buckets are silent: build sorts every display into one of
  six reasons and reports one of them, and six of the seven bugs were mis-bucketing. Printing the
  distribution would have made the alias gap obvious at a glance — zero alias-resolved beside 23
  unresolved is visibly wrong.

So the epic is to make the package's own answers auditable: every display in exactly one named
  bucket, counted, reported, and bound by a property-tested conservation law. Sliced #124-#127, with
  the detector (#126) as the point of the exercise and its catch rate as the evidence.

Records what is deliberately deferred behind it and why: the Track D GitHub Action is an adoption
  play this repo has already decided against, and shipping a gate that fails other people's builds
  while our own accounting is unauditable is backwards ordering. Generality work is real but is a
  feature list, not an epic — and Track F is what will say which parts of it matter.

* docs(roadmap): truth up Track D — seven classes, and the Action waits on Track F

Track D still read '0.3.4' and 'four false-positive classes', and promised the GitHub Action as the
  next step, which now contradicts Track F's deliberate deferral. afk reads this file verbatim, so a
  contradiction in it is a contradiction injected into the expander's prompt.

### Features

- **cli**: Graphmark links — surface the classification distribution (#125)
  ([#131](https://github.com/cdcoonce/graphmark/pull/131),
  [`3ccf11c`](https://github.com/cdcoonce/graphmark/commit/3ccf11c26028c03739cfa88e67119c230645a22e))

Track F slice 2. Slice 1 made the classification countable; this makes it readable. Counts sitting
  in a Python object are worthless to a vault owner, and that gap is not cosmetic: the six-release
  frontmatter-alias defect was legible in this distribution the whole time — 23 links reported
  broken beside zero resolved via alias — and nobody saw it because no surface printed it.

`graphmark links` emits the block as JSON on stdout with a one-line summary on stderr, so stdout
  stays pipeable. `check`'s report carries the same block under `links`, appended after `checks` so
  consumers already parsing that report keep working, and provably unable to change the verdict — a
  test pins that a passing and a breaching run produce identical `links`.

The byte-stability oracle in test_check.py is updated rather than sidestepped, and now pins a
  cross-check worth having: max_unresolved_links' actual equals counts.missing, so the gate's
  flagship number and the distribution behind it cannot silently disagree.

Filed #130 along the way: every CLI example in the README fails. --config and --root live on the
  parent parser, so argparse only accepts them before the subcommand, while the README documents the
  opposite in all ten examples. It survived because the suite exclusively uses the working form, so
  nothing exercised the documented one — the same shape as the rest of Track F, and the reason
  #130's acceptance criteria require every README example to be executed by a test.

Mutation testing caught that the report's zero-fill was untested: build() seeds all six keys, so
  only a directly constructed graph exercises it. Covered now.

- **graph**: Per-reason link counts and the conservation law (#124)
  ([#129](https://github.com/cdcoonce/graphmark/pull/129),
  [`4ba2ab6`](https://github.com/cdcoonce/graphmark/commit/4ba2ab65b32654af98f3987f2688c18af23c7f02))

Track F slice 1. build sorted every extracted display into one of the six DIAGNOSIS_REASONS and then
  kept exactly one bucket plus the edges. The other outcomes were decided and discarded, and that
  silence is why six of the seven correctness bugs in this package's history went unnoticed: each
  was a mis-bucketing, and nothing in the output made an implausible distribution visible.

graph.link_counts accounts for every display, one bucket each, with all six keys always present in
  DIAGNOSIS_REASONS order — a zero is a finding, so it must be reported rather than absent.
  graph.alias_resolved counts resolutions reached through an alias, which is not a DIAGNOSIS_REASONS
  value but is the distinction that would have made #119 visible.

LinkDiagnosis gains `via` ("stem" or "alias") so the counter reads the classifier's own verdict
  instead of re-deriving it. Re-deriving is how the two would eventually disagree, which is the
  failure this repo has spent Track E removing.

The conservation law — sum(link_counts.values()) equals the extractor's total — is asserted on a
  vault exercising all six outcomes, on the frozen fixtures, and against the pre-existing surface
  (unresolved occurrences == ambiguous + missing), so the new tally cannot drift from the old one.

On the live 521-note vault the payoff is legible in one line. Healthy: missing 0, alias-resolved 23.
  The same vault with aliases disabled, which is what the six-release defect actually looked like:
  missing 23, alias-resolved 0. Same 6226 total either way — nothing vanished, 23 links were in the
  wrong bucket, and now you can see that.

Purely additive: no metric changes, frozen fixtures byte-identical.

### Testing

- Property-based vault generation — Track F's detector (#126)
  ([#132](https://github.com/cdcoonce/graphmark/pull/132),
  [`cd76410`](https://github.com/cdcoonce/graphmark/commit/cd76410087157677f6f6515c94d11057060063eb))

The frozen oracle prevents regression and has never surfaced anything new, because fixtures only
  encode shapes somebody already thought of, and all seven historical bugs were shapes nobody
  thought of. This generates vaults nobody designed and asserts what must hold for any content at
  all.

Two layers, and the second is the one that matters.

STRUCTURAL invariants over generated vaults: conservation (every extracted display lands in a
  bucket), edges name real notes and never exceed the resolved count, self-links never become edges,
  back_links mirror out_links, unresolved is exactly ambiguous+missing, aliases never shadow a real
  note name, and build is deterministic — the headline claim of this package, asserted nowhere until
  now.

Those all passed on first run, which was the finding. Every one of the seven bugs kept conservation
  intact; each merely filed a link in the WRONG bucket. So the structural layer would have caught
  none of them, and shipping only that would have been a detector that cannot see the thing it
  exists for.

METAMORPHIC relations close that gap. Obsidian treats [[X]], [[X|alias]], [[X#Section]] and [[X.md]]
  as the same link, so each rewrite must leave the counts and edges identical. Re-injecting the real
  defects confirms the layer works: #104 (.md), #98 (intra-note), #101 (non-note file), #119
  (aliases) and the path-qualified whitespace bug each fail a property.

Two of those properties were over-specified on first write — they compared `unresolved`, which
  echoes the RAW display, so a rewrite legitimately changes it. Comparing it asserts a rewrite does
  not rewrite anything. They now compare counts and edges, with the reason documented at the helper.

The whitespace property also had to be sharpened: normalization collapses whitespace on its own, so
  a padded BARE display resolves either way and cannot detect the defect. Only the path-suffix
  branch is sensitive, which is exactly where the 13 live links were reported broken while pointing
  at real notes.

hypothesis is a dev dependency only; the shipped runtime dep is still networkx alone. Bounded and
  derandomized so CI stays fast and failures reproduce.


## v0.6.0 (2026-07-25)

### Bug Fixes

- **parse**: Parse block-style frontmatter lists (#118)
  ([#120](https://github.com/cdcoonce/graphmark/pull/120),
  [`723c517`](https://github.com/cdcoonce/graphmark/commit/723c517d30732286fd0e6005996fb36d577042f5))

* chore(release): 0.3.4 [skip ci]

* chore(release): 0.4.0 [skip ci]

* chore(release): 0.5.0 [skip ci]

* fix(parse): parse block-style frontmatter lists (#118)

_parse_frontmatter handled scalars, quoted strings and inline lists, but a block list's item lines
  contain no colon, so the loop skipped them and the bare `key:` line stored "". Every block-style
  property in a real vault — aliases:, tags: — silently became an empty string instead of a list.

Block form is what Obsidian's own Properties UI writes, so this is the common case, not the edge
  case, and Document.frontmatter is public: a consumer reading doc.frontmatter["tags"] got "" rather
  than a list. Not an error, just quietly wrong data.

Item lines are matched on the leading dash BEFORE the key/value split, so an item containing a colon
  ("- Note: A Subtitle") stays an item. A block closes at the next key rather than merely pausing —
  without that, a stray indented line later in a malformed note would silently grow the earlier
  list, which is misattribution rather than the promised fail-soft drop. That distinction survived
  the first four mutations and now has its own test.

A `key:` with no items still reads as "" — an empty value, not an empty list — so nothing that
  parsed before changes shape.

Parity: fixture notes use inline or scalar frontmatter only, so no expected.json can move. A test
  asserts that property directly rather than leaving it as a claim in the commit message.

Still a targeted scan, not a YAML dependency: this runs over every note in a vault and a note
  someone is mid-edit must not take the graph down.

---------

Co-authored-by: semantic-release <semantic-release>

### Features

- **graph**: Resolve frontmatter aliases in-package (#119)
  ([#121](https://github.com/cdcoonce/graphmark/pull/121),
  [`05bb6ce`](https://github.com/cdcoonce/graphmark/commit/05bb6ced17656a3fb3d1d1798068763b26b68588))

graphmark never read frontmatter during resolution, so every link written against an Obsidian
  `aliases:` entry was reported broken. Measured on a real 521-note vault: stock graphmark reported
  23 broken links where the actual count was 0, and dropped 17 edges with them. A 100%
  false-positive rate in max_unresolved_links — the flagship threshold of graphmark check, the one
  product this repo offers outward. Larger than the four false-positive classes already fixed
  (#98/#101/#104/#107) combined.

This reverses a documented decision. the-vault's AliasResolver says "naming policy belongs to the
  seam, so the fallback lives here rather than in the graph algorithm". That holds for idiosyncratic
  conventions; aliases: is core Obsidian, and this package claims to work on any Obsidian-family
  vault. Human-triaged: move it in-package, on by default, since a default that silently produces
  wrong answers is not fixed by a knob nobody knows to flip. resolve_aliases = false restores the
  old behavior.

That AliasResolver is the oracle, and the live-vault differential is exact: stock graphmark now
  reports the same broken-link set as the reference implementation, note for note — 0 and 0, from a
  51-entry alias map.

Its conservative rules are preserved. An alias colliding with any real note name is dropped at index
  time, not merely outranked, so a note's own title can never be hijacked and an already-ambiguous
  basename can't be rescued into resolving. An alias claimed by two notes resolves to nothing. A
  slash-bearing alias is refused when the map is built, because normalization turns "/" into a space
  and would otherwise make it reachable from a slash-free display — the lookup-side guard alone does
  not cover that, which mutation testing caught.

One honest note: rule 1 (resolver before alias) is structurally unreachable given the other two
  rules — no display can match both a catalog key and an alias key — so mutating the order leaves
  the suite green. It is kept as insurance against a future relaxation and is documented as untested
  rather than dressed up as covered.

Parity: this changes what resolves, so it is the most parity-sensitive change since extraction. It
  is safe only because no frozen fixture declares aliases; a test asserts that property directly so
  it cannot go stale.


## v0.5.0 (2026-07-25)

### Features

- **graph**: Add calibrated near-miss suggestions (#112)
  ([#116](https://github.com/cdcoonce/graphmark/pull/116),
  [`db873b1`](https://github.com/cdcoonce/graphmark/commit/db873b1009bbef599e9eef035720306b62a548b8))

Track E slice 3, and the last thing keeping a consumer's parallel resolver alive. diagnose(graph,
  display, suggest=k) fills candidates with near-miss notes for a `missing` verdict only — every
  other reason already carries the rel_paths in play — so the default of 0 leaves the check gate's
  hot path untouched.

The rule was calibrated, not invented. The prior art (bidirectional substring containment over
  stems) was frozen over a real 521-note vault's broken links, giving 53 distinct displays, each
  annotated by a human as useful / useless / missing / correct-none. Only then was an algorithm
  chosen, and it is justified against that set: 27/27 useful kept — the non-negotiable — 7 of 8
  useless dropped, 4 of 5 missing found, zero new false suggestions. Method and measured result in
  tests/fixtures/suggest/README.md; the vault is private, so every shape is reproduced as a named
  test with invented names rather than committing the rows.

Matching is directional, which is what separates a suggestion from a wrong answer. A display inside
  a candidate is an abbreviation and always offered ([[Jordan]] -> Jordan Ellis). A candidate inside
  a display is offered only above SUGGEST_MIN_COVERAGE: dropping a "-reference" suffix is the
  answer, matching one word out of five is a real note that is NOT the target, and that shape is
  what made the old hints untrustworthy. Partial overlap in neither direction is rejected — it
  carried no useful hint anywhere in the baseline, and rejecting it is what holds the
  false-suggestion rate at zero.

Two annotations were corrected mid-calibration and both changed the design: [[Work Tasks]] and
  [[Personal Index]] looked useless only because the old rule printed bare stems, rendering four
  distinct Index.md files as "Index, Index, Index, Index". Both are correct answers. Suggestions
  therefore return rel_paths, and `index` is deliberately NOT a generic stem.

Also scrubs real colleague names out of the package. They had been used as doc/test examples and one
  shipped in a docstring in 0.4.0; all replaced with invented placeholders. Published history still
  carries them.

Both constants are pinned by the baseline: the cap is the lowest value that keeps every useful
  suggestion, the floor the highest. Teeth-checked by mutation — disabling suppression fails 1,
  dropping the coverage floor fails 3, dropping folder-keying fails 2, suggesting on every reason
  fails 3, and dropping the digit filter initially survived until a ranking test was added to cover
  it.


## v0.4.0 (2026-07-25)

### Features

- **graph**: Add diagnose() — why a link failed, not just that it did (#111)
  ([#114](https://github.com/cdcoonce/graphmark/pull/114),
  [`1d124a3`](https://github.com/cdcoonce/graphmark/commit/1d124a3423fc5a6f3c8a0a084e8d15927dd1d828))

Track E slice 2. graph.unresolved conflates two problems needing opposite repairs: a link matching
  NOTHING wants its target created or deleted, a link matching TOO MUCH wants disambiguating against
  what it collided with. A consumer holding only unresolved cannot tell them apart, so it rebuilds
  the resolver — the drift this track exists to end.

diagnose(graph, display) returns a frozen LinkDiagnosis: display echoed verbatim, target when
  resolved, one of the six DIAGNOSIS_REASONS, and the rel_paths in play (the colliding notes for
  ambiguous, the unindexed markdown for out-of-scope-note). The reason set is exported as a tuple in
  decision order so a consumer can switch on it exhaustively.

build() now classifies through the same function rather than agreeing with it separately — two
  classifiers in one package would recreate the drift inside the package. Two property tests pin
  them together: unresolved is exactly the ambiguous+missing displays, edges are exactly the
  resolved non-self targets.

candidates_for() consolidates the two-branch matching that _targets_out_of_scope_note had duplicated
  from the resolver. It reports matches only; deciding uniqueness stays the Resolver's job, so the
  two cannot disagree about which notes were in play. The graph now also retains the resolver it was
  built with, so a diagnosis can never contradict its own graph.

Behavior is unchanged: on the live vault, 130 unresolved / 3582 edges both before and after, and all
  six frozen fixtures byte-identical. What is new is the answer — 8 of those 130 are ambiguous
  collisions ([[2026-W27-tasks]] existing under both personal/archive and work/archive,
  [[RESOURCES]] under four learning folders), which the old surface reported as plain breaks.

- **graph**: Retain catalog + out_of_scope on the built graph (#110)
  ([#113](https://github.com/cdcoonce/graphmark/pull/113),
  [`7f7a91c`](https://github.com/cdcoonce/graphmark/commit/7f7a91cae961a06155f565384a429c92356868fb))

* docs(roadmap): close Tracks C and D, open Track E (#110-#112)

afk-driver --expand reads this file verbatim, so a stale one makes the fleet propose already-built
  work and pollutes the telemetry dataset. It still targeted "v0.2.0 — every error path tested"
  while the package is 0.3.4 with Tracks C and D both fully shipped.

Track C closed (every item landed at 0.2.0). Track D marked shipped at 0.3.0, with its real
  remaining risk named: the credibility of its flagship number. Four false-positive classes have now
  been found by triaging a live vault against max_unresolved_links — #98 anchors (19%), #101
  non-markdown (10%), #104 the .md extension, #107 out-of-scope notes (7%) — so "keep truthing the
  metric before shipping a GitHub Action that fails someone's build" is the direction, not more
  surface.

Track E opened: absorb the consumer's second link stack. graphmark says whether a link resolves; the
  gardener needs to know why it failed and what to do about it, which is why it still carries its
  own resolver and why #107 had to be fixed in two places. Sliced #110/#111/#112, with #112 flagged
  not-autonomous-safe past freezing the baseline — its expected values are human judgment, not
  oracle-derived.

* feat(graph): retain catalog + out_of_scope on the built graph (#110)

Track E slice 1. build() computed both mappings and threw both away, so a consumer that needs to say
  anything about a link beyond "resolved / didn't" had to rebuild the entire parse/catalog/resolve
  stack. the-vault's graph_gardener.py does exactly that, and the two stacks drift: #107 was the
  fourth resolution fix that had to be applied in two places.

graph.catalog is normalized stem → in-scope rel_paths; a key with two or more paths IS an ambiguity
  set, which is what lets a consumer say WHICH notes a bare link collided with instead of only that
  it failed. graph.out_of_scope is the same for markdown outside the configured scope, retained from
  #107. Both are constructor-optional, so three-positional construction keeps working.

Value lists are sorted by rel_path explicitly rather than inheriting the walk's order. Those
  disagree: sorted(rglob) orders Path objects by parts tuple, yielding a/note.md before a-b/note.md,
  while rel_path string order is the reverse ('-' < '/'). The first version of the ordering tests
  used paths where the two agree, so deleting the sorts left the suite green — caught by mutation,
  and the tests now use the discriminating case.

No behavior change: nothing about what resolves or what an edge is moves, and every frozen fixture
  is byte-identical.


## v0.3.4 (2026-07-25)

### Bug Fixes

- **graph**: Links to existing out-of-scope notes are not broken (#107)
  ([#108](https://github.com/cdcoonce/graphmark/pull/108),
  [`9e386f6`](https://github.com/cdcoonce/graphmark/commit/9e386f6df700b1d866b7d50854b0cc8734a08bf5))

build() dropped unscoped folders, excluded dirs and rules files from the catalog and then forgot
  they existed, so a link to one failed the resolver and landed in unresolved. The link is correct —
  Obsidian follows it — it just points somewhere graphmark deliberately does not index, so there was
  nothing for anyone to fix. On the live vault that was 11 of 155 reported breaks: 8 [[CLAUDE]], 1
  [[AGENTS]], 2 into templates/.

The same rglob that builds the catalog now records what it skipped, so no extra I/O buys the ability
  to tell "exists but out of scope" apart from "exists nowhere". Consulted only AFTER the resolver
  fails — mirroring _targets_non_note_file — so an in-graph note always wins over an out-of-scope
  namesake and keeps its edge. Any candidate suppresses: out-of-scope notes are never link targets,
  so ambiguity among them says nothing about whether the in-graph link is broken.

Alias/anchor/.md stripping moved into a shared _strip_display so the resolver and the new check
  cannot drift on what a display names. That refactor also strips surrounding whitespace, which the
  resolver did not: 13 column-aligned links of the form [[folder/note | alias]] were reported broken
  while pointing at real notes, and now resolve into edges (3570 → 3583 on the live vault). Covered
  by its own test class.

Fixtures are untouched: only the unresolved path changes shape, no expected.json carries an
  unresolved key, and edges only grow via the whitespace fix. uv.lock catches up to the 0.3.3
  release bump.

Live vault: 155 → 130 unresolved (12 suppressed, 13 resolved), no genuine break lost — verified by
  diffing the full before/after sets.


## v0.3.3 (2026-07-25)

### Bug Fixes

- **resolve**: [[note.md]] resolves like [[Note]]
  ([#105](https://github.com/cdcoonce/graphmark/pull/105),
  [`916da52`](https://github.com/cdcoonce/graphmark/commit/916da52465cc3c5295a9440ae86af1ee6065e1d5))

Obsidian accepts an explicit .md extension, so [[Note.md]] and [[Note]] are the same link. graphmark
  resolved only the second: the normalizer turned "Note.md" into the key "note md" while the file's
  catalog key is "note", so the link never matched and was reported as broken. The path-suffix
  branch was worse — it appends ".md" itself, so [[folder/note.md]] searched for folder/note.md.md.

Strip a case-insensitive trailing ".md" after alias/anchor stripping and before both resolution
  branches. A missing [[Nowhere.md]] stays unresolved and an ambiguous stem stays ambiguous; a title
  merely ending in the word "MD" is untouched.

Parity-safe: no frozen fixture uses a .md-style link, so every expected.json is unchanged (81 oracle
  tests green). The change only adds resolutions that previously failed — it never removes one.

Also updates the test added in #101 that documented this gap as current behavior; it now asserts the
  fix.

Closes #104


## v0.3.2 (2026-07-25)

### Bug Fixes

- **graph**: Links to non-markdown files are out of scope, not broken
  ([#102](https://github.com/cdcoonce/graphmark/pull/102),
  [`0796aa0`](https://github.com/cdcoonce/graphmark/commit/0796aa02d1d582b85a8905fb4b43b72b076bd072))

unresolved reported wikilinks targeting Obsidian Bases, Canvas, images and PDFs as broken. graphmark
  only indexes *.md, so it has no basis to judge those targets — calling them broken just fills the
  vault-health count with entries nobody can act on.

Measured on the owner's live vault: 17 of 173 reported breaks (10%) targeted .base/.canvas, and all
  9 distinct targets exist on disk, in a bases/ directory outside scoped_folders. Every one of those
  links works in Obsidian.

When the resolver returns None and the target ends in a plausible file extension other than .md,
  treat it as out of scope: no edge, not counted. The extension test is deliberately strict
  (trailing dot plus 1-10 alphanumerics) so a title like "v1.2 release notes" is still read as a
  note. Applying the rule only after the resolver has already failed is what makes it safe — a note
  that genuinely resolves, such as a real report.v2.md linked as [[report.v2]], never reaches it.

Deliberately no filesystem existence check: it would couple build() to the disk and force
  enumerating excluded trees like .git. "Out of scope" is the honest report for a file type
  graphmark does not index.

Closes #101


## v0.3.1 (2026-07-25)

### Bug Fixes

- **graph**: Stop counting same-note anchor links as unresolved
  ([#99](https://github.com/cdcoonce/graphmark/pull/99),
  [`a1d03f3`](https://github.com/cdcoonce/graphmark/commit/a1d03f3eb0e7b36b6d44d2a4eecfe8bb70da8d11))

unresolved counted anchor-only wikilinks — [[#Heading]], [[#Heading|alias]], [[#^blockref]] — as
  broken. Those are Obsidian same-note references: they target no note at all, so they are neither
  an edge nor a broken link. Counting them corrupted the very metric Track D was built around,
  max_unresolved_links.

Measured on the owner's live 521-note vault: 40 of 213 reported unresolved links (19%) were
  anchor-only, and the note reported as the worst offender earned that spot purely by navigating
  itself heavily.

build() now skips a display whose note part (before | and #) is empty. [[Note#Heading]] is
  unaffected: it still resolves via Note, and still counts as unresolved when Note is missing.

This refines the #75 semantics, which defined ambiguous-counts and self-link-doesn't but never
  considered anchor-only links.

Closes #98


## v0.3.0 (2026-07-25)

### Bug Fixes

- Validate the vault root and handle config errors cleanly in the CLI
  ([#81](https://github.com/cdcoonce/graphmark/pull/81),
  [`7aaae1d`](https://github.com/cdcoonce/graphmark/commit/7aaae1d08530e2996636432a661180984c2221c6))

Three failures at the same boundary:

1. rglob on a missing dir silently yields nothing, so a typo'd --root produced a structurally valid
  zero-metrics graph with exit 0 — indistinguishable from an empty vault. VaultGraph.build now
  raises ValueError when root is not a directory. An existing-but-empty vault stays legitimate. 2.
  cli._load caught nothing: a missing config file, malformed TOML, or a config missing 'root' each
  dumped a raw traceback. It now catches OSError / TOMLDecodeError / ValueError and exits 2 with a
  one-line stderr message, matching the existing error convention. 3. load_config raised for a
  missing 'root' key BEFORE the --root override applied, so the shipped configs/my-brain.toml
  (policy-only, no root key) was unusable from the package's own CLI. load_config grows a
  keyword-only root_override; when given it wins over any root key and makes that key optional, so
  the override is applied during the load rather than patched on after.

Closes #64

- **cli**: Unify usage errors on exit 2; keep help off stdout
  ([#89](https://github.com/cdcoonce/graphmark/pull/89),
  [`a5c208d`](https://github.com/cdcoonce/graphmark/commit/a5c208d1c8be2033870605341b6c898bb6b78d87))

Three conflicting conventions coexisted: missing --config/--root exited 1 via a hand-rolled print, a
  bare 'graphmark' printed full help to STDOUT while exiting 1 (success-shaped output with a
  failure-shaped code — piping captured help as if it were data), while argparse's own errors and
  the CLI's deliberate error paths exited 2.

Unify on argparse's convention: the missing-source check moves into main() as parser.error(), and a
  missing command prints help to stderr and exits 2. One rule now holds — 0 success, 2 usage error —
  which also leaves exit 1 free for the domain outcome Track D reserves it for (a "check" threshold
  breach).

Closes #72

- **gaps**: Single-source the weaklink signature format
  ([#91](https://github.com/cdcoonce/graphmark/pull/91),
  [`dd695e2`](https://github.com/cdcoonce/graphmark/commit/dd695e2b953154321c7c53d1618f6d7ea01d8ae5))

The dismissal-signature format was written out twice — inline in metrics.gaps() and again as
  dismiss.weaklink_sig() — with nothing tying them together. The format is load-bearing across both
  modules: gaps() emits sig, callers persist it via record_dismissal, and feed active_dismissed_sigs
  back in as dismissed=. A drift in either definition would silently un-suppress every recorded
  dismissal, since the mismatch produces no error, just suggestions reappearing.

metrics now imports and calls dismiss.weaklink_sig. The import direction is engine -> store, but
  weaklink_sig is a pure string helper (no IO, no extra deps, no graph knowledge) and dismiss
  imports nothing from metrics, so no cycle and no real layering violation.

Add round-trip tests covering the loop end to end: a gaps()-emitted sig equals weaklink_sig(), and
  suggest -> record_dismissal -> active_dismissed_sigs -> gaps(dismissed=...) actually suppresses
  the suggestion.

Drive-by: restore the comment ordering in metrics.py, where the gaps banding comment had been
  orphaned above _MAX_ITER.

Closes #74

- **pagerank**: Validate alpha and raise on non-convergence
  ([#82](https://github.com/cdcoonce/graphmark/pull/82),
  [`6b9dcaa`](https://github.com/cdcoonce/graphmark/commit/6b9dcaa544448714d67a691af4385b2da0b1e976))

pagerank accepted any alpha and always returned after 100 iterations, converged or not — while its
  own docstring claims it 'matches networkx _pagerank_python', which rejects nothing-burger alphas
  and raises PowerIterationFailedConvergence at max_iter. Verified: alpha=1.5 returned
  plausible-looking values on the simple fixture (and negative, million-scale values on other
  topologies), presented as real scores; a 200-node chain at alpha=0.999 returned unconverged
  numbers silently.

Raise ValueError for alpha outside (0, 1), and raise nx.PowerIterationFailedConvergence (networkx's
  own type, since networkx is already the sole runtime dep) when tolerance is never reached — via a
  for/else so the success path is unchanged. The CLI catches both for its pagerank branch and exits
  2. Fixture pagerank outputs converge well inside 100 iterations, so every oracle is
  byte-identical.

Closes #65

- **parse**: Tolerate CRLF and EOF-terminated frontmatter delimiters
  ([#80](https://github.com/cdcoonce/graphmark/pull/80),
  [`7a97662`](https://github.com/cdcoonce/graphmark/commit/7a9766264bb00ff1545aa1c75517654c5e8e737d))

_FM_RE only matched LF, so on a CRLF note (Windows / git autocrlf) the delimiter line is '---\r\n',
  the regex failed, and the entire frontmatter block stayed in the body — turning a frontmatter
  wikilink like 'related: "[[X]]"' into a phantom graph edge. Every metric
  (orphans/hubs/clusters/pagerank/gaps) then differed purely by line-ending convention, silently.

Accept \r?\n on all three delimiter lines, and also accept a closing '---' at EOF with no trailing
  newline (a frontmatter-only note, which previously failed to parse at all). _parse_frontmatter
  already handles \r via splitlines. Frozen fixtures are LF, so all oracles are byte-identical.

Closes #63

### Continuous Integration

- Test the advertised python matrix; ship CHANGELOG.md in the sdist
  ([#87](https://github.com/cdcoonce/graphmark/pull/87),
  [`695c2fb`](https://github.com/cdcoonce/graphmark/commit/695c2fb34f1330de009a6b6f93d71ed420e3f637))

The classifiers advertise 3.11/3.12/3.13 but CI's matrix covered only OS, so 'uv run' resolved a
  single interpreter and two of the three claimed versions never executed — an untested promise to
  anyone who installs on the strength of the classifier. This repo already learned the lesson on the
  OS axis (the macOS leg exists because the afk gate is Linux-only); the python axis had the same
  hole.

Add python: [3.11, 3.12, 3.13] to the matrix, passed to setup-uv's python-version, and name the jobs
  so a failing leg is identifiable. Six legs, fail-fast already false. Verified locally: the full
  suite passes on all three (251 tests each).

Also add CHANGELOG.md to the sdist include list — semantic-release maintains it on every release but
  sdist consumers never received it — with a gate-enforced test (removing it from the include list
  fails).

Closes #70

### Documentation

- Rewrite the README around the current surface; accept str paths
  ([#96](https://github.com/cdcoonce/graphmark/pull/96),
  [`a5e151b`](https://github.com/cdcoonce/graphmark/commit/a5e151b0dbb1b8b6d1872b0f90b235e025d1efc6))

The README was the PyPI landing page and it opened with "Status: v0.1.1 on PyPI" while the package
  was 0.2.0 — and the drift was structural, since semantic-release bumps pyproject while the README
  hardcoded a number. Replace it with a PyPI version badge that cannot drift, and document the
  surface shipped since: the graphmark check CI gate, the top-level build() quickstart,
  GAPS_DEFAULT_BAND, the Similarity protocol, the dismiss store API, graph.unresolved, py.typed, and
  the config reference. The CLAUDE.md pointer becomes an absolute URL, since that file is neither
  shipped nor linkable from PyPI.

Executing every example surfaced two real footguns, fixed here rather than papered over: -
  load_config("vault.toml") crashed with AttributeError: 'str' object has no attribute 'parent'. It
  now accepts str | Path for both the config path and root_override, matching build(), which already
  took str. - VaultConfig(root="/path") survived construction and failed much later on the first
  Path operation. __post_init__ now coerces, so the declared type is honest.

Every code block in the README was run against the simple fixture and its output matched before
  commit.

Closes #79

### Features

- Add graphmark.build() and curated top-level re-exports
  ([#95](https://github.com/cdcoonce/graphmark/pull/95),
  [`9a0cdbf`](https://github.com/cdcoonce/graphmark/commit/9a0cdbf6d9fbad1fd035c2d81c7e94b3c03cbf23))

Getting a graph took four submodule imports plus the tribal knowledge that WikilinkExtractor pairs
  with NormalizeResolver — a pairing with no defaults that the CLI and the live vault consumer each
  re-implemented.

Add graphmark.build(source, *, extractor=None, resolver=None) accepting a vault-root str/Path or a
  full VaultConfig and defaulting the extractor/resolver pair, plus __all__ re-exports of the whole
  public surface: config and CheckPolicy, the graph and model types, the three Protocols, every
  metric, the gaps band constants, run_check, the dismissal-store helpers, and the exporters.
  Driving it from a TOML is build(load_config(path)) — no path/config-file guessing by extension.

The quickstart is now three lines:

import graphmark graph = graphmark.build("/path/to/vault") print(graphmark.stats(graph))

cli._load calls the same helper, deleting the duplicated construction. Purely additive —
  VaultGraph.build and every submodule import keep working unchanged, verified by test.

Closes #78

- **check**: Add the graphmark check vault-health gate
  ([#94](https://github.com/cdcoonce/graphmark/pull/94),
  [`0a4d234`](https://github.com/cdcoonce/graphmark/commit/0a4d2349c87299c192fff1a5b76084707314f934))

Track D slice 3 of 3, completing the deterministic CI gate the roadmap names as the one unserved
  ecosystem niche: Obsidian's official CLI needs the desktop app, the dormant python incumbent has
  no CLI, and link checkers do no graph metrics.

New check.py evaluates config.check against a built graph. It is policy evaluation rather than a
  structural metric, so it lives beside the engine instead of inside metrics.py, composing orphans
  (which honors transient_prefixes, so scratch notes cannot fail the gate), the unresolved-link
  count from slice 1, and siloed_notes.

The contract: - exit 0 = every enforced threshold passes; exit 1 = at least one breach, reserved for
  breach ALONE; exit 2 = usage or config error. A policy that enforces nothing exits 2, never 0 — a
  gate with nothing to check must not be able to report green. A bad vault root or a typo'd [check]
  key is likewise 2, so CI can tell "your vault is unhealthy" from "your config is wrong". - stdout
  is exactly one line, the JSON report; stderr carries one human-readable line per breach and never
  pollutes stdout. - thresholds are inclusive: actual == limit passes. - the report is byte-stable —
  key insertion order is fixed and checks appear in CheckPolicy field-declaration order — so runs
  over an unchanged vault diff to nothing. A test pins it against a literal.

Closes #77

- **cli**: Add --version and help text for every subcommand and flag
  ([#88](https://github.com/cdcoonce/graphmark/pull/88),
  [`7abfb5d`](https://github.com/cdcoonce/graphmark/commit/7abfb5d681db15da0b7efb233d32fb93d5edbf3a))

A PyPI-published CLI could not report its own version, and 'graphmark --help' printed a bare choices
  dump — none of the 10 subcommands or 5 flags carried a help string, so 'graphmark hubs --help'
  explained nothing and users had to read the source to learn what 'siloed' or 'bridges' meant.

Add --version (sourced from the already single-sourced __version__), a parser description naming the
  stdout-is-JSON/stderr-is-errors contract, a one-line help for each subcommand, and help for --n,
  --note, --depth, --alpha, and the export format argument.

Closes #71

- **config**: Add the [check] policy block for vault-health gating
  ([#93](https://github.com/cdcoonce/graphmark/pull/93),
  [`377ecf9`](https://github.com/cdcoonce/graphmark/commit/377ecf9ac742d554de623974be31d58ee537e0b1))

Track D slice 2 of 3. load_config read only flat top-level keys and documented unknown keys as
  silently ignored, so a [check] table written today was swallowed whole and the planned gate had
  nothing to read.

Add a frozen CheckPolicy dataclass (max_orphans, max_unresolved_links, max_siloed; None = not
  enforced) plus a check field on VaultConfig defaulting to all-None, and parse the optional [check]
  table.

The block is deliberately STRICT, unlike the rest of the file: an unknown key inside [check], a
  negative value, a non-integer, or a boolean all raise ValueError naming the file, the key, and the
  valid keys. A silently-ignored typo like max_orphan would leave a CI gate reporting green forever,
  which is the worst failure a gate can have. The documented leniency everywhere else in the TOML is
  preserved.

CheckPolicy.is_configured() reports whether anything is enforced at all, so slice 3 can refuse to
  report green on an empty policy rather than trivially passing. Field declaration order is the
  report order and thus part of the check contract.

Extending the seeded config surface is directed by docs/ROADMAP.md's Track D section, which
  CLAUDE.md's exception clause defers to.

Closes #76

- **gaps**: Add GAPS_DEFAULT_BAND and parameterize the signature annotations
  ([#90](https://github.com/cdcoonce/graphmark/pull/90),
  [`a5d0004`](https://github.com/cdcoonce/graphmark/commit/a5d0004e0a9d75ef2604b3fa893a3b6ec54412f8))

Opting into the validated banding policy took four keyword arguments referencing four separate
  constants — exactly what the live consumer hand-copies. Add GAPS_DEFAULT_BAND so the opt-in is one
  gesture: gaps(graph, fn, **GAPS_DEFAULT_BAND).

Parameterize the loose annotations for IDE/type-checker help, now that the package ships py.typed:
  dismissed set|frozenset -> Collection[str], exclude_prefixes tuple -> tuple[str, ...], targets
  list|None -> Sequence[str] | None. Runtime behavior is unchanged.

Document the note/targets precedence rather than making the conflict raise. The issue proposed
  raising ValueError, conditional on verifying no consumer relies on the precedence — verification
  found one that does: the-vault's graph_cli.py computes `targets = siloed_notes(graph) if
  args.near_bridges else None` and passes it alongside an optional `note=args.note` in the same
  call, so `--gaps --note X --near-bridges` passes both. Raising would break /connect and /garden at
  runtime. Passing both is a legitimate pattern (compute one unconditionally, keep the other
  optional), so the docstring now states that note wins as the more specific scope, and a test pins
  it.

Closes #73

- **graph**: Record unresolved links instead of dropping them silently
  ([#92](https://github.com/cdcoonce/graphmark/pull/92),
  [`32e5a1d`](https://github.com/cdcoonce/graphmark/commit/32e5a1d57167e1e645814a108472cc458725f8c1))

build() discarded every unresolvable link with no record anywhere, so "how many broken links does
  this vault have" — the flagship check threshold from the roadmap, and the one vault-health signal
  ordinary link checkers already cover — was uncomputable from any graphmark surface.

Add VaultGraph.unresolved: dict[str, list[str]] mapping a rel_path to the raw link displays in it
  that resolved to nothing, in extraction order; notes with none are absent. The constructor
  parameter is optional and defaults to {}, so three-argument construction keeps working. No
  Resolver/LinkExtractor protocol change and no model.py change.

Semantics the reference engine never defined for us, now pinned by test: - an AMBIGUOUS bare link
  counts as unresolved (the Resolver returns None for both cases; both are equally broken from a
  health view); - a resolved SELF-link does NOT count (it resolved, it is merely not an edge); -
  every OCCURRENCE counts, so three [[Missing]] links contribute 3.

Purely additive: every frozen expected.json is untouched, and the differential invariant covers only
  metrics shared with the reference.

Closes #75

- **packaging**: Ship the PEP 561 py.typed marker
  ([#86](https://github.com/cdcoonce/graphmark/pull/86),
  [`e289fcf`](https://github.com/cdcoonce/graphmark/commit/e289fcfefe0b47c590619b3d1afa1d70b6fd17a5))

The package is fully annotated — including the three Protocols that are its design seams
  (LinkExtractor, Resolver, and the Similarity protocol shipped in 0.2.0 to type the injected
  similar_fn) — but shipped no py.typed, so PEP 561 told mypy/pyright to treat every graphmark
  import as untyped Any. The entire payoff of the annotation work was zero for consumers, starting
  with the-vault's graph_cli.py.

Add the marker (hatchling's packages=['src/graphmark'] ships it with no build-config change),
  declare the 'Typing :: Typed' classifier, and annotate the one gap, export.to_json(obj: object).

The guarantee is gate-enforced rather than assumed: new tests/test_packaging.py builds the real
  wheel and sdist and asserts the marker is inside each. Removing the marker fails 3 of them.

Closes #69

### Testing

- Pin degenerate-vault behavior and enforce the networkx PageRank claim
  ([#85](https://github.com/cdcoonce/graphmark/pull/85),
  [`5124db8`](https://github.com/cdcoonce/graphmark/commit/5124db83e2c31af12a1bbfcc7baf9a869eecf5c5))

Two untested regions closed.

Degenerate vaults: no test built an empty vault, so the density guard (notes > 0) and the pagerank N
  == 0 guard never executed — yet pointing the CLI at an empty or wrong directory is a likely first
  contact for a PyPI user. Pin the full empty-vault surface (stats all-zero, every list metric
  empty, pagerank [], gaps [], a valid empty digraph, neighborhood raising, CLI exit 0 with valid
  JSON) plus the smallest non-empty case, a single unlinked note.

networkx parity: docs/ROADMAP.md claims 'PageRank is checked against networkx' but nothing enforced
  it. Cross-check both fixtures at three alphas (0.5/0.85/0.95) against networkx's _pagerank_python
  — the pure python implementation graphmark's docstring actually claims parity with, since
  nx.pagerank dispatches to a scipy backend and this package ships no numpy/scipy. Measured
  agreement is ~7e-7; the assertion uses 1e-5, far below any teleport or convergence mutation.

Mutation-verified: dropping dangling redistribution fails 9 tests, (1-alpha) -> alpha fails 7,
  loosening the convergence tolerance fails 6 (the fixture tolerance alone could not catch this),
  and corrupting the empty-graph guard fails 1.

Closes #68

- **build**: Cover the excluded_dirs and rules_files selection filters
  ([#83](https://github.com/cdcoonce/graphmark/pull/83),
  [`d8e5e3c`](https://github.com/cdcoonce/graphmark/commit/d8e5e3c24303497ffd81d72ef200ff52bf1e28cb))

Both filters in VaultGraph.build were mutation-dead: every fixture config sets
  excluded_dirs=['.git'] but no fixture vault holds a note under an excluded dir, and no fixture
  vault contains a rules file — so deleting either filter, or widening rel_parts[:-1] to rel_parts,
  left all 192 tests green. The live consumer depends on both daily; a silent regression would pull
  rules files and archived notes into the graph, corrupting orphans/stats/gaps behind a green gate.

Add 15 tests building real vaults under tmp_path (no frozen-fixture edits) covering: exclusion by
  name and at any depth, multiple excluded dirs, dirs-only semantics (a FILE whose name matches an
  entry stays — pinning the [:-1] slice), rules files at root and nested, custom and empty
  rules_files, no-edge/no-back-edge contribution from filtered notes, and all three filters
  composing with scoped_folders.

Mutation-verified: deleting the excluded_dirs filter fails 7 tests,

deleting the rules_files filter fails 5, and rel_parts[:-1] -> rel_parts fails 1.

Closes #66

- **gaps**: Cover the parameters the frozen oracle never exercises
  ([#84](https://github.com/cdcoonce/graphmark/pull/84),
  [`5924e96`](https://github.com/cdcoonce/graphmark/commit/5924e966f83861ff1e724ff238aa39d940a99554))

The gaps/ fixture pins the ranking algorithm end-to-end but always calls gaps() the same way: no
  note=, no targets=, no exclude_prefixes, no self-pairs, and fixture scores that never sit exactly
  on the threshold or max_score bound (0.55-0.95 vs bounds 0.6/0.92). Every one of those was a
  mutation the suite could not kill.

Add 18 tests using an in-memory graph and a recording Similarity stub, so each knob is isolated and
  the scan itself is observable: inclusive score boundaries, note=/targets= scoping (asserted via
  which rel_paths the similarity source was actually asked about), exclude_prefixes on both the
  source and candidate side, the self-pair skip, already-linked suppression through a back-link, and
  k pass-through.

Mutation-verified: threshold < -> <=, max_score > -> >=, dropping the self-pair skip, dropping
  either exclude_prefixes filter, and ignoring note= scoping each fail 1-2 tests.

Closes #67


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
