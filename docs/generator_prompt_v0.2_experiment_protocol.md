# Generator / Prompt v0.2 Experiment Protocol

**Status:** Draft (QC-reviewed)  
**Target comparison:** Prompt v0.1 vs Prompt v0.2  
**Generator implementation:** unchanged  
**Evaluator:** Evaluator v0.1

---

## 1. Objective

This protocol defines how Prompt v0.2 will be developed and evaluated.

The primary research question is:

> Can Prompt v0.2 reduce unnecessary delivery controls while preserving or improving pedagogical adequacy and maintaining the strong capabilities already demonstrated by Prompt v0.1?

The comparison should isolate the prompt revision as the main experimental variable.

---

## 2. Experimental Variable

The generator implementation remains unchanged.

The principal comparison is:

```text
Prompt v0.1
vs.
Prompt v0.2
```

Held constant:

- generator model,
- generator code,
- input schema,
- Speech Plan schema,
- decoding temperature,
- parser,
- validation stack,
- Evaluator v0.1,
- Judge Prompt v0.1,
- Judge model.

---

## 3. Existing 30-Case Pilot Set

The existing 30 Pilot cases are now treated as a **development set**.

They may be used for:

- diagnosing Prompt v0.1 weaknesses,
- developing Prompt v0.2,
- checking regressions,
- comparing Prompt v0.2 release candidates.

They must not later be described as an unseen held-out test set.

---

## 4. Development Procedure

Prompt development should remain limited and evidence-driven. Normally, one or two revision rounds are expected:

```text
Prompt v0.2-rc.1
→ development evaluation
→ optional evidence-driven revision
→ Prompt v0.2-rc.2
→ freeze as Prompt v0.2
```

If rc.1 already behaves as intended, it may be frozen directly as Prompt v0.2. If a clearly identified implementation defect remains after rc.2, a narrowly scoped additional correction is allowed, but repeated score-chasing iterations should be avoided.

The goal is not to maximize scores on all 30 development cases.

---

## 5. Development Evaluation Focus

On the 30-case development set, compare Prompt v0.1 and the Prompt v0.2 candidate with particular attention to:

### Primary target

- D5 Delivery Necessity / Sparsity

### Secondary target

- D4 Intent-Specific Instructional Adequacy

### Protected dimensions

- D1 Pedagogical Intent Fidelity
- D2 Content Faithfulness / Boundary
- D3 Learner-State Compatibility
- D6 Delivery–Pedagogy Alignment

### Priority slices

- scaffolding D5
- supportive_feedback D5
- explanation D4
- explanation D5
- hard/adversarial Block C

### Regression checks

- elicitation should not be degraded,
- no increase in critical flags,
- no new content-boundary failures,
- no systematic intent drift.

---

## 6. Prompt v0.2 Freeze

After the development stage:

1. select rc.1 or rc.2,
2. assign final `prompt_version = v0.2`,
3. freeze the exact Prompt v0.2 text,
4. compute and record its SHA256,
5. do not modify Prompt v0.2 after the held-out dataset is exposed to it.

Only after Prompt v0.2 is frozen should the confirmatory held-out dataset be finalized.

---

## 7. New Held-Out Dataset

Create a new balanced dataset with **36 cases**:

```text
6 pedagogical intents × 6 cases = 36
```

Three blocks:

| Block | Cases | Purpose |
|---|---:|---|
| H-A Standard | 12 | ordinary pedagogical situations |
| H-B Cross-domain | 12 | transfer across subjects and domains |
| H-C Hard / Adversarial | 12 | ambiguous, conflicting, difficult, or misleading contexts |

For each intent:

```text
2 Standard
2 Cross-domain
2 Hard / Adversarial
= 6 cases
```

This yields a balanced 6-intent × 3-block structure.

---

## 8. Held-Out Dataset Construction Rules

The held-out cases should:

- be newly authored,
- not copy existing Pilot cases,
- cover diverse subjects and learner states,
- preserve the same input contract,
- include realistic pedagogical ambiguity,
- contain sufficient hard cases to test intent discipline,
- avoid being written specifically to favor Prompt v0.2 wording.

The dataset should undergo human QC before use.

After QC:

- freeze the exact dataset,
- compute dataset SHA256,
- record a freeze record,
- do not edit after formal generation begins.

---

## 9. Formal Generation

For each of the 36 held-out inputs, generate two plans:

```text
Prompt v0.1 → output A
Prompt v0.2 → output B
```

Total:

```text
36 inputs × 2 prompt versions
= 72 generated plans
```

Generation conditions must be otherwise identical.

---

## 10. Evaluation

Each generated plan is evaluated with the frozen Evaluator v0.1.

Per plan:

```text
3 semantic Judge repeats
```

Use the existing frozen valid-artifact acquisition policy:

```text
max 3 physical attempts per semantic repeat
```

Therefore:

```text
72 plans × 3 semantic repeats
= 216 planned semantic Judge evaluations
```

Physical attempt count may exceed 216 because of operational retries.

---

## 11. Plan Eligibility

A generated plan is evaluation-eligible if:

```text
successful semantic Judge repeats >= 2 / 3
```

Failed physical attempts do not contribute score zero.

Only valid semantic artifacts enter aggregation.

---

## 12. Pair Eligibility

The formal comparison unit is the held-out input case.

