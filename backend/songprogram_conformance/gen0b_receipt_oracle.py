"""Independent logical-opcode and ChargeReceipt 1.1 primitives.

The emitter is intentionally separate from fixture construction.  It produces
only contract-level logical actions and never observes production callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from heapq import heappop, heappush
from itertools import combinations, product
from typing import Any, Iterable

from .canonical import canonical_bytes
from .gen0b_melody_oracle import artifact_hash

LEAVES = ("structural_items","placed_domain_points","exact_arithmetic_units",
          "numeric_eval_units","chord_search_nodes","pair_relations","ordering_units",
          "validation_items","emitted_events","progression_states","progression_edges")


def bit_length(value: int) -> int:
    return max(1, abs(value).bit_length())


def limbs(bits: int) -> int:
    return (bits + 63) // 64


def frac_mul_charge(a: int, b: int, c: int, d: int) -> int:
    numerator_bound = bit_length(a) + bit_length(c)
    denominator_bound = bit_length(b) + bit_length(d)
    return 1 + sum(limbs(bit_length(v)) for v in (a,b,c,d)) + limbs(numerator_bound) + limbs(denominator_bound)


def frac_div_charge(a: int, b: int, c: int, d: int) -> int:
    numerator_bound = bit_length(a) + bit_length(d)
    denominator_bound = bit_length(b) + bit_length(c)
    return 1 + sum(limbs(bit_length(v)) for v in (a,b,c,d)) + limbs(numerator_bound) + limbs(denominator_bound)


def frac_pow_charge(a: int, b: int, exponent: int) -> int:
    numerator_bound = max(1, abs(exponent) * bit_length(a if exponent >= 0 else b))
    denominator_bound = max(1, abs(exponent) * bit_length(b if exponent >= 0 else a))
    return 1 + sum(limbs(bit_length(v)) for v in (a,b,exponent)) + limbs(numerator_bound) + limbs(denominator_bound)


def frac_compare_charge(a: int, b: int, c: int, d: int) -> int:
    return 1 + sum(limbs(bit_length(v)) for v in (a,b,c,d)) + 1


def vector_add_charge(left: Iterable[int], right: Iterable[int]) -> int:
    return 1 + sum(limbs(bit_length(value)) for value in (*left,*right))


def _rhe_decimal(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def ratio_mc(value: Fraction) -> int:
    previous = None
    for precision in (80,112,144,176,208,240,256):
        with localcontext() as context:
            context.prec = precision
            current = _rhe_decimal(Decimal(1_200_000) *
                (Decimal(value.numerator).ln()-Decimal(value.denominator).ln()) / Decimal(2).ln())
        if current == previous: return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def edo_phase_mc(equave: Fraction, divisions: int, step: int) -> int:
    previous = None
    for precision in (80,112,144,176,208,240,256):
        with localcontext() as context:
            context.prec = precision
            current = _rhe_decimal(Decimal(1_200_000) *
                (Decimal(equave.numerator).ln()-Decimal(equave.denominator).ln()) /
                Decimal(2).ln() * Decimal(step % divisions) / Decimal(divisions))
        if current == previous: return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def rms_mc(errors: tuple[int,...], final_pair_count: int) -> int:
    if not errors: return 0
    previous = None
    for precision in (80,112,144,176,208,240,256):
        with localcontext() as context:
            context.prec = precision
            current = _rhe_decimal((Decimal(sum(x*x for x in errors))/Decimal(final_pair_count)).sqrt())
        if current == previous: return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def wrap_mc(value: int, period: int) -> int:
    return ((value + period//2) % period) - period//2


def _reduce_trace(emitter: "OpcodeEmitter", value: Fraction, equave: Fraction,
                  phase: str, child_id: str | None) -> Fraction:
    while True:
        emitter.emit(phase,"exact_arithmetic_units",
            1 + sum(limbs(bit_length(v)) for v in
                    (value.numerator,value.denominator,equave.numerator,equave.denominator)) + 1,
            child_id)
        if value >= equave:
            emitter.emit(phase,"exact_arithmetic_units",frac_div_charge(
                value.numerator,value.denominator,equave.numerator,equave.denominator),child_id)
            value /= equave
        elif value < 1:
            emitter.emit(phase,"exact_arithmetic_units",frac_mul_charge(
                value.numerator,value.denominator,equave.numerator,equave.denominator),child_id)
            value *= equave
        else: return value


def trace_domain(emitter: "OpcodeEmitter", lattice: dict[str, Any]) -> list[tuple[tuple[int, ...], int, Fraction]]:
    """Trace canonical placed-domain enumeration and return exact pitches."""
    generators=tuple(Fraction(value) for value in lattice["generators"])
    equave=Fraction(lattice["equave"])
    axes=[range(low,high+1) for low,high in lattice["coordinate_bounds"]]
    exponents=range(lattice["register_bounds"][0],lattice["register_bounds"][1]+1)
    cardinality=1
    for axis in axes: cardinality*=len(axis)
    cardinality*=len(exponents)
    emitter.emit("domain","placed_domain_points",cardinality)
    placed=[]
    for vector in product(*axes):
        for exponent in exponents:
            accumulator=Fraction(1)
            for generator,power in zip(generators,vector):
                emitter.emit("domain","exact_arithmetic_units",frac_pow_charge(generator.numerator,generator.denominator,power))
                powered=generator**power
                emitter.emit("domain","exact_arithmetic_units",frac_mul_charge(accumulator.numerator,accumulator.denominator,powered.numerator,powered.denominator))
                accumulator*=powered
            emitter.emit("domain","exact_arithmetic_units",frac_pow_charge(equave.numerator,equave.denominator,exponent))
            powered=equave**exponent
            emitter.emit("domain","exact_arithmetic_units",frac_mul_charge(accumulator.numerator,accumulator.denominator,powered.numerator,powered.denominator))
            accumulator*=powered
            reduced=_reduce_trace(emitter,accumulator,equave,"domain",None)
            odd_n=reduced.numerator
            while odd_n % 2 == 0: odd_n//=2
            odd_d=reduced.denominator
            while odd_d % 2 == 0: odd_d//=2
            complexity=reduced.numerator.bit_length()+reduced.denominator.bit_length()
            if max(odd_n,odd_d) > lattice.get("maximum_odd_limit",2**63-1):
                continue
            maximum_bits=(lattice.get("pitch_exploration") or {}).get(
                "maximum_reduced_complexity_bits",lattice.get("maximum_reduced_complexity_bits",2**63-1))
            if complexity > maximum_bits:
                continue
            emitter.emit("domain","numeric_eval_units",16)
            placed.append((tuple(vector),exponent,accumulator))
    return placed


def trace_bnb(emitter: "OpcodeEmitter", lattice: dict[str,Any], intent: dict[str,Any],
              anchor_vector: list[int], child_id: str, requested_k: int,
              register_millicents: tuple[int,int]) -> dict[str,Any]:
    """Independent canonical GEN0-A frontier trace and compact statistics."""
    raw = trace_domain(emitter,lattice)
    # Exact-ratio dedup retains first canonical placed spelling.
    seen: set[Fraction] = set(); placed=[]
    for vector, exponent, ratio in raw:
        if ratio not in seen:
            seen.add(ratio); placed.append((vector,exponent,ratio,ratio_mc(ratio)))
    equave=Fraction(lattice["equave"]); reference=Fraction(intent["reference"]["equave"])
    period=ratio_mc(reference)
    targets=sorted((edo_phase_mc(reference,intent["reference"]["divisions"],step),step % intent["reference"]["divisions"]) for step in intent["reference"]["steps"])
    for _ in targets: emitter.emit("chord","numeric_eval_units",8,child_id)
    voice_count=len(targets); final_pairs=voice_count*(voice_count-1)//2
    anchor=next(p for p in placed if p[0]==tuple(anchor_vector) and p[1]==0)
    non_anchor=[p for p in placed if p[2] != anchor[2]]
    # (preview lower prefix, identity, voices, errors, complexity)
    frontier=[]
    root_identity=(1,((anchor[0],anchor[1],anchor[2].numerator,anchor[2].denominator),))
    heappush(frontier,((0,0,0),root_identity,(anchor,),tuple(),0))
    incumbents=[]; popped=eligible=complete=hard_pruned=ranking_pruned=0
    proofs={}
    while frontier:
        preview,identity,voices,errors,complexity=heappop(frontier)
        emitter.emit("chord","chord_search_nodes",1,child_id); popped+=1
        if len(voices)==voice_count: complete+=1
        absolute=[v[3] for v in voices]
        failure=None
        if any(x < register_millicents[0] or x > register_millicents[1] for x in absolute): failure="DOMAIN_OR_REGISTER_VIOLATION"
        elif len({(v[0],v[1]) for v in voices}) != len(voices): failure="DUPLICATE_EXACT_RATIO"
        else:
            order=sorted(range(len(voices)),key=lambda i:(absolute[i],voices[i][2].numerator,voices[i][2].denominator,voices[i][0],voices[i][1]))
            adjacent=[absolute[b]-absolute[a] for a,b in zip(order,order[1:])]
            if adjacent and min(adjacent) < intent["voicing"]["minimum_spacing_millicents"]: failure="SPACING_VIOLATION"
            elif max(absolute)-min(absolute) > intent["voicing"]["maximum_span_millicents"]: failure="SPAN_VIOLATION"
            elif intent["voicing"]["bass_policy"]=="preserve_target" and order[0] != intent["voicing"]["bass_target_ordinal"]: failure="BASS_VIOLATION"
        node_errors=errors; node_complexity=complexity
        if failure is None and len(voices)>1:
            newest=len(voices)-1; additions=[]; extra_complexity=0
            for prior in range(newest):
                left,right=voices[prior][2],voices[newest][2]
                emitter.emit("chord","pair_relations",1,child_id)
                emitter.emit("chord","exact_arithmetic_units",frac_compare_charge(
                    left.numerator,left.denominator,right.numerator,right.denominator),child_id)
                emitter.emit("chord","exact_arithmetic_units",frac_div_charge(right.numerator,right.denominator,left.numerator,left.denominator),child_id)
                relation=_reduce_trace(emitter,right/left,equave,"chord",child_id)
                emitter.emit("chord","numeric_eval_units",16,child_id)
                emitter.emit("chord","numeric_eval_units",1,child_id)
                actual=wrap_mc(ratio_mc(relation),period)
                target=wrap_mc(targets[newest][0]-targets[prior][0],period)
                additions.append(wrap_mc(actual-target,period))
                high,low=(right,left) if right>left else (left,right)
                emitter.emit("chord","exact_arithmetic_units",frac_div_charge(
                    high.numerator,high.denominator,low.numerator,low.denominator),child_id)
                unordered=_reduce_trace(emitter,high/low,equave,"chord",child_id)
                extra_complexity += unordered.numerator.bit_length()+unordered.denominator.bit_length()-2
            node_errors=errors+tuple(additions); node_complexity=complexity+extra_complexity
            if node_complexity > intent["complexity_budget"]: failure="COMPLEXITY_VIOLATION"
            elif max(map(abs,node_errors)) > intent["recognition"]["maximum_pair_error_millicents"]: failure="PAIR_MAX_VIOLATION"
            else:
                emitter.emit("chord","numeric_eval_units",4+len(node_errors),child_id)
                lower=rms_mc(node_errors,final_pairs)
                if lower > intent["recognition"]["maximum_pair_rms_millicents"]: failure="PAIR_RMS_LOWER_BOUND"
                elif len(voices)<voice_count and len(incumbents)>=requested_k and (lower,max(map(abs,node_errors)),node_complexity) > incumbents[-1][0][:3]:
                    failure="WORSE_THAN_TOP_K"
        if failure:
            proofs[failure]=proofs.get(failure,0)+1
            if failure=="WORSE_THAN_TOP_K": ranking_pruned+=1
            else: hard_pruned+=1
            continue
        if len(voices)==voice_count:
            eligible+=1
            emitter.emit("ordering","ordering_units",requested_k.bit_length(),child_id)
            assignment=tuple((v[3]%period,v[2].numerator,v[2].denominator,v[0],v[1]) for v in voices)
            shape=tuple((tuple(v[0][axis]-anchor[0][axis] for axis in range(len(anchor[0]))),v[1]-anchor[1],v[2].numerator,v[2].denominator) for v in voices)
            score=(rms_mc(node_errors,final_pairs),max(map(abs,node_errors)),node_complexity,assignment,shape)
            incumbents.append((score,voices,node_errors)); incumbents.sort(key=lambda x:x[0]); incumbents=incumbents[:requested_k]
            continue
        for pitch in non_anchor:
            child_voices=voices+(pitch,)
            # Pure, uncharged canonical-integer preview; it does not populate the logical table.
            preview_errors=[]; preview_complexity=node_complexity
            for prior in range(len(voices)):
                relation=pitch[2]/voices[prior][2]
                while relation>=equave: relation/=equave
                while relation<1: relation*=equave
                actual=wrap_mc(ratio_mc(relation),period)
                target=wrap_mc(targets[len(voices)][0]-targets[prior][0],period)
                preview_errors.append(wrap_mc(actual-target,period))
                unordered=max(pitch[2],voices[prior][2])/min(pitch[2],voices[prior][2])
                while unordered>=equave: unordered/=equave
                while unordered<1: unordered*=equave
                preview_complexity += unordered.numerator.bit_length()+unordered.denominator.bit_length()-2
            all_errors=node_errors+tuple(preview_errors)
            prefix=(rms_mc(all_errors,final_pairs) if all_errors else 0,max(map(abs,all_errors)) if all_errors else 0,preview_complexity)
            child_identity=(len(child_voices),tuple((v[0],v[1],v[2].numerator,v[2].denominator) for v in child_voices))
            heappush(frontier,(prefix,child_identity,child_voices,node_errors,node_complexity))
    return {"popped_nodes":popped,"complete_nodes":complete,"eligible":eligible,
            "hard_pruned":hard_pruned,"ranking_pruned":ranking_pruned,"proofs":proofs,
            "incumbents":incumbents}


@dataclass
class OpcodeEmitter:
    input_hash: str
    records: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, phase: str, counter: str, charge: int, child_id: str | None = None) -> None:
        if counter not in LEAVES or charge < 1:
            raise ValueError("invalid logical opcode")
        self.records.append({"ordinal":len(self.records),"phase":phase,"counter":counter,
                             "charge":charge,"child_id":child_id})

    def structural_parse(self, value: Any) -> None:
        self.emit("parse", "structural_items", 1)
        if isinstance(value, dict):
            for key in sorted(value, key=lambda item:item.encode("utf-8")):
                self.structural_parse(value[key])
        elif isinstance(value, list):
            for item in value:
                self.structural_parse(item)

    def charged_sort(self, length: int, child_id: str | None = None) -> None:
        if length <= 1:
            return
        self.emit("ordering", "ordering_units", length * (length-1).bit_length(), child_id)

    def progression(self, layers: list[list[Any]], child_id: str) -> None:
        for layer in layers:
            for _ in layer:
                self.emit("progression", "progression_states", 1, child_id)
        for left, right in zip(layers, layers[1:]):
            for _ in left:
                for _ in right:
                    self.emit("progression", "progression_edges", 1, child_id)

    def stream(self) -> dict[str, Any]:
        result={"schema":"cps.logical-opcode-stream","schema_version":"1.0.0",
                "input_hash":self.input_hash,"records":self.records}
        result["stream_hash"]=artifact_hash("cps.logical-opcode-stream/v1",result)
        return result


def project_validation(emitter: OpcodeEmitter, project: dict[str, Any]) -> None:
    collections=("tracks","form","material_instances","resolved_chords","harmony_occurrences","events","mix")
    for name in collections:
        values=project[name]
        for _ in (values if isinstance(values,list) else sorted(values,key=lambda x:x.encode())):
            emitter.emit("validation","validation_items",1)
    for item in project["material_instances"]:
        for _ in (item["section_id"],item["track_id"]): emitter.emit("validation","validation_items",1)
    for item in project["harmony_occurrences"]:
        for _ in (item["section_id"],item["resolved_chord_id"]): emitter.emit("validation","validation_items",1)
    for event in project["events"]:
        refs=[event["track_id"],event["section_id"],event["source"]["material_instance_id"]]
        if event["chord_index"] is not None: refs.append(event["chord_index"])
        provenance=event.get("pitch_provenance") or {}
        for key in ("resolved_chord_id","active_resolved_chord_id","next_resolved_chord_id"):
            if provenance.get(key) is not None: refs.append(provenance[key])
        for _ in refs: emitter.emit("validation","validation_items",1)
    for _ in sorted(project["mix"],key=lambda x:x.encode()): emitter.emit("validation","validation_items",1)
    for event in project["events"]:
        emitter.emit("validation","validation_items",1); emitter.emit("validation","validation_items",1)
        if event["kind"] != "drum":
            emitter.emit("validation","validation_items",1); emitter.emit("validation","validation_items",1)
    for chord in project["resolved_chords"]:
        for _ in chord["voice_offsets"]: emitter.emit("validation","validation_items",1)
        count=len(chord["target_voice_ordinals"])
        for _ in range(count*(count-1)//2): emitter.emit("validation","validation_items",1)
        for _ in range(19): emitter.emit("validation","validation_items",1)
    for name in collections:
        for _ in range(max(0,len(project[name])-1)): emitter.emit("validation","validation_items",1)


def trace_symbols_and_timeline(emitter: OpcodeEmitter, program: dict[str,Any]) -> None:
    """Budget Contract step 2, without production symbol-table code."""
    collections=("form","tracks","materials","chord_intents","realizations")
    for name in collections:
        for _ in sorted(program.get(name,[]),key=lambda item:item["id"].encode("utf-8")):
            emitter.emit("symbols","structural_items",1)
    for _ in sorted(program.get("production",{}).get("envelopes",[]),key=lambda item:item["id"].encode("utf-8")):
        emitter.emit("symbols","structural_items",1)
    # Scalar ID references in stored field/array order.
    for material in program.get("materials",[]):
        if material.get("rhythm_id") is not None: emitter.emit("symbols","structural_items",1)
        for _ in material.get("chord_intent_ids",[]): emitter.emit("symbols","structural_items",1)
    for realization in program.get("realizations",[]):
        for _ in ("section_id","track_id","material_id"): emitter.emit("symbols","structural_items",1)
    for _ in sorted(program.get("production",{}).get("tracks",{}),key=lambda value:value.encode("utf-8")):
        emitter.emit("symbols","structural_items",1)
    for _ in program.get("form",[]): emitter.emit("symbols","structural_items",1)
    materials={item["id"]:item for item in program.get("materials",[])}
    for realization in program.get("realizations",[]):
        material=materials[realization["material_id"]]
        rhythm=materials.get(material.get("rhythm_id"),material)
        steps=rhythm.get("steps",[])
        for _repeat in range(realization["repeat"]):
            emitter.emit("events","structural_items",1)
            for _step in steps: emitter.emit("events","structural_items",1)
            for _transform in (*realization.get("rhythm_transforms",[]),*realization.get("pitch_transforms",[])):
                for _step in steps: emitter.emit("events","structural_items",1)
            emitter.emit("events","structural_items",1)  # material-instance record


def trace_event_lowering(emitter: OpcodeEmitter, project: dict[str,Any]) -> None:
    chords={item["id"]:item for item in project["resolved_chords"]}
    for event in project["events"]:
        provenance=event.get("pitch_provenance") or {}
        kind=provenance.get("kind")
        if kind=="resolved_chord_voice":
            emitter.emit("events","exact_arithmetic_units",vector_add_charge(
                provenance["anchor_vector"],provenance["offset_vector"]))
        elif kind=="resolved_melody":
            # chord_member copies its source vector and its two deltas are fixed zero;
            # the only written vector addition is active anchor + selected offset.
            chord=chords[provenance["active_resolved_chord_id"]]
            shape=chord["target_voice_ordinals"].index(provenance["active_target_voice_ordinal"])
            emitter.emit("events","exact_arithmetic_units",vector_add_charge(
                chord["anchor_vector"],chord["voice_offsets"][shape]))
        emitter.emit("events","emitted_events",1)


def usage(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    result={name:0 for name in LEAVES}
    for record in records: result[record["counter"]]+=record["charge"]
    result["total_logical_units"]=sum(result.values())
    return result


def child_stream(root: dict[str, Any], child_id: str, input_hash: str) -> dict[str, Any]:
    records=[]
    for record in root["records"]:
        if record["child_id"] == child_id:
            copied=dict(record); copied["ordinal"]=len(records); records.append(copied)
    result={"schema":"cps.logical-opcode-stream","schema_version":"1.0.0",
            "input_hash":input_hash,"records":records}
    result["stream_hash"]=artifact_hash("cps.logical-opcode-stream/v1",result)
    return result
