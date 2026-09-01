# Decision Log — TeachIntent

Records *why* decisions were made, not current state. Current state lives in
`docs/CODEX_HANDOFF.md`. Each entry: Context / Decision / Evidence /
Consequence.

---

## Decision 1 — Study the Speech Planning layer, not TTS architecture

- **Context:** Text-to-speech (TTS) is a crowded field; the open research
  question is how high-level teaching intent becomes a *sayable* utterance.
- **Decision:** Position TeachIntent on the **planning layer** between pedagogy
  and speech realization — the mapping `(C, P, L, G) -> (V, D)` — and treat the
  TTS/audio side as out of scope.
- **Evidence:** The plan is interpretable, machine-actionable, and evaluable
  *before* audio rendering, which isolates the research variable (pedagogical
  planning) from acoustic realization.
- **Consequence:** Hy3 is used only as the planner; no TTS synthesis, voice
  cloning, intent auto-selection, or multi-turn tutoring policy.

## Decision 2 — Six pedagogical intents

- **Context:** A usable control variable needs a tractable, well-defined intent
  set grounded in prior work (teacher moves, human tutoring, ITS, formative
  feedback, motivational support).
- **Decision:** Operationalize exactly six intents — Elicitation, Scaffolding,
  Explanation, Corrective Feedback, Supportive Feedback, Extension.
- **Evidence:** Cross-framework triangulation (TMSSR, AutoTutor, Tutor Move
  Taxonomy, formative-feedback literature) rather than any single taxonomy.
- **Consequence:** The set is a chosen control space for v1, explicitly *not*
  claimed to be exhaustive; classified by intended learner-state change, not
  surface sentence form.

## Decision 3 — Split Speech Plan into `verbal_plan` + `delivery_plan`

- **Context:** "What to say" and "how to say it" are different concerns; mixing
  them makes the plan hard to evaluate.
- **Decision:** Represent the plan as two parts: `verbal_plan` (segments,
  content) and `delivery_plan` (prosodic/delivery controls), where `delivery_plan`
  may be empty.
- **Evidence:** This separation lets D5 (sparsity/necessity of delivery) and D6
  (delivery–pedagogy alignment) be assessed independently from verbal adequacy.
- **Consequence:** Enables the D5/D6 diagnostic pair and makes "minimum
  justified control" expressible.

## Decision 4 — Evaluator is a diagnostic instrument, not a scalar reward

- **Context:** A single scalar reward hides *where* a plan fails and invites
  over-optimization.
- **Decision:** Evaluator v0.1 scores six independent dimensions (D1–D6) plus
  zero-or-more critical flags, with no scalar reward and no hidden penalties.
- **Evidence:** Six dimensions — D1 Intent Fidelity, D2 Content Faithfulness &
  Boundary, D3 Learner-State Compatibility, D4 Instructional Adequacy, D5
  Delivery Necessity/Sparsity, D6 Delivery-Pedagogy Alignment — each reported
  separately; flags reported as flags, never converted to score.
- **Consequence:** Results are read as multi-dimensional evidence, not a number
  to maximize; D5 over-specification and D6 under-specification stay separable.

## Decision 5 — Freeze Evaluator v0.1 after Protocol v0.2 confirmatory

- **Context:** An instrument used to compare prompts must itself be stable and
  validated, or prompt differences are confounded with instrument drift.
- **Decision:** Freeze Evaluator v0.1 only after the Diagnostic Protocol v0.2
  confirmatory run (`20260829T154127Z`) passed semantic validation.
- **Evidence:** Confirmatory run on the frozen holdout dataset (24 pairs /
  48 plans) reached **semantic validation PASS**.
- **Consequence:** Evaluator v0.1 + Judge Prompt v0.1 are treated as immutable
  thereafter; they are never edited to improve downstream results.

## Decision 6 — Upgrade baseline evaluation to Protocol v0.2

- **Context:** Protocol v0.1 conflated judge acquisition/retry failures with
  semantic evaluation; a failed API call should not look like a low score.
