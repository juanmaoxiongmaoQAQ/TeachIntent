# TeachIntent — Speech Plan Schema

> **Status:** Release Candidate Specification  
> **Schema Version:** `1.0.0-rc.3`  
> **Scope:** Hy3-generated pedagogical speech planning output

## 1. Purpose

The TeachIntent Speech Plan is a machine-readable representation of:

> what the teacher should say and how that utterance should be delivered to realize a specified pedagogical intent.

It is a **planning representation**, not an acoustic ground-truth representation.

The schema is designed to be:

- interpretable;
- sparse;
- machine-validatable;
- renderer-agnostic;
- compatible with real TTS systems through adapters;
- conservative about unsupported acoustic precision.

## 2. Core Structure

```text
PedagogicalSpeechPlan
├── schema_version
├── verbal_plan
│   └── segments[]
│       ├── segment_id
│       └── text
└── delivery_plan
    ├── global
    │   ├── attitudinal_tone
    │   ├── emotion
    │   └── prosody
    │       ├── speaking_rate
    │       ├── pitch_level
    │       ├── pitch_range
    │       └── volume
    └── segment_overrides[]
        ├── segment_id
        ├── attitudinal_tone
        ├── emotion
        ├── prosody
        ├── contour_shape
        ├── prominence_targets[]
        └── boundary_after
```

## 3. Design Principles

### 3.1 Sparse Control

Normative principle:

> **Do not specify a control unless it is pedagogically motivated.**

The planner must not mechanically fill every field with neutral/default values.

Bad pattern:

```json
{
  "speaking_rate": "medium",
  "pitch_level": "medium",
  "pitch_range": "medium",
  "volume": "medium",
  "emotion": "neutral"
}
```

Preferred pattern:

```json
{
  "prosody": {
    "speaking_rate": "slow"
  }
}
```

when only slower speech is pedagogically justified.

### 3.2 Function and Acoustic Realization Are Distinct

The schema represents communicative and prosodic control at an interpretable level.

It does not assume one-to-one mappings such as:

```text
prominence = higher F0
emotion = energy RMS
supportive = fixed pitch range
```

A renderer may realize one functional target through multiple acoustic cues.

### 3.3 Relative Control Before Absolute Control

The core planner should use categorical or speaker-relative controls.

The planner must not fabricate unsupported values such as:

- absolute F0 in Hz;
- energy RMS;
- exact dB targets;
- exact numerical semitone trajectories;
- exact millisecond pauses.

Renderer-specific numeric parameters belong in the adapter layer.

### 3.4 Global + Segment-Level Control

The schema supports:

- an optional global delivery baseline;
- sparse segment-level overrides.

### 3.5 Language Is Explicit Input Context

Speech realization is language-dependent. The Speech Plan itself does not duplicate language metadata; instead, the renderer must receive the plan together with the input field:

```text
output_language
```

This avoids ambiguous language inference and prevents duplicated language fields from drifting out of sync.

### 3.6 Open Style Descriptors Are Renderer Hints

`attitudinal_tone` and `emotion` are optional free-form style hints rather than universal categorical taxonomies.

Therefore:

- validators enforce their type/format, not psychological truth;
- exact string equality should **not** be used as a correctness criterion;
- renderer adapters may report them as `applied`, `approximated`, or `unsupported`.

## 4. Top-Level Fields

### 4.1 `schema_version`

Example:

```json
"schema_version": "1.0.0-rc.3"
```

Type:

- string

Required:

- yes

Release policy:

- development / pilot stage: `1.0.0-rc.x`
- stable first release: `1.0.0`
- backward-compatible feature additions after stable release: minor version
- backward-compatible fixes/clarifications: patch version
- breaking structural change: major version

### 4.2 `verbal_plan`

Required:

- yes

Purpose:

> Specify the actual teacher/tutor verbal realization.

### 4.3 `delivery_plan`

Required:

- yes

Purpose:

> Specify pedagogically motivated delivery controls.

Important sparse-control rule:

> `delivery_plan` itself MAY be `{}`.

