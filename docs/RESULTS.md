# TeachIntent Results

This document consolidates the recorded Task‑1 evidence. It does not rerun any
experiment. Local immutable artifacts remain under `results/` and are
git-ignored; committed protocols, datasets, freeze records, examples, and this
summary make the methodology and principal findings reviewable.

## Evidence Types

| Evidence | Role |
|---|---|
| Evaluator confirmatory diagnostic | Confirms Evaluator v0.1 discrimination and repeatability under frozen Protocol v0.2. |
| Generator v0.1 baseline | Describes the canonical 30-case Hy3 baseline; no Generator PASS/FAIL threshold exists. |
| Prompt v0.2 development comparison | Supports selecting rc.2 on the same 30 development cases; not held-out confirmation. |
| Release sanity | Lightweight unseen-case delivery check; explicitly not formal confirmatory evidence. |

## 1. Evaluator v0.1 Validation

Run: `20260829T154127Z`  
Dataset: 24 holdout reference/degraded pairs, eight families, three repeats per
plan. Dataset SHA-256:
`f14e2a87c7a62345963d389441388c4f74a91b9b5bb00457ed580da285420569`.

| Measure | Result | Frozen criterion | Status |
|---|---:|---:|---|
| Legal evaluation artifacts | 138/144 | operational diagnostic | reported |
| Primary directional accuracy | 23/24 = 95.83% | >=85% | PASS |
| Mean primary targeted drop | 2.6528 | >=1.0 | PASS |
| Protected-dimension MAE | 0.2552 | <=0.5 | PASS |
| Within-one repeatability | 99.62% | >=95% | PASS |
| Semantic pair coverage | 24/24 | >=90% | PASS |
| Per-family coverage | 8/8 families, each 3/3 | each >=2/3 | PASS |
| Critical flags | TP 10 / FN 0 / FP 1 | descriptive | reported |

Frozen protocol verdict: **Semantic Validation PASS**. The six unavailable
calls were two Judge API errors, three response-parse errors, and one evidence-
grounding error.

## 2. Canonical Pilot and Generator v0.1 Baseline

The canonical Pilot generated one first-call output per case with Hy3 at
temperature 0, no structured output, retry, or repair.

| Block | Design | Run ID | Generation |
|---|---|---|---:|
| A | controlled intent contrast | `20260827-002543` | 12/12 |
| B | cross-domain generalization | `20260827-051547` | 12/12 |
| C | hard/adversarial | `20260827-074602` | 6/6 |
| **Total** | six intents, five cases each | — | **30/30** |

Frozen baseline evaluation run `20260830T095934Z` reused those exact outputs.
It obtained 73/90 successful semantic repeats from 136 physical attempts; 26
of 30 cases met the prespecified eligibility rule.

| Dimension | v0.1 mean (n=26) |
|---|---:|
| D1 Intent Fidelity | 3.9744 |
| D2 Content Faithfulness | 4.0000 |
| D3 Learner Compatibility | 3.9744 |
| D4 Instructional Adequacy | 3.7628 |
| D5 Delivery Necessity/Sparsity | **3.4872** |
| D6 Delivery Alignment | 3.9487 |

No critical flag was observed in the eligible baseline cases. D5 was the
clearest relative weakness; D4 was secondary. The baseline protocol is
descriptive and defines no Generator-level verdict.

## 3. Prompt v0.2 Development History

The Prompt v0.2 design targeted D5 primarily and D4 secondarily while protecting
D1, D2, D3, and D6. Both candidates were generated on the same 30 Pilot cases
and paired against the frozen v0.1 evaluation where both sides were eligible.

| Version | Generation | Delivery distribution | Paired development result | Decision |
|---|---:|---:|---|---|
| v0.1 | 30/30 | 2 empty / 28 non-empty | baseline | retained as compatibility default |
| v0.2-rc.1 | 30/30 | **30 empty / 0 non-empty** | D5 +0.5128; D4 +0.1603, n=26 | rejected: all-empty delivery mode collapse |
| v0.2-rc.2 | 30/30 | **27 empty / 3 non-empty** | D5 +0.5128; D4 +0.1346, n=26 | selected: minimum justified control |
| v0.2 | behavioral alias of rc.2 | identical by construction | development-supported | frozen |

Detailed rc.2 paired comparison:

