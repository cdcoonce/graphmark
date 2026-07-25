# Suggestion calibration — provenance

`suggest_notes()` is the one part of graphmark whose expected output is **human judgment, not
oracle-derived**. There is no reference engine to diff against: the question "is this a useful
suggestion?" has no mechanical answer. So the rule was calibrated rather than invented, and this
file records how, because the numbers in `SUGGEST_MAX_MATCHES` / `SUGGEST_MIN_COVERAGE` are
meaningless without it.

## Method

1. **Freeze the baseline.** The prior art was a consumer's hint rule — bidirectional substring
   containment over normalized note stems, capped at 5 for display. It was run over a real
   521-note vault's actual broken links, yielding **53 distinct displays** that reached the hint
   search.
2. **Annotate it.** A human marked every row:
   - `useful` (25 → 27 after correction) — the hint is the answer; a new rule **must** keep it
   - `useless` (8) — a wrong or unactionable suggestion; a new rule should drop it
   - `missing` (5) — no hint today, but an obvious answer exists
   - `correct-none` (13) — no hint, and nothing to find
3. **Then** choose an algorithm, and justify it against the annotation.

The vault is private, so the annotated rows are not committed here — every distinct shape they
cover is reproduced as a named test case in `tests/test_suggestions.py`, with invented names.

## What the annotation established

Two rows were reclassified during calibration, and both changed the design:

- `[[Work Tasks]] → Tasks` and `[[Personal Index]] → Index` were first marked useless, because the
  hint rendered as a bare repeated stem (`Index, Index, Index, Index`). Both are in fact **correct**
  — `work/Tasks.md` and `personal/Index.md`. The defect was the _display format_, not the matching:
  showing stems threw away the path that disambiguates them. Suggestions therefore return
  **rel_paths**. This is also why `index` is not in `GENERIC_STEMS`.

## Result

|                       | old rule | calibrated rule |
| --------------------- | -------- | --------------- |
| useful kept           | 27/27    | **27/27**       |
| useless dropped       | 0/8      | **7/8**         |
| missing found         | 0/5      | **4/5**         |
| new false suggestions | —        | **0**           |

The two knowingly-accepted gaps:

- **`[[My Brain]]`** still suggests two real notes sharing that prefix. Defensible, so not worth
  distorting the rule to remove.
- **`[[graphify-knowledge-graph-tool]] → graphify-memory-layer-eval`** is still missed. They share
  one token of four in neither direction, so only edit distance would find it — and every
  edit-distance variant tried scored worse overall, losing useful rows to keep this one. Rejecting
  partial overlap is what holds the false-suggestion rate at zero.

## Why the constants are what they are

- `SUGGEST_MAX_MATCHES = 12` — the **lowest** cap that keeps every useful suggestion. One display
  (a two-token personal name whose first token appears in 9 note stems) needs 12; at 8 it is lost.
  The pathological case it exists for matched 47 notes.
- `SUGGEST_MIN_COVERAGE = 0.4` — the **highest** floor that keeps every useful suggestion. At 0.5
  two rows are lost; at 0.67 six are.

Re-running the calibration after any change to the rule is the check that matters. A green unit
suite proves the shapes still behave; only the annotated set proves the rule is still _useful_.
