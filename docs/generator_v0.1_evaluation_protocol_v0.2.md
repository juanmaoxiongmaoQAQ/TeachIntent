# TeachIntent Generator v0.1 Baseline Evaluation Protocol v0.2

**Status: Frozen**

| Field | Value |
|---|---|
| Status | **Frozen** |
| Drafted | 2026-08-30 |
| Frozen | **2026-08-30** |
| `protocol_version` | `v0.2` |
| `protocol_status` | `Frozen` |
| Supersedes | none (operational revision of Protocol v0.1, which stays Frozen) |

> Drafted 2026-08-30 and **frozen 2026-08-30** after explicit human QC
> approval. This document is an **operational revision** of
> `generator_v0.1_evaluation_protocol_v0.1.md`, which remains **Frozen** and
> **unmodified**.
>
> The `protocol_document_sha256` recorded in any run manifest MUST be the SHA256
> of **this frozen text**. Any SHA computed from an earlier Draft revision of
> this file is void.

---

## 0. Scope of this revision (read first)

Protocol v0.2 changes **only** *how a valid Evaluator artifact is acquired*.

It does **not** change:

* the semantic population;
* the Evaluator;
* the Judge condition or Judge Prompt;
* case eligibility;
* any aggregation mathematics;
* critical-flag rules;
* the absence of a Generator PASS/FAIL verdict.

The single purpose of v0.2 is:

> **valid-artifact acquisition reliability**

### 0.1 Why v0.2 exists

The first formal baseline run executed under Protocol v0.1 produced:

| Field | Value |
|---|---|
| Run ID | `20260830T063227Z` |
| Successful semantic evaluations | `58 / 90` |
| Failed semantic evaluations | `32 / 90` |
| Eligible cases | `19 / 30` |
| `evidence_grounding_error` | 18 |
| `judge_response_parse_error` | 11 |
| `judge_api_error` | 2 |
| `evidence_source_error` | 1 |

Only **2 of 32** failures were API/network errors. The remaining **30** were
cases where the Judge produced *something* but no **legal Evaluator artifact**
was formed. Because v0.1 allowed exactly one physical attempt per semantic
repeat, those 30 repeats were lost, and **11 of 30 cases** were operationally
excluded.

That is an **operational** problem, not a semantic one. v0.2 addresses it at the
runner layer only.

### 0.2 The governing principle

> The purpose of one **semantic repeat** is to obtain **one legal Evaluator
> artifact**.

Therefore:

* if an attempt **does not** produce a legal artifact, it MAY be re-attempted
  within the pre-declared maximum number of attempts;
* if an attempt **does** produce a legal artifact, that semantic repeat is
  **immediately accepted and closed**.

### 0.3 The absolute prohibition

A semantic repeat that has produced a legal artifact is **never** re-attempted,
regardless of:

1. how low the D1–D6 scores are;
2. how low the `overall_score` is;
3. how many critical flags were raised;
4. how an intent or block is performing;
5. any human judgement that the Judge is "too strict";
6. how poor the Generator output appears to be.

**Retry is triggered exclusively by the absence of a legal artifact.**
Low quality is a *result*; it is never a *retry condition*.

---

## 1. Purpose

Identical to Protocol v0.1 Section 1. This protocol defines how the
**already-frozen Generator v0.1 outputs** are evaluated with the
**already-validated Evaluator v0.1** in order to establish a **Generator v0.1
semantic baseline**.

The output of a run executed under this protocol is:

> **Generator v0.1 Baseline Evaluation (Protocol v0.2)**

It is explicitly **not** a Generator PASS/FAIL validation. No Generator-level
acceptance threshold is defined or introduced (Section 15).

---

## 2. Prerequisite: Evaluator v0.1 Validity

Unchanged from Protocol v0.1 Section 2. The Evaluator's semantic validity was
established independently by the frozen **Evaluator Diagnostic Protocol v0.2**
confirmatory experiment, run `20260829T154127Z`:

| Field | Value |
|---|---|
| Semantic Validation | **PASS** |
| Primary Directional Accuracy | `23/24 = 95.83%` |
| Mean Primary Targeted Drop | `2.6528` |
| Protected-Dimension MAE | `0.2552` |
| Within-one Repeatability | `99.62%` |
| Semantic Pair Coverage | `24/24` |
| Per-family Coverage | `8/8` families, all `3/3` eligible |

