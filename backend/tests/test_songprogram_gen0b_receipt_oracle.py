from fractions import Fraction
import json
from pathlib import Path

from songprogram_conformance.gen0b_receipt_oracle import (
    OpcodeEmitter, child_stream, frac_div_charge, frac_mul_charge, frac_pow_charge,
    trace_bnb, trace_domain, usage,
)


def test_child_stream_is_an_exact_renumbered_root_projection() -> None:
    digest = "sha256:" + "0" * 64
    emitter = OpcodeEmitter(digest)
    emitter.emit("parse", "structural_items", 1)
    emitter.progression([[1], [2, 3]], "progression_0000000000000000")
    root = emitter.stream()
    child = child_stream(root, "progression_0000000000000000", digest)
    assert [record["ordinal"] for record in child["records"]] == list(range(5))
    assert usage(child["records"])["progression_states"] == 3
    assert usage(child["records"])["progression_edges"] == 2


def test_fraction_charges_include_operands_and_result_bounds() -> None:
    assert frac_mul_charge(1, 1, 1, 1) == 7
    assert frac_div_charge(1, 1, 1, 1) == 7
    assert frac_pow_charge(1, 1, 0) == 6


def test_domain_trace_is_vector_then_exponent_order() -> None:
    digest = "sha256:" + "0" * 64
    emitter = OpcodeEmitter(digest)
    placed = trace_domain(emitter, {"generators":["3/1"],"equave":"2/1","coordinate_bounds":[[0,1]],"register_bounds":[0,1]})
    assert [(v,k,str(r)) for v,k,r in placed] == [((0,),0,"1"),((0,),1,"2"),((1,),0,"3"),((1,),1,"6")]
    assert usage(emitter.records)["placed_domain_points"] == 4


def test_bnb_root_is_anchor_and_pair_work_is_charged_after_pop() -> None:
    digest = "sha256:" + "0" * 64
    emitter = OpcodeEmitter(digest)
    result = trace_bnb(emitter,
        {"generators":["3/1"],"equave":"2/1","coordinate_bounds":[[0,1]],
         "register_bounds":[-1,0]},
        {"reference":{"equave":"2/1","divisions":12,"steps":[0,7]},
         "voicing":{"bass_policy":"preserve_target","bass_target_ordinal":0,
                    "minimum_spacing_millicents":70000,"maximum_span_millicents":2400000},
         "recognition":{"maximum_pair_error_millicents":38000,
                        "maximum_pair_rms_millicents":22000},"complexity_budget":30},
        [0], "chord_0000000000000000", 1, (-1200000,3600000))
    assert result["popped_nodes"] >= 2
    assert result["incumbents"][0][1][1][2] == Fraction(3,1)
    chord = [r for r in emitter.records if r["phase"] == "chord"]
    assert chord[0]["counter"] == "numeric_eval_units"  # target phases
    node = next(i for i,r in enumerate(chord) if r["counter"] == "chord_search_nodes")
    pair = next(i for i,r in enumerate(chord) if r["counter"] == "pair_relations")
    assert node < pair


def test_unordered_complexity_breaks_equave_phase_tie_in_favor_of_three_halves() -> None:
    fixture=Path(__file__).parents[1]/"songprogram_conformance"/"fixtures"/"compiler"/"gen0b_melody_song_program.json"
    program=json.loads(fixture.read_text())
    emitter=OpcodeEmitter("sha256:"+"0"*64)
    result=trace_bnb(emitter,program["lattice"],program["chord_intents"][0],[0,0],
        "chord_0000000000000000",1,tuple(program["tracks"][0]["register_millicents"]))
    winner=result["incumbents"][0]
    assert [voice[2] for voice in winner[1]] == [Fraction(1),Fraction(5,2),Fraction(3,2)]
    assert winner[0][:3] == (12052,15641,9)
