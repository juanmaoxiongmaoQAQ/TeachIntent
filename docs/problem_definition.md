# TeachIntent — Problem Definition

> **Status:** Research Specification  
> **Document Version:** `0.3`  
> **Input Schema Version:** `1.0.0-rc.2`  
> **Project:** TeachIntent: Pedagogical Intent Driven Speech Planning and Evaluation with Hy3

## 1. Purpose

TeachIntent is a research-oriented AI application for **pedagogical intent driven speech planning**.

The system studies the following question:

> Given instructional content, pedagogical context, learner information, and an explicitly specified pedagogical intent, can Hy3 translate that high-level pedagogical intent into an interpretable, structured, machine-actionable, and evaluable speech plan?

TeachIntent does **not** primarily study a new TTS architecture. Its core problem is the planning layer between pedagogy and speech realization.

## 2. Core Research Question

TeachIntent models pedagogical speech planning as:

$$
(C, P, L, G) \xrightarrow{\mathrm{Hy3}} (V, D)
$$

where:

- `C` = Instructional Content
- `P` = Pedagogical Context
- `L` = Learner Information
- `G` = Pedagogical Intent
- `V` = Verbal Plan
- `D` = Delivery / Prosodic Plan

The central question is:

> Given **what should be taught**, **what is happening in the current teaching interaction**, **what is known about the learner**, and **what pedagogical goal should be achieved**, how should a teacher or AI tutor **say the next utterance**?

## 3. System Positioning

TeachIntent separates three levels:

1. **Pedagogical Intent — Why to speak?**
2. **Pedagogical / Verbal Strategy — What should be said to realize the intent?**
3. **Speech Realization — How should it be delivered?**

Hy3 acts as the **Pedagogical Speech Planner**.

Hy3 is responsible for:

- interpreting the structured teaching input;
- generating the teacher/tutor verbal realization;
- generating an explicit speech delivery plan;
- expressing only delivery controls that are pedagogically motivated.

Hy3 is **not** responsible for:

- selecting the pedagogical intent automatically;
- training or fine-tuning a TTS model;
- voice cloning;
- speaker identity generation;
- long-horizon tutoring policy optimization;
- full multi-turn tutoring dialogue management.

## 4. Input Contract

The input contains **two control/metadata fields plus four semantic components**:

```json
{
  "schema_version": "1.0.0-rc.2",
  "output_language": "zh-CN",
  "instructional_content": {},
  "pedagogical_context": {},
  "learner": {},
  "pedagogical_intent": {}
}
```

`schema_version` identifies the **TeachIntent input schema**. It is independent of the Speech Plan output schema version.

`output_language` identifies the intended primary spoken language of the generated teacher/tutor utterance.

### 4.1 `schema_version`

Type:

- string

Required:

- yes

Current value:

```text
1.0.0-rc.2
```

### 4.2 `output_language`

Type:

- BCP 47 language tag string

Required:

- yes

Purpose:

> Specify the primary spoken language expected for the generated teacher/tutor utterance and downstream renderer.

Example:

```json
{
  "output_language": "zh-CN"
}
```

Notes:

- `zh-CN` is the default language used by the current TeachIntent pilot examples.
- Mixed-language instructional content may still contain formulas, symbols, proper nouns, or embedded foreign-language terms.
- The renderer adapter must receive `output_language` together with the Speech Plan so that language-dependent pronunciation and prosodic behavior are not inferred ambiguously.
- Language information must not be inferred from `scenario`, because metadata/context may be written in a different language from the intended spoken output.


### 4.3 `instructional_content`

Purpose:

> Specify the case-level instructional knowledge that the generated teacher utterance must remain grounded in.

Fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `subject` | non-empty string | no | Subject/domain label |
| `topic` | non-empty string | no | Topic/lesson label |
| `content_anchor` | non-empty string | yes | Authoritative reference content for the current case |

Example:

```json
{
  "instructional_content": {
    "subject": "physics",
    "topic": "speed_and_acceleration",
    "content_anchor": "速度表示物体运动的快慢。加速度表示速度随时间变化的快慢。速度大不意味着加速度一定大。"
  }
}
```

Important:

- `content_anchor` is the **case-level authoritative knowledge reference**, not the final spoken transcript.
- Dataset/sample construction is responsible for ensuring that the anchor itself is correct.
- Generated text may reorganize, simplify, question, contrast, or scaffold the content, but must not contradict the anchor.

