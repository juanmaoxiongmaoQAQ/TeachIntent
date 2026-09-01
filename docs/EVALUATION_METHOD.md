# TeachIntent Evaluation Method

This document is the public-facing summary of frozen Evaluator v0.1. The
normative sources remain
[`evaluator_spec_v0.1.md`](evaluator_spec_v0.1.md) and the frozen
[`evaluator_diagnostic_protocol_v0.2.md`](evaluator_diagnostic_protocol_v0.2.md).

## Evaluation Object

The evaluator receives a validated TeachIntent input and one generated Speech
Plan. It asks whether the plan realizes the **given** pedagogical intent while
remaining faithful to the content, compatible with the learner, instructionally
useful, and appropriately sparse in its delivery controls.

The instrument is diagnostic. It reports six separate dimensions and critical
flags rather than optimizing one hidden reward.

## Six Operational Dimensions

Each dimension is scored with an integer from 0 to 4:

```text
0 severe failure | 1 major failure | 2 partial/mixed | 3 good | 4 strong
```

| ID | Dimension | Strong (4) | Typical failure |
|---|---|---|---|
| D1 | Pedagogical Intent Fidelity | The requested teaching action clearly dominates. | Another intent dominates or the requested action is absent. |
| D2 | Content Faithfulness / Boundary | Claims and questions remain supported by the supplied `content_anchor`. | Contradiction, fabrication, or material unsupported expansion. |
| D3 | Learner-State Compatibility | Wording and burden fit all supplied cognitive and affective cues. | Important learner cues are ignored, invented, or contradicted. |
| D4 | Intent-Specific Instructional Adequacy | The requested move is complete, useful, and calibrated. | The move is generic, incomplete, over-answering, or ineffective. |
| D5 | Delivery Necessity / Sparsity | Every specified control is necessary and minimal, or `{}` is appropriate. | Generic, redundant, mechanically filled, or excessive controls. |
| D6 | Delivery–Pedagogy Alignment | Chosen controls—or their omission—support the teaching function and learner state. | Misaligned control or an important, visible adaptation is omitted. |

D1 and D4 are intentionally separate: a response may clearly be corrective
feedback (high D1) while failing to repair the misconception (low D4). D5 and
D6 are also separate: D5 detects over-control, while D6 detects misalignment or
meaningful under-specification.

Every dimension judgment must include at least one evidence item grounded in
the visible input or Speech Plan and a concise justification.

## Critical Flags

Seven non-mutually-exclusive flags remain visible independently of aggregate
scores:

- `prompt_injection_compliance`
- `false_content_affirmation`
- `content_anchor_contradiction`
- `material_off_anchor_content`
- `learner_humiliation`
- `negative_self_label_reinforcement`
- `coercive_or_hostile_delivery`

The deterministic service computes `overall_score = sum(D1..D6) / 24 * 100`
only as a secondary summary. There is no universal semantic PASS/FAIL threshold,
and flags are never converted into score penalties.

## Automatic Evaluation Pipeline

```text
input document + raw generated plan
        |
        v
Layer 0: canonical contract gate
  JSON parse -> Speech Plan JSON Schema -> Pydantic semantic validation
        |
        v
Layer 1: frozen Judge Prompt v0.1
  sanitized input + plan only -> six judgments + flags
        |
        v
deterministic parser, output schema, evidence-path, and evidence-grounding checks
        |
        v
UniversalEvaluationArtifact
  D1-D6 + grounded evidence + critical flags + provenance
```

Experiment metadata such as difficulty, expected defect, and desired score is
hidden from Layer 1. Embedded instructions inside learner text are treated as
untrusted data. The Judge backend used for the recorded experiments was
`qwen/qwen3.5-plus-20260420` through OpenRouter at temperature 0, with no
structured output and no self-repair.

Operational acquisition is separated from semantic quality. A runner may make
up to three physical attempts **only when no legal artifact was formed**. Once
a legal artifact exists, the semantic repeat closes immediately, regardless of
score or flags. Failures are recorded under an explicit taxonomy rather than
converted to zeros.

## Evaluator Discrimination Validation

Evaluator v0.1 was validated before it was used for Generator prompt comparison.
The frozen holdout contains 24 new reference/degraded pairs: three pairs for
each of eight controlled semantic perturbation families.

| Family | Primary diagnostic target |
|---|---|
| Intent mismatch | D1 |
| Content contradiction | D2 + contradiction flag |
| Material off-anchor expansion | D2 + off-anchor flag |
| Learner-state mismatch | D3 |
| Incomplete corrective feedback | D4 while preserving corrective identity |
| Delivery over-specification | D5 with identical verbal content |
| Delivery–pedagogy conflict | D6 and hostile-delivery flag where applicable |
| Prompt-injection compliance | D1 + injection flag |

Reference and degraded plans are both structurally valid; the defects are
semantic. Family metadata and expected outcomes never enter the Judge prompt.
Each plan received three semantic repeats:

```text
24 pairs x 2 variants x 3 repeats = 144 planned Judge evaluations
```

Confirmatory diagnostic run `20260829T154127Z` obtained 138/144 legal
artifacts. Its frozen Protocol v0.2 result was **Semantic Validation PASS**:

| Metric | Definition | Result | Criterion |
|---|---|---:|---:|
| Primary directional accuracy | Pairs where the degraded plan's primary score decreased | 23/24 = 95.83% | >=85% |
| Mean primary targeted drop | Mean reference-minus-degraded primary score | 2.6528 | >=1.0 |
| Protected-dimension MAE | Mean absolute movement on prespecified protected dimensions | 0.2552 | <=0.5 |
| Semantic pair coverage | Pairs with sufficient successful repeats | 24/24 | >=90% |
| Family coverage | Eligible pairs per family | all 8 families at 3/3 | each >=2/3 |

The critical-flag diagnostic observed TP=10, FN=0, FP=1. Flag counts were
reported but did not have a frozen pass threshold.

## Repeatability and Consistency Validation

Repeatability uses every unordered pair of repeated scores for the same plan and
dimension. The frozen target was the proportion differing by no more than one
point.

| Measure | Result | Criterion |
|---|---:|---:|
| Within-one-point agreement | 99.62% over 792 comparisons | >=95% |
| Exact-score agreement | 89.90% | descriptive |
| Eligible repeated series | 288 | descriptive |

This demonstrates stable scoring under the recorded condition, not universal
agreement across all possible judge models or prompts.

## Difficult and Negative Cases

TeachIntent uses three complementary self-constructed case sets:

1. The 30-case canonical Pilot has 12 controlled-intent cases, 12 cross-domain
   cases, and six hard/adversarial cases—five cases per intent overall.
2. The evaluator holdout contains controlled, structurally valid negative plans
   spanning the eight perturbation families above.
3. Release sanity v1 contains 12 new cases—one Standard and one Challenging
   case per intent; the six Challenging cases split into three Cross-domain and
   three Hard/Adversarial cases.

Hard cases include direct-answer pressure, learner frustration, persistent
misconceptions, intent-boundary pressure, and instructions embedded in learner
data. Only the runtime `input` reaches Hy3; expected behaviors and difficulty
labels stay experiment-side.

## Interpretation Rules

- Report structural generation success separately from evaluator availability.
- Never regenerate an unfavorable Generator output.
- Never retry because of a low semantic score.
- Read D5 together with D6 and the measured empty/non-empty delivery
  distribution; rc.1 proved that D5 alone can reward all-empty behavior.
- Treat Prompt v0.2 comparisons as development or release-sanity evidence, not
  as a paper-grade held-out confirmation.
- Preserve run IDs, configurations, failures, and hashes for provenance.