- **Decision:** Adopt Protocol v0.2, which separates operational acquisition
  (attempt retry, max 3 per semantic repeat) from semantic evaluation, and
  records every physical attempt in `evaluations.jsonl`.
- **Evidence:** Baseline v0.2 run `20260830T095934Z` recorded 73/90 successful
  semantic repeats from 136 physical attempts, with failures preserved rather
  than dropped.
- **Consequence:** "Failed calls are not silently dropped" became a project
  invariant; eligibility is computed from successful semantic repeats, and
  operational vs semantic quality are reported separately.

## Decision 7 — Prompt v0.2 targets D5 (primary) and D4 (secondary)

- **Context:** The v0.1 baseline showed unnecessary/overly dense delivery
  controls (low D5) and some weak instructional adequacy (low D4), especially
  in explanation and hard/adversarial cases.
- **Decision:** Design Prompt v0.2 to improve D5 Delivery Necessity/Sparsity as
  primary and D4 Instructional Adequacy as secondary, while preserving strong
  v0.1 performance on D1/D2/D3/D6.
- **Evidence:** Recorded in `docs/generator_prompt_v0.2_design_spec.md`
  (primary/secondary weaknesses) and `..._experiment_protocol.md` (isolation of
  prompt as the only variable).
- **Consequence:** D5/D4 become the measured success axes; D1/D2/D3/D6 become
  protected dimensions checked for regression.

## Decision 8 — Reject rc.1 (delivery mode collapse)

- **Context:** rc.1 raised D5, but that came at the price of an empty
  `delivery_plan` for every case.
- **Decision:** Reject rc.1; do not freeze it.
- **Evidence:** 30/30 cases produced `delivery_plan = {}`. A candidate that
  collapses delivery to always-empty can look sparse without being correct —
  D5 alone cannot see this (under-specification is D6's job).
- **Consequence:** Established the rule that D5 must be read **together with**
  the measured delivery distribution; a high D5 alone is never accepted.

## Decision 9 — rc.2 uses minimum justified control

- **Context:** rc.1 over-corrected to zero control; the v0.1 baseline had too
  much. Neither is right.
- **Decision:** rc.2 specifies **minimum justified control**: sparse delivery,
  emitted only when case evidence clearly justifies it, not zero control.
- **Evidence:** rc.2 generation produced 27 empty / 3 non-empty (vs rc.1's
  30/0 and v0.1's 2 empty / 28 non-empty); the 3 non-empty cases are
  Corrective Feedback and Scaffolding, where prosody is pedagogically relevant.
- **Consequence:** rc.2 broke the collapse without returning to v0.1's
  over-specification.

## Decision 10 — rc.2 is worth held-out evaluation

- **Context:** After the rc.2 paired development evaluation, decide whether to
  proceed toward a formal v0.2 freeze.
- **Decision:** Treat rc.2 as the v0.2 candidate and move to held-out
  evaluation / final freeze rather than more development tuning.
- **Evidence:** Paired eval `20260901T043729Z` (n=26): D5 +0.513 (CI
  [0.326, 0.699], 16 improved / 0 worsened); D4 +0.135 (CI [0.017, 0.252]);
  protected D1/D2/D3/D6 all non-significant; delivery 27/3 not 30/0.
- **Consequence:** Development evidence supports rc.2; it is *not yet*
  confirmatory, so no final freeze occurs until a held-out run is planned and
  executed.

## Decision 11 — Stop tuning on the 30 development cases

- **Context:** Continued tuning on the same 30 Pilot cases risks overfitting to
  the development set.
- **Decision:** Do not keep iterating the prompt on these 30 cases; do not
  create an rc.3 without clear systematic evidence.
- **Evidence:** The 30 cases have now informed rc.1 and rc.2 and both paired
  evaluations; further gains measured here would not generalize.
- **Consequence:** Any further version change requires new held-out evidence;
  the next step is held-out evaluation planning, not more development-set
  optimization.