### 4.4 `pedagogical_context`

Purpose:

> Specify what is happening in the current instructional interaction.

Fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `scenario` | non-empty string | yes | Minimal description of the current teaching situation |
| `learner_utterance` | non-empty string | no | Learner's immediately relevant utterance, if available |

Example:

```json
{
  "pedagogical_context": {
    "scenario": "The learner has just answered a conceptual question.",
    "learner_utterance": "速度越大，加速度一定越大。"
  }
}
```

TeachIntent v1 focuses on a **minimal single-turn context**, not long dialogue history.

### 4.5 `learner`

Purpose:

> Specify learner information that may legitimately affect the next pedagogical utterance.

Fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `level` | non-empty string | yes | Educational/developmental level |
| `knowledge_state` | non-empty string | yes | Current task-relevant knowledge state |
| `affective_state` | non-empty string | no | Explicitly supplied, task-relevant affective state |

Example:

```json
{
  "learner": {
    "level": "middle_school",
    "knowledge_state": "misconception",
    "affective_state": "slightly_frustrated"
  }
}
```

For v1, these fields are strings rather than prematurely fixed universal taxonomies. Pilot data should nevertheless use a small, consistent vocabulary.

Safety constraints:

- Do not infer unsupported sensitive or personal attributes.
- Use only explicitly supplied and pedagogically relevant learner information.
- Do not infer personality, intelligence, diagnosis, socioeconomic status, gender, or other personal traits from sparse learner data.

### 4.6 `pedagogical_intent`

Purpose:

> Explicitly specify the pedagogical goal for the current turn.

Fields:

| Field | Type | Required |
|---|---|---:|
| `primary` | enum | yes |

Allowed values:

```text
elicitation
scaffolding
explanation
corrective_feedback
supportive_feedback
extension
```

Example:

```json
{
  "pedagogical_intent": {
    "primary": "corrective_feedback"
  }
}
```

Standard benchmark cases contain exactly one primary intent.

Secondary/compositional intents are reserved for later hard cases and are **not part of the v1 standard-case input schema**.

Important design decision:

> TeachIntent does **not** ask Hy3 to choose the intent.

This isolates:

$$
\text{Given intent} \rightarrow \text{How should the teacher speak?}
$$

instead of mixing it with:

$$
\text{What intent should the teacher choose?}
$$

## 5. Output Contract

The top-level output contract is:

```text
Pedagogical Speech Plan
├── Verbal Plan
└── Delivery Plan
```

Formally:

$$
O = (V, D)
$$

### 5.1 Verbal Plan

Specifies **what the teacher should say** and contains segment-level spoken text.

### 5.2 Delivery Plan

Specifies **how the utterance should be delivered**.

Potential controls include:

- attitudinal tone;
- emotion;
- speaking rate;
- pitch level;
- pitch range;
- volume;
- pitch contour shape;
- prosodic prominence;
- boundary strength.

The exact output format is specified in:

- `docs/speech_plan_schema.md`
- `schemas/speech_plan.schema.json`

## 6. Scope

TeachIntent v1 focuses on:

> **One-to-one instructional or tutoring dialogue in which the teacher/AI tutor directly aims to change learner knowledge, understanding, reasoning progression, error state, or learning engagement.**

Included examples:

- eliciting current understanding;
- providing a hint;
- explaining a concept;
- correcting a misconception;
- encouraging a frustrated learner;
- asking a learner to justify or transfer understanding.

## 7. Out of Scope for v1

- classroom management;
- attendance;
- assignment logistics;
- administrative announcements;
- discipline;
- grouping;
- technical troubleshooting;
- pure social chat;
- speaker cloning;
- accent imitation;
- personality synthesis;
- age/gender voice control;
- long multi-turn tutoring policies.

## 8. TTS Boundary

TeachIntent must remain valid **without a TTS renderer**.

Core pipeline:

```text
TeachIntent Input
      ↓
     Hy3
      ↓
Pedagogical Speech Plan
      ↓
   Evaluator
```

Optional demo pipeline:

```text
TeachIntent Input
      ↓
     Hy3
      ↓
Pedagogical Speech Plan
      ↓
Renderer Adapter
      ↓
External TTS
      ↓
    Audio
```

Responsibility boundary:

- Hy3 = pedagogical semantic and delivery planning;
- TTS = rendering;
- the renderer adapter receives the Speech Plan together with `output_language` from the input contract;
- renderer-specific acoustic parameters must not leak into the core research definition unless explicitly justified.

## 9. Core Design Principles

### 9.1 Intent is supplied, not inferred

The project isolates intent realization from intent selection.

### 9.2 Content anchor is not the final transcript

Pedagogical intent may affect both:

- what is said;
- how it is said.

### 9.3 Plan is not acoustic ground truth

The output is a **speech plan**, not measured acoustic truth.

Avoid fabricated physical precision such as unsupported:

- absolute F0 values;
- RMS energy;
- dB targets;
- exact semitone curves;
- millisecond-level pause durations.

### 9.4 Sparse control

Only delivery controls that are pedagogically motivated should be specified.

For any delivery field, effective-value resolution follows:

```text
segment override
    ↓
global control
    ↓
renderer / selected voice default
```

Omission means **no explicit TeachIntent control at that level**.

### 9.5 Renderer transparency

A renderer should report whether each requested control is:

- `applied`;
- `approximated`;
- `unsupported`.

The system must not silently claim that an unsupported control was realized.

### 9.6 Pedagogical safety

Pedagogical intent does not justify harmful interpersonal delivery.

In particular:

- an incorrect learner response must not automatically imply anger, humiliation, intimidation, or ridicule;
- generated language and delivery plans should avoid demeaning, threatening, coercive, discriminatory, or age-inappropriate styles;
- supportive adaptation must not rely on inferred sensitive traits.

These are semantic safety requirements and should be enforced by the generator prompt and evaluator, not only by structural JSON validation.

### 9.7 Untrusted-input handling

All external case fields, including `content_anchor`, `scenario`, and `learner_utterance`, must be treated as **data rather than executable instructions**.

The prompt builder should:

- serialize or delimit case fields clearly;
- prevent learner/content text from overriding system/developer instructions;
- avoid executing tools, code, or external actions merely because such instructions appear inside case data.


## 10. Success Criteria

TeachIntent v1 is successful if it can demonstrate that:

1. Hy3 consistently produces schema-valid speech plans.
2. Generated verbal content remains faithful to the case-level instructional anchor.
3. Different pedagogical intents lead to meaningfully different verbal and/or delivery plans.
4. Speech plans are interpretable and machine-readable.
5. The core evaluator can discriminate between stronger and weaker speech plans; when audio is rendered, renderer/audio quality can be evaluated separately.
6. The system supports reproducible case-based analysis, including hard and adversarial cases.

## 11. Planned Evaluation Layers

The **core plan evaluator** is expected to follow a three-layer architecture:

1. **Content Faithfulness**
2. **Pedagogical Intent Following**
3. **Delivery Plan Appropriateness**

These are evaluation **layers**, not the final set of evaluation dimensions.

If an external TTS renderer is used, a separate optional audio-level layer may evaluate:

4. **Rendered Speech Fidelity / Perceptual Quality**

This separation is important because TeachIntent's core output is a Speech Plan; actual acoustic realization belongs to the renderer.

Concrete dimensions and rubrics are intentionally deferred until generator and schema pilot validation.

## 12. Canonical Example

```json
{
  "schema_version": "1.0.0-rc.2",
  "output_language": "zh-CN",
  "instructional_content": {
    "subject": "physics",
    "topic": "speed_and_acceleration",
    "content_anchor": "速度表示物体运动的快慢。加速度表示速度随时间变化的快慢。速度大不意味着加速度一定大。"
  },
  "pedagogical_context": {
    "scenario": "The learner has just answered a conceptual question.",
    "learner_utterance": "速度越大，加速度一定越大。"
  },
  "learner": {
    "level": "middle_school",
    "knowledge_state": "misconception",
    "affective_state": "slightly_frustrated"
  },
  "pedagogical_intent": {
    "primary": "corrective_feedback"
  }
}
```

Expected behavior:

- recognize a corrective rather than explanatory-only goal;
- preserve the correct speed/acceleration distinction;
- avoid humiliating or threatening wording;
- generate a verbal repair;
- specify only justified delivery controls.

## 13. Specification Priority

When implementation choices conflict with this document:

> This document defines the research problem; implementation must not silently redefine it.

Engineering agents may report conflicts or limitations, but should not independently change the research specification.