An empty top-level `delivery_plan` means:

> Hy3 judged that no explicit delivery override was sufficiently motivated, so rendering should use the selected renderer/voice defaults.

This is the **only intentionally permitted empty control object**.

Within a non-empty `delivery_plan`:

- `global` is optional;
- `segment_overrides` is optional;
- at least one of them must be present.

If `global` is present, it must contain at least one control.

If `segment_overrides` is present, it must contain at least one override.

## 5. Verbal Plan

### 5.1 `verbal_plan.segments`

Type:

- array

Required:

- yes

Constraint:

- at least one segment

Segmentation principle:

> Segment by semantically coherent phrase/clause units that can reasonably receive an independent delivery plan.

Do not segment every word.

Word/phrase-level local salience is handled through `prominence_targets`.

### 5.2 `segment_id`

Example:

```json
"segment_id": "seg_01"
```

Type:

- string

Required:

- yes

Constraints:

- unique within a Speech Plan;
- referenced by `segment_overrides`.

Required pattern:

```text
^seg_[0-9]{2,}$
```

### 5.3 `text`

Example:

```json
"text": "这里有一个关键点需要纠正。"
```

Type:

- non-empty string

Required:

- yes

Constraints:

- must contain non-whitespace content.

The segment array order is canonical.

Each segment should include any punctuation/spacing needed for its own linguistic form; the core schema does not invent additional words or punctuation when rendering.

There is intentionally no duplicate top-level `spoken_text` field, avoiding synchronization errors.

## 6. Delivery Plan — Global Controls

`global` defines an optional utterance-level baseline.

If `global` is present, it must contain at least one of:

- `attitudinal_tone`
- `emotion`
- `prosody`

### 6.1 `attitudinal_tone`

Example:

```json
"attitudinal_tone": "reassuring"
```

or:

```json
"attitudinal_tone": "firm but supportive"
```

Type:

- trimmed, single-line string

Required:

- no

Constraints:

- 1–64 Unicode characters after trimming;
- must contain non-whitespace content;
- must not contain line breaks.

Meaning:

> the speaker's interpersonal/pragmatic stance toward the learner.

Examples:

- `reassuring`
- `supportive`
- `patient`
- `inviting`
- `firm`
- `serious`
- `firm but supportive`

Important:

- this is an open operational descriptor, not a universal tone taxonomy;
- do not use quality labels such as `clear` or `fluent`;
- do not merely repeat the pedagogical-intent label;
- the name `attitudinal_tone` avoids confusion with lexical tone in tonal languages.

### 6.2 `emotion`

Example:

```json
"emotion": "calm"
```

Type:

- trimmed, single-line string

Required:

- no

Constraints:

- 1–64 Unicode characters after trimming;
- must contain non-whitespace content;
- must not contain line breaks.

Meaning:

> an affective state expressed by the planned teacher voice.

Examples:

- `calm`
- `pleased`
- `concerned`
- `relieved`

Important:

- no mandatory fixed emotion taxonomy is assumed in v1;
- no unsupported numerical emotion intensity should be generated;
- omit the field if no meaningful emotional control is needed;
- do not use pragmatic-stance labels such as `encouraging` here when they are better represented by `attitudinal_tone`.

### 6.3 `prosody`

Type:

- object

Required:

- no

Constraint:

- if present, it must contain at least one valid control field.

Allowed fields:

- `speaking_rate`
- `pitch_level`
- `pitch_range`
- `volume`

Unknown fields are forbidden.

## 7. Prosody Fields

TeachIntent uses a **categorical subset** of SSML-style controls. It intentionally omits precise numerical values.

### 7.1 Global `speaking_rate`

Meaning:

> relative speaking rate with respect to the selected voice/renderer baseline.

Allowed global values:

```text
x-slow
slow
medium
fast
x-fast
```

Required:

- no

### 7.2 Global `pitch_level`

Meaning:

> overall perceived pitch level relative to the selected voice baseline.

Allowed global values:

```text
x-low
low
medium
high
x-high
```

