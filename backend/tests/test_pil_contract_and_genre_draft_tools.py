"""Guard tests for the read-only PIL consistency tools.

These tools compare normative contract declarations, the authoritative schema
pack, the implementation bindings, and the non-normative genre design drafts.
Any silent drift must fail the test suite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _run_tool(relative: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, relative],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


def test_pil_contract_schema_hashes_match() -> None:
    result = _run_tool("tools/check_pil_contract_schema_hashes.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_pil_genre_draft_consistency() -> None:
    result = _run_tool("tools/check_pil_genre_draft_consistency.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
    # G6 must stay visible until the owner closes it.
    assert "G6 OPEN" in result.stdout