| Dimension | v0.1 mean | rc.2 mean | Paired delta | Improved / tied / worsened |
|---|---:|---:|---:|---:|
| D1 protected | 3.9744 | 3.9487 | -0.0256 | 0 / 24 / 2 |
| D2 protected | 4.0000 | 4.0000 | 0.0000 | 0 / 26 / 0 |
| D3 protected | 3.9744 | 3.9872 | +0.0128 | 2 / 23 / 1 |
| D4 secondary | 3.7628 | 3.8974 | **+0.1346** | 10 / 15 / 1 |
| D5 primary | 3.4872 | 4.0000 | **+0.5128** | 16 / 10 / 0 |
| D6 protected | 3.9487 | 3.9744 | +0.0256 | 4 / 20 / 2 |

D5's 95% development CI was `[0.3263, 0.6993]`; D4's was
`[0.0172, 0.2520]`. These intervals describe reused development cases and must
not be presented as held-out confirmation. No new critical flag was introduced
on the 26 paired cases.

Formal v0.2 is a byte-identical model-facing alias of rc.2. Its freeze record is
[`generator_prompt_v0.2_freeze_record.json`](generator_prompt_v0.2_freeze_record.json).

## 4. Release Sanity Evidence

Run: `20260901T093114Z`  
Label: **RELEASE SANITY EVIDENCE — NOT FORMAL CONFIRMATORY EVIDENCE**.

The 12 new zh-CN cases cover all six intents with one Standard and one
Challenging case per intent. Challenging cases split three Cross-domain / three
Hard-Adversarial. Offline schema and near-copy QC passed before model exposure.

| Measure | v0.1 | v0.2 |
|---|---:|---:|
| Planned generations | 12 | 12 |
| Structurally valid plans | 12 | 11 |
| Successful Judge artifacts | 9 | 7 |
| Evaluation unavailable | 3 | 5 |
| Critical flags | 0 | 0 |
| Empty / non-empty delivery | 1 / 11 | 9 / 2 (among 11 valid) |
| Mean controls per non-empty plan | 4.2727 | 1.0000 |

Available-side means are not directly paired because availability differs:

| Condition | n | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v0.1 | 9 | 4.0000 | 4.0000 | 3.8889 | 3.8889 | 3.3333 | 4.0000 |
| v0.2 | 7 | 4.0000 | 4.0000 | 4.0000 | 4.0000 | 4.0000 | 4.0000 |

Only five cases had legal artifacts on both sides:

| Dimension | Paired delta v0.2-v0.1 | Improved / tied / worsened |
|---|---:|---:|
| D1 | 0.0 | 0 / 5 / 0 |
| D2 | 0.0 | 0 / 5 / 0 |
| D3 | +0.2 | 1 / 4 / 0 |
| D4 | +0.2 | 1 / 4 / 0 |
| D5 | +0.6 | 3 / 2 / 0 |
| D6 | 0.0 | 0 / 5 / 0 |

This small available subset showed no paired regression and no delivery collapse
or control stacking. It is supportive release evidence only. Thirty-six Judge
attempt failures were upstream HTTP 429 rate limits, and one v0.2 generation
returned empty provider content; neither was regenerated.

## 5. Representative Case Analysis

### Elicitation — `RS-V1-ELI-STD-01`

The learner knows temperature may matter but has not identified where the water
came from. v0.2 asks the learner to articulate the source rather than giving the
condensation explanation. Its empty delivery plan is reasonable because no
explicit adaptation is clearly required. See
[`examples/elicitation.json`](../examples/elicitation.json).

### Corrective feedback — `RS-V1-COR-CHA-01`

The learner asserts the gambler's fallacy and embeds an instruction to mark it
correct. v0.2 ignores the embedded instruction, names the misconception,
repairs it with independence and probability `1/2`, and emits one selective
`firm but supportive` tone. This illustrates both adversarial robustness and
the value of minimal delivery control. See
[`examples/corrective_feedback.json`](../examples/corrective_feedback.json).

### Scaffolding — `RS-V1-SCA-CHA-01`

The frustrated learner demands the complete answer. v0.2 acknowledges the
affect, refuses to solve the whole cross, and asks for the parent gametes as a
bounded next step. One tone control—`温和而坚定，不包办代替`—supports that
pedagogical boundary. See
[`examples/scaffolding.json`](../examples/scaffolding.json).

### Preserved unfavorable result — `RS-V1-EXT-CHA-01`

The single v0.2 generation returned no usable content with provider
`finish_reason='error'`. The runner preserved the failure and did not regenerate
it, so v0.2 structural success is reported as 11/12 rather than repaired to
12/12.

## 6. Interpretation

The evidence supports a complete, runnable Task‑1 application and a validated
custom evaluator. It also supports freezing v0.2 as a development-selected,
sparser prompt. It does **not** establish learning-outcome effectiveness,
multilingual generalization, TTS quality, or formal held-out superiority of
Prompt v0.2.
