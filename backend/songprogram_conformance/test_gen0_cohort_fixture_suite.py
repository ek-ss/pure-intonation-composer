from __future__ import annotations

import hashlib

from .build_gen0_cohort_fixtures import OUT
from .gen0_cohort_fixture_validator import validate_suite


def test_authoritative_gen0_cohort_suite_is_readonly_and_complete() -> None:
    before = {
        p.relative_to(OUT): hashlib.sha256(p.read_bytes()).digest()
        for p in OUT.rglob("*")
        if p.is_file()
    }
    result = validate_suite(OUT)
    after = {
        p.relative_to(OUT): hashlib.sha256(p.read_bytes()).digest()
        for p in OUT.rglob("*")
        if p.is_file()
    }
    assert result["coverage_count"] == 34
    assert result["case_count"] == 24
    assert before == after
