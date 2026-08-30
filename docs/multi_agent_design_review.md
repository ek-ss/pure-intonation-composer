# Multi-Agent Design Review Protocol

## Purpose

Use multiple agents as an evidence-producing design gate, not as a discussion
group. Agreement is not the objective. The loop must turn every material
objection into a decision, an accepted risk, or a testable experiment.

## Roles

Run the first pass independently so agents cannot anchor on earlier opinions.

1. **Generative-systems critic** — representation, priors, searchability,
   mutation locality, diversity, and mode collapse.
2. **Music/production critic** — form, arrangement, sound design, genre
   experience, editability, and renderer ceiling.
3. **Tuning/perception critic** — lattice audibility, psychoacoustics,
   counterfactual controls, and listening-test validity.
4. **Evaluation/ML red team** — metric gaming, leakage, calibration,
   evaluator drift, and hidden-test design.
5. **Systems/operations critic** — reproducibility, failure recovery, cost,
   cancellation, artifacts, and versioning.
6. **Arbiter** — normalizes findings and makes decisions from evidence and
   acceptance tests. The arbiter does not decide by majority vote.

Four agents are usually sufficient per pass; combine adjacent roles and rotate
the omitted specialist in the next pass.

## Frozen Review Package

Every review round receives the same immutable package:

- design document version and commit/hash;
- explicit questions and scope exclusions;
- relevant source files and current test results;
- known constraints and cost envelope;
- decisions already closed and the evidence required to reopen them.

Do not expose other reviewers' findings during the independent pass.

## Finding Contract

Free-form essays may accompany a review, but only typed findings enter the
decision process.

```yaml
id: GEN-001
scope: representation | search | music | perception | evaluation | operations
severity: P0 | P1 | P2
claim: one falsifiable sentence
evidence:
  - file, section, measurement, or minimal counterexample
failure_scenario: concrete consequence
proposed_change: smallest useful intervention
acceptance_test: measurable pass/fail condition
estimated_cost: S | M | L
confidence: 0.0-1.0
dissent: optional minority position
```

Severity means:

- `P0`: invalidates the architecture or makes claimed evaluation meaningless;
- `P1`: likely to cause poor results, major rework, or an unusable workflow;
- `P2`: useful improvement that does not block the next experiment.

## Review Loop

```text
freeze proposal Rn
  -> independent specialist reviews
  -> normalize and deduplicate findings
  -> designer responds with evidence
  -> red team attacks the responses and proposed tests
  -> arbiter: accept / reject / experiment / accept-risk
  -> execute the smallest discriminating experiments
  -> update decision log, risk register, and proposal Rn+1
  -> targeted re-review of changed assumptions
```

An `experiment` decision must name an owner, artifact, budget, metric, and
pass/fail rule. A prose promise does not close a finding.

## Required Outputs

Each round produces:

- machine-readable findings;
- an Architecture Decision Record;
- unresolved risk register;
- experiment backlog with acceptance tests;
- dissent/minority log;
- cost and elapsed-time report;
- change summary from the previous design version.

Stable finding IDs survive revisions. A closed finding may be reopened only
with new evidence or because its underlying assumption changed.

## Stopping Conditions

Stop a review round when all P0 findings are either closed, accepted explicitly
as risks, or converted into funded experiments, and one of these holds:

- two passes produce few genuinely new findings;
- repeated objections contain no new evidence;
- the arbiter determines that further argument cannot replace an experiment;
- the declared token, time, or monetary budget is exhausted.

Consensus is not a stopping condition. Preserve minority objections in the
risk register.

## Guardrails

- Use separate exploration and holdout evaluators to limit metric gaming.
- Require source citations, code locations, measurements, or minimal
  counterexamples for P0/P1 findings.
- Prefer experiments that distinguish competing hypotheses over large builds.
- Cap each design cycle at two independent passes and one rebuttal pass.
- Track finding precision: reviewers that repeatedly emit unsupported P0s
  should receive less weight, regardless of rhetorical confidence.
- Remember that agents using the same foundation model are not independent
  human experts; human listening and implementation evidence remain necessary.

## Initial Review Gate for the Lattice Generator

The first review cycle should not debate the full LLM loop. It should freeze a
minimal `SongProgram` proposal and answer these questions:

1. Is genotype-to-phenotype compilation total, deterministic, canonical, and
   bounded?
2. Does its sampling prior produce musically viable candidates often enough?
3. Are small mutations measurably local in symbolic and perceptual space?
4. Do structural and rendered-audio diversity exceed the fixed Kawaii baseline?
5. Can the renderer reproduce the target production grammar at all?
6. Can lattice tuning be distinguished from a matched 12-TET counterfactual,
   and is that difference musically preferred or appropriate?

Until these are answered experimentally, adding more agents or an LLM planner
only increases the volume of unverified design claims.
