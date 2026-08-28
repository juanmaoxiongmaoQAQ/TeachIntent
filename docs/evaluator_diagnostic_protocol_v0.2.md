# TeachIntent Evaluator Diagnostic Protocol v0.2

**Status:** Frozen  
**Version:** v0.2  
**Frozen on:** 2026-08-28  
**Scope:** Experiment-side validation protocol for **TeachIntent Evaluator v0.1**  
**Evaluator under test:** Evaluator Specification v0.1 + Evaluator Implementation v0.1  
**Development diagnostic dataset:** `cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl` (retrospective only)  
**Development dataset status:** Frozen  
**Confirmatory holdout dataset:** `cases/evaluator_diagnostic/diagnostic_pairs_v0.2_holdout.jsonl`  
**Confirmatory holdout status:** To be constructed and frozen after this protocol is frozen, before any confirmatory Judge call  
**Protocol lineage:** v0.2 is a post-hoc methodological revision following analysis of Diagnostic Protocol v0.1 results.

---

## 1. Purpose

This protocol defines the confirmatory validation procedure for **TeachIntent Evaluator v0.1** after the first controlled diagnostic study revealed that the original diagnostic protocol treated all non-target dimensions as if they were theoretically independent.

The Evaluator itself is **not changed** by this protocol.

The purpose of Diagnostic Protocol v0.2 is to answer the following question:

> Given a structurally valid Speech Plan with a deliberately introduced semantic defect, does TeachIntent Evaluator v0.1 reliably detect the intended defect while keeping dimensions that should theoretically remain unaffected sufficiently stable?

The protocol therefore separates:

1. **Primary semantic effects** — the dimension(s) directly targeted by a perturbation.
2. **Allowed collateral effects** — dimensions that may reasonably shift because of known rubric coupling.
3. **Protected dimensions** — dimensions that should remain comparatively stable.
4. **Operational failures** — API, parsing, evidence-grounding, or evaluator-execution failures that are not themselves semantic judgments.

---

## 2. Relationship to Evaluator v0.1

This protocol does **not** modify:

- Evaluator Specification v0.1
- Evaluator Implementation v0.1
- D1–D6 rubric semantics
- critical-flag definitions
- Judge Prompt v0.1
- overall-score computation
- evidence rules
- failure taxonomy
- Generator v0.1
- Generator Prompt v0.1
- TeachIntent Input Schema `1.0.0-rc.2`
- Speech Plan Schema `1.0.0-rc.3`

All Evaluator behavior remains frozen.

This document only defines how controlled diagnostic results are partitioned, aggregated, interpreted, and judged.

---

## 3. Methodological Disclosure

Diagnostic Protocol v0.2 was developed **after inspection of the results produced under Diagnostic Protocol v0.1**.

It is therefore:

- not preregistered;
- not independent of the first diagnostic run;
- not permitted to retroactively convert the v0.1 result from FAIL to PASS.

The first diagnostic run remains a valid historical result and must be preserved.

### 3.1 Historical v0.1 run

Historical run identifier:

```text
20260828T110723Z
```

Judge condition:

```text
provider:                  openrouter
requested model:           qwen/qwen3.5-plus-20260420
temperature:               0
structured_output_enabled: false
retry_enabled:             false
self_repair_enabled:       false
judge_prompt_version:      v0.1
```

Observed result under Diagnostic Protocol v0.1:

```text
Expected calls:                 144
Successful evaluations:        135
Evaluator failures:              9

Directional Accuracy:          24/24 = 100.0%
Mean Targeted Drop:            2.7014
Off-target MAE:                0.6889
Within-one Repeatability:      0.9606
Critical Flags:                TP=9, FN=1, FP=1

Diagnostic Protocol v0.1:
FAIL
```

The FAIL determination is final for Protocol v0.1 because:

```text
Off-target MAE = 0.6889 > 0.5
```

### 3.2 Why v0.2 exists

Post-hoc inspection showed that the v0.1 metric treated every non-target dimension as a protected dimension.

This was too strong for the frozen D1–D6 rubric.

Examples of theoretically plausible coupling include:

- D1 Pedagogical Intent Fidelity ↔ D4 Intent-Specific Instructional Adequacy
- D2 Content Faithfulness/Boundary ↔ D3 Learner-State Compatibility
- D2 Content Faithfulness/Boundary ↔ D4 Intent-Specific Instructional Adequacy
- D6 Delivery–Pedagogy Alignment ↔ D5 Delivery Necessity/Sparsity
- D6 Delivery–Pedagogy Alignment ↔ D3 Learner-State Compatibility

Protocol v0.2 therefore makes these relationships explicit **before a new confirmatory run**.

---

## 4. Diagnostic Materials and Units

Protocol v0.2 distinguishes two diagnostic datasets with different methodological roles.

### 4.1 Development diagnostic dataset v0.1

The existing frozen dataset:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl
```

contains:

```text
24 pairs
8 perturbation families
3 pairs per family
```

It was used in the historical Protocol v0.1 run and subsequently inspected when Protocol v0.2 was designed.

It is therefore a:

```text
development / retrospective diagnostic dataset
```

and must **not** be used to provide confirmatory PASS/FAIL evidence for Protocol v0.2.

### 4.2 Confirmatory holdout dataset v0.2

The formal Protocol v0.2 confirmatory run must use a new holdout dataset:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.2_holdout.jsonl
```

The holdout dataset must contain:

```text
24 new pairs
8 perturbation families
3 new pairs per family
```

The concrete input cases and reference/degraded Speech Plans must not be copies or trivial paraphrases of the v0.1 development pairs.

The holdout cases must not have been used to define:

- the v0.2 family coupling matrix;
- primary / allowed-collateral / protected partitions;
- v0.2 thresholds;
- v0.2 aggregation rules.

No real Judge call may be made on any holdout case until the holdout dataset has completed mechanical validation, manual QC, and dataset freeze.

### 4.3 Pair structure

Each diagnostic pair consists of:

```text
TeachIntent input
reference Speech Plan
degraded Speech Plan
family label
expected critical flags
experiment-side notes
```

Both plans must remain structurally valid under the frozen Layer-0 pipeline.

The semantic unit of analysis is a **reference/degraded pair**.

The repeated execution unit is:

```text
pair × variant × repeat
```

where:

```text
variant ∈ {reference, degraded}
repeat ∈ {1, 2, 3}
```

A full confirmatory run therefore contains:

```text
24 holdout pairs × 2 variants × 3 repeats = 144 calls
```

## 5. Development Dataset v0.1 — Frozen but Retrospective Only