**This protocol does not modify, re-tune, or re-validate the Evaluator.**

---

## 3. Semantic Population

The evaluation population is **identical** to Protocol v0.1 Section 3: the
**30 canonical Generator v0.1 Pilot outputs**.

| Block | Block name | Source run ID | Source path | Cases |
|---|---|---|---|---|
| A | `controlled_contrast` | `20260827-002543` | `results/pilot/block_a/20260827-002543` | 12 |
| B | `cross_domain_generalization` | `20260827-051547` | `results/pilot/block_b/20260827-051547` | 12 |
| C | `hard_adversarial` | `20260827-074602` | `results/pilot/block_c/20260827-074602` | 6 |
| | | | **Total** | **30** |

### 3.1 Reuse-only, no regeneration

Inherited verbatim from Protocol v0.1 Section 3.1. The following are
**prohibited**:

* regenerate any Pilot output;
* replace any Pilot output with a later run;
* cherry-pick among multiple runs of the same case;
* drop low-quality or low-scoring cases;
* manually repair, rewrite, normalize, or post-edit a generated Speech Plan;
* retry a Generator call that failed in the canonical run.

There is exactly **one** canonical Generator output per case.

### 3.2 Provenance

Inherited verbatim from Protocol v0.1 Section 3.2.

```
generator_version = "v0.1"

generator_version_provenance =
  "inferred_from_frozen_generator_stack_and_prompt_v0.1; source Pilot artifacts
   do not directly record generator_version"
```

```
prompt_version = "v0.1"

prompt_version_provenance =
  "artifact_directly_recorded; cases/<case_id>/prompt.json and metadata.json
   both record prompt_version = v0.1 and are asserted per case"
```

### 3.3 Population integrity checks (pre-flight, offline)

Inherited verbatim from Protocol v0.1 Section 3.3. Before **any** Judge call the
runner MUST verify and abort on any failure:

1. all three run directories and their `manifest.json` exist;
2. case counts are exactly **12 / 12 / 6**, total **30**;
3. all 30 `case_id` values are unique;
4. every case directory contains the six required artifacts;
5. every case's `metadata.json` records `outcome = success`;
6. every case's `prompt_version` is `v0.1`;
7. every case's raw response re-parses and re-validates through the frozen
   Layer-0 contract.

### 3.4 Population fingerprint (`source_population_sha256`)

Inherited verbatim from Protocol v0.1 Section 3.4. The population is pinned by
content using the SHA256 of the six raw source artifacts of all 30 cases, with
records sorted by `case_id` and serialized as canonical JSON:

```python
json.dumps(
    population_records,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

The frozen expected value is **unchanged**:

```
source_population_sha256 =
    a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b
