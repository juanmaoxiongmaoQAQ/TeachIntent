# TeachIntent — Pedagogical Intents

> **Status:** Research Specification  
> **Document Version:** `0.3`  
> **Positioning:** Literature-Grounded Operational Intent Set

## 1. Positioning

TeachIntent does **not** claim to introduce a new universal taxonomy of teacher discourse.

Instead, the project operationalizes six high-level pedagogical intents grounded in prior research on:

- teacher moves;
- human tutoring;
- intelligent tutoring systems;
- formative feedback;
- social-emotional and motivational support.

The six categories are used as:

> **system control variables for one-to-one instructional speech planning.**

The exact six-way aggregation is a TeachIntent engineering operationalization chosen for controllability and tractable evaluation.

The set is **not claimed to be exhaustive of all possible teacher/tutor moves**; it defines the control space used by TeachIntent v1.

The source frameworks have different scopes. For example, TMSSR was developed in inquiry-oriented mathematics instruction, whereas AutoTutor and the Tutor Move Taxonomy concern tutoring dialogue more broadly. TeachIntent therefore uses **cross-framework triangulation**, rather than treating any one framework as a universal taxonomy.

## 2. Scope

The intent set applies to:

> one-to-one instructional or tutoring turns in which the teacher/AI tutor directly aims to change learner knowledge, understanding, reasoning progression, error state, or learning engagement.

Out of scope for v1:

- classroom management;
- administration;
- assignment logistics;
- attendance;
- discipline;
- technical support;
- pure social conversation.

`out_of_scope` may be used for dataset filtering/QC, but is not part of the generation-time intent enum.

## 3. Shared Classification Principle

Classify the intent by the:

> **intended learner state change**

rather than by surface sentence form.

A question is not automatically Elicitation.  
A statement is not automatically Explanation.  
A hint can be corrective if its primary purpose is repairing an already identified misconception.

## 4. Intent Set

| ID | Intent | 中文 | Intended learner-state change |
|---|---|---|---|
| PI-01 | `elicitation` | 引导表达 / 诊断 | Make the learner's current understanding or reasoning observable |
| PI-02 | `scaffolding` | 支架提示 | Make progress possible through limited guidance while preserving learner responsibility |
| PI-03 | `explanation` | 解释讲解 | Fill missing knowledge or understanding directly |
| PI-04 | `corrective_feedback` | 纠错反馈 | Repair an identified error, misconception, or mismatch |
| PI-05 | `supportive_feedback` | 支持性反馈 | Maintain or improve competence, confidence, emotional security, and engagement |
| PI-06 | `extension` | 深化拓展 | Deepen, broaden, justify, connect, generalize, or transfer established understanding |

## 5. PI-01 — Elicitation

### Definition

Elicitation aims to:

> elicit, activate, assess, clarify, or make visible the learner's current knowledge, reasoning, strategy, or understanding **without injecting substantive directional solution information**.

### Main goal

Make the learner's current state observable.

### Typical functions

- prior knowledge probe;
- answer elicitation;
- reasoning elicitation;
- clarification;
- understanding check.

### Inclusion criteria

Use `elicitation` when the turn primarily asks the learner to reveal:

- what they know;
- what they think;
- how they reasoned;
- what they mean;
- whether they understand.

### Exclusion criteria

Do not use `elicitation` when:

- the teacher provides a directional hint that narrows the solution space → `scaffolding`;
- the teacher directly supplies missing knowledge → `explanation`;
- the teacher is trying to repair an already identified error → `corrective_feedback`;
- the teacher asks the learner to go beyond already established understanding → `extension`.

### Example

> “你刚才是怎么判断这个答案的？”

### Counterexample

> “想一想，加速度关注的不是速度本身，而是什么发生了变化？”

This already injects directional information and is better classified as `scaffolding`.

## 6. PI-02 — Scaffolding

### Definition

In the broader educational literature, scaffolding is typically characterized by **contingency, fading, and transfer of responsibility**.

TeachIntent v1 is single-turn, so it cannot observe the full longitudinal scaffolding process. Therefore, the runtime label `scaffolding` operationalizes a **local scaffolding move**:

> contingent, limited guidance that helps the learner progress while preserving meaningful learner responsibility for completing the key reasoning step.

### Main goal

Increase progressability without taking over the learner's core cognitive work.

### Typical functions

- cue;
- hint;
- prompt;
- partial step;
- strategy guidance.

### Inclusion criteria

Use `scaffolding` when:

- the learner is stuck or incomplete;
- the teacher introduces a limited cue or structure;
- the learner is still expected to generate the key missing reasoning or answer.

### Exclusion criteria

Do not use `scaffolding` when:

- no directional information is introduced → `elicitation`;
- the teacher completes the key cognitive step directly → `explanation`;
- the main function is repairing an identified error → usually `corrective_feedback`.

### Example

> “先别急着算。你可以先看看题目给出的两个量分别代表什么。”

### Counterexample

> “这里应该使用加速度公式，因为它描述速度随时间的变化率。”

The teacher has already provided the key conceptual/procedural step, so this is closer to `explanation`.

## 7. PI-03 — Explanation

### Definition

Explanation directly provides:

> missing domain knowledge, conceptual relationships, procedures, mechanisms, definitions, examples, summaries, or answers.

### Main goal

Fill a knowledge or understanding gap.

### Typical functions

- conceptual explanation;
- procedural explanation;
- worked or modeled example;
- summary;
- answer provision.

### Inclusion criteria

Use `explanation` when:

- the teacher directly introduces the knowledge needed for understanding;
- the teacher carries out the key explanatory or procedural step.

### Exclusion criteria

Do not use `explanation` when:

- the learner should still generate the key reasoning after a limited hint → `scaffolding`;
- the explanation exists mainly because a prior learner error must be repaired → `corrective_feedback`;
- the learner is being asked to generate deeper reasoning beyond established understanding → `extension`.

### Example

> “速度描述物体运动的快慢；加速度描述速度随时间变化的快慢，所以速度大并不意味着加速度一定大。”

## 8. PI-04 — Corrective Feedback

### Definition

Corrective Feedback aims to:

> signal and repair a discrepancy between the learner's current response/understanding and the target knowledge.

It may identify, correct, or prompt correction of:

- an error;
- a misconception;
- incomplete reasoning;
- an incorrect procedure.

### Main goal

Repair an existing error state.

### Typical functions

- error flagging;
- prompted self-correction;
- direct correction;
- misconception explanation.

### Inclusion criteria

Use `corrective_feedback` when:

- an error or misconception has already been identified;
- the current turn depends on that learner error;
- the main instructional purpose is repair.

### Exclusion criteria

Do not use `corrective_feedback` when:

- there is no identified learner error and the teacher is simply teaching new material → `explanation`;
- the learner is merely stuck and receives a hint without an identified misconception → `scaffolding`;
- the main goal is motivational support → `supportive_feedback`.

### Example

> “这里有一个关键点需要纠正：速度大并不代表加速度大。速度描述运动快慢，而加速度描述速度变化得有多快。”

## 9. PI-05 — Supportive Feedback

### Definition

Supportive Feedback aims to:

> affirm valid understanding, effort, progress, or productive strategy, and support the learner's competence, confidence, emotional security, persistence, or engagement.

It is not equivalent to generic praise.

### Main goal

Maintain or improve the learner's willingness and psychological readiness to continue learning.

### Typical functions

- affirmation;
- process praise;
- encouragement;
- emotion validation.

### Inclusion criteria

Use `supportive_feedback` when the main purpose is to:

- acknowledge valid progress;
- normalize difficulty;
- encourage persistence;
- validate frustration without endorsing incorrect content;
- reinforce a productive process or strategy.

### Exclusion criteria

Do not use `supportive_feedback` when:

- the main purpose is to teach new knowledge → `explanation`;
- the main purpose is to repair an error → `corrective_feedback`;
- the utterance is empty or person-level praise unrelated to learning.

### Good example

> “你刚才先比较两个概念的含义，再做判断，这个思路是有效的。继续保持这种先辨析概念再作答的方法。”

### Poor example

> “你真聪明！”

This is person-level praise and contains little task/process information.

## 10. PI-06 — Extension

### Definition

