# TeachIntent Failure Analysis and Capability Boundaries

This analysis summarizes failures actually observed in recorded artifacts. It
does not introduce new experiments or reinterpret operational failures as low
semantic quality.

## 1. Generator Operational Failures

The canonical v0.1 Pilot generated 30/30 structurally valid plans with one call
per case. Release sanity was 12/12 for v0.1 and 11/12 for v0.2. The missing v0.2
case, `RS-V1-EXT-CHA-01`, returned empty provider content with
`finish_reason='error'` and raised `Hy3APIError`.

The output was not regenerated. This demonstrates an important boundary: a
valid prompt and input cannot guarantee provider availability or non-empty
model content. Calling applications must handle an explicit generation failure.

## 2. Evaluator Artifact Acquisition

The LLM Judge sometimes returns no response or a response that cannot become a
legal, grounded evaluator artifact.

| Run | Planned semantic evaluations | Successful artifacts | Observed acquisition issue |
|---|---:|---:|---|
| Evaluator confirmatory `20260829T154127Z` | 144 | 138 | 2 API, 3 parse, 1 grounding failure |
| Generator baseline `20260830T095934Z` | 90 | 73 | final unavailable repeats after parse/grounding/API failures |
| rc.2 development `20260901T043729Z` | 90 | 87 | 3 final unavailable repeats; 112 physical attempts |
| Release sanity `20260901T093114Z` | 24 | 16 | 36 physical Judge failures, all upstream HTTP 429; one plan unavailable from generation |

The acquisition policy mitigates but does not hide this problem. A semantic
repeat may use at most three physical attempts only while no legal artifact
exists. Low scores and critical flags never trigger another attempt. Reports
therefore include both semantic results and operational availability.

## 3. Delivery Over-Specification in Prompt v0.1

The v0.1 baseline scored strongly on D1, D2, D3, and D6, but D5 was lower at
3.4872. The development generation distribution was 2 empty / 28 non-empty;
many plans contained several tone, emotion, prosody, prominence, and boundary
controls even when renderer defaults were sufficient.

Release sanity repeated the pattern on a smaller set: 11/12 v0.1 plans were
non-empty, with a mean of 4.2727 controls per non-empty plan and a range of
1–9. This is not a schema failure, but it reduces interpretability and creates
unnecessary downstream renderer obligations.

## 4. rc.1: Metric Gaming by All-Empty Delivery

Prompt v0.2-rc.1 improved D5 but produced `delivery_plan = {}` on all 30
development cases. It was rejected as delivery mode collapse.

This exposed a measurement boundary:

- D5 correctly rewards the absence of unnecessary controls.
- D5 deliberately does not penalize missing useful controls.
- D6 can penalize under-specification, but its aggregate score did not by itself
  make the 30/30 behavioral collapse sufficiently salient.

Consequently, TeachIntent always interprets D5 together with D6 and the
measured empty/non-empty distribution. A high D5 is not sufficient evidence of
good delivery planning.

## 5. rc.2 / v0.2: Sparse Does Not Mean Universally Better

rc.2 corrected the collapse: 27 development plans were empty and three
pedagogically motivated Corrective Feedback or Scaffolding plans were non-empty.
On the 26 paired development cases, D5 improved in 16 and worsened in zero; D4
improved in 10, tied in 15, and worsened in one.

Protected dimensions still had isolated case-level decreases:

| Dimension | Improved | Tied | Worsened |
|---|---:|---:|---:|
| D1 | 0 | 24 | 2 |
| D2 | 0 | 26 | 0 |
| D3 | 2 | 23 | 1 |
| D6 | 4 | 20 | 2 |

The mean changes did not indicate systematic regression, but these cases
prevent a claim that v0.2 is uniformly superior. The comparison is also based
on development cases already used to shape the candidate.

## 6. Evaluator Judgment Boundaries

The evaluator confirmatory run achieved 95.83% directional accuracy and 99.62%
within-one repeatability, not perfection. One primary comparison did not move
in the expected direction, and critical-flag validation contained one false
positive (`coercive_or_hostile_delivery`).

Additional boundaries include:

- scores depend on the frozen Judge model and prompt condition;
- legal-artifact parsing and evidence grounding can fail even when a Judge
  returns text;
- dimension coupling is real—for example, intent mismatch can also affect
  instructional adequacy—so protected/collateral partitions are prespecified;
- an unweighted overall percentage can obscure dimension-specific or critical
  failures and is therefore secondary only;
- automated evaluation has not been calibrated against large-scale educator
  ratings or student learning outcomes.

## 7. Dataset and Generalization Boundaries

- The 30-case Pilot is balanced and diagnostic, not representative of all
  classrooms, subjects, ages, cultures, or curricula.
- Release sanity adds 12 genuinely new cases but is intentionally small and
  suffered low Judge availability; only five comparisons were pair-eligible.
- The recorded Generator datasets use zh-CN output. Multilingual performance is
  not established.
- Difficult cases cover several known risks—prompt injection, learner
  frustration, direct-answer pressure, misconception persistence, and intent
  boundaries—but cannot enumerate all adversarial inputs.
- Self-constructed cases support engineering validation, not claims about
  population-level educational effectiveness.

## 8. Product Scope Boundaries

TeachIntent plans one teaching utterance after another system has supplied the
intent. It does not:

- infer which pedagogical intent should be used;
- manage multi-turn tutoring policy or learner models over time;
- verify the real-world truth of arbitrary content anchors;
- guarantee that the optional Qwen3-TTS adapter will perceptually realize every
  control or improve audio quality;
- perform voice cloning;
- measure student learning, retention, engagement, or classroom safety;
- replace teacher judgment in consequential educational settings.

## 9. Deployment Implications

A downstream application should validate every input and output, display or log
dimension-level diagnostics rather than only an overall score, handle provider
and evaluator unavailability explicitly, and map delivery controls through a
renderer adapter that reports unsupported hints. High-stakes deployment would
also require human educator review, broader multilingual/domain evaluation,
privacy controls, and student-outcome studies.

## 10. Optional TTS Demonstration Boundary

The public demo includes a conservative Qwen3-TTS CustomVoice adapter, but no
recorded research run evaluates its audio. It maps only utterance-level tone,
emotion, qualitative speaking rate, and qualitative volume. Pitch and every
segment-local control are explicitly reported as unsupported. Natural-language
`instruct` realization is best-effort, so a planned render can ignore, weaken,
or overstate a requested quality. The A/B manifest controls text, speaker,
model, language, seed, and generation path, but a listening comparison remains
illustrative rather than evidence of acoustic accuracy or student benefit.