```

Requirements:

* the fingerprint MUST be **recomputed and verified before every formal run**;
* dry-run MUST print `source_population_sha256`, its expected value, and the
  match flag;
* `run_manifest.json` MUST record all three values;
* a mismatch MUST **fail fast before any Judge call**.

---

## 4. Evaluator / Judge Condition

**Completely unchanged from Protocol v0.1 Section 4.**

| Field | Value |
|---|---|
| Evaluator version | `v0.1` |
| Judge provider | `openrouter` |
| Judge model (requested) | `qwen/qwen3.5-plus-20260420` |
| Judge Prompt version | `v0.1` |
| `temperature` | `0` |
| `structured_output_enabled` | `false` |
| `self_repair_enabled` | `false` |
| `evaluator_retry_enabled` | `false` |

### 4.1 Two distinct retry concepts (MUST NOT be conflated)

| Concept | Value | Layer | Meaning |
|---|---|---|---|
| `evaluator_retry_enabled` | `false` | Evaluator v0.1 (frozen) | Inside a single `evaluate_speech_plan` call the Evaluator makes **exactly one** Judge completion. No retry, no self-repair, no fallback. |
| `baseline_attempt_retry_enabled` | `true` | baseline runner (v0.2) | The **runner** may invoke the frozen Evaluator again for the same semantic repeat, up to `max_attempts_per_semantic_repeat`, when — and only when — the previous invocation failed to produce a legal artifact. |

**Protocol v0.2 does not modify Evaluator v0.1's retry behaviour in any way.**
Both values are recorded separately in the run manifest and in `summary.json`.

### 4.2 No reimplementation

Inherited verbatim from Protocol v0.1 Section 4.1. The runner MUST call
`teachintent.evaluator.evaluate_speech_plan` once per physical attempt. It MUST
NOT copy, fork, re-implement, or wrap-around-modify any Evaluator logic, and
MUST NOT convert an operational failure into a semantic score.

### 4.3 Evaluation unit inputs

Inherited verbatim from Protocol v0.1 Section 4.2. One physical attempt receives
exactly:

* the restored validated input document (`input.json`);
* the restored raw Generator response (`raw_response.txt`).

Only `input_case_id`, `generator_version`, and `prompt_version` are passed as
run context. Experiment metadata (block, intent, case ordering, attempt index)
never reaches the Evaluator or the Judge.

---

## 5. Semantic Repeats and Physical Attempts

### 5.1 Semantic repeats (unchanged)

Every case receives **exactly 3 semantic repeats**:

```
repeat_index ∈ {1, 2, 3}
```

```
30 cases × 3 semantic repeats = 90 planned semantic evaluations
```

This is **frozen and unchanged** from v0.1.

### 5.2 Physical attempts (new in v0.2)

Each **semantic repeat** may consume up to **3 physical attempts**:

```
attempt_index ∈ {1, 2, 3}
```

A physical attempt is **one** invocation of the frozen Evaluator (and therefore
at most one Judge completion, because `evaluator_retry_enabled = false`).

### 5.3 The distinction, by example

```
case X / repeat 1
    attempt 1 -> judge_response_parse_error
    attempt 2 -> valid artifact
    semantic repeat 1 = SUCCESS   (2 physical attempts)

case X / repeat 2
    attempt 1 -> valid artifact
    semantic repeat 2 = SUCCESS   (1 physical attempt)

case X / repeat 3
    attempt 1 -> evidence_grounding_error
    attempt 2 -> evidence_grounding_error
    attempt 3 -> valid artifact
    semantic repeat 3 = SUCCESS   (3 physical attempts)
```

This case still has **exactly 3 semantic repeats**, not 7. It consumed 6
physical attempts.

### 5.4 Call-budget wording (mandatory)

To avoid semantic confusion, the run manifest MUST report the three quantities
**separately** and MUST NOT collapse them into a single `expected_calls`:

| Field | Value | Meaning |
|---|---|---|
| `planned_semantic_repeats` | `90` | the frozen design size |
| `max_possible_physical_attempts` | `270` | worst-case upper bound (`90 × 3`) |
| `actual_physical_attempts` | filled after the run | what actually happened |

Writing `expected_calls = 270` is **prohibited**: 270 is a worst-case bound on
Judge calls, not the size of the experiment.

---

## 6. Attempt Retry Policy

### 6.1 Retryable failure taxonomy (frozen)

Attempt retry is permitted **only** when the attempt failed to produce a legal
Evaluator artifact **and** the failure type is one of:

```
judge_api_error
judge_response_parse_error
judge_output_schema_error
evidence_source_error
evidence_grounding_error
```

All five mean: *the current attempt did not form a legal Evaluator artifact that
can enter semantic aggregation.*

### 6.2 Non-retryable failure taxonomy (frozen)

The following MUST NOT trigger an attempt retry:

```
setup_input_jsonschema_error
setup_input_pydantic_error
setup_run_context_error
setup_judge_config_error
internal_evaluator_error
```

These are **fatal** for the semantic repeat and are recorded as-is.

### 6.3 Layer-0 structural failure of a canonical Generator output

If a canonical Generator output fails the Layer-0 gate (failure type
`gate_<stage>`, i.e. `gate_response_parse`, `gate_json_schema`,
`gate_pydantic`), this is an **invariant violation**, not a Judge flakiness
issue:

* it MUST **NOT** be masked by retrying the Judge;
* the semantic repeat is terminated immediately (no further attempts);
* the event is recorded explicitly in the attempt log and surfaced in the run
  artifacts.

Because the canonical population is verified Layer-0-restorable during
pre-flight (Section 3.3), observing this at attempt time indicates a defect in
the runner or in the restorable-population guarantee, and must be investigated
rather than retried away.

### 6.4 Conditions that MUST NEVER trigger a retry

Repeated for emphasis — none of the following is a retry condition:

1. a legal Evaluator artifact **was** produced;
2. D1–D6 scores are low;
3. `overall_score` is low;
4. critical flags were raised;
5. an intent performs poorly;
6. a block performs poorly;
7. a human considers the Judge "too strict";
8. the Generator output quality is poor.

The runner implements this structurally: the retry decision reads only
`(artifact is None or not legal) and failure_type ∈ retryable_taxonomy`. Scores
and flags are not inputs to that decision.

---

## 7. Retry Termination Rules

For each semantic repeat:

### Case A — first attempt produces a legal artifact

```
attempt 1 -> legal artifact
=> STOP. No further attempt is permitted for this semantic repeat.
   attempt_count = 1
   successful_attempt_index = 1
   semantic_repeat_success = true