Required:

- no

Important:

- this is not absolute F0;
- no Hz value should be generated by Hy3.

### 7.3 Global `pitch_range`

Meaning:

> overall degree of pitch variability/dynamic pitch range.

Allowed global values:

```text
x-low
low
medium
high
x-high
```

Required:

- no

Distinction:

```text
pitch_level = overall high/low baseline
pitch_range = amount of pitch variation
```

### 7.4 Global `volume`

Meaning:

> perceived loudness level relative to the selected voice baseline.

Allowed global values:

```text
x-soft
soft
medium
loud
x-loud
```

Required:

- no

TeachIntent intentionally omits SSML `silent` from v1 because silence is not a core pedagogical voice-style target here.

The core plan uses `volume`; it does not separately expose `energy`, `RMS`, and `intensity` as overlapping physical controls.

## 8. Segment-Level Overrides

Each override:

- references one verbal segment;
- specifies only controls that differ from, reset, or add to the global plan.

Fields are optional except `segment_id`.

Each `segment_id` may appear **at most once** in `segment_overrides`.

Each override must contain at least one actual control besides `segment_id`.

### 8.1 Inheritance and Reset Rule

Effective delivery for each segment follows:

```text
Segment Override
      ↓
Global Delivery
      ↓
Renderer / Voice Default
```

Omission means:

> inherit from the global plan if defined; otherwise use renderer default.

For segment-level prosody only, the explicit value:

```text
default
```

means:

> reset this field to the selected renderer/voice default, overriding any inherited global value.

Therefore `default` is useful in segment overrides but is intentionally not allowed in global prosody.

To preserve Sparse Control, a segment-level `default` is valid **only if the corresponding global prosody field is present**. Otherwise it would be a redundant no-op and must be omitted.

### 8.2 Segment-level prosody values

For `speaking_rate`, allowed values are:

```text
default
x-slow
slow
medium
fast
x-fast
```

For `pitch_level` and `pitch_range`, allowed values are:

```text
default
x-low
low
medium
high
x-high
```

For `volume`, allowed values are:

```text
default
x-soft
soft
medium
loud
x-loud
```

### 8.3 `attitudinal_tone` override

Use only when the local stance meaningfully differs from the global stance.

### 8.4 `emotion` override

Use only for a pedagogically motivated local affective change.

### 8.5 `prosody` override

Any non-empty subset of the valid segment-level prosody fields may be specified.

## 9. `contour_shape`

Meaning:

> coarse segment/phrase-level intonation movement.

Allowed values:

```text
level
rising
falling
rise-fall
fall-rise
```

Required:

- no

Important:

- this is a TeachIntent operational control vocabulary;
- it is **not** claimed to be a universal phonological taxonomy;
- Hy3 should choose a coarse shape, not generate a fabricated numerical F0 trajectory.

### 9.1 Contour Conflict Rule

SSML 1.1 gives `contour` precedence over `pitch` and `range`.

TeachIntent therefore intentionally forbids redundant segment-level combinations:

> if a segment explicitly sets `contour_shape`, the same segment must not simultaneously set segment-level `pitch_level` or `pitch_range`.

A global pitch baseline may still exist.

## 10. `prominence_targets`

Purpose:

> mark local linguistic spans that should perceptually stand out.

Example:

```json
{
  "prominence_targets": [
    {
      "text": "速度",
      "level": "strong"
    }
  ]
}
```

Type:

- non-empty array

Required:

- no

### 10.1 `prominence_targets[].text`

Type:

- non-empty string

Constraints:

- must be an exact substring of the referenced segment text;
- must occur **exactly once** in that segment.

If the intended span occurs multiple times, the planner must choose a longer unique span.

This avoids ambiguous target localization without introducing fragile character-offset conventions.

Within one segment:

- duplicate prominence targets are forbidden;
- prominence target spans must not overlap.

If no unique, non-overlapping span can be selected, the planner should revise the segmentation rather than emit an ambiguous target.

### 10.2 `prominence_targets[].level`

Allowed values:

