# TeachIntent Demo Script (<=2 minutes)

This storyboard uses only the committed offline demo artifacts. It is safe to
record without an API key or network connection. Target duration: 115–120
seconds.

## Preparation

Open two windows:

1. README at the mapping and architecture sections.
2. A terminal in the repository with the environment installed.

Use a readable terminal font and pre-run this once to confirm layout:

```bash
python scripts/run_demo.py \
  --example corrective-feedback \
  --prompt-version v0.2
```

## Exact Screen Sequence and Narration

### 0–20 seconds — Problem

**Screen:** README title, user scenario, and `(C, P, L, G) -> (V, D)` mapping.

**Narration:**

> AI tutors need more than a plausible answer. They must realize a selected
> teaching intent, stay within the instructional content, adapt to the learner,
> and control delivery only when useful. TeachIntent uses Hy3 to turn content,
> context, learner state, and intent into a structured Speech Plan.

### 20–45 seconds — Input

**Screen:** Run the command below and hold on `[Input context]` and
`[Pedagogical intent]`.

```bash
python scripts/run_demo.py \
  --example corrective-feedback \
  --prompt-version v0.2
```

**Narration:**

> This hard case gives Hy3 the probability content, an impatient learner with
> the gambler's fallacy, and an embedded instruction asking the tutor to mark
> the error correct. The requested intent is corrective feedback. Difficulty
> labels and expected behavior are never shown to the model.

### 45–75 seconds — Hy3 Speech Plan

**Screen:** Scroll to `[Generated Speech Plan]`, then highlight `verbal_plan`
and `delivery_plan`.

**Narration:**

> Hy3 resists the embedded instruction, identifies the misconception, and
> repairs it with independence and probability one half. The verbal plan says
> what the tutor should say. The delivery plan adds only one justified control:
> a firm but supportive tone. Both parts pass JSON Schema and Pydantic checks.

### 75–105 seconds — Evaluator

**Screen:** Open `docs/EVALUATION_METHOD.md`, showing the six-dimension table,
then `docs/RESULTS.md`, showing evaluator validation.

**Narration:**

> The automatic evaluator scores six operational dimensions: intent,
> faithfulness, learner fit, instructional adequacy, delivery sparsity, and
> delivery alignment, with grounded evidence and critical flags. On 24 frozen
> holdout reference/degraded pairs it achieved 95.83 percent directional
> accuracy and 99.62 percent within-one repeatability.

### 105–120 seconds — v0.1 vs v0.2 and Conclusion

**Screen:** In `docs/RESULTS.md`, show the Prompt v0.2 development-history table
and the release-sanity table.

**Narration:**

> Prompt v0.1 often over-controlled delivery. rc.1 over-corrected to thirty out
> of thirty empty plans and was rejected. Frozen v0.2 uses minimum justified
> control: development D5 improved by 0.51 without systematic protected-
> dimension regression. The final twelve-case sanity check is supportive, not
> formal confirmation. TeachIntent is a complete open-source planning and
> evaluation application, not a TTS system.

## Recording Checklist

- Keep the final exported video or GIF at or below two minutes.
- Do not show `.env`, API keys, shell history containing credentials, or local
  absolute paths.
- Use the recorded demo mode; do not risk provider latency during recording.
- Verify that Chinese text is legible at the final video resolution.
- End on the personal-project disclaimer or README title.
