"""Tests for scripts/corpus/report.py: build_vault_report and report_json.

Uses a small synthetic vault under tmp_path (same style as tests/fixtures/simple), so this needs
no network access and no real corpus vault checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus.manifest import CorpusVault  # noqa: E402
from scripts.corpus.report import build_vault_report, report_json  # noqa: E402


def _write_synthetic_vault(cache_root: Path, name: str) -> CorpusVault:
    vault_dir = cache_root / name
    vault_dir.mkdir(parents=True)
    (vault_dir / "alpha.md").write_text("See [[beta]] and [[missing]].\n")
    (vault_dir / "beta.md").write_text("# Beta\n")

    return CorpusVault(
        name=name,
        clone_url="https://github.com/example/vault",
        sha="0123456789abcdef0123456789abcdef01234567",
        license="MIT",
        excluded_dirs=(),
    )


def test_build_vault_report_counts(tmp_path):
    vault = _write_synthetic_vault(tmp_path, "synthetic-vault")

    report = build_vault_report(vault, tmp_path)

    assert report["vault"] == "synthetic-vault"
    assert report["notes"] == 2
    assert report["links"] == 2
    assert report["buckets"]["resolved"] == {"count": 1, "share": 0.5}
    assert report["buckets"]["missing"] == {"count": 1, "share": 0.5}
    for reason in ("ambiguous", "non-note-file", "out-of-scope-note", "intra-note"):
        assert report["buckets"][reason] == {"count": 0, "share": 0.0}


def test_report_json_is_byte_stable_across_calls(tmp_path):
    vault = _write_synthetic_vault(tmp_path, "synthetic-vault")

    first = report_json(vault, tmp_path)
    second = report_json(vault, tmp_path)

    assert first == second
    assert first.endswith("\n")


def test_report_json_is_byte_stable_across_subprocesses(tmp_path):
    import subprocess

    vault = _write_synthetic_vault(tmp_path, "synthetic-vault")

    script = (
        f"import sys; sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from pathlib import Path\n"
        "from scripts.corpus.manifest import CorpusVault\n"
        "from scripts.corpus.report import report_json\n"
        "vault = CorpusVault(\n"
        f"    name={vault.name!r},\n"
        "    clone_url='https://github.com/example/vault',\n"
        "    sha='0123456789abcdef0123456789abcdef01234567',\n"
        "    license='MIT',\n"
        "    excluded_dirs=(),\n"
        ")\n"
        f"sys.stdout.write(report_json(vault, Path({str(tmp_path)!r})))\n"
    )

    first = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    second = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )

    assert first.stdout == second.stdout