The content of:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl
```

must remain unchanged.

Its frozen SHA-256 is:

```text
a004715338c97d9e85b92fe0221a18631aa2884f6bb8b1d78a66066ccdd12664
```

Under Protocol v0.2, this dataset may be used only for:

- historical reporting;
- retrospective descriptive analysis;
- parser/interface testing;
- metrics implementation tests;
- offline regression tests.

It must not be used to declare Protocol v0.2 Semantic Validation PASS.

## 6. Confirmatory Holdout Dataset v0.2 Requirements

The holdout dataset is a separate experimental artifact from this protocol. The protocol may be frozen before the holdout dataset is authored, but no confirmatory API run is authorized until the holdout dataset itself is frozen.

### 6.1 Construction

The holdout dataset must contain exactly:

```text
24 pairs
8 families
3 pairs per family
```

Each pair must be newly authored for holdout use.

The holdout may follow the same perturbation-family definitions as the development dataset, but its concrete:

- instructional content;
- pedagogical context;
- learner state;
- reference plan;
- degraded plan

must be new.

The holdout must not be created by copying a v0.1 pair and making superficial lexical substitutions.

### 6.2 Structural validity

For every holdout pair:

- the TeachIntent input must pass Input Schema `1.0.0-rc.2`;
- the reference plan must pass the frozen Layer-0 Speech Plan validation pipeline;
- the degraded plan must pass the same Layer-0 pipeline;
- the degraded plan must remain structurally valid and differ semantically from the reference plan.

Malformed JSON, missing required fields, illegal enums, and other structural failures are not valid semantic perturbations.

### 6.3 Family assignment

Every holdout pair must be assigned to exactly one of the eight frozen perturbation families.

Its dimension partition is inherited from the frozen family matrix in Section 9.

Pair authors may not redefine primary, allowed-collateral, or protected dimensions at the individual-pair level.

### 6.4 Manual QC before Judge exposure

Before any real Judge call, each holdout pair must be manually reviewed to verify that:

1. the reference plan is pedagogically reasonable;
2. the degraded plan introduces the intended family-level defect;
3. the degraded plan does not contain an obvious avoidable confound outside the family coupling policy;
4. both plans remain Layer-0 valid;
5. expected critical flags are specified consistently with the frozen critical-flag definitions;
6. no result from the Judge has been observed for that pair.

Mechanical validation and manual QC must occur before dataset freeze.

### 6.5 Holdout freeze

After QC, the holdout dataset must be frozen before the first confirmatory Judge call.

The freeze record must include:

```text
dataset path
dataset version
SHA-256
pair count
family distribution
freeze timestamp
```

Once the first real Judge call begins, the holdout dataset may not be edited.

If a substantive dataset defect is discovered after Judge exposure, the affected confirmatory run must not be repaired by editing the dataset in place. A new holdout dataset version and a fresh confirmatory run are required.

### 6.6 Separation from Layer-1 Judge input

Experiment-side metadata, including:

```text
family
primary_target_dimensions
allowed_collateral_dimensions
protected_dimensions
expected_flags
notes
```

must never be exposed to the Layer-1 Judge.

## 7. Frozen Evaluator Dimensions

The six evaluator dimensions are:

| ID | Frozen field name | Short name |
|---|---|---|
| D1 | `pedagogical_intent_fidelity` | Pedagogical Intent Fidelity |
| D2 | `content_faithfulness_boundary` | Content Faithfulness / Boundary |
| D3 | `learner_state_compatibility` | Learner-State Compatibility |
| D4 | `intent_specific_instructional_adequacy` | Intent-Specific Instructional Adequacy |
| D5 | `delivery_necessity_sparsity` | Delivery Necessity / Sparsity |
| D6 | `delivery_pedagogy_alignment` | Delivery–Pedagogy Alignment |

These names and score semantics remain frozen.

---

## 8. Dimension-Coupling Policy

Each perturbation family must partition all six dimensions into three mutually exclusive groups:

```text
primary_target_dimensions
allowed_collateral_dimensions
protected_dimensions
```

The following invariants are mandatory.

### 8.1 Disjointness

For every family:

```text
primary ∩ allowed_collateral = ∅
primary ∩ protected          = ∅
allowed_collateral ∩ protected = ∅
```

### 8.2 Completeness

For every family:

```text
primary ∪ allowed_collateral ∪ protected
=
{D1, D2, D3, D4, D5, D6}
```

No dimension may be omitted.

No unknown dimension may be added.

### 8.3 Interpretation

**Primary dimensions** are expected to decrease when moving from the reference plan to the degraded plan.

**Allowed collateral dimensions** may shift because the rubric makes them theoretically coupled to the manipulated defect. These dimensions are diagnostic-only and do not count against semantic specificity.

**Protected dimensions** are expected to remain relatively stable and are the basis for specificity testing.

---

## 9. Frozen Family Coupling Matrix v0.2

The following matrix is frozen when this protocol is frozen.

### 9.1 Family A — Intent mismatch

**Primary**

```text
D1 pedagogical_intent_fidelity
```

**Allowed collateral**

```text
D4 intent_specific_instructional_adequacy
```

**Protected**

```text
D2 content_faithfulness_boundary
D3 learner_state_compatibility
D5 delivery_necessity_sparsity
D6 delivery_pedagogy_alignment
```

### 9.2 Family B — Content contradiction

**Primary**

```text
D2 content_faithfulness_boundary
```

**Allowed collateral**

```text
D3 learner_state_compatibility
D4 intent_specific_instructional_adequacy
```

**Protected**

```text
D1 pedagogical_intent_fidelity
D5 delivery_necessity_sparsity
D6 delivery_pedagogy_alignment
```

### 9.3 Family C — Material off-anchor content

**Primary**

```text
D2 content_faithfulness_boundary
```

**Allowed collateral**

```text
D4 intent_specific_instructional_adequacy
```

**Protected**

```text
D1 pedagogical_intent_fidelity
D3 learner_state_compatibility
D5 delivery_necessity_sparsity
D6 delivery_pedagogy_alignment
```

### 9.4 Family D — Learner-state mismatch

**Primary**

```text
D3 learner_state_compatibility
```

**Allowed collateral**

```text
D4 intent_specific_instructional_adequacy
```

**Protected**

```text
D1 pedagogical_intent_fidelity
D2 content_faithfulness_boundary
D5 delivery_necessity_sparsity
D6 delivery_pedagogy_alignment
```

### 9.5 Family E — Incomplete corrective feedback

**Primary**

```text
D4 intent_specific_instructional_adequacy
```

**Allowed collateral**

```text
none
```

**Protected**

```text
D1 pedagogical_intent_fidelity
D2 content_faithfulness_boundary
D3 learner_state_compatibility
D5 delivery_necessity_sparsity
D6 delivery_pedagogy_alignment
```

### 9.6 Family F — Delivery over-specification

**Primary**

```text
D5 delivery_necessity_sparsity
```

**Allowed collateral**

```text
none
```

**Protected**

```text
D1 pedagogical_intent_fidelity
D2 content_faithfulness_boundary
D3 learner_state_compatibility
D4 intent_specific_instructional_adequacy
D6 delivery_pedagogy_alignment
```

### 9.7 Family G — Delivery–pedagogy conflict

**Primary**

```text
D6 delivery_pedagogy_alignment
```

**Allowed collateral**

```text
D3 learner_state_compatibility
D5 delivery_necessity_sparsity
```

**Protected**

```text
D1 pedagogical_intent_fidelity
D2 content_faithfulness_boundary
D4 intent_specific_instructional_adequacy
```

### 9.8 Family H — Prompt-injection compliance

**Primary**

```text
D1 pedagogical_intent_fidelity
```

**Allowed collateral**

```text
D4 intent_specific_instructional_adequacy
```

**Protected**

```text
D2 content_faithfulness_boundary
D3 learner_state_compatibility
D5 delivery_necessity_sparsity
D6 delivery_pedagogy_alignment
```

---

## 10. Protocol Metadata Contract

Protocol-specific dimension metadata should be stored separately from the frozen diagnostic dataset.

Recommended file:

```text
cases/evaluator_diagnostic/protocol_v0.2_metadata.json
```

Recommended top-level structure:

```json
{
  "protocol_version": "v0.2",
  "families": {
    "intent_mismatch": {
      "primary_target_dimensions": [],
      "allowed_collateral_dimensions": [],
      "protected_dimensions": []
    }
  }
}
```

Each family entry must pass the disjointness and completeness rules in Section 8.

The metadata must not be exposed to the Layer-1 Judge.

---

## 11. Successful Semantic Evaluation

A run contributes semantic scores only if it returns a valid:

```text
UniversalEvaluationArtifact
```

with:

```text
structural_valid = true
scores != null
```

EvaluatorFailureArtifact instances do not contribute numeric semantic scores.

A failed execution must never be converted into a semantic score of zero.

---

## 12. Repeat Aggregation

Each plan variant is evaluated three times independently.

For every:

```text
pair
variant
dimension
```

collect only successful semantic scores.

### 12.1 Pair-variant semantic score

The pair-variant semantic score is the arithmetic mean over successful repeats:

```text
mean_variant_dimension
=
sum(successful repeat scores)
/
number of successful repeat scores
```

Do not use:

- best-of-three
- worst-of-three
- median
- majority score
- manual selection
- failure replacement
- post-hoc reruns

### 12.2 Variant eligibility

A variant is semantically eligible only if it has:

```text
at least 2 successful repeats
```

### 12.3 Pair eligibility

A pair is semantically eligible only if:

```text
reference variant has >=2 successful repeats
AND
degraded variant has >=2 successful repeats
```

Otherwise the pair is:

```text
operationally incomplete
```

Operationally incomplete pairs do not enter confirmatory pair-level semantic metrics.

They must still be reported.

---

## 13. Primary Directional Accuracy

For every semantically eligible pair and every primary target dimension:

```text
reference_mean > degraded_mean
```

is counted as a correct directional comparison.

Define:

```text
Primary Directional Accuracy
=
correct primary directional comparisons
/
eligible primary directional comparisons
```

Report:

```text
numerator
denominator
percentage
```

### Frozen threshold

```text
Primary Directional Accuracy >= 85%
```

Ties do not count as correct.

---

## 14. Mean Primary Targeted Drop

For each eligible primary comparison:

```text
drop
=
reference_mean - degraded_mean
```

Define:

```text
Mean Primary Targeted Drop
=
arithmetic mean of all eligible primary drops
```

### Frozen threshold

```text
Mean Primary Targeted Drop >= 1.0
```

---

## 15. Protected-Dimension MAE

Protocol v0.2 replaces the v0.1 "all non-target dimensions" interpretation with explicitly protected dimensions.

For each semantically eligible pair and each protected dimension:

```text
protected_shift
=
abs(reference_mean - degraded_mean)
```

Define:

```text
Protected-Dimension MAE
=
arithmetic mean of all eligible protected shifts
```

### Frozen threshold

```text
Protected-Dimension MAE <= 0.5
```

Allowed-collateral dimensions are excluded from this metric.

Primary dimensions are excluded from this metric.

---

## 16. Allowed-Collateral Diagnostics

Allowed-collateral dimensions are reported but do not participate in PASS/FAIL thresholds.

For each allowed-collateral dimension, report:

### 16.1 Mean Signed Drop

```text
reference_mean - degraded_mean
```

aggregated arithmetically.

Positive values indicate lower degraded scores.

### 16.2 Mean Absolute Shift

```text
abs(reference_mean - degraded_mean)
```

aggregated arithmetically.

### 16.3 Breakdown

Report at least:

```text
global
per family
per allowed-collateral dimension
```

These values are descriptive.

They must not be used to alter the frozen coupling matrix after the confirmatory run.

---

## 17. Repeatability

Repeatability is evaluated on successful runs only.

For every:

```text
pair
variant
dimension
```

with at least two successful scores, construct all unordered successful run pairs.

For three successful repeats:

```text
C(3,2) = 3
```

For two successful repeats:

```text
C(2,2) = 1
```

### 17.1 Exact agreement

A repeat pair agrees exactly if:

```text
score_a == score_b
```

Report:

```text
exact agreements
n
exact agreement rate
```

### 17.2 Within-one-point agreement

A repeat pair is within one point if:

```text
abs(score_a - score_b) <= 1
```

Report:

```text
within-one agreements
n
within-one agreement rate
```

### Frozen threshold

```text
Within-one-point agreement >= 95%
```

### 17.3 Repeatability coverage

Define a theoretical score series as:

```text
pair × variant × dimension
```

The full experiment therefore has:

```text
24 × 2 × 6 = 288 theoretical score series
```

A score series enters repeatability analysis if it has at least two successful scores.

Report:

```text
eligible repeatability score series
/
288
```

No separate hard threshold is imposed on repeatability coverage, because semantic pair coverage in Section 18 provides the main operational completeness guard.

---

## 18. Semantic Coverage

Operational failure must not be allowed to reduce the confirmatory semantic evidence to a trivial subset.

### 18.1 Overall Semantic Pair Coverage

Define:

```text
Semantic Pair Coverage
=
semantically eligible pairs / 24
```

### Frozen minimum

```text
Semantic Pair Coverage >= 90%
```

Because there are 24 pairs, this requires at least:

```text
22 semantically eligible pairs
```

### 18.2 Per-family minimum

Each family contains 3 pairs.

Every family must contain at least:

```text
2 / 3 semantically eligible pairs
```

If any family has fewer than 2 eligible pairs, confirmatory semantic validation must FAIL.

---

## 19. Critical Flag Diagnostics

Critical flags remain diagnostic-only in Protocol v0.2.

They do not create a hard PASS/FAIL threshold.

### 19.1 Repeat-level reporting

For every successful run, report:

- expected flag occurrence;
- missing expected flag;
- unexpected flag occurrence;
- reference-side unexpected flag occurrence.

### 19.2 Pair-level degraded-variant majority

For a semantically observed degraded variant, use successful repeats only.

An expected flag is detected at pair level if it appears in:

```text
strictly more than 50%
```

of successful degraded runs.

Examples:

```text
3 successful degraded runs:
2/3 or 3/3 => detected

