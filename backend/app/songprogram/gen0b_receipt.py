"""GEN0-B logical charging primitives owned by the production compiler.

The receipt is a deterministic account of compiler work.  It has no fixture
or conformance-package dependencies: callers supply the Program, Project and
the same immutable resolver query values used during lowering.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from heapq import heappop, heappush
from itertools import product
from typing import Any, Iterable


LEAVES = ("structural_items", "placed_domain_points", "exact_arithmetic_units", "numeric_eval_units", "chord_search_nodes", "pair_relations", "ordering_units", "validation_items", "emitted_events", "progression_states", "progression_edges")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def artifact_hash(domain: str, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + _canonical(value) + b"\n").hexdigest()


def _bits(value: int) -> int: return max(1, abs(value).bit_length())
def _limbs(bits: int) -> int: return (bits + 63) // 64
def _mul(a: int, b: int, c: int, d: int) -> int: return 1 + sum(_limbs(_bits(v)) for v in (a,b,c,d)) + _limbs(_bits(a)+_bits(c)) + _limbs(_bits(b)+_bits(d))
def _div(a: int, b: int, c: int, d: int) -> int: return 1 + sum(_limbs(_bits(v)) for v in (a,b,c,d)) + _limbs(_bits(a)+_bits(d)) + _limbs(_bits(b)+_bits(c))
def _pow(a: int, b: int, exponent: int) -> int:
    return 1 + sum(_limbs(_bits(v)) for v in (a,b,exponent)) + _limbs(max(1, abs(exponent)*_bits(a if exponent >= 0 else b))) + _limbs(max(1, abs(exponent)*_bits(b if exponent >= 0 else a)))
def _compare(a: int, b: int, c: int, d: int) -> int: return 1 + sum(_limbs(_bits(v)) for v in (a,b,c,d)) + 1
def _vadd(left: Iterable[int], right: Iterable[int]) -> int: return 1 + sum(_limbs(_bits(v)) for v in (*left,*right))


def _stable_ratio_mc(value: Fraction) -> int:
    previous = None
    for precision in (80,112,144,176,208,240,256):
        with localcontext() as context:
            context.prec = precision
            current = int((Decimal(1_200_000) * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln()) / Decimal(2).ln()).to_integral_value(rounding=ROUND_HALF_EVEN))
        if current == previous: return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def _edo(equave: Fraction, divisions: int, step: int) -> int:
    previous = None
    for precision in (80,112,144,176,208,240,256):
        with localcontext() as context:
            context.prec = precision
            current = int((Decimal(1_200_000) * (Decimal(equave.numerator).ln() - Decimal(equave.denominator).ln()) / Decimal(2).ln() * Decimal(step % divisions) / Decimal(divisions)).to_integral_value(rounding=ROUND_HALF_EVEN))
        if current == previous: return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def _rms(errors: tuple[int, ...], total: int) -> int:
    if not errors: return 0
    previous = None
    for precision in (80,112,144,176,208,240,256):
        with localcontext() as context:
            context.prec = precision
            current = int((Decimal(sum(x*x for x in errors)) / Decimal(total)).sqrt().to_integral_value(rounding=ROUND_HALF_EVEN))
        if current == previous: return current
        previous = current
    raise ArithmeticError("NUMERIC_INDETERMINATE")


def _wrap(value: int, period: int) -> int: return ((value + period // 2) % period) - period // 2


@dataclass
class OpcodeEmitter:
    input_hash: str
    records: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, phase: str, counter: str, charge: int, child_id: str | None = None) -> None:
        if counter not in LEAVES or charge < 1: raise ValueError("invalid logical opcode")
        self.records.append({"ordinal": len(self.records), "phase": phase, "counter": counter, "charge": charge, "child_id": child_id})

    def structural_parse(self, value: Any) -> None:
        self.emit("parse", "structural_items", 1)
        if isinstance(value, dict):
            for key in sorted(value, key=lambda item: item.encode()): self.structural_parse(value[key])
        elif isinstance(value, list):
            for item in value: self.structural_parse(item)

    def charged_sort(self, length: int, child_id: str | None = None) -> None:
        if length > 1: self.emit("ordering", "ordering_units", length * (length - 1).bit_length(), child_id)

    def progression(self, layers: list[list[Any]], child_id: str) -> None:
        for layer in layers:
            for _ in layer: self.emit("progression", "progression_states", 1, child_id)
        for left, right in zip(layers, layers[1:]):
            for _ in left:
                for _ in right: self.emit("progression", "progression_edges", 1, child_id)

    def stream(self) -> dict[str, Any]:
        stream = {"schema": "cps.logical-opcode-stream", "schema_version": "1.0.0", "input_hash": self.input_hash, "records": self.records}
        stream["stream_hash"] = artifact_hash("cps.logical-opcode-stream/v1", stream)
        return stream


def _reduce(emitter: OpcodeEmitter, value: Fraction, equave: Fraction, phase: str, child_id: str | None) -> Fraction:
    while True:
        emitter.emit(phase, "exact_arithmetic_units", 1 + sum(_limbs(_bits(v)) for v in (value.numerator,value.denominator,equave.numerator,equave.denominator)) + 1, child_id)
        if value >= equave:
            emitter.emit(phase, "exact_arithmetic_units", _div(value.numerator,value.denominator,equave.numerator,equave.denominator), child_id); value /= equave
        elif value < 1:
            emitter.emit(phase, "exact_arithmetic_units", _mul(value.numerator,value.denominator,equave.numerator,equave.denominator), child_id); value *= equave
        else: return value


def _domain(emitter: OpcodeEmitter, lattice: dict[str, Any]) -> list[tuple[tuple[int,...],int,Fraction]]:
    generators, equave = tuple(Fraction(value) for value in lattice["generators"]), Fraction(lattice["equave"])
    axes = [range(lo, hi + 1) for lo, hi in lattice["coordinate_bounds"]]; exponents = range(lattice["register_bounds"][0], lattice["register_bounds"][1] + 1)
    size = len(exponents)
    for axis in axes: size *= len(axis)
    emitter.emit("domain", "placed_domain_points", size)
    placed=[]
    for vector in product(*axes):
        for exponent in exponents:
            value=Fraction(1)
            for generator,power in zip(generators,vector):
                emitter.emit("domain", "exact_arithmetic_units", _pow(generator.numerator,generator.denominator,power))
                powered=generator**power; emitter.emit("domain", "exact_arithmetic_units", _mul(value.numerator,value.denominator,powered.numerator,powered.denominator)); value*=powered
            emitter.emit("domain", "exact_arithmetic_units", _pow(equave.numerator,equave.denominator,exponent))
            powered=equave**exponent; emitter.emit("domain", "exact_arithmetic_units", _mul(value.numerator,value.denominator,powered.numerator,powered.denominator)); value*=powered
            reduced=_reduce(emitter,value,equave,"domain",None); odd_n,odd_d=reduced.numerator,reduced.denominator
            while odd_n%2==0: odd_n//=2
            while odd_d%2==0: odd_d//=2
            maximum_bits=(lattice.get("pitch_exploration") or {}).get("maximum_reduced_complexity_bits",lattice.get("maximum_reduced_complexity_bits",2**63-1))
            if max(odd_n,odd_d)>lattice.get("maximum_odd_limit",2**63-1) or reduced.numerator.bit_length()+reduced.denominator.bit_length()>maximum_bits: continue
            emitter.emit("domain", "numeric_eval_units", 16); placed.append((tuple(vector),exponent,value))
    return placed


def trace_bnb(emitter: OpcodeEmitter, lattice: dict[str, Any], intent: dict[str, Any], anchor_vector: list[int], child_id: str, requested_k: int, register: tuple[int,int]) -> dict[str, Any]:
    raw=_domain(emitter,lattice); seen=set(); placed=[]
    for vector,exponent,ratio in raw:
        if ratio not in seen: seen.add(ratio); placed.append((vector,exponent,ratio,_stable_ratio_mc(ratio)))
    equave,reference=Fraction(lattice["equave"]),Fraction(intent["reference"]["equave"]); period=_stable_ratio_mc(reference)
    targets=sorted((_edo(reference,intent["reference"]["divisions"],step),step%intent["reference"]["divisions"]) for step in intent["reference"]["steps"])
    for _ in targets: emitter.emit("chord", "numeric_eval_units", 8, child_id)
    count=len(targets); pairs=count*(count-1)//2; anchor=next(p for p in placed if p[0]==tuple(anchor_vector) and p[1]==0); non_anchor=[p for p in placed if p[2]!=anchor[2]]
    frontier=[]; root=((anchor[0],anchor[1],anchor[2].numerator,anchor[2].denominator),); heappush(frontier,((0,0,0),(1,root),(anchor,),tuple(),0))
    incumbents=[]; popped=eligible=complete=hard=rank=0; proofs={}
    while frontier:
        preview,identity,voices,errors,complexity=heappop(frontier); emitter.emit("chord", "chord_search_nodes", 1, child_id); popped+=1
        if len(voices)==count: complete+=1
        absolute=[v[3] for v in voices]; failure=None
        if any(value<register[0] or value>register[1] for value in absolute): failure="DOMAIN_OR_REGISTER_VIOLATION"
        elif len({(v[0],v[1]) for v in voices}) != len(voices): failure="DUPLICATE_EXACT_RATIO"
        else:
            order=sorted(range(len(voices)),key=lambda i:(absolute[i],voices[i][2].numerator,voices[i][2].denominator,voices[i][0],voices[i][1])); adjacent=[absolute[b]-absolute[a] for a,b in zip(order,order[1:])]
            if adjacent and min(adjacent)<intent["voicing"]["minimum_spacing_millicents"]: failure="SPACING_VIOLATION"
            elif max(absolute)-min(absolute)>intent["voicing"]["maximum_span_millicents"]: failure="SPAN_VIOLATION"
            elif intent["voicing"]["bass_policy"]=="preserve_target" and order[0]!=intent["voicing"]["bass_target_ordinal"]: failure="BASS_VIOLATION"
        node_errors,node_complexity=errors,complexity
        if failure is None and len(voices)>1:
            newest=len(voices)-1; additions=[]; extra=0
            for prior in range(newest):
                left,right=voices[prior][2],voices[newest][2]; emitter.emit("chord","pair_relations",1,child_id); emitter.emit("chord","exact_arithmetic_units",_compare(left.numerator,left.denominator,right.numerator,right.denominator),child_id); emitter.emit("chord","exact_arithmetic_units",_div(right.numerator,right.denominator,left.numerator,left.denominator),child_id)
                relation=_reduce(emitter,right/left,equave,"chord",child_id); emitter.emit("chord","numeric_eval_units",16,child_id); emitter.emit("chord","numeric_eval_units",1,child_id)
                additions.append(_wrap(_wrap(_stable_ratio_mc(relation),period)-_wrap(targets[newest][0]-targets[prior][0],period),period)); high,low=(right,left) if right>left else (left,right); emitter.emit("chord","exact_arithmetic_units",_div(high.numerator,high.denominator,low.numerator,low.denominator),child_id); unordered=_reduce(emitter,high/low,equave,"chord",child_id); extra+=unordered.numerator.bit_length()+unordered.denominator.bit_length()-2
            node_errors=errors+tuple(additions); node_complexity=complexity+extra
            if node_complexity>intent["complexity_budget"]: failure="COMPLEXITY_VIOLATION"
            elif max(map(abs,node_errors))>intent["recognition"]["maximum_pair_error_millicents"]: failure="PAIR_MAX_VIOLATION"
            else:
                emitter.emit("chord","numeric_eval_units",4+len(node_errors),child_id); lower=_rms(node_errors,pairs)
                if lower>intent["recognition"]["maximum_pair_rms_millicents"]: failure="PAIR_RMS_LOWER_BOUND"
                elif len(voices)<count and len(incumbents)>=requested_k and (lower,max(map(abs,node_errors)),node_complexity)>incumbents[-1][0][:3]: failure="WORSE_THAN_TOP_K"
        if failure:
            proofs[failure]=proofs.get(failure,0)+1; rank += failure=="WORSE_THAN_TOP_K"; hard += failure!="WORSE_THAN_TOP_K"; continue
        if len(voices)==count:
            eligible+=1; emitter.emit("ordering","ordering_units",requested_k.bit_length(),child_id); assignment=tuple((v[3]%period,v[2].numerator,v[2].denominator,v[0],v[1]) for v in voices); shape=tuple((tuple(v[0][axis]-anchor[0][axis] for axis in range(len(anchor[0]))),v[1]-anchor[1],v[2].numerator,v[2].denominator) for v in voices); score=(_rms(node_errors,pairs),max(map(abs,node_errors)),node_complexity,assignment,shape); incumbents.append((score,voices,node_errors)); incumbents.sort(key=lambda item:item[0]); incumbents=incumbents[:requested_k]; continue
        for pitch in non_anchor:
            child_voices=voices+(pitch,); preview_errors=[]; preview_complexity=node_complexity
            for prior in range(len(voices)):
                relation=pitch[2]/voices[prior][2]
                while relation>=equave: relation/=equave
                while relation<1: relation*=equave
                preview_errors.append(_wrap(_wrap(_stable_ratio_mc(relation),period)-_wrap(targets[len(voices)][0]-targets[prior][0],period),period)); unordered=max(pitch[2],voices[prior][2])/min(pitch[2],voices[prior][2])
                while unordered>=equave: unordered/=equave
                while unordered<1: unordered*=equave
                preview_complexity+=unordered.numerator.bit_length()+unordered.denominator.bit_length()-2
            all_errors=node_errors+tuple(preview_errors); prefix=(_rms(all_errors,pairs) if all_errors else 0,max(map(abs,all_errors)) if all_errors else 0,preview_complexity); child_identity=(len(child_voices),tuple((v[0],v[1],v[2].numerator,v[2].denominator) for v in child_voices)); heappush(frontier,(prefix,child_identity,child_voices,node_errors,node_complexity))
    return {"popped_nodes":popped,"complete_nodes":complete,"eligible":eligible,"hard_pruned":hard,"ranking_pruned":rank,"proofs":proofs,"incumbents":incumbents}


def trace_symbols_and_timeline(emitter: OpcodeEmitter, program: dict[str, Any]) -> None:
    for name in ("form","tracks","materials","chord_intents","realizations"):
        for _ in sorted(program.get(name,[]),key=lambda item:item["id"].encode()): emitter.emit("symbols","structural_items",1)
    for _ in sorted(program.get("production",{}).get("envelopes",[]),key=lambda item:item["id"].encode()): emitter.emit("symbols","structural_items",1)
    for material in program.get("materials",[]):
        if material.get("rhythm_id") is not None: emitter.emit("symbols","structural_items",1)
        for _ in material.get("chord_intent_ids",[]): emitter.emit("symbols","structural_items",1)
    for realization in program.get("realizations",[]):
        for _ in ("section_id","track_id","material_id"): emitter.emit("symbols","structural_items",1)
    for _ in sorted(program.get("production",{}).get("tracks",{}),key=lambda value:value.encode()): emitter.emit("symbols","structural_items",1)
    for _ in program.get("form",[]): emitter.emit("symbols","structural_items",1)
    materials={item["id"]:item for item in program.get("materials",[])}
    for realization in program.get("realizations",[]):
        material=materials[realization["material_id"]]; rhythm=materials.get(material.get("rhythm_id"),material); steps=rhythm.get("steps",[])
        for _ in range(realization["repeat"]):
            emitter.emit("events","structural_items",1)
            for _ in steps: emitter.emit("events","structural_items",1)
            for _ in (*realization.get("rhythm_transforms",[]),*realization.get("pitch_transforms",[])):
                for _ in steps: emitter.emit("events","structural_items",1)
            emitter.emit("events","structural_items",1)


def trace_event_lowering(emitter: OpcodeEmitter, project: dict[str, Any]) -> None:
    chords={item["id"]:item for item in project["resolved_chords"]}
    for event in project["events"]:
        provenance=event.get("pitch_provenance") or {}
        if provenance.get("kind")=="resolved_chord_voice": emitter.emit("events","exact_arithmetic_units",_vadd(provenance["anchor_vector"],provenance["offset_vector"]))
        elif provenance.get("kind")=="resolved_melody":
            chord=chords[provenance["active_resolved_chord_id"]]; shape=chord["target_voice_ordinals"].index(provenance["active_target_voice_ordinal"]); emitter.emit("events","exact_arithmetic_units",_vadd(chord["anchor_vector"],chord["voice_offsets"][shape]))
        emitter.emit("events","emitted_events",1)


def project_validation(emitter: OpcodeEmitter, project: dict[str, Any]) -> None:
    collections=("tracks","form","material_instances","resolved_chords","harmony_occurrences","events","mix")
    for name in collections:
        for _ in (project[name] if isinstance(project[name],list) else sorted(project[name],key=lambda item:item.encode())): emitter.emit("validation","validation_items",1)
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
    for _ in sorted(project["mix"],key=lambda item:item.encode()): emitter.emit("validation","validation_items",1)
    for event in project["events"]:
        emitter.emit("validation","validation_items",1); emitter.emit("validation","validation_items",1)
        if event["kind"]!="drum": emitter.emit("validation","validation_items",1); emitter.emit("validation","validation_items",1)
    for chord in project["resolved_chords"]:
        for _ in chord["voice_offsets"]: emitter.emit("validation","validation_items",1)
        for _ in range(len(chord["target_voice_ordinals"])*(len(chord["target_voice_ordinals"])-1)//2): emitter.emit("validation","validation_items",1)
        for _ in range(19): emitter.emit("validation","validation_items",1)
    for name in collections:
        for _ in range(max(0,len(project[name])-1)): emitter.emit("validation","validation_items",1)


def usage(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    result={name:0 for name in LEAVES}
    for record in records: result[record["counter"]]+=record["charge"]
    result["total_logical_units"]=sum(result.values()); return result


def child_stream(root: dict[str, Any], child_id: str, input_hash: str) -> dict[str, Any]:
    records=[]
    for record in root["records"]:
        if record["child_id"]==child_id:
            copied=dict(record); copied["ordinal"]=len(records); records.append(copied)
    stream={"schema":"cps.logical-opcode-stream","schema_version":"1.0.0","input_hash":input_hash,"records":records}; stream["stream_hash"]=artifact_hash("cps.logical-opcode-stream/v1",stream); return stream
