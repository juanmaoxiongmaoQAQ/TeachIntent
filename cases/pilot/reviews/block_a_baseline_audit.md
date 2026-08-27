# TeachIntent — Block A Baseline Audit

> **Run ID:** `20260827-002543`
> **Dataset:** Block A Controlled Intent Contrast v0.2
> **Case Count:** 12
> **Prompt:** `v0.1`
> **Model:** `tencent/hy3`
> **API Gateway:** OpenRouter
> **Temperature:** `0`
> **Structured Output:** disabled
> **Retry:** disabled
> **Self-repair:** disabled
> **Audit Status:** Preliminary semantic audit after frozen first-call baseline

## 1. Scope

This document records the first semantic audit of the frozen Block A baseline run.

The audit is intentionally diagnostic. It does **not** assign a final composite score and does **not** revise Prompt v0.1, the frozen Block A cases, or the Speech Plan schema.

The purpose is to record:

- engineering/contract-following behavior;
- preliminary pedagogical-intent differentiation;
- content-faithfulness issues;
- intent-specific realization issues;
- delivery-control patterns worth testing again in Blocks B and C.

Any observation in this document is treated as a hypothesis or preliminary failure pattern unless it repeats across the complete 30-case baseline.

---

## 2. Frozen Run Conditions

```text
run_id              = 20260827-002543
api_gateway          = openrouter
base_url             = https://openrouter.ai/api/v1
model                = tencent/hy3
temperature          = 0
structured_output    = false
retry                 = false
self_repair           = false
attempts_per_case     = 1
```

All 12 cases were executed sequentially in frozen dataset order.

No failed case was retried. No model output was manually repaired.

---

## 3. Engineering and Contract Results

```text
Generation attempts          12
First-call successes         12 / 12
Response parsing             12 / 12 PASS
Speech Plan JSON Schema      12 / 12 PASS
Speech Plan Pydantic         12 / 12 PASS
finish_reason = stop         12 / 12
reported_model=tencent/hy3   12 / 12
```

All 12 raw responses were directly parseable JSON objects and matched their corresponding parsed artifacts without silent repair.

This provides strong preliminary evidence that, under Prompt v0.1, Hy3 can follow the TeachIntent Speech Plan structural contract without structured-output enforcement.

### Runtime latency

```text
total duration     ≈ 462.7 s
mean per case      ≈ 38.6 s
fastest case       PILOT-A-COR-01 ≈ 20.7 s
slowest case       PILOT-A-SCA-01 ≈ 61.3 s
```

`token_usage` was unavailable through the current Hy3 client layer and was therefore recorded as `null`, not inferred.

---

## 4. Preliminary Intent Differentiation

The six pedagogical intents produced visibly different verbal-plan behaviors across both controlled content anchors.

| Intent | Observed behavior | Preliminary judgment |
|---|---|---|
| `elicitation` | Invited the learner to externalize current thinking without directly supplying the target distinction | Strong |
| `scaffolding` | Added limited directional guidance while leaving the final cognitive step to the learner | Strong |
| `explanation` | Directly supplied missing conceptual knowledge | Strong |
| `corrective_feedback` | Responded to an already expressed misconception and attempted repair | Generally strong |
| `supportive_feedback` | Acknowledged valid progress and supported confidence/persistence | Strong |
| `extension` | Asked the learner to go beyond already established understanding | Strong, with one content-boundary issue |

The contrast between `elicitation` and `scaffolding` was especially clear:

- Elicitation primarily asked the learner to state current reasoning.
- Scaffolding introduced task-relevant directional information but did not directly give the final answer.

This is a positive signal for the central TeachIntent hypothesis that an explicitly given pedagogical intent can produce meaningfully different Speech Plans under a shared knowledge anchor.

---

## 5. Case-by-Case Audit

### `PILOT-A-ELI-01`

**Intent realization:** strong.

The response asked the learner to make the current mental model explicit and did not supply the target conceptual distinction.

**Delivery observation:** `attitudinal_tone = 鼓励表达` is plausible, although this was a pre-labeled `delivery_need = low` case and the control may not be strictly necessary.

**Status:** no major semantic issue.

---