```text
moderate
strong
```

Required:

- yes

Rationale:

SSML also defines `none` and `reduced`, but `reduced` may involve phonetic reduction and `none` suppresses automatic emphasis. TeachIntent v1 uses `prominence_targets` only for spans intended to **stand out**, so `moderate` and `strong` are the safer operational subset.

If future versions need explicit de-emphasis, that should be modeled separately rather than overloaded into `prominence_targets`.

Important:

> prominence is treated as a functional/perceptual target, not as a synonym for pitch, stress, or intensity.

The renderer may use multiple acoustic cues to realize it.

## 11. `boundary_after`

Purpose:

> control the prosodic boundary after a segment.

Example:

```json
{
  "boundary_after": {
    "strength": "strong"
  }
}
```

Required:

- no

### 11.1 `boundary_after.strength`

Allowed values:

```text
none
x-weak
weak
medium
strong
x-strong
```

Required when `boundary_after` exists:

- yes

Semantics:

- `none` explicitly requests suppression of a boundary the renderer might otherwise produce;
- stronger labels request progressively stronger prosodic boundaries.

Important:

- boundary strength is not equivalent to silence duration;
- Hy3 v1 should not freely generate exact pause milliseconds.

## 12. Fields Explicitly Excluded from Core v1

| Candidate | Decision | Reason |
|---|---:|---|
| Absolute F0 / Hz | Excluded | speaker-dependent and prone to fabricated precision |
| Mean F0 | Excluded | represented through relative `pitch_level` |
| F0 slope | Excluded | represented through coarse `contour_shape` |
| Numeric semitone curve | Excluded | unsupported precision for core planner |
| Energy RMS | Excluded | signal-level realization; use `volume` abstraction |
| Energy slope | Excluded | signal-level realization |
| Exact dB | Excluded | renderer-level parameter |
| Exact pause milliseconds | Excluded | unsupported precision |
| Spectral centroid | Excluded | closer to timbre/voice quality |
| Timbre / texture | Excluded | not core to pedagogical intent v1 |
| Gender | Excluded | speaker identity |
| Age | Excluded | speaker identity |
| Accent | Excluded | not core to current intent realization |
| Personality | Excluded | persistent speaker trait |
| Clarity | Excluded | evaluation quality dimension rather than style control |
| Fluency | Excluded | evaluation quality dimension |
| Lexical stress | Excluded | language-specific; local salience represented via prominence |
| Full chain-of-thought | Excluded | not an executable speech plan |
| Paralinguistic events | Deferred | possible later hard-case extension |

## 13. Mandarin / Tonal-Language Safety Constraint

For tonal languages such as Mandarin, as identified by the input `output_language`:

> `pitch_level`, `pitch_range`, and `contour_shape` must describe phrase/segment-level prosodic tendencies and must not intentionally overwrite lexical tone contrasts.

Renderer adapters should preserve lexical tone while approximating requested intonation.

## 14. Semantic Safety Constraints

Structural validation cannot determine whether a delivery style is pedagogically safe.

The generator prompt and evaluator should reject or flag delivery plans that are:

- humiliating or ridiculing;
- threatening or intimidating;
- coercive or manipulative;
- discriminatory;
- age-inappropriate;
- based on unsupported sensitive-attribute inference.

A learner error alone is not a valid reason to generate anger, hostility, or humiliation.

These semantic constraints complement, rather than replace, the structural schema.

## 15. Validator Rules

### Rule 1 — Segment ID Uniqueness

Every:

```text
verbal_plan.segments[].segment_id
```

must be unique.

### Rule 2 — Segment Reference Integrity

Every:

```text
segment_overrides[].segment_id
```

must reference an existing verbal segment.

### Rule 3 — One Override per Segment

A `segment_id` may appear at most once in:

```text
segment_overrides[]
```

### Rule 4 — Non-Empty Override

Every segment override must contain at least one actual control in addition to `segment_id`.

### Rule 5 — Prominence Span Integrity

Every:

```text
prominence_targets[].text
```

