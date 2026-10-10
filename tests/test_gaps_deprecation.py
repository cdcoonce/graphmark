"""metrics.gaps() is deprecated in favor of ragmark v0.2.0 (#384) — and otherwise unchanged.

ragmark v0.2.0 shipped the ``ragmark.gaps`` module, the home the roadmap recorded for the gap
policy graphmark kept until then. These tests pin the deprecation contract: the warning is emitted
once per call, attributed to the caller's file, names where to go next, and does NOT promise
removal; and the function's output stays byte-for-byte what the frozen
``tests/fixtures/gaps/expected.json`` oracle says. The CLI half lives beside the other gaps CLI
tests in ``tests/test_cli.py``.

Every test observes the warning through ``warnings.catch_warnings(record=True)`` +
``simplefilter("always")`` so it is independent of the suite's ``filterwarnings`` config.
"""

from __future__ import annotations

import inspect
import json
import re
import warnings
from pathlib import Path

import graphmark
from graphmark.config import load_config
from graphmark.dismiss import active_dismissed_sigs, record_dismissal, weaklink_sig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import gaps
from graphmark.parse import WikilinkExtractor

REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gaps"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())
_MAP = {
    k: v
    for k, v in json.loads((FIXTURE_DIR / "similar.json").read_text()).items()
    if not k.startswith("_")
}

# ragmark is distributed as GitHub release assets, NOT on PyPI (the PyPI project of that name is an
# unrelated package), so the release page is the one correct pointer — never a `pip install`.
RELEASE_URL = "https://github.com/cdcoonce/ragmark/releases/tag/v0.2.0"


def _similar_fn(rel, k):
    return [tuple(x) for x in _MAP.get(rel, [])][:k]