### `PILOT-A-SCA-01`

**Intent realization:** strong.

The response first reminded the learner what acceleration describes, then asked whether the train's velocity magnitude or direction changes. This is directional help while preserving the learner's final judgment.

**Delivery observation:** relatively dense control:

```text
attitudinal_tone = 安抚
emotion = 平静
speaking_rate = slow
prominence("加速度") = strong
prominence("大小和方向") = moderate
boundary = medium
question contour = rising
```

The local prominence choices are pedagogically interpretable, but the global `安抚 / 平静 / slow` pattern may be more control than this case requires.

**Status:** verbal plan strong; delivery-density observation retained.

---

### `PILOT-A-EXP-01`

**Intent realization:** strong.

The output directly explained the concepts and stayed close to the supplied content anchor.

**Delivery observation:** despite `delivery_need = low`, the model generated:

```text
attitudinal_tone = reassuring
emotion = calm
speaking_rate = slow
```

No learner affect in the frozen case clearly required this adaptation.

**Status:** content/intent strong; possible global-delivery over-specification.

---

### `PILOT-A-COR-01`

**Intent realization:** strong.

The response explicitly repaired the learner's misconception that unchanged speed magnitude during a turn implies zero acceleration.

It correctly shifted attention to velocity direction:

```text
方向变了
加速度就不为0
```

The prominence targets were placed on corrective conceptual information rather than on labels such as “错误” or “误解”.

**Status:** one of the strongest Block A examples.

---

### `PILOT-A-SUP-01`

**Intent realization:** strong.

The response recognized the learner's demonstrated understanding and connected encouragement to concrete progress rather than generic person-level praise.

The supportive tone is consistent with the frozen `slightly_frustrated` learner state and `delivery_need = high`.

**Status:** strong.

---

### `PILOT-A-EXT-01`

**Intent realization:** extension is clearly realized.

However, the output asked the learner to:

> 举一个匀速圆周运动的例子，并说明其中加速度的方向大致指向哪里

The frozen content anchor establishes that a direction change implies nonzero acceleration, but it does **not** establish the direction of acceleration in uniform circular motion.

Therefore the generated task requires knowledge beyond the authoritative case-level content boundary.

**Preliminary diagnosis:**

```text
Intent Following       PASS
Structural Validity    PASS
Content Faithfulness   CONCERN
```

This is a useful future evaluator case for detecting content-boundary expansion.

---

### `PILOT-A-ELI-02`

**Intent realization:** strong.

The response asked what cues the learner currently uses to distinguish the two rhetorical devices and did not provide the intended classification rule.

**Delivery observation:** a `strong` phrase boundary after the diagnostic question may be defensible but is not obviously necessary for a `delivery_need = low` case.

**Status:** verbal plan strong; minor sparse-control observation.

---

### `PILOT-A-SCA-02`

**Intent realization:** strong.

The response focused attention on “抚摸” and asked whether that action is normally human, providing a useful hint without stating “这是拟人”.

**Delivery observation:** the global combination:

```text
attitudinal_tone = 循循善诱
emotion = 平和
speaking_rate = slow
```

again suggests a tendency toward generic calm/slow delivery even in a `delivery_need = low` case.

**Status:** verbal plan strong; delivery over-specification hypothesis strengthened.

---

### `PILOT-A-EXP-02`

**Intent realization:** strong.

The explanation accurately distinguishes simile and personification and correctly states that the presence of “像” is not itself the decision rule.

**Delivery observation:** another `delivery_need = low` case received:

```text
attitudinal_tone = reassuring
emotion = calm
speaking_rate = slow
```

plus two moderate prominence targets.

**Status:** content/intent strong; repeated global-delivery pattern.

---

### `PILOT-A-COR-02`

**Intent realization:** corrective feedback is present.

The response correctly states that the learner cannot rely only on whether “像” appears and redirects attention to expression mechanism.

However, the repair is incomplete relative to the learner's two-part mechanical rule:

```text
有“像” -> 一定是比喻
没有“像” -> 一定不是比喻
```

The supplied example (“春风轻轻抚摸着我的脸”) shows a no-“像” personification. That does not itself demonstrate that a simile can occur without “像”, nor does it directly refute every part of the learner's rule.