must be an exact substring of the corresponding segment `text` and must occur exactly once.

### Rule 6 — Unknown Fields Forbidden

Controlled JSON Schema objects should use:

```json
{
  "additionalProperties": false
}
```

Hy3 must not invent fields such as:

```json
{
  "teacher_authority": 0.8,
  "vocal_warmness": 0.7
}
```

### Rule 7 — Empty-Object Policy

Allowed:

```json
{
  "delivery_plan": {}
}
```

Not allowed when the field is present:

```json
{
  "global": {}
}
```

or:

```json
{
  "prosody": {}
}
```

### Rule 8 — Contour Conflict

Within the same segment, `contour_shape` must not coexist with segment-level:

- `pitch_level`
- `pitch_range`

### Rule 9 — No Fabricated Precision

The core Hy3 planner must not output unsupported precise acoustic values including:

- F0 Hz;
- RMS;
- dB;
- numeric semitone curves;
- exact pause milliseconds.

### Rule 10 — Non-Empty Verbal Plan

`verbal_plan.segments` must contain at least one non-empty text segment.

### Rule 11 — Meaningful `default` Reset

A segment-level prosody value of `default` is valid only when the same field is defined in global prosody.

### Rule 12 — Prominence Non-Overlap

Within a segment:

- duplicate `prominence_targets` are forbidden;
- resolved target spans must not overlap.

### Rule 13 — Style Descriptor Normalization

`attitudinal_tone` and `emotion` must be trimmed, single-line strings of 1–64 Unicode characters.

### Rule 14 — Schema Version Exactness

For this release:

```text
schema_version == "1.0.0-rc.3"
```

### Rule 15 — Validation Responsibility

Use JSON Schema for structural constraints such as:

- required fields;
- types;
- enums;
- `const`;
- `minItems`;
- `minLength` / `maxLength`;
- object shape;
- `additionalProperties: false`.

Use Pydantic/custom semantic validators for cross-field constraints such as:

- segment-ID uniqueness and reference integrity;
- one override per segment;
- prominence occurrence and non-overlap;
- contour conflicts;
- meaningful `default` resets.

All controlled objects should forbid unknown properties, including the root object, `verbal_plan`, segments, `delivery_plan`, `global`, prosody objects, segment overrides, prominence targets, and `boundary_after`.

## 16. Canonical Example

```json
{
  "schema_version": "1.0.0-rc.3",
  "verbal_plan": {
    "segments": [
      {
        "segment_id": "seg_01",
        "text": "你的思路已经很接近了。"
      },
      {
        "segment_id": "seg_02",
        "text": "不过这里有一个关键点需要纠正。"
      },
      {
        "segment_id": "seg_03",
        "text": "速度大，并不代表加速度一定大。"
      },
      {
        "segment_id": "seg_04",
        "text": "速度描述运动的快慢，而加速度描述速度变化的快慢。"
      }
    ]
  },
  "delivery_plan": {
    "global": {
      "attitudinal_tone": "supportive",
      "emotion": "calm"
    },
    "segment_overrides": [
      {
        "segment_id": "seg_02",
        "attitudinal_tone": "firm but supportive",
        "prosody": {
          "speaking_rate": "slow"
        },
        "prominence_targets": [
          {
            "text": "关键点",
            "level": "strong"
          }
        ],
        "boundary_after": {
          "strength": "strong"
        }
      },
      {
        "segment_id": "seg_03",
        "prosody": {
          "speaking_rate": "slow"
        },
        "prominence_targets": [
          {
            "text": "速度大",
            "level": "strong"
          },
          {
            "text": "并不代表",
            "level": "strong"
          },
          {
            "text": "加速度一定大",
            "level": "strong"
          }
        ]
      },
      {
        "segment_id": "seg_04",
        "prosody": {
          "speaking_rate": "slow"
        },
        "prominence_targets": [
          {
            "text": "运动的快慢",
            "level": "moderate"
          },
          {
            "text": "速度变化的快慢",
            "level": "moderate"
          }
        ]
      }
    ]
  }
}
```

