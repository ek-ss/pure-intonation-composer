"""0.3 exact sparse binding and legacy 0.2 isolation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from app.songprogram.compiler import CompileError, CompilerIdentity, compile_sp0
from app.songprogram.sparse_variant import exact_sparse_core, variant_hash
from app.harmony_dictionary.storage import read_sealed
from tools.generate_piano_tritave_trial import generate

ROOT = Path(__file__).resolve().parents[1] / "songprogram_conformance"


def test_tritave_absolute_window_bound_through_project_and_pcm() -> None:
    program, project, wav, report = generate(0)
    for name, value in (("song_program_0_3.schema.json", program),
                        ("arrangement_project_1_3_sparse.schema.json", project)):
        jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / name).read_text())).validate(value)
    assert report["reference"] == "12-edo-absolute-24/v1"
    assert all(value["covered"] and value["target_steps"] == list(range(24))
               for value in report["coverage_by_axis"].values())
    assert all(section["matched"] for section in report["sections"])
    assert any("3/1" in section["exact_ratios"] for section in report["sections"])
    assert sum(section["source_kind"] == "sealed_dictionary" for section in report["sections"]) == 3
    assert report["pcm"]["nonzero_samples"] > 0 and wav.startswith(b"RIFF")


def test_sparse_rejects_hash_ratio_and_anchor_tampering() -> None:
    program, _, _, _ = generate(0)
    intent = program["chord_intents"][1]
    lattice = program["lattice"]
    # The internal compiler lattice carries flattened resource limits.
    limits = {**lattice, "maximum_reduced_complexity_bits": lattice["pitch_exploration"]["maximum_reduced_complexity_bits"]}
    for field, value, error_code in (
        ("exact_ratio", "3/2", "SPARSE_VARIANT_HASH_MISMATCH"),
        ("exact_ratio", "3/2", "SPARSE_VARIANT_INVALID"),
    ):
        altered = copy.deepcopy(intent)
        altered["dictionary_variant"]["voices"][1][field] = value
        if error_code == "SPARSE_VARIANT_INVALID":
            altered["dictionary_variant"]["variant_hash"] = variant_hash(altered["dictionary_variant"])
        with pytest.raises(CompileError) as error:
            exact_sparse_core(limits, altered, [0] * 5, 0)
        assert error.value.code == error_code
    altered = copy.deepcopy(intent)
    altered["dictionary_variant"]["voices"][0]["equave_exponent"] = 1
    altered["dictionary_variant"]["voices"][0]["exact_ratio"] = "3/1"
    altered["dictionary_variant"]["variant_hash"] = variant_hash(altered["dictionary_variant"])
    with pytest.raises(CompileError, match="SPARSE_VARIANT_ANCHOR_MISMATCH"):
        exact_sparse_core(limits, altered, [0] * 5, 0)
    sealed = program["chord_intents"][2]
    dictionary = read_sealed(Path(__file__).resolve().parents[1] /
                             "harmony_dictionary_data/harmony_dictionary_3-1.json", "harmony-dictionary/3/1")
    with pytest.raises(CompileError, match="SPARSE_DICTIONARY_AUTHORITY_MISSING"):
        exact_sparse_core(limits, sealed, [0] * 5, 0)
    wrong = copy.deepcopy(sealed)
    wrong["dictionary_variant"]["source_chord_key"] = "11/3/absent/0,1,2"
    wrong["dictionary_variant"]["variant_hash"] = variant_hash(wrong["dictionary_variant"])
    with pytest.raises(CompileError, match="SPARSE_DICTIONARY_KEY_INVALID"):
        exact_sparse_core(limits, wrong, [0] * 5, 0, {dictionary["hash"]: dictionary})
    forged = copy.deepcopy(dictionary)
    forged["dictionary_version"] = "forged"
    with pytest.raises(CompileError, match="SPARSE_DICTIONARY_HASH_MISMATCH"):
        exact_sparse_core(limits, sealed, [0] * 5, 0, {dictionary["hash"]: forged})
    wrong = copy.deepcopy(sealed)
    wrong["dictionary_variant"]["voices"][1] = {
        "vector": [-1, 0, 0, 0, 0], "equave_exponent": 1, "exact_ratio": "3/2"
    }
    wrong["dictionary_variant"]["variant_hash"] = variant_hash(wrong["dictionary_variant"])
    with pytest.raises(CompileError, match="SPARSE_DICTIONARY_VARIANT_MISMATCH"):
        exact_sparse_core(limits, wrong, [0] * 5, 0, {dictionary["hash"]: dictionary})


def test_legacy_fixture_still_compiles_without_sparse_binding() -> None:
    fixture = ROOT / "fixtures/compiler_v2_5d/gen0b_melody_song_program.json"
    program = json.loads(fixture.read_text())
    identity = CompilerIdentity("legacy-fixture", "fixture-resolver", "sha256:" + "10" * 32,
                                "sha256:" + "11" * 32, program["production"]["catalog_digest"])
    project = compile_sp0(program, identity, stochastic_realization=False)
    assert project["source_program"]["schema_version"] == "0.2.0"
