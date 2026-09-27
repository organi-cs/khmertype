"""Run the browser version's JavaScript tests (skipped if Node isn't installed),
and make sure the shared parity fixture is up to date with the Python code."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_parity_fixture_is_current():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import make_parity_fixture
    finally:
        sys.path.pop(0)
    current = json.loads((ROOT / "tests/fixtures/khmer_cases.json").read_text(encoding="utf-8"))
    assert current == make_parity_fixture.build(), "run: uv run python scripts/make_parity_fixture.py"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_javascript_suite():
    files = sorted(str(p) for p in (ROOT / "tests" / "js").glob("*.test.mjs"))
    assert files
    result = subprocess.run(["node", "--test", *files], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