2 successful degraded runs:
2/2 => detected
1/2 => not detected
```

If a degraded variant has only one successful run, it is excluded from pair-level flag-majority reporting.

### 19.3 Pair-level diagnostics

Report:

```text
TP
FN
FP
```

and a per-flag breakdown.

Pair-level counting is defined over **pair × flag type**.

For a degraded variant:

- **TP**: an expected flag reaches strict majority among successful degraded repeats;
- **FN**: an expected flag does not reach strict majority among successful degraded repeats, provided the degraded variant has at least two successful repeats;
- **FP**: a flag type that is **not** listed in `expected_flags` nevertheless reaches strict majority among successful degraded repeats.

If a pair has both an expected flag and a different unexpected majority flag, the expected flag may contribute a TP while the unexpected flag contributes a separate FP.

Reference-side critical flags must be reported separately as **reference-side unexpected flags** and must not be silently merged into degraded-side FP counts.

---

## 20. Execution Failure vs Semantic Failure

The following evaluator-owned failures are **operational/execution failures**, not semantic scores:

```text
setup_input_jsonschema_error
setup_input_pydantic_error
setup_run_context_error
setup_judge_config_error
judge_api_error
judge_response_parse_error
judge_output_schema_error
evidence_source_error
evidence_grounding_error
internal_evaluator_error
```

A Generator Layer-0 structural failure, if encountered, is also not converted into a semantic score.

Execution failures:

- must be preserved as artifacts;
- must be reported separately;
- must not be converted to zeros;
- must not be silently retried;
- must not be self-repaired;
- must not be omitted from operational reporting.

---

## 21. Operational Reliability

Operational reliability is reported separately from semantic validation.

Report:

```text
Expected calls
Successful UniversalEvaluationArtifacts
EvaluatorFailureArtifacts
Operational Success Rate
```

where:

```text
Operational Success Rate
=
successful universal evaluations
/
expected calls
```

Also report failure counts by failure type.

### Protocol v0.2 operational threshold

There is **no hard PASS/FAIL threshold** on raw operational success rate in v0.2.

Operational reliability remains descriptive.

However, execution failures indirectly constrain confirmatory validity through the Semantic Pair Coverage requirements in Section 18.

---

## 22. Semantic Acceptance Criteria

A new confirmatory run under Diagnostic Protocol v0.2 receives:

```text
Semantic Validation = PASS
```

only if **all** of the following hold:

1. **Primary Directional Accuracy**
   ```text
   >= 85%
   ```

2. **Mean Primary Targeted Drop**
   ```text
   >= 1.0
   ```

3. **Protected-Dimension MAE**
   ```text
   <= 0.5
   ```

4. **Within-one-point Repeatability**
   ```text
   >= 95%
   ```

5. **Semantic Pair Coverage**
   ```text
   >= 90%
   ```

6. **Per-family semantic coverage**
   ```text
   every family >= 2/3 eligible pairs
   ```

If any criterion fails:

```text
Semantic Validation = FAIL
```

Critical-flag performance is report-only.

Raw operational success rate is report-only.

---

## 23. Confirmatory Run Requirement

The historical v0.1 run and the v0.1 development dataset must **not** be used as confirmatory evidence for Protocol v0.2.

After this protocol is frozen, a new confirmatory holdout dataset must be authored, mechanically validated, manually QC'd, and frozen according to Section 6.

Only then may a new independent real run begin.

The confirmatory run must use:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.2_holdout.jsonl
```

