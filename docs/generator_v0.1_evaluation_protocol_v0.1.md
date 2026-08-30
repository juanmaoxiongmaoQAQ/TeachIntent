# TeachIntent Generator v0.1 Baseline Evaluation Protocol v0.1

**Status: Frozen**

> Frozen: 2026-08-29. This protocol is the authoritative contract for the
> Generator v0.1 baseline evaluation run. Changing any frozen field below
> (Section 18) invalidates any run recorded against it.

## Frozen Contract (summary)

| Field | Frozen value |
|---|---|
| Canonical source run IDs | `20260827-002543`, `20260827-051547`, `20260827-074602` |
| Source population SHA256 | `a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b` |
| Cases | `30` (Block A `12` / Block B `12` / Block C `6`) |
| Repeats | `3` (`repeat ∈ {1, 2, 3}`) |
| Expected calls | `90` |
| Evaluator version | `v0.1` |
| Judge Prompt version | `v0.1` |
| Judge provider | `openrouter` |
| Judge model (requested) | `qwen/qwen3.5-plus-20260420` |
| `temperature` | `0` |
| `structured_output_enabled` | `false` |
| `retry_enabled` | `false` |
| `self_repair_enabled` | `false` |
| Verdict | **none** — descriptive baseline only (Section 12) |

---

## 1. Purpose

This protocol defines how the **already-frozen Generator v0.1 outputs** are
evaluated with the **already-validated Evaluator v0.1**, in order to establish a
**Generator v0.1 semantic baseline**.

The output of a run executed under this protocol is:

> **Generator v0.1 Baseline Evaluation**

It is explicitly **not**:

> ~~Generator v0.1 Validation PASS / FAIL~~

This protocol does **not** define a Generator-level acceptance threshold and
does **not** introduce one. See Section 12.

---

## 2. Prerequisite: Evaluator v0.1 Validity

The Evaluator v0.1 is used here as a measuring instrument. Its semantic
validity was established independently by the frozen
**Evaluator Diagnostic Protocol v0.2** confirmatory experiment.

The final stable networked replication referenced by this protocol:

| Field | Value |
|---|---|
| Run ID | `20260829T154127Z` |
| Artifact directory | `results/evaluator_diagnostic_confirmatory/20260829T154127Z/` |
| Semantic Validation | **PASS** |
| Primary Directional Accuracy | `23/24 = 95.83%` |
| Mean Primary Targeted Drop | `2.6528` |
| Protected-Dimension MAE | `0.2552` |
| Within-one Repeatability | `99.62%` |
| Semantic Pair Coverage | `24/24` |
| Per-family Coverage | `8/8` families, all `3/3` eligible |

All six v0.2 acceptance criteria passed. On that basis the Evaluator v0.1 is
regarded as usable for Generator baseline evaluation.

**This protocol does not modify, re-tune, or re-validate the Evaluator.**

---

## 3. Evaluation Population

The evaluation population is fixed to the **30 canonical Generator v0.1 Pilot
outputs** produced by three pre-existing Pilot runs.

| Block | Block name | Source run ID | Source path | Cases |
|---|---|---|---|---|
| A | `controlled_contrast` | `20260827-002543` | `results/pilot/block_a/20260827-002543` | 12 |
| B | `cross_domain_generalization` | `20260827-051547` | `results/pilot/block_b/20260827-051547` | 12 |
| C | `hard_adversarial` | `20260827-074602` | `results/pilot/block_c/20260827-074602` | 6 |
| | | | **Total** | **30** |

### 3.1 Provenance of the Generator outputs

The Generator v0.1 is frozen. The three runs above are the **canonical** record
of its behaviour. They are reused as-is.

The following are **prohibited**:

* regenerate any Pilot output;
* replace any Pilot output with a later run;
* cherry-pick among multiple runs of the same case;
* drop low-quality or low-scoring cases;
* manually repair, rewrite, normalize, or post-edit a generated Speech Plan;
* retry a Generator call that failed in the canonical run.

There is exactly **one** canonical Generator output per case. No case has more
than one candidate output.

### 3.2 Per-case restorability

For each of the 30 cases the following MUST be restorable from the canonical
Pilot artifacts before any evaluation is executed:

| Item | Source artifact |
|---|---|
| validated input | `cases/<case_id>/input.json` |
| raw Generator response | `cases/<case_id>/raw_response.txt` |
| generated Speech Plan | `cases/<case_id>/parsed.json` (re-parsed and re-validated from `raw_response.txt`) |
| Generator prompt version | `cases/<case_id>/prompt.json` and `cases/<case_id>/metadata.json` (`prompt_version = v0.1`) |
| Generator run outcome | `cases/<case_id>/validation.json` (`outcome = success`) |

**Generator version — provenance (explicit).** The Pilot source artifacts do
**not** contain a `generator_version` field. The Generator version is therefore
**inferred**, not artifact-confirmed. It is stated in the manifest as:

```
generator_version = "v0.1"

generator_version_provenance =
  "inferred_from_frozen_generator_stack_and_prompt_v0.1; source Pilot artifacts
   do not directly record generator_version"
```

The inference rests on:

* `src/teachintent/generator/` — the single-pass Generator v0.1 pipeline
  (`generate_speech_plan`), whose module contract declares **Generator v0.1**;
* all three canonical runs were produced through that pipeline with
  `PROMPT_VERSION = v0.1`.

This protocol does **not** claim that the artifacts directly confirm
`generator_version`.

By contrast **`prompt_version = v0.1` IS artifact-directly-recorded**: both
`cases/<case_id>/prompt.json` and `cases/<case_id>/metadata.json` carry it, and
the runner asserts the recorded value equals `v0.1` for all 30 cases:

```
prompt_version = "v0.1"

prompt_version_provenance =
  "artifact_directly_recorded; cases/<case_id>/prompt.json and metadata.json
   both record prompt_version = v0.1 and are asserted per case"
```

### 3.3 Population integrity checks (pre-flight, offline)

Before any Judge call, the runner MUST verify and abort on any failure:

1. all three run directories and their `manifest.json` exist;
2. case counts are exactly **12 / 12 / 6**, total **30**;
3. all 30 `case_id` values are unique (no duplicates across or within blocks);
4. every case directory contains the six required artifacts;
5. every case's `metadata.json` records `outcome = success`;
6. every case's `prompt_version` is `v0.1`;
7. every case's raw response re-parses and re-validates through the frozen
   Layer-0 contract (Generator parser + JSON Schema + Pydantic).

### 3.4 Population fingerprint (`source_population_sha256`)

Pinning the three source run IDs is not sufficient: an edit to any canonical
artifact would leave the IDs unchanged. The population is therefore pinned by
content as well, as a single **population fingerprint**.

For each of the 30 cases a population record is built from the SHA256 of the six
raw source artifacts, exactly as stored on disk:

| Field | Source |
|---|---|
| `block` | `A` / `B` / `C` |
| `source_run_id` | canonical Pilot run ID |
| `case_id` | case directory name |
| `input_sha256` | `cases/<case_id>/input.json` |
| `metadata_sha256` | `cases/<case_id>/metadata.json` |
| `parsed_sha256` | `cases/<case_id>/parsed.json` |
| `prompt_sha256` | `cases/<case_id>/prompt.json` |
| `raw_response_sha256` | `cases/<case_id>/raw_response.txt` |
| `validation_sha256` | `cases/<case_id>/validation.json` |

The 30 records are **sorted by `case_id`** and serialized as canonical JSON:

```python
json.dumps(
    population_records,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

The UTF-8 encoding of that string is hashed with SHA256 and reported as
lowercase hex:

```
source_population_sha256 =
    a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b