```

### Case B — previous attempt was a retryable failure

```
attempt k -> retryable failure, k < max_attempts
=> attempt k+1 is permitted (subject to the backoff in Section 8).
```

### Case C — all attempts exhausted

```
attempt 1, 2, 3 -> no legal artifact
=> semantic_repeat_success = false
   successful_attempt_index = null
   final_artifact = null
   attempt_count = 3
   ALL attempts are recorded.
   A 4th attempt is PROHIBITED.
```

### Case D — non-retryable failure

```
attempt k -> non-retryable failure (Section 6.2 / 6.3)
=> STOP immediately. No further attempt.
   semantic_repeat_success = false
```

`max_attempts_per_semantic_repeat = 3` is a hard bound enforced by the runner.

---

## 8. Attempt Timing / Backoff Policy

Judge calls MUST NOT be issued at high frequency. Before a retry attempt the
runner sleeps according to this frozen policy:

| Previous failure type | Sleep before next attempt |
|---|---|
| `judge_api_error` | `5 s` before attempt 2, `15 s` before attempt 3 |
| `judge_response_parse_error` | `2 s` |
| `judge_output_schema_error` | `2 s` |
| `evidence_source_error` | `2 s` |
| `evidence_grounding_error` | `2 s` |

Formally:

```python
RETRY_BACKOFF_SECONDS = {
    "judge_api_error": (5.0, 15.0),
    "DEFAULT": (2.0, 2.0),
}
# sleep_before_attempt(attempt_index=k+1) = RETRY_BACKOFF_SECONDS[ft][k-1]
```

No sleep occurs:

* before attempt 1;
* after a successful attempt;
* after a non-retryable failure (the repeat stops anyway).

### 8.1 Implemented at the runner layer only

The backoff lives in the baseline runner. **Nothing under
`src/teachintent/evaluator/` is modified.** The sleep function is injectable so
that offline tests never wait in real time.

---

## 9. Attempt Logging (complete)

**Every physical attempt is persisted.** A later success never overwrites an
earlier failure.

### 9.1 Storage layout

`evaluations.jsonl` contains **one JSON record per semantic repeat** (90 lines in
a complete run). Each record embeds an `attempts` array holding every physical
attempt of that repeat, in attempt order.

### 9.2 Per-attempt fields (all mandatory)

```
case_id
block
intent
repeat_index
attempt_index
started_at
completed_at
outcome                 # "artifact" | "failure"
failure_type            # null on success; frozen Evaluator taxonomy otherwise
failure_summary         # null on success
artifact                # full verbatim Evaluator artifact dump, null on failure
judge_model_reported    # as reported by the provider; null when no completion
run_metadata            # full Evaluator RunMetadata block
retryable               # bool: was this failure in the retryable taxonomy
```

### 9.3 Per-semantic-repeat fields (record level)

```
case_id
block
intent
repeat_index
semantic_repeat_success
successful_attempt_index
attempt_count
attempt_failure_types
final_artifact
attempts                # the array from 9.2
```

---

## 10. Semantic Repeat Result

Every semantic repeat produces exactly this structure:

```json
{
  "case_id": "...",
  "repeat_index": 2,
  "semantic_repeat_success": true,
  "successful_attempt_index": 3,
  "attempt_count": 3,
  "attempt_failure_types": [
    "evidence_grounding_error",
    "judge_response_parse_error"
  ],
  "final_artifact": { "...": "verbatim Evaluator artifact" }
}
```

When all attempts fail:

```json
{
  "case_id": "...",
  "repeat_index": 3,
  "semantic_repeat_success": false,
  "successful_attempt_index": null,
  "attempt_count": 3,
  "attempt_failure_types": [
    "judge_api_error",
    "judge_api_error",
    "judge_api_error"
  ],
  "final_artifact": null
}
```

`attempt_failure_types` is ordered by `attempt_index` and keeps **every**
failure, including duplicates.

---

## 11. Case Eligibility (UNCHANGED)

Inherited verbatim from Protocol v0.1 Section 6.2.

| Successful **semantic repeats** | Status |
|---|---|
| 3 / 3 | eligible |
| 2 / 3 | eligible |
| 1 / 3 | **excluded** — `excluded_due_to_operational_failure` |
| 0 / 3 | **excluded** — `excluded_due_to_operational_failure` |

Eligibility counts **semantic repeat successes**, **never** physical attempt
successes.

Worked example:

```
repeat 1: attempt 2 succeeded   -> semantic repeat 1 SUCCESS
repeat 2: attempt 1 succeeded   -> semantic repeat 2 SUCCESS
repeat 3: attempts 1,2,3 failed -> semantic repeat 3 FAILURE
=> successful semantic repeats = 2/3
=> case eligible = true
```

**No make-up semantic repeats.** A case that loses semantic repeats to
operational failure is not re-run to "top up" to 3.

---

## 12. Aggregation (UNCHANGED)

Inherited verbatim from Protocol v0.1 Section 6. The aggregation mathematics is
**identical to v0.1**:

```
repeat artifact
  -> case-level arithmetic mean (over successful semantic repeats)
    -> global / intent / block aggregation (over eligible cases)
