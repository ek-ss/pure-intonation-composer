# Composition Transition Expression 2.1

Status: normative specification, implementation pending.

## Purpose and version boundary

Composition Generation Profile 2.1 adds pair-conditioned transition expression to the
2.0 ordered-form contract. It does not reinterpret existing 2.0 profiles or plans.
Implementations must reject a 2.1 profile that omits this contract and must not synthesize
ambient defaults.

Every adjacent section pair is lowered through three explicit temporal phases:

```text
source section ending       exact boundary        destination section opening
pre_boundary             -> boundary           -> post_boundary
```

The input identity is the ordered pair, not either section in isolation:

```text
(from_section_id, from_function, to_section_id, to_function, boundary_ordinal)
```

Reversing the pair creates a different transition. An expression eligible for
`preparation -> arrival` is not implicitly eligible for `arrival -> preparation`.

## Profile payload

A 2.1 profile adds one required `transition_expression_policy` object conforming to:

```text
backend/songprogram_conformance/schemas/composition_transition_expression_policy_2_1.schema.json
```

The policy contains:

- `algorithm = pair-conditioned-three-phase-bundle/v1`;
- normalized pre- and post-boundary window sizes;
- an exact mapping from every legal ordered function pair used by a form template to one
  transition class;
- one or more weighted expression bundles for every referenced class.

The initial complete machine-readable policy is checked in at:

```text
backend/songprogram_conformance/profiles/composition_transition_expression_v1.json
```

Every expression bundle contains all three phase arrays. At least one operation in the
bundle must be non-`none`. Randomly selecting each operation independently is forbidden:
the bundle is the unit of choice so preparation, boundary and arrival remain musically
coherent.

## Deterministic selection

For boundary ordinal `i`, the generator resolves the exact function pair to a class and
selects one weighted bundle using the existing
`seed-domain-sha256-weighted/v1` algorithm with domain:

```text
transition-expression/<template_id>/<boundary_ordinal>/<from_function>/<to_function>
```

Profile order is retained. No ambient randomness, retry-until-interesting behavior or
renderer-dependent choice is permitted.

The selected bundle is copied into `CompositionPlan 2.1.transition_plan[]` with:

```text
boundary_ordinal
from_section_id
from_function
to_section_id
to_function
transition_class_id
expression_id
pre_boundary[]
boundary[]
post_boundary[]
```

There is exactly one transition-plan entry for each adjacent section pair and no entry
before the first or after the last section.

## Time model

`pre_boundary_window_q` is a normalized suffix of the source section's final bar.
`post_boundary_window_q` is a normalized prefix of the destination section's first bar.
Both are integers on `[1, 10000]`. Operation-local `position_q` is relative to its phase
window, not the whole section.

The exact boundary tick is the first tick of the destination section. A pre-boundary
operation may not emit at or after that tick. A post-boundary operation may not emit
before it. Boundary operations may emit at the boundary tick or reserve a declared
silence immediately before it.

## Closed operation set

### `pre_boundary`

| Operation | Required payload | Meaning |
| --- | --- | --- |
| `drum_fill` | `subdivision`, `intensity_q` | Replace the ordinary drum pattern inside the pre-window with a bounded fill |
| `role_dropout` | `roles` | Mute listed roles for the complete pre-window |
| `density_ramp` | `roles`, `from_q`, `to_q` | Deterministically thin or subdivide eligible onsets across the window |
| `sustain` | `roles`, `gate_q` | Replace ordinary retriggers with one sustained event per listed pitched role |
| `pickup` | `role`, `source` | Emit a pickup derived from the destination hook or source motif |
| `none` | no additional fields | Make no pre-boundary change |

### `boundary`

| Operation | Required payload | Meaning |
| --- | --- | --- |
| `silence` | `duration_q` | Reserve silence immediately before the boundary for all roles |
| `impact` | `drum_notes`, `gain_q` | Emit a catalog-resolved multi-lane impact at the boundary |
| `unison_attack` | `roles`, `gate_q` | Align listed roles to one boundary attack |
| `harmonic_resolution` | `target` | Require the destination harmony to expose its home, arrival or open target at the boundary |
| `none` | no additional fields | Make no boundary change |

