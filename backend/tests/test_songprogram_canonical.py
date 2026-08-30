from __future__ import annotations

import pytest

from songprogram_conformance.canonical import (
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
)


def test_canonical_json_ascii_and_utf8_byte_key_order() -> None:
    value = {"é": "かわいい", "a": 1, "control": "\n\x00", "slash": "/"}
    expected = (
        b'{"a":1,"control":"\\n\\u0000","slash":"/",'
        b'"\xc3\xa9":"\xe3\x81\x8b\xe3\x82\x8f\xe3\x81\x84\xe3\x81\x84"}'
    )
    assert canonical_bytes(value) == expected
    assert canonical_sha256(value) == "2eb433147eb4cb050ce7f95819ed9e1795312a28bf8d59e7b48b201961df9e1c"


@pytest.mark.parametrize("value", [1.0, float("nan"), {"x": "e\u0301"}])
def test_canonical_json_rejects_outside_subset(value: object) -> None:
    with pytest.raises(CanonicalJsonError):
        canonical_bytes(value)
