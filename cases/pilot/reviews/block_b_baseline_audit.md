# TeachIntent — Block B Baseline Audit

> **Run ID:** `20260827-051547`
> **Block:** `cross_domain_generalization`
> **Dataset:** Block B Cross-Domain Generalization v0.2
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

This document records the first semantic audit of the frozen Block B baseline run.

The audit is diagnostic rather than a final evaluator score. It does not revise Prompt v0.1, either frozen dataset, the generator, or the Speech Plan schema.

Block B is specifically intended to test cross-domain generalization across mathematics, English, chemistry, Chinese, biology, and physics.

---

## 2. Frozen Run Conditions

```text
run_id              = 20260827-051547
block               = cross_domain_generalization
api_gateway         = openrouter
base_url            = https://openrouter.ai/api/v1
model               = tencent/hy3
temperature         = 0
structured_output   = false
retry               = false
self_repair         = false
attempts_per_case   = 1
prompt_version      = v0.1
```

All 12 cases were executed sequentially in frozen dataset order.

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
attempt_index = 1            12 / 12
```

Every raw response was directly parseable as JSON and exactly matched its corresponding `parsed.json`.

No retry, self-repair, or structured-output enforcement was used.

### Runtime latency

```text
total duration     ≈ 333.5 s
mean per case      ≈ 27.8 s
fastest case       PILOT-B-EXT-01 ≈ 16.2 s
slowest case       PILOT-B-EXP-02 ≈ 44.4 s
```

`token_usage` remained unavailable through the current client layer and was recorded as `null`.

---

## 4. Preliminary Cross-Domain Intent Differentiation

Across six subject domains, the verbal behavior remained clearly aligned with the explicitly supplied pedagogical intent.

| Intent | Cross-domain cases | Preliminary judgment |
|---|---|---|
| `elicitation` | mathematics, English | Strong |
| `scaffolding` | chemistry, Chinese | Strong |
| `explanation` | mathematics, biology | Strong |
| `corrective_feedback` | chemistry, English | Strong |
| `supportive_feedback` | mathematics, biology | Strong |
| `extension` | physics, Chinese | Strong |

No obvious intent-collapse pattern was observed.

In particular:

- Elicitation asks learners to externalize their current reasoning without supplying the target rule.
- Scaffolding gives limited directional help while preserving the learner's final cognitive step.
- Explanation directly supplies missing knowledge.
- Corrective feedback targets an already expressed misconception and repairs it.
- Supportive feedback ties encouragement to demonstrated progress or valid reasoning.
- Extension requires new comparison, transfer, or reasoning beyond simple recall.

This strengthens the Block A signal that explicit pedagogical intent can drive meaningfully different Speech Plans across domains.

---

## 5. Case-by-Case Audit

### `PILOT-B-ELI-01`

**Verbal plan:** strong elicitation.

The model asks the learner to explain how they are currently thinking about `1/2` and `2/4`, without giving the equality relation or equivalent-fraction rule.

**Delivery observation:** the prominence target is placed on “不确定”. This is structurally valid but pedagogically debatable because emphasizing the learner's uncertainty may foreground lack of confidence rather than the mathematical object of reasoning.

**Status:** intent/content strong; minor delivery–pedagogy alignment concern.

---

### `PILOT-B-ELI-02`

**Verbal plan:** strong.

The response asks how the learner currently distinguishes the two tense forms and does not reveal the frozen core criteria.

**Delivery:** minimal, with only an exploratory/supportive attitudinal tone.

**Status:** strong.

---

### `PILOT-B-SCA-01`

**Verbal plan:** strong procedural scaffolding.

The model suggests counting atoms on both sides and asks whether the learner wants to begin with hydrogen or oxygen. It does not give the final coefficients.

**Delivery:** calm/slow delivery is plausible because the learner is explicitly `uncertain` and the experiment-side delivery need is `medium`.

**Status:** strong.

---

### `PILOT-B-SCA-02`

**Verbal plan:** strong.

The response narrows attention to action details (“停了几秒”“反复捏着衣角”) but leaves the final emotion inference to the learner.

**Delivery observation:** despite `delivery_need = low`, the response uses a global guiding tone, calm emotion, slow speaking rate, and strong prominence.

**Status:** verbal plan strong; possible delivery over-specification.

---

### `PILOT-B-EXP-01`

**Verbal plan:** strong and content-faithful.

The response directly explains the distributive property and gives the frozen example.

**Delivery:** `{}`.

This is an important positive counterexample showing that Prompt v0.1 / Hy3 is capable of emitting no explicit delivery controls when it judges them unnecessary.

**Status:** strong.

---

### `PILOT-B-EXP-02`

**Verbal plan:** accurate and age-appropriate.

The model explains the functions of roots, stems, and leaves within the supplied anchor.

**Delivery observation:** the case was pre-labeled `delivery_need = low`, but the model uses `耐心亲切 + 平静 + slow`, three prominence targets, and multiple boundaries.

**Status:** content/intent strong; clear sparse-control concern.

---

### `PILOT-B-COR-01`

**Verbal plan:** corrective repair is complete.

The output clearly distinguishes faster approach to equilibrium from changing equilibrium position or equilibrium yield.

**Content precision observation:** the phrase “同时同等加快正、逆反应速率” is slightly stronger than the frozen anchor, which only states that the catalyst accelerates both forward and reverse reactions. “同等加快” is potentially ambiguous and could be interpreted as equal absolute rate increases.

**Interpersonal observation:** “这是个常见误解” is not a safety violation, but it is somewhat more error-labeling than necessary.

**Status:** intent strong; minor content-precision / wording concern.

---

### `PILOT-B-COR-02`

**Verbal plan:** strong corrective feedback.

The response repairs the exact misconception that `more` can be stacked with an `-er` comparative, explains the duplication, and supplies the correct sentence.

Unlike the incomplete repair observed in Block A `COR-02`, this case fully addresses the learner's erroneous rule.

**Delivery observation:** `supportive + calm + slow` is plausible but continues the global-template tendency.

**Status:** strong.

---

### `PILOT-B-SUP-01`

**Verbal plan:** strong supportive feedback.

The response explicitly validates the learner's correct operations and links confidence support to the actual use of equation-preserving transformations.

**Delivery:** `reassuring + calm + slow` is well motivated by the frozen `slightly_frustrated` state and `delivery_need = high`.

**Wording observation:** “要有信心” is somewhat directive, but not a substantive intent error.

**Status:** strong.

---

### `PILOT-B-SUP-02`

**Verbal plan:** strong.

The response grounds praise in the learner's use of cell wall and chloroplast evidence rather than giving generic person-level praise.

**Delivery:** calm/reassuring treatment is compatible with the learner's explicit uncertainty and `delivery_need = medium`.

**Content precision observation:** “关键证据” is slightly stronger than the anchor's “重要证据”, but does not materially alter the intended instructional content in this case.

**Status:** strong.

---

### `PILOT-B-EXT-01`

**Verbal plan:** strong extension.

The model creates a new within-anchor comparison: if both net force and mass double, how will acceleration change? The learner must reason using `F_net = ma`.

This stays inside the authoritative content boundary and does not introduce friction, inclined planes, or other forbidden mechanisms.

**Delivery observation:** `启发探究 + slow` is not clearly necessary for this `delivery_need = low` case.

**Status:** strong extension; mild sparse-control concern.

---

### `PILOT-B-EXT-02`

**Verbal plan:** strong extension.

The learner is asked to compare evidence A and B and justify which more strongly supports the claim. The model does not provide the answer or require unsupported statistical/causal machinery.

**Delivery:** the prominence/boundary choices are interpretable and the global plan does not use calm/slow.

**Status:** strong.

---

## 6. Delivery-Control Pattern

The Block A global-delivery pattern partially replicates in Block B.

### Overall Block B

```text
speaking_rate = slow       7 / 12
calm-like emotion          7 / 12
empty delivery_plan        1 / 12
non-empty delivery_plan   11 / 12
```

### Pre-labeled low-delivery-need cases

There are seven `delivery_need = low` cases:

```text
ELI-01
ELI-02
SCA-02
EXP-01
EXP-02
EXT-01
EXT-02
```

Among them:

```text
non-empty delivery_plan    6 / 7
speaking_rate = slow       3 / 7
calm-like emotion          2 / 7
empty delivery_plan        1 / 7
```

The exact same high-level sparsity pattern observed in Block A therefore remains visible: six of seven low-need cases still receive explicit delivery controls.

The concern should be stated narrowly:

> Hy3 is often capable of useful local salience planning, but Prompt v0.1 / Hy3 appears to over-specify delivery controls relative to the experiment-side sparse-control expectation.

The Block B data also show that the behavior is not absolute: `PILOT-B-EXP-01` correctly emits an empty delivery plan.

---

## 7. Status of Block A Hypotheses After Block B

### H1 — Generic delivery over-specification

**Replicated / strengthened.**

Block A already showed frequent calm/slow/reassuring controls and only one empty delivery plan. Block B again has only one empty delivery plan and six of seven low-need cases receive explicit delivery controls.

This is now the clearest repeated baseline finding.

---

### H2 — Extension content-boundary drift

**Not replicated in Block B.**

Both Block B extension cases remain within the supplied content anchor:

- `EXT-01` uses a new Newton's-second-law comparison fully derivable from `F_net = ma`.
- `EXT-02` asks for evidence-strength comparison using criteria already present in the anchor.

The Block A `EXT-01` issue should therefore remain a notable case-level failure, not yet a systematic extension failure.

---

### H3 — Incomplete misconception repair

**Not replicated in Block B.**

Both corrective-feedback cases in Block B perform substantially complete repair.

`COR-02` in particular directly repairs the erroneous comparative-formation rule, unlike the partial repair observed in Block A `COR-02`.

The Block A observation therefore remains an important case-level evaluator target but is not yet a repeated systematic pattern.

---

## 8. New Block B Diagnostic Observations

### H4 — Delivery emphasis can target learner uncertainty rather than instructional content

`PILOT-B-ELI-01` applies prominence to “不确定”.

This is structurally valid but may be pedagogically less appropriate than emphasizing the object of comparison or using no explicit prominence at all.

This supports the need for a future **Delivery–Pedagogy Alignment** dimension rather than evaluating delivery solely for schema validity.

### H5 — Minor content-strengthening can occur without outright hallucination

Examples include:

- `COR-01`: “同等加快” is stronger/more ambiguous than the anchor's “同时加快”.
- `SUP-02`: “关键证据” slightly strengthens “重要证据”.

These are not major factual failures, but they motivate a Content Faithfulness evaluator that can distinguish:
- faithful paraphrase;
- harmless strengthening;
- unsupported extension;
- contradiction/hallucination.

---

## 9. Prompt Revision Decision

**Prompt v0.1 should remain unchanged after Block B.**

Reasons:

1. The full planned baseline contains 30 cases; Block C has not yet been run.
2. Intent differentiation remains strong across domains.
3. The main repeated concern is delivery sparsity, but changing the prompt now would destroy A/B/C comparability.
4. The two other Block A concerns — extension drift and incomplete correction — did not replicate in Block B.

The correct next step is to keep Prompt v0.1 frozen and proceed to the 6 hard/adversarial Block C cases.

---

## 10. Block B Baseline Status

```text
Authoring                       PASS
Final QC                       PASS
Pre-generation Freeze          PASS
Structural Validation          PASS
First-call Generation          12 / 12 PASS
Response Parsing               12 / 12 PASS
Speech Plan JSON Schema        12 / 12 PASS
Speech Plan Pydantic           12 / 12 PASS

Preliminary semantic findings:
  Cross-domain intent differentiation      strong
  Content faithfulness                     strong overall
  Corrective repair completeness           strong in both Block B cases
  Extension boundary control               strong in both Block B cases
  Sparse delivery control                  repeated concern
  Delivery–pedagogy alignment              one notable low-severity concern
```

The original run artifacts for `20260827-051547` must be preserved unchanged.