## 17. Renderer Adapter Contract

The Speech Plan is renderer-agnostic.

A renderer adapter should translate TeachIntent controls into model-specific parameters and must receive the input `output_language` together with the Speech Plan.

For each requested control, the adapter should be able to report:

```text
applied
approximated
unsupported
```

The exact capability-report JSON shape is **not part of Speech Plan Schema v1** and should be defined separately when the renderer layer is implemented.

The system must not silently ignore unsupported controls.

## 18. Relation to SSML

TeachIntent intentionally aligns several categorical controls with SSML-style concepts:

- speaking rate;
- pitch;
- pitch range;
- volume;
- emphasis/prominence;
- break strength.

TeachIntent intentionally uses only a conservative categorical subset rather than all legal SSML numerical forms.

However:

> TeachIntent is not an SSML replacement.

TeachIntent represents **pedagogical planning intent**.

An adapter may convert part of the plan into SSML or another TTS control language.

## 19. Research Basis

The schema is informed by complementary evidence layers:

1. **Speech and prosody theory**  
   Prosody involves timing, amplitude, fundamental frequency, accentuation, and discourse-level organization.

2. **Prosodic prominence research**  
   Prominence is a multi-faceted functional/perceptual construct and should not be reduced to a single acoustic cue.

3. **Communicative-intent research**  
   Prosodic patterns can convey communicative intent even when lexical content is unavailable.

4. **Teacher prosody research**  
   Real teacher speech exhibits meaningful F0 variation and contour patterns.

5. **Instruction-following TTS research**  
   Modern systems increasingly separate high-level instruction understanding from explicit vocal planning and rendering.

6. **SSML engineering standard**  
   Provides established cross-platform concepts for rate, pitch, range, volume, emphasis, contour, and break.

## 20. Key References

- Cutler, A., Dahan, D., & van Donselaar, W. (1997). *Prosody in the Comprehension of Spoken Language: A Literature Review*.
- Wagner, P., et al. (2015). *Different Parts of the Same Elephant: A Roadmap to Disentangle and Connect Different Perspectives on Prosodic Prominence*.
- Fernald, A. (1989). *Intonation and Communicative Intent in Mothers' Speech to Infants: Is the Melody the Message?*
- Thorson, J. C., & Nesbitt, K. (2024). *Melodies of Learning: A Prosodic Analysis of Preschool Teachers' Language Patterns in the Classroom*.
- W3C (2010). *Speech Synthesis Markup Language (SSML) Version 1.1*.
- *BatonVoice: An Operationalist Framework for Enhancing Controllable Speech Synthesis with Linguistic Intelligence from LLMs* (2026).
- *InstructTTSEval: Benchmarking Complex Natural-Language Instruction Following in TTS Systems* (2025).
- *MINT-Bench: A Comprehensive Multilingual Benchmark for Instruction-Following Text-to-Speech* (2026).
- *OV-InstructTTS: Towards Open-Vocabulary Instruct Text-to-Speech* (2026).
- Bascandziev, I., Shafto, P., & Bonawitz, E. (2025). *Prosodic Cues Support Inferences About the Question's Pedagogical Intent*.

## 21. Pilot Validation Before Stable Release

`1.0.0-rc.3` should be tested on approximately 20–30 pilot cases before being promoted to `1.0.0`.

Pilot validation should check:

1. schema validity;
2. unnecessary control over-generation;
3. conflicts among speech controls;
4. intent differentiation;
5. content preservation;
6. pedagogical plausibility;
7. language consistency and tonal-language safety where applicable;
8. absence of unsafe or coercive delivery styles.

Only structural issues found during the pilot should justify schema revision.

## 22. Specification Priority

This document is the authoritative design specification for the TeachIntent Speech Plan.

Implementation agents may:

- report technical conflicts;
- suggest alternative implementations;
- implement validators and adapters.

They must not:

- silently add new fields;
- redefine field meanings;
- replace categorical controls with unsupported precise acoustic values;
- modify the research specification without explicit approval.