```

Requirements:

* dry-run MUST print `source_population_sha256` and its match status;
* the formal `run_manifest.json` MUST record `source_population_sha256`, its
  expected value, and the match flag;
* if **any** canonical source artifact is modified, added, removed, or replaced,
  the recomputed fingerprint differs and the run MUST **fail fast** — before any
  Judge call.

The canonical Pilot runs are read-only inputs. Nothing writes to them.

---

## 4. Evaluator

The Evaluator is fixed and reused as-is.

| Field | Value |
|---|---|
| Evaluator version | `v0.1` |
| Judge provider | `openrouter` |
| Judge model (requested) | `qwen/qwen3.5-plus-20260420` |
| Judge Prompt version | `v0.1` |
| `temperature` | `0` |
| `structured_output_enabled` | `false` |
| `retry_enabled` | `false` |
| `self_repair_enabled` | `false` |

### 4.1 No reimplementation

The baseline runner MUST call the existing Evaluator v0.1 entry point
(`teachintent.evaluator.evaluate_speech_plan`) once per planned call. The
runner MUST NOT:

* copy, fork, or re-implement any Evaluator logic;
* recompute, override, or "fix" an `overall_score`;
* convert an operational failure into a semantic score (no failure is ever
  scored as zero);
* add retry, self-repair, or fallback behaviour;
* modify anything under `src/teachintent/evaluator/`.

The Judge condition constants are imported from the frozen protocol module so
that the baseline can never silently declare a different condition.

### 4.2 Evaluation unit

One evaluation unit is **one (case, repeat)** pair. The unit inputs are exactly:

* the restored validated input document (`input.json`);
* the restored raw Generator response (`raw_response.txt`).

Only `input_case_id`, `generator_version`, and `prompt_version` are passed as
run context. Experiment metadata (block, intent, case ordering) is never passed
to the Evaluator or to the Judge.

---

## 5. Judge Repeats

Each of the 30 Generator outputs receives **3 independent Judge evaluations**.

```
repeat ∈ {1, 2, 3}
```

Total planned calls:

```
30 cases × 3 repeats = 90 Evaluator calls
```

Each call is a single independent attempt. There is no retry and no
self-repair; a failed call is recorded as an operational failure.

**Selective repetition is prohibited.** Extra repeats MUST NOT be added for
low-scoring, high-variance, or failed cases. The repeat count is uniformly 3
for every case.

The `repeat` label written into every experiment-facing artifact is strictly
`1`, `2`, `3` (1-based), matching the frozen confirmatory convention.

---

## 6. Aggregation

### 6.1 Case-level dimension mean

For each case and each dimension `D ∈ {D1..D6}`:

```
case_dimension_mean = arithmetic mean of D over that case's SUCCESSFUL repeats
```

Only successful repeats contribute. Failed repeats contribute nothing — they
are never imputed as zero.

### 6.2 Case eligibility

| Successful repeats | Status |
|---|---|
| 3 / 3 | eligible |
| 2 / 3 | eligible |
| 1 / 3 | **excluded** — `excluded_due_to_operational_failure` |
| 0 / 3 | **excluded** — `excluded_due_to_operational_failure` |

A case is **semantic-eligible** iff it has **at least 2 of 3** successful
repeats. Excluded cases are reported but do not contribute to any semantic
mean, median, or standard deviation.

**No make-up calls.** A case that loses repeats to operational failure is not
re-run to "top up" to 3.

### 6.3 Case-level overall score

Each successful repeat carries the Evaluator's deterministic `overall_score`
(`sum(D1..D6) / 24 × 100`, rounded to 2 dp — computed by the Evaluator, never
by this protocol).

```
case_overall_mean = arithmetic mean of overall_score over the case's successful repeats
```

### 6.4 Hierarchical aggregation

Global / per-intent / per-block statistics are computed over **eligible cases**,
using each case's already-computed case-level mean. Cases are the unit of
analysis; repeats are not pooled directly into global statistics. This keeps
every case equally weighted regardless of how many of its 3 repeats survived.

### 6.5 Statistical conventions

* **mean** — arithmetic mean;
* **median** — `statistics.median` (average of the two middle values for even n);
* **standard deviation** — sample standard deviation, Bessel-corrected (`n − 1`);
  reported as `0.0` when fewer than 2 eligible cases are available;
* all reported statistics are rounded to **4 decimal places**.

---

## 7. Global Metrics

A run MUST report all of the following.

1. **Eligible case count / 30** — how many of the 30 cases are
   semantic-eligible (Section 6.2).
2. **Operational success rate** — `successful_calls / expected_calls`
   (expected = 90).
3. **D1–D6 global mean** — over eligible cases, per dimension.
4. **D1–D6 median** — over eligible cases, per dimension.
5. **D1–D6 standard deviation** — over eligible cases, per dimension.
6. **Overall score mean** — over eligible cases.
7. **Overall score median** — over eligible cases.
8. **Critical flag counts** — case-level counts per flag type, plus a total.
9. **Excluded case count** — cases marked
   `excluded_due_to_operational_failure`, with their `case_id`s.
10. **Judge failure taxonomy counts** — counts per Evaluator failure type,
    using the frozen Evaluator v0.1 failure taxonomy (never a new taxonomy).

---

## 8. Per-Intent Metrics

Reported separately for each of the six pedagogical intents:

`elicitation`, `scaffolding`, `explanation`, `corrective_feedback`,
`supportive_feedback`, `extension`.

Per intent, all three counts MUST be reported together:

* **`n_total`** — every case carrying that intent, regardless of outcome;
* **`n_eligible`** — cases with at least 2 successful repeats;
* **`n_excluded`** — cases marked `excluded_due_to_operational_failure`
  (together with their `case_id`s in `excluded_case_ids`);
* **D1–D6 mean** — over the intent's **eligible** cases only;
* **overall mean** — mean of case-level overall means over eligible cases;
* **critical flag count** — total case-level critical flags raised across the
  intent's eligible cases.

Reporting only a single ambiguous `n` is **not** permitted: an operational
exclusion must never be presented as a smaller population.

The intent of a case is read from its restored input
(`pedagogical_intent.primary`); it is never re-derived, re-labelled, or
inferred.

---

## 9. Per-Block Metrics

Reported separately for Block A, Block B, and Block C.

Per block, all three counts MUST be reported together:

* **`n_total`** — every case in the block (12 / 12 / 6), regardless of outcome;
* **`n_eligible`** — cases with at least 2 successful repeats;
* **`n_excluded`** — cases marked `excluded_due_to_operational_failure`
  (with their `case_id`s in `excluded_case_ids`);
* **D1–D6 mean** — over the block's **eligible** cases only;
* **overall mean** — mean of case-level overall means over eligible cases.

As in Section 8, a single ambiguous `n` is **not** permitted.

Block membership comes from the canonical source run, not from intent or score.

---

## 10. Case-Level Diagnostics

For **every** case (eligible and excluded), the run MUST report:

* `case_id`
* `block`
* `intent`
* `successful_repeats`
* `eligible` (bool) and the exclusion marker when ineligible
* **D1–D6 mean** (empty when the case has no successful repeat)
* **overall mean** (empty when the case has no successful repeat)
* **critical flags** (case-level, Section 11) and the raw repeat-level flags
* **failure types** observed among the case's repeats, if any

### 10.1 Diagnostic thresholds

Two thresholds are reported per case as **diagnostics**:

| Condition | Label |
|---|---|
| dimension mean `< 3.0` | **weakness** |
| dimension mean `< 2.0` | **severe weakness** |

> These are **diagnostic thresholds only**. They are **not** a validated
> PASS/FAIL benchmark, are **not** derived from any empirical calibration, and
> carry **no** acceptance meaning. They exist solely to make weak regions of the
> baseline visible for inspection.

---

## 11. Critical Flags

### 11.1 Basis

Case-level critical flags are computed from **successful repeats only**. Failed
repeats contribute no flag evidence and are not counted in the denominator.

### 11.2 Strict majority

Case-level flags are computed **only for semantic-eligible cases** — that is,
cases with at least 2 successful repeats (Section 6.2). An excluded case reports
no case-level flag.

For an eligible case with `k` successful repeats, a flag `f` becomes a
**case-level flag** iff:

```
count(successful repeats raising f)  >  k / 2
```

Concretely:

| Successful repeats | Required to raise |
|---|---|
| 3 | 2 or 3 |
| 2 | 2 |
| 1 | n/a — case is excluded |
| 0 | n/a — case is excluded |

### 11.3 Raw repeat-level retention

The raw repeat-level flags are retained in full in `evaluations.jsonl` and are
also echoed in the case-level diagnostics. Case-level majority flags never
overwrite or discard repeat-level data.

---

## 12. No Generator PASS / FAIL

**This protocol defines no Generator-level acceptance threshold.**

The goal of this stage is to establish a descriptive **Generator v0.1 semantic
baseline** — where the frozen Generator stands on the frozen Evaluator, across
30 canonical outputs, with known operational caveats.

Therefore:

* no overall Generator PASS/FAIL verdict is emitted;
* no "Generator is good/bad" claim is made;
* no acceptance threshold is invented for the aggregate score;
* the diagnostic thresholds in Section 10.1 are not acceptance criteria.

The artifact is named and reported as a **Baseline Evaluation**.

---

## 13. Artifacts

Output directory:

```
results/generator_v0_1_baseline_evaluation/<run_id>/
```

| File | Content |
|---|---|
| `run_manifest.json` | full provenance + condition record (Section 14) |
| `evaluations.jsonl` | all repeat-level results, verbatim Evaluator artifacts |
| `case_metrics.csv` | per-case metrics + diagnostics (Section 10) |
| `intent_metrics.csv` | per-intent metrics (Section 8) |
| `block_metrics.csv` | per-block metrics (Section 9) |
| `summary.json` | global metrics (Section 7) + provenance |
| `README.md` | human-readable run summary |

`results/` is git-ignored. These artifacts are never committed.

---

## 14. Run Manifest

`run_manifest.json` MUST record at minimum:

* the three source Pilot run paths;
* the three source run IDs;
* **`source_population_sha256`** (Section 3.4), its expected value, and the
  match flag;
* Generator version **and** `generator_version_provenance`;
* Generator Prompt version **and** `prompt_version_provenance`;
* Evaluator version;
* Judge Prompt version;
* Judge Prompt SHA256;
* Judge provider;
* requested model;
* reported model (as actually returned; `null` in dry-run);
* temperature;
* `structured_output_enabled`;
* `retry_enabled`;
* `self_repair_enabled`;
* `case_count = 30`;
* `repeats = 3`;
* `expected_calls = 90`;
* timestamps (start, completion).

The API key is never printed, logged, or written to any artifact.

---

## 15. Dry-Run and Formal-Mode Preconditions

### 15.1 Dry-run

`--dry-run` MUST:

* perform all population-integrity, fingerprint, and condition checks offline;
* print the canonical run IDs, per-block case counts, total, uniqueness,
  versions, **provenance strings**, `source_population_sha256` and its match
  status, repeats, and expected call count;
* make **no** Judge API call;
* state explicitly that no Judge API call was made.

Dry-run does **not** require `OPENROUTER_API_KEY`.

### 15.2 Formal-mode credential check (fail-fast)

Formal mode MUST verify that `OPENROUTER_API_KEY` is present and non-empty
**before** constructing the Judge and **before** the first evaluation. If the
key is missing the runner MUST abort immediately with a non-zero exit code and a
clear message.

It MUST NOT:

* enter the 90-call loop without a key;
* produce a batch of `judge_api_error` records;
* silently fall back to dry-run.

The key value is never printed, logged, or written to any artifact.

### 15.3 Repeat count

The runner MUST reject any repeat count other than 3 (`fail-fast`), because the
frozen design is fixed at `30 × 3 = 90` calls.

---

## 16. Prohibitions

Under this protocol it is not permitted to:

* call the Judge during dry-run;
* modify the Generator, the Generator Prompt, the Evaluator, or the Judge
  Prompt;
* modify the Pilot dataset or the three canonical Generator runs (any such
  change invalidates `source_population_sha256` and fails the run);
* modify the frozen diagnostic protocol v0.2 or the holdout dataset v0.2;
* modify existing confirmatory results;
* re-weight, re-order, or re-select the population based on observed scores;
* add a Generator PASS/FAIL threshold under this protocol version.

---

## 17. Status History

| Date | Status | Note |
|---|---|---|
| 2026-08-29 | Draft | Initial draft. Not frozen. No acceptance thresholds defined. |
| 2026-08-29 | **Frozen** | Population fingerprint `a880833ad…f129706b` recorded; `generator_version_provenance` made explicit; formal-mode credential fail-fast added; per-intent / per-block `n_total` / `n_eligible` / `n_excluded` reporting required. |

---

## 18. Frozen Fields and Change Control

The following are frozen with this document. Changing any of them requires a
new protocol version (`v0.2`) and invalidates runs recorded against `v0.1`:

1. the three canonical source run IDs and their 12 / 12 / 6 case split;
2. `source_population_sha256`;
3. the population of 30 cases (no additions, removals, or substitutions);
4. `repeats = 3` and `expected_calls = 90`;
5. the repeat labelling convention `repeat ∈ {1, 2, 3}`;
6. case eligibility (`≥ 2` successful repeats) and the "failed repeats are never
   scored as zero" rule;
7. case-level equal-weight aggregation (Section 6.4);
8. Evaluator v0.1 and its call contract;
9. Judge condition — `openrouter` / `qwen/qwen3.5-plus-20260420` /
   `temperature = 0` / `structured_output = false` / `retry = false` /
   `self_repair = false`;
10. Judge Prompt v0.1 and its SHA256;
11. the absence of any Generator PASS/FAIL threshold (Section 12).

Non-frozen (may be refined without a new protocol version): purely presentational
aspects of the report that do not alter any statistic, and the diagnostic
thresholds in Section 10.1 — which carry no acceptance meaning in either case.