```

* the case is the unit of analysis;
* every eligible case is weighted equally;
* a case is **not** up-weighted because it consumed more physical attempts;
* a failed attempt is **never** counted as a score of `0`;
* a failed semantic repeat is **never** imputed as a score of `0`;
* statistics: arithmetic mean, `statistics.median`, sample stdev (`n − 1`),
  rounded to 4 decimal places.

The only difference from v0.1 is that a semantic repeat now has a *higher
chance* of producing an artifact — the value that enters the mean is still
exactly one artifact per successful semantic repeat.

---

## 13. Critical Flags (UNCHANGED)

Inherited verbatim from Protocol v0.1 Section 11.

Case-level flags are computed from **successful semantic repeats only**, using
**strict majority**:

```
count(flag) > successful_repeat_count / 2
```

| Successful semantic repeats | Required to raise |
|---|---|
| 3 | 2 or 3 |
| 2 | 2 |
| 1 | n/a — case excluded |
| 0 | n/a — case excluded |

**Attempt-level failure and critical flag are different concepts and MUST NOT be
conflated.** A failed attempt contributes no flag evidence and no denominator
mass. A raised critical flag never triggers a retry (Section 6.4).

---

## 14. Metrics

### 14.1 Semantic baseline metrics (all v0.1 metrics retained)

Global (over eligible cases): eligible case count, D1–D6 mean / median / stdev,
overall score mean / median, case-level critical flag counts and total, excluded
case count and IDs, Judge failure taxonomy counts.

Per-intent and per-block: `n_total` / `n_eligible` / `n_excluded` (plus
`excluded_case_ids`) reported **together**, D1–D6 mean, overall mean, and (per
intent) critical flag count. A single ambiguous `n` is not permitted.

### 14.2 Operational attempt metrics (new in v0.2)

A v0.2 run MUST additionally report:

| Metric | Definition |
|---|---|
| `planned_semantic_repeats` | `90` |
| `successful_semantic_repeats` | count of semantic repeats with `semantic_repeat_success = true` |
| `failed_semantic_repeats` | count of semantic repeats with `semantic_repeat_success = false` |
| `semantic_repeat_success_rate` | `successful_semantic_repeats / planned_semantic_repeats` |
| `total_physical_attempts` | total number of physical attempts actually executed |
| `successful_first_attempts` | semantic repeats whose **attempt 1** produced the artifact |
| `successful_after_retry` | semantic repeats that succeeded with `successful_attempt_index > 1` |
| `exhausted_after_max_attempts` | semantic repeats that used all 3 attempts with no legal artifact |
| `mean_attempts_per_semantic_repeat` | `total_physical_attempts / planned_semantic_repeats` |
| `attempt_failure_taxonomy_counts` | counts over **all failed attempts** by failure type |
| `first_attempt_success_rate` | `successful_first_attempts / planned_semantic_repeats` |
| `retry_recovery_rate` | `successful_after_retry / retryable_first_attempt_failures` |
| `max_possible_physical_attempts` | `270` |
| `actual_physical_attempts` | `total_physical_attempts` (after the run) |

with the denominator defined exactly as:

```
retryable_first_attempt_failures =
    number of semantic repeats whose attempt 1 failed
    with a failure_type in the retryable taxonomy (Section 6.1)
