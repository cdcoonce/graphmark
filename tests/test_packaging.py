"""Packaging guarantees the gate must prove, not assume.

The PEP 561 marker only helps consumers if it is actually inside the built wheel — a fact no
amount of source-tree inspection establishes. These build the real distributions and look.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None, reason="uv is required to build the distributions"
)


def _build(tmp_path: Path, kind: str) -> Path:
    """Build one distribution (--wheel or --sdist) into tmp_path and return its path."""
    result = subprocess.run(
        ["uv", "build", f"--{kind}", "--out-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"uv build --{kind} failed:\n{result.stderr}"
    suffix = "*.whl" if kind == "wheel" else "*.tar.gz"
    built = sorted(tmp_path.glob(suffix))
    assert len(built) == 1, f"expected exactly one {kind}, got {[p.name for p in built]}"
    return built[0]


class TestPyTypedMarker:
    def test_marker_exists_in_the_source_tree(self):
        assert (REPO_ROOT / "src" / "graphmark" / "py.typed").is_file()

    def test_marker_is_inside_the_built_wheel(self, tmp_path):
        # PEP 561: without this file in the INSTALLED package, type checkers treat every
        # graphmark import as untyped, and the package's annotations do consumers no good.
        wheel = _build(tmp_path, "wheel")
        assert "graphmark/py.typed" in zipfile.ZipFile(wheel).namelist()

    def test_marker_is_inside_the_sdist(self, tmp_path):
        sdist = _build(tmp_path, "sdist")
        with tarfile.open(sdist) as tar:
            names = tar.getnames()
        assert any(n.endswith("src/graphmark/py.typed") for n in names), names[:20]


class TestTypedClassifier:
    def test_typing_typed_classifier_is_declared(self):
        data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        assert "Typing :: Typed" in data["project"]["classifiers"]


class TestSdistContents:
    def test_sdist_includes_the_changelog(self, tmp_path):
        # semantic-release maintains CHANGELOG.md on every release; sdist consumers
        # (distro packagers) should get it too.
        sdist = _build(tmp_path, "sdist")
        with tarfile.open(sdist) as tar:
            names = tar.getnames()
        assert any(n.endswith("/CHANGELOG.md") for n in names), names[:20]

    def test_sdist_includes_the_tests(self, tmp_path):
        sdist = _build(tmp_path, "sdist")
        with tarfile.open(sdist) as tar:
            names = tar.getnames()
        assert any(n.endswith("/tests/test_smoke.py") for n in names)
