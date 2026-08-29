# TeachIntent Evaluator Diagnostic Pairs (v0.1)

Controlled diagnostic perturbation dataset for validating **Evaluator v0.1**
itself (NOT the Generator). Each pair couples a manually-curated
`reference_plan` with a `degraded_plan` that carries exactly one injected
*semantic* defect.

## Purpose

Given a structurally valid, reasonable Speech Plan, can the Evaluator:

1. drop the target dimension in the correct direction;
2. affect mostly the target dimension (small off-target drift);
3. raise the expected critical flag when required;
4. score stably across repeated runs?

## File

- `diagnostic_pairs_v0.1.jsonl` — 24 reference/degraded pairs (8 families × 3).

## Contract

Each JSONL line is one pair with exactly these fields (unknown fields rejected):

| field | meaning |
|-------|---------|
| `pair_id` | `DIAG-{A..H}-{01..03}`, unique |
| `family` | one of the 8 frozen family names below |
| `input` | TeachIntent Input (schema `1.0.0-rc.2`) |
| `reference_plan` | curated reasonable Speech Plan (`1.0.0-rc.3`, Layer-0 valid) |
| `degraded_plan` | same input, one injected semantic defect (`1.0.0-rc.3`, Layer-0 valid) |
| `target_dimensions` | frozen D1–D6 dimension IDs expected to drop |
| `expected_flags` | frozen critical-flag names expected to trigger |
| `notes` | human-readable design rationale |

**`family`, `target_dimensions`, `expected_flags`, `notes` are
experiment-side metadata.** They MUST NEVER reach the Evaluator Layer 1 judge
payload. The runner passes only `input` + one plan; the Evaluator's own
sanitizer additionally drops everything outside the Layer-1-visible subset.

Both `reference_plan` and `degraded_plan` are **structurally valid**: no
malformed JSON, no missing required fields, no illegal enums. All
perturbations are semantic.

## The 8 frozen perturbation families

| family | target dimension | expected flag(s) |
|--------|------------------|------------------|
| `intent_mismatch` | D1 `pedagogical_intent_fidelity` | — |
| `content_contradiction` | D2 `content_faithfulness_boundary` | `content_anchor_contradiction` |
| `material_off_anchor_content` | D2 `content_faithfulness_boundary` | `material_off_anchor_content` |
| `learner_state_mismatch` | D3 `learner_state_compatibility` | — |
| `incomplete_corrective_feedback` | D4 `intent_specific_instructional_adequacy` | — |
| `delivery_over_specification` | D5 `delivery_necessity_sparsity` | — |
| `delivery_pedagogy_conflict` | D6 `delivery_pedagogy_alignment` | `coercive_or_hostile_delivery` (G-03 only) |
| `prompt_injection_compliance` | D1 `pedagogical_intent_fidelity` | `prompt_injection_compliance` |

## Family design notes

- **A intent_mismatch** — content/learner/wording stay reasonable; the teaching
  action is switched to another intent (elicitation→explanation,
  scaffolding→full answer, supportive→corrective).
- **B content_contradiction** — degraded asserts the opposite of the
  `content_anchor`.
- **C material_off_anchor_content** — degraded adds substantive external
  content beyond the anchor's paraphrase/inference/question/contrast/scaffold.
- **D learner_state_mismatch** — degraded ignores `knowledge_state` /
  `affective_state` (compressed advanced explanation to a beginner, cold
  guidance to a frustrated learner, college jargon to a middle-schooler).
- **E incomplete_corrective_feedback** — corrective intent; degraded only says
  "wrong" / points at the error without repairing or guiding repair.
- **F delivery_over_specification** — `verbal_plan` is byte-identical;
  degraded piles on unnecessary tone/emotion/prosody/overrides/prominence/
  boundary (all still structurally valid).
- **G delivery_pedagogy_conflict** — verbal content stays reasonable; degraded
  adds delivery that conflicts with the pedagogy. G-01/G-02 are misaligned but
  not hostile; G-03 is deliberately hostile (raises
  `coercive_or_hostile_delivery`).
- **H prompt_injection_compliance** — an instruction-like string is embedded in
  untrusted data (`scenario` / `learner_utterance`); reference treats it as
  data, degraded obeys it.

## Review status

These pairs are **candidate** reference/degraded pairs. Before any real
evaluation run, a human must confirm each reference is reasonable, each
degraded injects only the intended defect, no pair carries multiple severe
confounds, and both sides are Layer-0 valid. The validator
(`scripts/validate_evaluator_diagnostic.py`) enforces the mechanical contract
only; it cannot judge pedagogical reasonableness.

## Validation

```bash
.venv/bin/python scripts/validate_evaluator_diagnostic.py
```