```

`retry_recovery_rate` is `null` when
`retryable_first_attempt_failures == 0`.

`attempt_failure_taxonomy_counts` counts **every** failed attempt (so up to 2
failures per semantic repeat), whereas the v0.1 `failure_taxonomy_counts`
counts **one** failure type per failed semantic repeat. Both are reported and
are not interchangeable.

### 14.3 Per-case diagnostics (v0.1 retained + retry info added)

Every case (eligible and excluded) keeps the v0.1 fields (`case_id`, `block`,
`intent`, `successful_repeats`, `eligible`, `exclusion_reason`, D1–D6 mean,
overall mean, critical flags, repeat-level flags, failure types, weak /
severe dimensions) and additionally reports:

```
successful_semantic_repeats
failed_semantic_repeats
total_physical_attempts
first_attempt_successes
recovered_by_retry_count
exhausted_repeat_count
attempt_failure_types
```

---

## 15. No Generator PASS / FAIL

Unchanged from Protocol v0.1 Section 12. **This protocol defines no
Generator-level acceptance threshold.** The diagnostic thresholds
(dimension mean `< 3.0` weak, `< 2.0` severe) remain **diagnostic only** and
carry no acceptance meaning.

---

## 16. Artifacts

Output directory (distinct from v0.1 so Run 1 can never be overwritten):

```
results/generator_v0_1_baseline_evaluation_v0_2/<run_id>/
```

| File | Content |
|---|---|
| `run_manifest.json` | full provenance + condition + attempt policy (Section 17) |
| `evaluations.jsonl` | one record per semantic repeat, embedding every physical attempt (Section 9) |
| `case_metrics.csv` | per-case metrics + diagnostics + retry info (Section 14.3) |
| `intent_metrics.csv` | per-intent metrics (Section 14.1) |
| `block_metrics.csv` | per-block metrics (Section 14.1) |
| `summary.json` | global metrics + operational attempt metrics + provenance |
| `README.md` | human-readable run summary |

`results/` is git-ignored. These artifacts are never committed.

---

## 17. Run Manifest (v0.2 additions)

In addition to every v0.1 field (Section 14 of v0.1), `run_manifest.json` MUST
record:

```
protocol_version                     = "v0.2"
protocol_status                      = "Frozen"
protocol_document_sha256

source run IDs
source run paths
source_population_sha256
source_population_sha256_expected
source_population_sha256_match

generator_version                    = "v0.1"
generator_version_provenance
prompt_version                       = "v0.1"
prompt_version_provenance

evaluator_version                    = "v0.1"

judge_prompt_version                 = "v0.1"
judge_prompt_sha256
judge_provider
judge_model_requested
judge_model_reported

temperature                          = 0
structured_output_enabled            = false
self_repair_enabled                  = false

evaluator_retry_enabled              = false      # Evaluator v0.1 internal
baseline_attempt_retry_enabled       = true       # baseline runner outer policy
max_attempts_per_semantic_repeat     = 3

retryable_failure_types              = [5 types, Section 6.1]
non_retryable_failure_types          = [5 types, Section 6.2]
retry_backoff_policy                 = {judge_api_error: [5, 15], DEFAULT: [2, 2]}

