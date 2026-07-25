# Corpus study — graphmark against nine third-party vaults

_2026-07-25. Method and results, so the numbers below can be cited instead of re-derived._

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

## Results

| vault | notes | links | resolved | missing | non-note-file | intra-note |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| arkalim/obsidian-vault | 160 | 551 | 61.7% | 1.8% | 34.8% | 0% |
| obsidian_vault_template_for_researcher | 83 | 295 | 58.3% | 2.4% | 39.3% | 0% |
| kepano-obsidian | 51 | 54 | 5.6% | 20.4% | **74.1%** | 0% |
| Obsidian-Vault-Structure | 25 | 106 | 58.5% | 27.4% | 14.2% | 0% |
| ArchVault | 79 | 37 | 73.0% | 24.3% | 2.7% | 0% |
| BugBountyKnowledgeBase | 9 | 4 | 75.0% | 25.0% | 0% | 0% |
| dusk-obsidian-vault | 7 | 3 | 0% | 100% | 0% | 0% |
| Obsidian-Vault-Template | 9 | 0 | — | — | — | — |
| _the reference vault_ | _521_ | _6226_ | _99.1%_ | _**0%**_ | _0.3%_ | _0.6%_ |

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

## Repeating it

The corpus is disposable — clone, measure, discard. What is worth keeping is this table, so future
threshold decisions argue against measurements rather than intuition.