Extension aims to:

> move beyond already established or expressed understanding through deeper reasoning, justification, reflection, comparison, generalization, transfer, or conceptual connection.

### Main goal

Deepen or broaden understanding.

### Typical functions

- justification;
- comparison;
- reflection;
- generalization;
- transfer;
- connection.

### Inclusion criteria

Use `extension` when the learner already has enough understanding to be asked to:

- explain why;
- compare alternatives;
- generalize;
- transfer knowledge to a new case;
- connect concepts;
- reflect on strategy.

### Exclusion criteria

Do not use `extension` when:

- the teacher is only trying to determine what the learner currently understands → `elicitation`;
- the learner still needs direct missing knowledge → `explanation`;
- the learner is stuck and needs limited guidance → `scaffolding`.

### Example

Given that the learner has already correctly distinguished speed from acceleration:

> “如果一个物体速度很大，但速度始终不变，它的加速度是多少？为什么？”

## 11. Boundary Rules

The following are **TeachIntent operational decision rules** derived from the distinctions supported by prior frameworks. They are not claimed to be universal theoretical definitions.

### 11.1 Elicitation vs Scaffolding

Question:

> Does the teacher inject directional information that narrows the solution space?

- No → `elicitation`
- Yes, but learner still completes the key step → `scaffolding`

### 11.2 Scaffolding vs Explanation

Question:

> Who completes the key cognitive step?

- Learner → `scaffolding`
- Teacher → `explanation`

### 11.3 Corrective Feedback vs Scaffolding

Question:

> Is there an already identified error/misconception and is repair the main function?

- Yes → `corrective_feedback`
- No, learner is mainly stuck/incomplete → `scaffolding`

A corrective turn may still use a hint as its local strategy.

### 11.4 Corrective Feedback vs Explanation

Diagnostic heuristic:

> Would the same utterance likely still be given if the learner had not made the prior error?

- Yes → likely `explanation`
- No; it exists because of the error → likely `corrective_feedback`

A corrective turn may contain explanatory material.

### 11.5 Elicitation vs Extension

- `elicitation` makes current understanding explicit.
- `extension` asks the learner to move beyond established understanding.

Typical Extension signals:

- justify;
- compare;
- generalize;
- transfer;
- reflect;
- connect.

### 11.6 Supportive Feedback vs Content-Oriented Moves

If the main intended state change concerns:

- confidence;
- emotional security;
- persistence;
- engagement;
- recognition of valid progress;

then classify as `supportive_feedback`.

If the main goal is content repair or knowledge delivery, classify by that instructional function instead.

### 11.7 Explanation vs Extension

- Teacher supplies the key new knowledge → `explanation`
- Learner is asked to generate deeper reasoning, justification, comparison, generalization, or transfer → `extension`

## 12. Multi-Intent Policy

Real teaching turns can be multi-functional.

### Standard cases

Use exactly one:

```json
{
  "pedagogical_intent": {
    "primary": "scaffolding"
  }
}
```

### Hard / compositional cases

Future hard cases may contain:

- one primary intent;
- one optional secondary intent;
- segment-level realizations reflecting different local functions.

The primary intent must still represent the dominant intended learner-state change.

## 13. Strategy Layer

Recommended second-level strategies are listed below for analysis and future development.

### Elicitation

- `prior_knowledge_probe`
- `answer_elicitation`
- `reasoning_elicitation`
- `clarification`
- `understanding_check`

### Scaffolding

- `cue`
- `hint`
- `prompt`
- `partial_step`
- `strategy_guidance`

### Explanation

- `conceptual_explanation`
- `procedural_explanation`
- `example_modeling`
- `summary`
- `answer_provision`

### Corrective Feedback

- `error_flagging`
- `prompted_self_correction`
- `direct_correction`
- `misconception_explanation`

### Supportive Feedback

- `affirmation`
- `process_praise`
- `encouragement`
- `emotion_validation`

### Extension

- `justification`
- `comparison`
- `reflection`
- `generalization`
- `transfer`
- `connection`

These are **not** additional top-level intents.

Important:

> Strategies may be used later for interpretability or analysis, but should not be added to the core runtime schema until their controlled vocabulary and implementation need are finalized.