def _graph():
    cfg = load_config(FIXTURE_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


def _oracle_call(graph):
    p = EXPECTED["params"]
    return gaps(
        graph,
        _similar_fn,
        threshold=p["threshold"],
        k=p["k"],
        max_score=p["max_score"],
        hub_degree=p["hub_degree"],
        dismissed=set(p["dismissed"]),
    )


def _record(call):
    """Run ``call()`` and return ``(result, [DeprecationWarning records])``."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = call()
    return result, [w for w in caught if issubclass(w.category, DeprecationWarning)]


class TestWarningContent:
    def test_gaps_emits_a_deprecation_warning_naming_ragmark(self):
        _, recorded = _record(lambda: _oracle_call(_graph()))
        assert len(recorded) == 1
        message = str(recorded[0].message)
        assert "gaps()" in message and "deprecated" in message
        # "ragmark v0.2.0" as a phrase: the bare version also appears inside the release URL, so
        # a check on "v0.2.0" alone would stay green after the sentence stopped naming ragmark.
        assert "ragmark v0.2.0" in message
        assert "ragmark.gaps" in message
        assert "pypi" not in message.lower()
        assert RELEASE_URL in message

    def test_message_does_not_promise_removal(self):
        # Removing gaps(), dismiss.py and weaklink_sig is a separate, later decision: ragmark's own
        # dismiss.py is a byte-for-byte port of graphmark's, so those must stay readable.
        _, recorded = _record(lambda: _oracle_call(_graph()))
        assert len(recorded) == 1
        assert "remov" not in str(recorded[0].message).lower()

    def test_message_never_points_at_pypi(self):
        # The PyPI "ragmark" is an unrelated project; a `pip install ragmark` hint installs it.
        _, recorded = _record(lambda: _oracle_call(_graph()))
        assert len(recorded) == 1
        assert "pip install" not in str(recorded[0].message).lower()


class TestStacklevel:
    # gaps() is called straight from the test body inside the recording block, with no helper frame
    # of this file in between: stacklevel=3 would otherwise land on a same-file helper and still
    # report this filename. Pinning the line of the call closes that gap too.
    def test_warning_is_attributed_to_the_callers_line_not_metrics(self):
        graph = _graph()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            call_line = inspect.currentframe().f_lineno + 1
            gaps(graph, _similar_fn)
        recorded = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(recorded) == 1
        assert Path(recorded[0].filename).resolve() == Path(__file__).resolve()
        assert recorded[0].lineno == call_line

    def test_reexported_graphmark_gaps_is_attributed_to_the_caller_too(self):
        graph = _graph()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            call_line = inspect.currentframe().f_lineno + 1
            graphmark.gaps(graph, _similar_fn)
        recorded = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(recorded) == 1
        assert Path(recorded[0].filename).resolve() == Path(__file__).resolve()
        assert recorded[0].lineno == call_line


class TestExactlyOneWarningPerCall:
    def test_many_targets_still_warn_once(self):
        graph = _graph()
        assert len(graph.nodes) >= 3  # guard: a one-note fixture would make "once" vacuous
        _, recorded = _record(lambda: gaps(graph, _similar_fn, targets=list(graph.nodes) * 2))
        assert len(recorded) == 1

    def test_default_all_nodes_scan_warns_once(self):
        graph = _graph()
        _, recorded = _record(lambda: gaps(graph, _similar_fn))
        assert len(recorded) == 1

    def test_each_call_warns_once_so_two_calls_warn_twice(self):
        graph = _graph()

        def two_calls():
            gaps(graph, _similar_fn)
            gaps(graph, _similar_fn)

        _, recorded = _record(two_calls)
        assert len(recorded) == 2

    def test_warns_before_any_scan_even_with_no_targets(self):
        # The warning is the FIRST statement: a caller who hits an empty scan (or an error on a bad
        # argument downstream) is still told. Guards a warn() moved inside the per-target loop.
        _, recorded = _record(lambda: gaps(_graph(), _similar_fn, targets=[]))
        assert len(recorded) == 1


class TestBehaviourUnchanged:
    def test_output_is_identical_to_the_frozen_oracle_under_the_warning(self):
        assert EXPECTED["gaps"]  # guard: an empty oracle would make equality vacuous
        result, recorded = _record(lambda: _oracle_call(_graph()))
        assert len(recorded) == 1  # the call really ran through the deprecated path
        assert result == EXPECTED["gaps"]

    def test_scores_are_still_rounded_to_four_decimals(self):
        # The oracle's scores all have at most two decimals, so it cannot see a change to the
        # rounding. A score with more digits pins the rounding gaps() has always applied.
        def fn(rel, k):
            return [("refs/b.md", 0.123456)] if rel == "docs/a.md" else []

        result, recorded = _record(lambda: gaps(_graph(), fn, note="docs/a.md"))
        assert len(recorded) == 1
        assert result == [
            {
                "a": "docs/a.md",
                "b": "refs/b.md",
                "score": 0.1235,
                "sig": "weaklink|docs/a.md|refs/b.md",
            }
        ]

    def test_signature_is_unchanged(self):
        params = inspect.signature(gaps).parameters
        assert [(name, p.default) for name, p in params.items()] == [
            ("graph", inspect.Parameter.empty),
            ("similar_fn", inspect.Parameter.empty),
            ("threshold", 0.0),
            ("k", 5),
            ("note", None),
            ("dismissed", frozenset()),
            ("exclude_prefixes", ()),
            ("max_score", None),
            ("hub_degree", None),
            ("targets", None),
        ]

    def test_dismissal_store_does_not_warn(self, tmp_path):
        # The store (weaklink_sig / record_dismissal / active_dismissed_sigs) is NOT deprecated:
        # ragmark's dismiss.py reads the same store format, so it must stay quiet and unchanged.
        (tmp_path / "a.md").write_text("one\n", encoding="utf-8")
        (tmp_path / "b.md").write_text("two\n", encoding="utf-8")

        def use_store():
            sig = weaklink_sig("a.md", "b.md")
            record_dismissal(tmp_path, "a.md", "b.md")
            return sig, active_dismissed_sigs(tmp_path)

        (sig, active), recorded = _record(use_store)
        assert recorded == []
        assert sig == "weaklink|a.md|b.md"
        assert active == {sig}


def _section(text: str, start: str, end: str) -> str:
    """The slice of ``text`` from the line starting ``start`` up to the line starting ``end``."""
    pattern = rf"^{re.escape(start)}.*?(?=^{re.escape(end)})"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    assert match, f"section {start!r} not found"
    return match.group(0)


class TestDocsPointAtRagmark:
    def test_readme_gaps_section_leads_with_the_deprecation_callout(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        section = _section(readme, "## `gaps`", "## Other metrics")
        quote = [line for line in section.splitlines() if line.startswith(">")]
        assert quote, "the gaps section has no blockquote callout"
        callout = " ".join(line.removeprefix(">").strip() for line in quote)
        assert RELEASE_URL in callout
        assert "ragmark.gaps" in callout
        assert "pypi" not in callout.lower()
        assert "deprecated but still work" in callout
        # The dismissal store is not part of the deprecation: it is named, and said to be unchanged.
        assert "weaklink_sig" in callout and "record_dismissal" in callout
        assert "is unchanged" in callout
        assert "pip install" not in section.lower()
        # The callout leads the section: it comes before the first code example.
        assert section.index(quote[0]) < section.index("```python")

    def test_roadmap_states_the_present_deprecation_not_the_future_trigger(self):
        roadmap = (REPO / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        raw = _section(roadmap, "- **`gaps()` with injected similarity**", "- **Packaging**")
        bullet = " ".join(raw.split())  # the bullet is hard-wrapped; compare on its words
        assert RELEASE_URL in bullet
        assert "ragmark.gaps" in bullet
        assert "pypi" not in bullet.lower()
        assert "now deprecated" in bullet
        assert "**not removed**" in bullet
        assert "pip install" not in bullet.lower()
        # The pre-trigger wording is now false: the module landed, and the surface is not "frozen".
        assert "and not before" not in bullet
        assert "do not remove it" not in bullet
        # ragmark's dismiss.py is a port of a later graphmark (v0.10.0 at ragmark v0.2.0), not of
        # v0.9.1, and any version number here rots as ragmark follows graphmark: name none.
        assert "v0.9.1" not in bullet
