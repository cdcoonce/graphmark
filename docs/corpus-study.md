# Corpus study — graphmark against nine third-party vaults

_2026-07-25. Method and results, so the numbers below can be cited instead of re-derived._

> **Superseded as the oracle (2026-08-01, Track G / #176).** The machine-generated reports under
> `docs/corpus/expected/` are now the frozen distribution. This page is retained for the analysis
> it carries — the reasoning in "What it established" is unchanged and still cited — but its
> tables are a hand-run snapshot and are **not** what a report is diffed against.
>
> The two disagree, deliberately. This run excluded a hand-picked template/meta directory per
> vault; `docs/corpus/manifest.toml` excludes only `.git` / `.obsidian` / `.github`, mechanically
> and identically for every vault. That was the decision: a per-vault exclusion list has no
> derivable criterion — three of the four directories are named for templates, CyanVoxel's
> `99 - Meta` is not — so it can only be transcribed, which is exactly the human step Track G
> exists to remove.
>
> **The gap is one vault.** Under manifest semantics archvault, BugBountyKnowledgeBase and
> Obsidian-Vault-Template change note count only; their link distributions are identical. The
> four other vaults are unaffected entirely. Only kepano-obsidian moves, because its `Templates/`
> is 52 of its 103 notes:
>
> | kepano-obsidian                   | notes | links | resolved | missing | non-note-file |
> | --------------------------------- | ----: | ----: | -------: | ------: | ------------: |
> | this page (template dir excluded) |    51 |    54 |     5.6% |   20.4% |         74.1% |
> | manifest semantics (the oracle)   |   103 |    75 |     4.0% |   14.7% |     **81.3%** |
>
> No conclusion below changes. The #101 evidence — kepano's vault being dominated by `.base`
> links — gets _stronger_ at 81.3%. The 1.8%–27% missing range is set by ArchVault (24.3%) and
> Obsidian-Vault-Structure (27.4%), neither of which moves; kepano shifts inward.

## Why

graphmark has had exactly **one** real vault. Every correctness bug in its history was found by a
human reading link lists from that vault, and every judgment call that needed calibration — see
#127 — was uncalibratable for the same reason.

A coverage run made the problem sharper than "n=1". The reference vault now has **zero** broken
links, so it never executes graphmark's error handling at all: `suggest_notes` in full, the
`ambiguous` / `missing` / `out-of-scope-note` verdicts, `unresolved` recording, and the public
`diagnose()` wrapper are all dark. 54% of the package is unexercised by it, including 26% of
`graph.py`. **The healthier that vault gets, the less of graphmark it validates.**

## Method

Nine public Obsidian vaults cloned shallow from GitHub (MIT / GPL / CC0 / unlicensed samples),
chosen for variety of size, domain and language rather than popularity. `graphmark.build` plus
`links_report` on each, with `.git` / `.obsidian` / `.github` and common template directories
excluded. The corpus is third-party content and is **not** committed here; the table is the
artifact.

The template-directory exclusions were per-vault and are recorded here so this run stays
reproducible: `Templates` for kepano-obsidian and ArchVault, `_templates` for
BugBountyKnowledgeBase, and `99 - Meta` for Obsidian-Vault-Template. Exclusions match on any
path component, not just the first (`graph.py`), so nested `.obsidian` directories were already
covered. The Track G harness does **not** apply these — see the note at the top.

## Results

| vault                                  | notes |  links | resolved |  missing | non-note-file | intra-note |
| -------------------------------------- | ----: | -----: | -------: | -------: | ------------: | ---------: |
| arkalim/obsidian-vault                 |   160 |    551 |    61.7% |     1.8% |         34.8% |         0% |
| obsidian_vault_template_for_researcher |    83 |    295 |    58.3% |     2.4% |         39.3% |         0% |
| kepano-obsidian                        |    51 |     54 |     5.6% |    20.4% |     **74.1%** |         0% |
| Obsidian-Vault-Structure               |    25 |    106 |    58.5% |    27.4% |         14.2% |         0% |
| ArchVault                              |    79 |     37 |    73.0% |    24.3% |          2.7% |         0% |
| BugBountyKnowledgeBase                 |     9 |      4 |    75.0% |    25.0% |            0% |         0% |
| dusk-obsidian-vault                    |     7 |      3 |       0% |     100% |            0% |         0% |
| Obsidian-Vault-Template                |     9 |      0 |        — |        — |             — |          — |
| _the reference vault_                  | _521_ | _6226_ |  _99.1%_ | _**0%**_ |        _0.3%_ |     _0.6%_ |

## What it established

**graphmark runs on other people's vaults.** Nine vaults, zero crashes, zero exceptions. This is
the first evidence for the README's "works on any Obsidian-family vault" claim, which had never
been tested.

**#101 was worth fixing, and the reference vault understated it.** kepano's vault — the Obsidian
CEO's public vault, a showcase for Bases — is **74% `.base` links**. Before #101 those were all
counted as broken. On the reference vault the same class was 10%.

**The reference vault is an outlier in health.** Third-party vaults sit at **1.8%–27% missing**;
the reference vault is at 0%. Its error paths are not merely under-exercised, they are unexercised.

**#127's closure is confirmed against real data.** The largest false-positive class this package
has had (#119) moved `missing` by **0.4%** of links. The normal range across real vaults is
1.8%–27%. A share-based threshold cannot separate a serious defect from ordinary variation, which
is why those heuristics were dropped in favour of the relational assertion in #133.

**`intra-note` usage is idiosyncratic.** 0% in every third-party vault, 0.6% in the reference
vault. #98 was a real bug, but the class it fixed is rarer in the wild than one vault suggested.

**No NFD filenames anywhere in the corpus.** #123 (Unicode NFD/NFC) remains correct but
theoretical — real data has not yet reproduced it. Worth knowing when prioritising.

## What it did not find

**No new defects.** Two distributions looked wrong and both were graphmark being right:
kepano's 74% is genuine Bases usage, and a Spanish vault's apparent 67% missing was my own scoping
error — I excluded English template directory names and not `Plantillas`. The residue was reported
`ambiguous` with both colliding paths, which identified the cause in one step.

That is a real methodological lesson for any repeat: **scope configuration is language- and
convention-specific, and naive defaults produce meaningless distributions.** Per-vault scoping is
required for the numbers to mean anything.

## Second run — 2026-07-25, after five fixes

Repeated the same day, after #123/#136/#137/#138/#139 shipped, to answer two questions the first run
could not: did those fixes move any real number, and is there demand for the link-syntax work the
roadmap defers. Six vaults resolved (several URLs from the first run are dead); two overlap.

| vault                            |    notes |  links | resolved |   missing | non-note-file | md-style `.md` links | BOMs |
| -------------------------------- | -------: | -----: | -------: | --------: | ------------: | -------------------: | ---: |
| arkalim/obsidian-vault           |      160 |    551 |    61.7% |      1.8% |         34.8% |                    0 |    0 |
| kepano-obsidian                  |       51 |     54 |     5.6% |     20.4% |         74.1% |                    0 |    0 |
| jackyzha0/quartz                 |      113 |    411 |    92.0% |      1.9% |          3.9% |                    0 |    0 |
| bramses-highly-opinionated-vault |       59 |     78 |    65.4% |     11.5% |          3.8% |                    0 |    0 |
| DashboardPlusPlus                |       34 |     29 |     100% |        0% |            0% |                    0 |    0 |
| **lyz-code/blue-book**           | **1120** | **39** |   **0%** | **97.4%** |          2.6% |           **11,198** |    0 |
| _the reference vault_            |    _531_ | _6226_ |  _99.1%_ |      _0%_ |        _0.3%_ |                 _17_ |  _0_ |

### The null result, stated plainly

**The five fixes moved nothing.** arkalim and kepano reproduce the first run's percentages to the
decimal — 61.7/1.8/34.8 and 5.6/20.4/74.1, unchanged. No vault in the corpus contains an NFD
filename, a BOM, a numeric title suffix read as an extension, or a folder pair one of whose names
ends with the other's.

That is worth recording rather than burying. Those five were found by reading the code, are correct,
and are pinned by tests — but against real data they remain **theoretical**, joining #123 in that
category. The honest prioritization reading: correctness-by-inspection has now outrun what this
corpus can corroborate, and further defect-hunting of that kind has diminishing evidence behind it.

### The finding that was not theoretical

`lyz-code/blue-book` — 1120 notes, **11,198 markdown-style `[text](note.md)` links, 11,048 of them
(99%) targeting a note that exists** — extracts to **zero** edges. Every note an orphan; no clusters,
no hubs, no bridges; uniform PageRank. And `check` looks nearly healthy, because
`max_unresolved_links` sees 38: the 11,198 links it cannot see were never extracted, so they are not
_unresolved_.

This is a named limit of the Track F thesis and belongs beside the other one. The conservation law
added in #124 sums over what the **extractor** produced, so a link syntax the extractor does not know
is invisible to it by construction — the buckets balance perfectly at 39 while 11,198 links sit
outside the universe being counted. **The accounting is auditable only within the universe the
extractor defines.**

Filed as [#151](https://github.com/cdcoonce/graphmark/issues/151) (warn rather than report an empty
graph — cheap, no interface change) and [#152](https://github.com/cdcoonce/graphmark/issues/152)
(the markdown-syntax decision, Track B, explicitly the "on demand" trigger the roadmap's non-goal
reserved).

blue-book is an mkdocs garden, not an Obsidian vault, so it is arguably out of contract — but nothing
tells the user that, which is the whole point of #151.

## Repeating it

The corpus is disposable — clone, measure, discard. What is worth keeping is this table, so future
threshold decisions argue against measurements rather than intuition.