## 14. Evidence Matrix

| TeachIntent intent | Main grounding | Relevant established functions/moves |
|---|---|---|
| `elicitation` | TMSSR; Tutor Move Taxonomy | eliciting reasoning, probing, prompting self-explanation |
| `scaffolding` | AutoTutor; scaffolding literature; Tutor Move Taxonomy | cue, hint, prompt, guided next step |
| `explanation` | AutoTutor; TMSSR facilitating; Li & Hu's guiding/providing operationalization; Tutor Move Taxonomy | assertion, conceptual/procedural explanation, answer, summary |
| `corrective_feedback` | TMSSR responding; AutoTutor; Tutor Move Taxonomy | correcting errors, prompting self-correction, feedback on incorrect responses |
| `supportive_feedback` | Tutor Move Taxonomy; Shute; Hattie & Timperley | validation, encouragement, process praise, supportive formative feedback |
| `extension` | TMSSR extending | justification, comparison, reflection, generalization, connection/transfer |

## 15. Literature Grounding

Key sources include:

1. **Ellis, A., Özgür, Z., & Reiten, L. (2019).** *Teacher Moves for Supporting Student Reasoning*. Mathematics Education Research Journal, 31(2), 107–132. DOI: `10.1007/s13394-018-0246-6`.  
   TMSSR organizes moves into eliciting, responding, facilitating, and extending. TeachIntent uses this as one major source, not as a universal taxonomy.

2. **Graesser, A. C., Lu, S., Jackson, G. T., et al. (2004).** *AutoTutor: A Tutor with Dialogue in Natural Language*. Behavior Research Methods, Instruments, & Computers, 36(2), 180–192. DOI: `10.3758/BF03195563`.  
   AutoTutor distinguishes pumps, hints, prompts, assertions, corrections, answers, and summaries, strongly supporting the operational distinction between elicitation/scaffolding/explanation/correction.

3. **van de Pol, J., Volman, M., & Beishuizen, J. (2010).** *Scaffolding in Teacher–Student Interaction: A Decade of Research*. Educational Psychology Review, 22, 271–296. DOI: `10.1007/s10648-010-9127-6`.  
   Identifies contingency, fading, and transfer of responsibility as key scaffolding characteristics. TeachIntent v1 operationalizes only a local scaffolding move because its runtime scope is single-turn.

4. **Shute, V. J. (2008).** *Focus on Formative Feedback*. Review of Educational Research, 78(1), 153–189. DOI: `10.3102/0034654307313795`.  
   Describes formative feedback as supportive, timely, specific information and discusses verification, explanations, hints, and worked examples.

5. **Hattie, J., & Timperley, H. (2007).** *The Power of Feedback*. Review of Educational Research, 77(1), 81–112. DOI: `10.3102/003465430298487`.  
   Shows that feedback effects depend strongly on feedback type and delivery; feedback should not be treated as one undifferentiated category.

6. **Li, J., & Hu, W. (2026; version of record published online 2025).** *Metadiscourse and Teacher Moves for Supporting Student Reasoning in Linguistics Classroom Interactions*. International Journal of Applied Linguistics, 36(1), 522–539. DOI: `10.1111/ijal.12793`.  
   This study explicitly operationalizes TMSSR facilitating moves through **guiding** and **providing** subtypes, which is useful supporting evidence for TeachIntent's engineering separation between `scaffolding` and `explanation`. This subtype distinction should not be misattributed to the original TMSSR paper alone.

7. **Zhou, Z., Vanacore, K., Thompson, T., St John, J., & Kizilcec, R. (2026).** *Tutor Move Taxonomy: A Theory-Aligned Framework for Analyzing Instructional Moves in Tutoring*. arXiv:`2603.05778`.  
   A recent preprint developed for the National Tutoring Observatory. It provides useful corroborating one-to-one tutoring move categories, including learning support and social-emotional/motivational support. Because it is a recent preprint, TeachIntent treats it as supporting evidence rather than the sole theoretical foundation.

The exact six-class aggregation and boundary rules remain a **TeachIntent engineering operationalization** intended for controllability and evaluation.