A case is pair-eligible only when both:

```text
Prompt v0.1 output
and
Prompt v0.2 output
```

are individually evaluation-eligible.

Only pair-eligible cases enter paired comparison metrics.

---

## 13. Primary Endpoint

Primary endpoint:

```text
ΔD5 = D5(v0.2) - D5(v0.1)
```

Primary objective:

> D5 should show a clear positive paired improvement.

Interpretation should be based on the observed effect size, confidence interval, and improved/tied/worsened case distribution rather than a preselected numeric cutoff.

---

## 14. Secondary Endpoint

Secondary endpoint:

```text
ΔD4 = D4(v0.2) - D4(v0.1)
```

Secondary objective:

> D4 should improve or remain stable.

A small neutral change is acceptable if D5 improves clearly and protected dimensions remain stable.

---

## 15. Protected Dimensions

For:

- D1
- D2
- D3
- D6

compute:

```text
ΔDk = Dk(v0.2) - Dk(v0.1)
```

Protection objective:

> D1, D2, D3, and D6 should show no meaningful systematic degradation.

The purpose is to prevent an apparent D5/D4 improvement that sacrifices already strong capabilities. Report the actual paired deltas and inspect any notable regressions rather than enforcing an arbitrary fixed cutoff.

---

## 16. Critical Flags

Compare case-level critical flags between v0.1 and v0.2.

Prompt v0.2 should not increase the total number of case-level critical flags.

Particular attention should be paid to:

- material_off_anchor_content
- content_anchor_contradiction
- prompt_injection_compliance
- coercive_or_hostile_delivery

---

## 17. Coverage

Pair coverage must be reported explicitly.

The preferred outcome is high coverage across the full 36-case held-out set and balanced coverage across all six intents. If coverage is incomplete, the final interpretation must clearly state the number of pair-eligible cases overall and per intent.

Per-intent results with sparse coverage should be treated as descriptive rather than definitive.

---

## 18. Severe Regression Check

Define a protected-dimension severe regression as:

```text
any protected dimension decreases by >= 1.0 point
```

Report:

```text
severe_regression_case_count
```

All severe regressions should receive manual case-level review.

The count is a diagnostic safeguard rather than a hard pass/fail threshold.

---

## 19. Statistical Reporting

For each paired dimension delta, report:

- number of pair-eligible cases,
- mean delta,
- median delta,
- standard deviation,
- improved / tied / worsened counts,
- 95% bootstrap confidence interval.

For the main endpoints, additionally report:

- Wilcoxon signed-rank test,
- matched rank-biserial correlation.

Effect magnitude and direction should remain primary; p-values are supplementary.

---

## 20. Per-Intent and Per-Block Analysis

Report D1–D6 and overall metrics for:

### Six intents

- elicitation
- scaffolding
- explanation
- corrective_feedback
- supportive_feedback
- extension

### Three held-out blocks

- Standard
- Cross-domain
- Hard / Adversarial

These analyses are diagnostic and help identify where Prompt v0.2 improves or regresses.

---

## 21. Overall Score

Overall score may be reported as a descriptive summary but is not the primary optimization target.

Prompt v0.2 should not be selected solely because overall score increases.

The central interpretation should prioritize:

```text
D5 improvement
D4 improvement
protection of D1/D2/D3/D6
```

---

## 22. Development Ablation

Optional ablation may be conducted on the 30-case development set:

```text
A0 = Prompt v0.1

A1 = v0.1
     + Delivery Necessity Gate

A2 = A1
     + Intent-Specific Minimum Adequacy

A3 = A2
     + Hard / Adversarial Intent Discipline
     = full Prompt v0.2
```

Ablation is optional and should not delay the main Prompt v0.2 experiment.

The held-out 36-case dataset should not be repeatedly reused for prompt ablation.

---

## 23. Decision Logic

Prompt v0.2 should be considered successful when the held-out paired evaluation supports the intended behavioral change:

```text
Primary:
D5 shows a clear positive paired improvement.

Secondary:
D4 improves or remains stable.

Protected:
D1, D2, D3, and D6 show no meaningful systematic degradation.

Coverage:
Pair eligibility is high enough to support the overall interpretation,
with balanced representation across the six intents.

Critical flags:
No concerning increase attributable to Prompt v0.2.

Severe regressions:
Any notable protected-dimension regressions are few, localized, and explainable on case review.
```

The final conclusion should be based on the full pattern of paired effects, confidence intervals, coverage, and case-level diagnostics rather than a single hard threshold.

---

## 24. Experimental Sequence

```text
Generator / Prompt v0.1
        ↓
30-case development baseline
        ↓
Prompt v0.2 Design Spec
        ↓
Prompt v0.2-rc.1
        ↓
30-case development evaluation
        ↓
optional one-time rc.2 revision
        ↓
Prompt v0.2 Frozen
        ↓
new 36-case held-out dataset
        ↓
dataset human QC + freeze
        ↓
paired generation:
v0.1 vs v0.2
        ↓
Evaluator v0.1
        ↓
paired D1–D6 comparison
        ↓
final conclusion
```

---

## 25. Status

This document is a **QC-reviewed Draft**.

The protocol may now be used for Prompt v0.2-rc.1 development. Freeze the final experiment protocol before the held-out confirmatory stage begins.