or the formally frozen successor path recorded in the holdout freeze artifact.

It must **not** simply rerun:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl
```

under revised metrics and call that result confirmatory.

Nominal confirmatory design:

```text
24 previously unused holdout pairs
× 2 variants
× 3 independent repeats
= 144 real Evaluator calls
```

"Previously unused" here means the holdout pairs were not used to design the Protocol v0.2 coupling matrix, metrics, thresholds, or acceptance rules, and no real Judge result for those pairs was observed before holdout freeze.

The new run must use a single frozen Judge condition for all calls.

The intended condition remains:

```text
provider:                  openrouter
requested model:           qwen/qwen3.5-plus-20260420
temperature:               0
structured_output_enabled: false
retry_enabled:             false
self_repair_enabled:       false
evaluator_version:         v0.1
judge_prompt_version:      v0.1
```

Any planned change to these conditions must be documented **before** the first confirmatory call. A mid-run change invalidates the run as a single-condition confirmatory experiment.

## 24. Retrospective Use of v0.1 Dataset and Artifacts

The development dataset:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl
```

and historical artifacts from:

```text
results/evaluator_diagnostic/20260828T110723Z/
```

may be used only for:

- offline parser testing;
- metrics implementation testing;
- regression testing;
- descriptive retrospective analysis;
- interface validation.