**Preliminary diagnosis:**

```text
Intent Following          PASS
Error Identification      PASS
Repair Completeness       CONCERN
```

This is not an intent mismatch; it is a possible corrective-sufficiency issue.

---

### `PILOT-A-SUP-02`

**Intent realization:** strong.

The output acknowledges the learner's effective strategy and gives confidence-oriented feedback tied to actual reasoning.

**Delivery observation:** `reassuring / calm / slow` is plausible for an uncertain learner, though the repeated global template should be examined across later blocks.

**Status:** strong.

---

### `PILOT-A-EXT-02`

**Intent realization:** strong.

The output asks the learner to produce a new example without “像” and explain its relation to personification, clearly extending beyond simple definition recall while staying within the supplied content anchor.

**Delivery observation:** `strong` prominence and `strong` boundary may be richer than necessary for a `delivery_need = low` case.

**Status:** strong verbal/content realization; sparse-control observation retained.

---

## 6. Systematic Delivery Observation

The clearest repeated Block A pattern is global delivery over-specification.

### Speaking rate

`speaking_rate = slow` occurred in:

```text
8 / 12 cases
```

The same eight cases also used an emotion equivalent to calm:

```text
calm / 平静 / 平和 = 8 / 12
```

Only one case used an entirely empty delivery plan:

```text
PILOT-A-EXT-01
```

### Low-delivery-need cases

Seven frozen Block A cases were labeled:

```text
tags.delivery_need = low
```

Only one of these seven (`PILOT-A-EXT-01`) produced `{}` as its delivery plan.

The remaining low-need cases received one or more explicit controls, including:

- reassuring/calm/slow global settings;
- explicit attitudinal tone;
- strong phrase boundary;
- strong prominence.

This does **not** establish that the controls are incorrect case by case. It does establish a pattern worth retesting.

### Preliminary hypothesis

> Hy3 under Prompt v0.1 appears to favor generic calm/slow/reassuring global delivery, including in cases with low pre-annotated delivery need.

At the same time, local prominence planning was often pedagogically meaningful. Therefore the current concern is more specific than “delivery planning is poor”:

> Local salience planning is often useful, while global rate/emotion/tone controls may be over-specified or template-like.

---

## 7. Preliminary Failure Hypotheses for Later Blocks

The following hypotheses should be tested again in Blocks B and C without altering Prompt v0.1:

### H1 — Generic global-delivery over-specification

Hy3 may overuse:

```text
slow
calm / 平静 / 平和
reassuring-like attitudinal tone
```

even when learner affect and instructional context do not strongly motivate such controls.

### H2 — Extension content-boundary drift

When asked to extend learning, Hy3 may introduce a reasonable but unsupported next-step concept that lies outside the authoritative `content_anchor`.

### H3 — Incomplete misconception repair

Corrective feedback may correctly identify the direction of an error while failing to repair every logically relevant part of the learner's misconception.

These are hypotheses, not yet final evaluator findings.

---

## 8. Prompt Revision Decision

**No Prompt revision is made after Block A.**

Prompt v0.1 remains frozen for Blocks B and C.

Reason:

- Block A is only 12 of the planned 30 cases.
- The pilot specification requires repeated patterns, not isolated cases, to drive revision.
- Changing the prompt now would destroy comparability across the full baseline.

The current workflow remains:

```text
Block A baseline
    ↓
record observations
    ↓
Block B baseline
    ↓
Block C baseline
    ↓
complete 30-case analysis
    ↓
then decide Prompt v0.2 / evaluator design
```

---

## 9. Block A Baseline Status

```text
Authoring                       PASS
Human QC                       PASS
Pre-generation Freeze          PASS
Structural Validation          PASS
First-call Generation          12 / 12 PASS
Schema / Pydantic Validation   12 / 12 PASS

Preliminary semantic findings:
  Intent differentiation       strong
  Content faithfulness         mostly strong; 1 notable boundary concern
  Corrective completeness      1 notable concern
  Sparse delivery control      repeated concern
```

The original run artifacts for `20260827-002543` must be preserved unchanged.