case_count                           = 30
semantic_repeats_per_case            = 3
planned_semantic_repeats             = 90
max_possible_physical_attempts       = 270
actual_physical_attempts             = <filled after the run>
```

The API key is never printed, logged, or written to any artifact.

---

## 18. Run 1 Is a Permanent Historical Record

Protocol v0.1 Run 1:

| Field | Value |
|---|---|
| Run ID | `20260830T063227Z` |
| Artifact directory | `results/generator_v0_1_baseline_evaluation/20260830T063227Z/` |
| Successful semantic evaluations | `58 / 90` |
| Eligible cases | `19 / 30` |
| Failure taxonomy | `evidence_grounding_error` 18, `judge_response_parse_error` 11, `judge_api_error` 2, `evidence_source_error` 1 |

Run 1 is:

* **permanently preserved** — never deleted, never overwritten;
* **never merged** into a v0.2 run;
* **never topped up** by re-running only its failed samples;
* **not** a complete 30-case baseline;
* the empirical justification for this operational revision.

Protocol v0.2 runs **from scratch**: all 30 cases × 3 semantic repeats, fully
independently of Run 1. v0.2 runs are written under
`results/generator_v0_1_baseline_evaluation_v0_2/`, which is a different
directory from Run 1, so Run 1 is structurally unreachable by a v0.2 run.

Protocol v0.1 remains Frozen and unmodified, and
`scripts/run_generator_v0_1_baseline_evaluation.py` remains available for
historical reproduction of Run 1's behaviour.

---

## 19. Dry-Run and Formal-Mode Preconditions

### 19.1 Dry-run

`--dry-run` MUST perform all population-integrity, fingerprint, and condition
checks offline and MUST print at least:

```
Protocol version: v0.2
Protocol status: Frozen
protocol_document_sha256 = <SHA256 of this frozen document>

source runs:
A = 20260827-002543
B = 20260827-051547
C = 20260827-074602

A/B/C = 12/12/6
total cases = 30

source_population_sha256
expected source_population_sha256
SHA match = True

Generator = v0.1
Prompt = v0.1
Evaluator = v0.1
Judge = qwen/qwen3.5-plus-20260420

semantic repeats per case = 3
planned semantic repeats = 90

max attempts per semantic repeat = 3
max possible physical attempts = 270

baseline attempt retry = enabled

retryable failure types:
- judge_api_error
- judge_response_parse_error
- judge_output_schema_error
- evidence_source_error
- evidence_grounding_error

evaluator internal retry = disabled