### `post_boundary`

| Operation | Required payload | Meaning |
| --- | --- | --- |
| `role_entry` | `roles`, `stagger_q` | Introduce listed roles together or with deterministic staggering |
| `hook_statement` | `variant` | State the destination foreground hook as root, answer or developed form |
| `groove_variant` | `variant_id` | Select a profile-owned destination groove variant |
| `tail_overlap` | `roles`, `duration_q` | Allow only listed source-role tails to overlap into the post-window |
| `none` | no additional fields | Make no post-boundary change |

Unknown operations or extra fields are invalid. `none` must be the only operation in its
phase array.

## Application and collision order

Lowering applies a selected bundle in this fixed order:

1. construct the unmodified source and destination section events;
2. apply pre-boundary `role_dropout`, `density_ramp`, `sustain`, `drum_fill`, then `pickup`;
3. apply boundary `silence` before all other boundary operations;
4. apply boundary `harmonic_resolution`, `unison_attack`, then `impact`;
5. apply post-boundary `tail_overlap`, `role_entry`, `groove_variant`, then
   `hook_statement`;
6. canonical-sort and validate the resulting events.

`silence` removes every ordinary event intersecting its reserved interval. An explicitly
selected boundary `impact` or `unison_attack` may sound at the boundary tick and is not
removed by that silence. `role_dropout` dominates source-section ordinary events but not
an explicit pickup. A generated event that exceeds its phase window is clipped; a zero-
duration result is removed. Polyphony, range and catalog constraints remain hard compiler
constraints after transition application.

## Pair classes for the initial profile

The initial profile must map ordered pairs into these behavioral classes:

| Transition class | Required pairs | Intended three-phase behavior |
| --- | --- | --- |
| `establish` | `opening -> statement`, `opening -> arrival` | pickup or restrained fill; clear boundary; destination groove/hook entry |
| `intensify` | `statement -> preparation`, `contrast -> preparation`, `return -> preparation` | increasing subdivision/density; optional boundary accent; denser destination groove |
| `release` | `statement -> arrival`, `preparation -> arrival` | fill/riser-like preparation and optional silence; impact/resolution; full destination entry |
| `reduce` | `arrival -> statement`, `arrival -> contrast` | dropout or sustain; light boundary; reduced destination role entry |
| `recall` | `preparation -> return`, `arrival -> return`, `contrast -> return` | motif pickup; resolution/accent; transformed hook recall |
| `close` | `arrival -> closure`, `return -> closure` | role dropout or sustain; harmonic resolution; tail overlap and staged role removal |

Every adjacent pair present in any checked-in form template must have exactly one mapping.
Unused legal pairs may be omitted. Duplicate mappings are invalid.

## Minimum diversity and boundedness

Each referenced class must provide at least two bundles with distinct canonical payloads.
No class may contain more than 16 bundles. Weights are positive 31-bit integers. A bundle
may contain at most four operations per phase and twelve operations total.

The policy is arrangement authority, not renderer authority. It may reference only roles,
drum-note identities and profile-owned groove/hook variants. It must not embed PCM bytes,
renderer build identities or unversioned instrument names.

## Failure precedence

Transition generation and lowering add these stable failures after base profile/form
validation and before ordinary part realization:

```text
COMPOSITION_TRANSITION_PAIR_UNMAPPED
COMPOSITION_TRANSITION_CLASS_INVALID
COMPOSITION_TRANSITION_EXPRESSION_UNAVAILABLE
COMPOSITION_TRANSITION_OPERATION_INVALID
COMPOSITION_TRANSITION_LOWERING_CONSTRAINT
```

The first invalid boundary in playback order wins. Within a boundary, validation order is
pair mapping, class, selected bundle, pre-boundary operations, boundary operations, then
post-boundary operations.

## Current implementation boundary

CompositionPlan 2.0 and the current lowering remain unchanged until the 2.1 schema,
profile payload, fixtures and lowering tests are implemented together. The current shared
single boundary hit is not conformant with this 2.1 contract and must be removed when the
2.1 lowering becomes active.
