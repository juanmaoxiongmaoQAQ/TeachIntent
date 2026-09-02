# TeachIntent Visual + Audio Demo Script (<=2 minutes)

Target duration: 115–120 seconds. The recording uses the offline visual demo
and existing release artifacts. No live Hy3 or Judge call is needed. If the
optional A/B WAV pair has not been rendered on a compatible GPU beforehand,
skip the two playback clicks and use the on-screen mapping/manifest explanation;
do not substitute fabricated audio.

## Preparation

```bash
python -m pip install -e ".[demo]"
python scripts/run_visual_demo.py
```

Open `http://127.0.0.1:7860`, select `corrective-feedback`, `v0.2`, and
`Offline artifact`. Keep the README results table open in a second tab. If real
Qwen audio was prepared, verify that both players load and that
`render_manifest.json` names the same text, speaker, model, language, and seed.

Never show `.env`, an API key, shell history, or a personal absolute path.

## Exact Screen Sequence and Narration

### 0–20 seconds — Problem

**Screen:** App title, mapping, and the line “Same words. Same voice. Different
pedagogical delivery.”

**Narration:**

> AI tutors need more than a plausible answer. They must realize a selected
> teaching intent, stay faithful to the lesson, fit the learner, and control
> delivery only when useful. TeachIntent uses Hy3 to map content, context,
> learner state, and intent into a structured verbal and delivery plan.

### 20–45 seconds — Input

**Screen:** Corrective-feedback context and intent. Briefly point to the
learner's gambler's fallacy and embedded instruction.

**Narration:**

> This difficult case supplies the probability anchor, an impatient learner,
> and an embedded request to mark a misconception correct. The tutor policy has
> already chosen corrective feedback; the model must perform that move without
> obeying the learner's injected instruction.

### 45–73 seconds — Hy3 Speech Plan

**Screen:** Side-by-side “What to say” and “How to say it”; briefly expand raw
JSON, then close it.

**Narration:**

> Hy3 names the gambler's fallacy and repairs it using independence and one
> half. The verbal plan is directly sayable. The delivery plan adds just one
> justified control: firm but supportive. The result passes the frozen JSON
> Schema and Pydantic contract.

### 73–95 seconds — Six-dimensional evaluator

**Screen:** D1–D6 table and recorded-evidence note.

**Narration:**

> Evaluator v0.1 scores intent, content faithfulness, learner fit,
> instructional adequacy, delivery sparsity, and delivery alignment. This table
> is the matching recorded release artifact—there is no live Judge call. The
> evaluator's frozen holdout validation reached 95.83 percent directional
> accuracy and 99.62 percent within-one repeatability.

### 95–108 seconds — Optional audio A/B

**Screen:** Play neutral, then planned audio; show the collapsed mapping report
or manifest after playback.

**Narration:**

> The optional Qwen3-TTS adapter holds the words, voice, model, language, and
> seed constant. Neutral uses an empty instruction; planned uses only the
> supported delivery-plan mapping. Unsupported controls are reported rather
> than converted into invented acoustic values.

**No-audio narration alternative:**

> Audio is optional and no model weights are bundled here. The visible mapping
> and manifest contract define the controlled A/B, but this recording does not
> claim audio evidence without real generated WAV files.

### 108–120 seconds — v0.1 to v0.2 conclusion

**Screen:** README main findings, then return to the personal-project disclaimer.

**Narration:**

> v0.1 often over-controlled delivery; rc.1 collapsed to all-empty plans and
> was rejected. Frozen v0.2 uses minimum justified control. Development and a
> twelve-case release sanity check support the change without claiming formal
> held-out superiority. TeachIntent is a personal open-practice project, not an
> official Tencent release.

## Export Checklist

- Final media duration is at most 2:00.
- Chinese text is readable at the submitted resolution.
- Audio, if played, is real output accompanied by its manifest.
- No credential, personal path, or private provider response is visible.
- The personal-project disclaimer appears before the recording ends.