No Judge API call was made.
```

Dry-run requires **no** `OPENROUTER_API_KEY` and MUST make **no** Judge API
call.

### 19.2 Formal-mode credential check (fail-fast)

Formal mode MUST verify that `OPENROUTER_API_KEY` is present and non-empty
**before** constructing the Judge and **before** the first physical attempt. If
the key is missing or empty the runner MUST:

* exit with code **2**;
* create **no** formal result run directory;
* not enter the attempt loop;
* never print the key.

It MUST NOT silently fall back to dry-run.

### 19.3 Frozen design parameters

The runner MUST reject (fail-fast):

* `--repeats != 3`;
* `--max-attempts != 3`.

---

## 20. Prohibitions

Under this protocol it is not permitted to:

* call the Judge during dry-run;
* retry an attempt that produced a legal artifact, for any reason
  (Section 6.4);
* retry a non-retryable failure (Section 6.2);
* mask a Layer-0 structural failure of a canonical Generator output by retrying
  the Judge (Section 6.3);
* modify the Generator, Generator Prompt, Evaluator, Judge Prompt, or Judge
  model;
* modify `evaluator_retry_enabled` (Evaluator v0.1 internal retry stays `false`);
* modify the Pilot dataset, the three canonical Generator runs, or
  `source_population_sha256`;
* modify the frozen diagnostic protocol v0.2, holdout v0.2, or the confirmatory
  results;
* modify **Protocol v0.1** (`docs/generator_v0.1_evaluation_protocol_v0.1.md`)
  or **Run 1** (`results/.../20260830T063227Z/`);
* re-weight, re-order, or re-select the population based on observed scores;
* add a Generator PASS/FAIL threshold under this protocol version.

---

## 21. Implementation and Testing Requirements

Minimum test coverage:

1. exactly 3 semantic repeats per case;
2. semantic repeat indexes are `1 / 2 / 3`;
3. attempt indexes are `1 / 2 / 3`;
4. first-attempt success → no further attempt;
5. retryable failure → retry occurs;
6. success on attempt 2 → stop;
7. success on attempt 3 → stop;
8. 3 failures → semantic repeat failure;
9. no attempt 4;
10. a low but **valid** semantic score does not trigger retry;
11. a critical flag does not trigger retry;
12–16. each of the five retryable failure types is retryable;
17. `internal_evaluator_error` is **not** retryable;
18. setup errors are **not** retryable;
19. case eligibility is based on semantic repeats, not attempts;
20. failed attempts never contribute `score = 0`;
21. case aggregation is unchanged from v0.1;
22. attempt logs preserve every failure;
23. `first_attempt_success_rate` is correct;
24. `retry_recovery_rate` is correct;
25. exhausted-repeat count is correct;
26. `source_population_sha256` is unchanged;
27. Protocol v0.1 is unchanged;
28. the v0.1 runner behaviour is unchanged;
29. dry-run makes no API call;
30. missing API key in formal mode fails fast.

Backoff MUST be injectable / mockable: tests MUST NOT actually sleep 5 s or
15 s.

---

## 22. Status History

| Date | Status | Note |
|---|---|---|
| 2026-08-30 | **Draft** | Operational revision of v0.1. Adds the semantic-repeat / physical-attempt distinction, a frozen retryable-failure taxonomy, `max_attempts_per_semantic_repeat = 3`, backoff timing, complete attempt logging, and operational attempt metrics. No semantic logic changed. |
| 2026-08-30 | **Frozen** | Human QC of the v0.2 implementation passed. Status changed to Frozen on 2026-08-30. **The Document SHA256 changed at freeze time** (the header, Section 17, Section 19.1 and Sections 22–23 were edited); the Draft-revision SHA is void and MUST NOT be used in any run manifest. Protocol v0.1, the v0.1 runner, Run 1, and all other frozen components remain unmodified. |

---

## 23. Change Control

This document is **Frozen** as of **2026-08-30**, following explicit human QC
approval of the v0.2 implementation.

Consequences of the freeze:

* the text of this file MUST NOT be edited; any edit would change
  `protocol_document_sha256` and invalidate every v0.2 run recorded against it;
* `protocol_status` in every subsequent v0.2 run manifest is `"Frozen"`;
* `protocol_document_sha256` in every subsequent v0.2 run manifest MUST be the
  SHA256 of this frozen text (the Draft-revision SHA is void);
* any change to the fields listed below requires a new protocol version
  (`v0.3`), not an edit to this file.

Fields frozen by v0.1 and **inherited unchanged** here (changing any of them
requires a new protocol version and invalidates runs recorded against both
v0.1 and v0.2):

1. the three canonical source run IDs and the 12 / 12 / 6 case split;
2. `source_population_sha256`;
3. the population of 30 cases;
4. `semantic_repeats_per_case = 3` and `planned_semantic_repeats = 90`;
5. the semantic repeat labelling `repeat_index ∈ {1, 2, 3}`;
6. case eligibility (`≥ 2` successful **semantic repeats**) and the "failures are
   never scored as zero" rule;
7. case-level equal-weight aggregation;
8. Evaluator v0.1 and its call contract;
9. Judge condition — `openrouter` / `qwen/qwen3.5-plus-20260420` /
   `temperature = 0` / `structured_output = false` / `self_repair = false` /
   `evaluator_retry_enabled = false`;
10. Judge Prompt v0.1 and its SHA256;
11. the absence of any Generator PASS/FAIL threshold.

New in v0.2 and frozen **as of 2026-08-30**:

12. `max_attempts_per_semantic_repeat = 3` (attempt 4 is prohibited);
13. the retryable failure taxonomy (Section 6.1);
14. the non-retryable failure taxonomy (Section 6.2);
15. the rule that a legal artifact immediately terminates the semantic repeat;
16. the retry backoff policy (Section 8);
17. the per-attempt logging contract (Section 9).