Any output derived from those historical materials under Protocol v0.2 must be labeled:

```text
RETROSPECTIVE
NON-CONFIRMATORY
NOT A v0.2 VALIDATION RESULT
```

Historical material must not be used to declare Protocol v0.2 PASS, regardless of what the v0.2 metrics would yield if recomputed retrospectively.

## 25. Artifacts for a v0.2 Confirmatory Run

A new confirmatory run must preserve:

```text
run_manifest.json
evaluations.jsonl
pair_metrics.csv
summary.json
README.md
```

At minimum, the run manifest must include:

```text
run_id
started_at
completed_at

protocol_version
protocol_document_sha256
protocol_metadata_sha256

confirmatory_dataset_path
confirmatory_dataset_version
confirmatory_dataset_sha256

development_dataset_path
development_dataset_sha256

pair_count
plan_count
repeats
expected_calls
successful_evaluations
failed_evaluations

evaluator_version
judge_prompt_version
judge_prompt_sha256

judge_provider
judge_model_requested
temperature
structured_output_enabled
retry_enabled
self_repair_enabled
```

The confirmatory dataset SHA-256 must match the dataset frozen before the first Judge call.

The development-dataset fields are provenance only; the development dataset must not contribute confirmatory scores.

Do not store API secrets.

## 26. Pair-Level Reporting

For every diagnostic pair, the confirmatory output should expose enough information to reproduce the semantic decision.

At minimum:

```text
pair_id
family

semantic_eligibility

primary_target_dimensions
allowed_collateral_dimensions
protected_dimensions

reference successful repeat count
degraded successful repeat count

reference mean D1–D6
degraded mean D1–D6

primary drops
protected shifts
allowed-collateral signed drops
allowed-collateral absolute shifts

reference critical flags
degraded critical flags
expected critical flags

operational failures associated with the pair
```

---

## 27. Family-Level Reporting

For each of the eight perturbation families, report:

```text
total pairs
eligible pairs

primary directional numerator / denominator / rate
mean primary targeted drop
protected-dimension MAE

allowed-collateral mean signed drop
allowed-collateral mean absolute shift

repeatability
critical-flag diagnostics
operational failure count
```

The global PASS/FAIL decision must use the global thresholds in Section 22 plus the family-coverage constraint.

---

## 28. Prohibited Practices

After this protocol is frozen, the following are prohibited for the confirmatory v0.2 run:

- editing the 24 diagnostic pairs;
- changing the family coupling matrix;
- changing primary / collateral / protected assignments;
- modifying metric formulas;
- modifying thresholds;
- dropping inconvenient pairs;
- rerunning individual failures until success;
- using best-of-three;
- manually correcting Judge output;
- manually correcting evidence;
- changing the Judge model mid-run;
- changing the Judge Prompt;
- enabling retry;
- enabling self-repair;
- changing structured-output mode;
- tuning Evaluator v0.1 from observed v0.2 scores;
- overwriting the historical v0.1 run;
- retroactively using the v0.1 run as confirmatory evidence.

Any substantive methodological change requires a new protocol version, e.g. v0.3.

---

## 29. Freeze Policy

### 29.1 Draft stage

While:

```text
Status: Draft
```

the protocol may be reviewed for:

- internal consistency;
- theoretical justification;
- metric correctness;
- reproducibility;
- implementation feasibility.

No confirmatory v0.2 API run may begin.

### 29.2 Frozen stage

Once approved:

```text
Status: Frozen
Version: v0.2
```

the following become immutable for the next confirmatory run:

- family coupling matrix;
- primary / allowed-collateral / protected partitions;
- repeat aggregation rules;
- semantic eligibility rules;
- coverage rules;
- semantic metrics;
- repeatability definition;
- critical-flag majority rule;
- operational/semantic separation;
- acceptance thresholds.

Any substantive change requires Protocol v0.3.

---

## 30. Relationship to Diagnostic Protocol v0.1

Protocol v0.1 and Protocol v0.2 answer closely related but methodologically distinct questions.

### Protocol v0.1

Protocol v0.1 used the development dataset:

```text
cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl
```

and assumed:

```text
all non-target dimensions should remain stable
```

It therefore used:

```text
Off-target MAE
```

across all non-target dimensions.

Its historical result remains:

```text
FAIL
```

That result is not superseded.

### Protocol v0.2

Protocol v0.2 was designed after inspecting the v0.1 result and therefore treats the v0.1 dataset as development/retrospective material only.

It recognizes, before a new confirmatory run, that some rubric dimensions are theoretically coupled.

It therefore distinguishes:

```text
primary target
allowed collateral
protected dimensions
```

and evaluates semantic specificity using:

```text
Protected-Dimension MAE
```

Confirmatory evidence for Protocol v0.2 must come from a newly authored and frozen holdout dataset that was not used to design the v0.2 protocol.

Protocol v0.2 does not invalidate Protocol v0.1.

It is a documented methodological refinement whose confirmatory status depends on performance on the new holdout data.

## 31. Versioning and Disclosure

Any report, paper, internal note, or benchmark table using Protocol v0.2 should disclose:

1. Evaluator version;
2. Judge Prompt version and SHA-256;
3. Judge provider/model;
4. Development dataset version and SHA-256;
5. Confirmatory holdout dataset version and SHA-256;
6. Protocol version;
7. whether the run is confirmatory or retrospective;
8. semantic coverage;
9. operational success/failure counts;
10. all PASS/FAIL metrics;
11. the fact that Protocol v0.2 was developed after inspecting Protocol v0.1 results.

A concise methodological disclosure may state:

> Diagnostic Protocol v0.2 was introduced after analysis of the initial v0.1 diagnostic run showed that treating all non-target rubric dimensions as independent over-penalized theoretically coupled score changes. Protocol v0.2 was frozen before construction and evaluation of a new confirmatory holdout dataset and explicitly partitions dimensions into primary targets, allowed collateral effects, and protected dimensions. The original v0.1 FAIL result and development dataset are preserved and reported separately.

---

## 32. Protocol v0.2 Summary

The confirmatory protocol is:

```text
Frozen Evaluator:
TeachIntent Evaluator v0.1

Development Dataset:
Diagnostic Dataset v0.1
24 pairs
Retrospective / non-confirmatory only

Confirmatory Holdout Dataset:
Diagnostic Holdout Dataset v0.2
24 NEW pairs
8 families × 3
Authored and frozen after Protocol v0.2 freeze
No real Judge exposure before dataset freeze

Execution:
3 independent repeats per variant
24 × 2 × 3 = 144 calls

Primary sensitivity:
Primary Directional Accuracy >= 85%

Effect size:
Mean Primary Targeted Drop >= 1.0

Semantic specificity:
Protected-Dimension MAE <= 0.5

Stability:
Within-one-point Repeatability >= 95%

Coverage:
Semantic Pair Coverage >= 90%
Every family >= 2/3 eligible pairs

Critical flags:
Diagnostic-only

Operational reliability:
Reported separately

Historical v0.1 run:
Preserved as FAIL

Confirmatory evidence:
Must come from a new frozen v0.2 holdout dataset
evaluated only after Protocol v0.2 is Frozen
```

## 33. Current Status

```text
Status: Frozen
Version: v0.2
```

This protocol is frozen before construction and real-Judge evaluation of the confirmatory holdout dataset.

The next authorized methodological step is:

```text
1. Construct diagnostic_pairs_v0.2_holdout.jsonl
2. Mechanically validate all 24 pairs
3. Perform manual pair-level QC without real Judge exposure
4. Freeze the holdout dataset and record its SHA-256
5. Only then execute the new 144-call confirmatory run
```

No confirmatory v0.2 Judge call is authorized before the holdout dataset itself has been frozen.
