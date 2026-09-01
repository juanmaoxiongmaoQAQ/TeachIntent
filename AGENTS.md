# AGENTS.md — TeachIntent

Stable instructions for autonomous agents working in this repository.
Read this first, then `docs/CODEX_HANDOFF.md` for the current snapshot, then
the task-relevant frozen protocol.

---

## Project

TeachIntent studies **Pedagogical Intent Driven Speech Planning**.

Core mapping:

```
(C, P, L, G) -> (V, D)
```

- `C` = Instructional Content
- `P` = Pedagogical Context
- `L` = Learner Information
- `G` = Pedagogical Intent
- `V` = Verbal Plan (what to say)
- `D` = Delivery / Prosodic Plan (how to deliver it)

TeachIntent is **not** a new TTS architecture. It is a **planning layer**
between pedagogy and speech realization. The model (Hy3) is the pedagogical
speech planner; it does not do TTS synthesis, voice cloning, intent selection,
or multi-turn tutoring policy. The output is a structured, machine-actionable,
evaluable Speech Plan.

Six pedagogical intents (the control space, see `docs/pedagogical_intents.md`):
Elicitation, Scaffolding, Explanation, Corrective Feedback, Supportive
Feedback, Extension.

## Repository map

```
docs/                              frozen specs & protocols (source of truth)
src/teachintent/generator/         Generator v0.1 (client, service, parser)
src/teachintent/prompts/           versioned prompts + registry (v0.1 default)
src/teachintent/evaluator/         Evaluator v0.1 (diagnostic, 6 dims D1-D6)
src/teachintent/generator_evaluation/  baseline evaluation protocol v0.2
src/teachintent/prompt_development/    prompt dev runner + paired eval
src/teachintent/evaluator_diagnostic/  evaluator diagnostic / confirmatory runner
src/teachintent/models/            Pydantic models (input + speech plan)
src/teachintent/validators/        JSON Schema validation
src/teachintent/adapters/          external API adapters
cases/                             canonical datasets (pilot, diagnostic)
results/                           immutable experiment evidence (git-ignored)
schemas/                           JSON Schema files
scripts/                           thin CLI entry points
tests/                             pytest suite
```

`cases/` and `docs/` are committed source of truth. `results/` is generated
evidence and is git-ignored — do not commit it, and do not delete it.

## Frozen contracts

The following are **Frozen** and must NOT be modified to improve experiment
results:

- Evaluator v0.1 (`docs/evaluator_spec_v0.1.md`, `src/teachintent/evaluator/`)
- Judge Prompt v0.1 (`src/teachintent/evaluator/prompt.py`)
- Input Schema (`1.0.0-rc.2`) and Speech Plan Schema (`1.0.0-rc.3`)
- Evaluator Diagnostic Protocol v0.2 + its holdout dataset
- Generator Baseline Evaluation Protocol v0.2
- formal Prompt v0.2 (`src/teachintent/prompts/speech_plan_v0_2.py`), a
  byte-identical behavioral alias of v0.2-rc.2, plus its freeze record
- canonical Pilot runs (Generator v0.1, blocks A/B/C)
- frozen baseline evaluation (`generator_v0_1_baseline_evaluation_v0_2/...`)
- all already-recorded experiment results

If a task genuinely requires changing a frozen component, **state this
explicitly to the user first** and get approval. Never silently edit frozen
specs, frozen prompts, or recorded results.

## Prompt versions

```
v0.1        original default (src/teachintent/prompts/speech_plan.py)
v0.2-rc.1   narrow behavioral revision (speech_plan_v0_2_rc1.py)
v0.2-rc.2   minimal correction of rc.1 (speech_plan_v0_2_rc2.py)
v0.2        formal frozen alias of v0.2-rc.2 (speech_plan_v0_2.py)
```

Selection is **explicit** via `registry.py` / `build_speech_plan_prompt_for_version`.
The default is always `v0.1`; v0.1-compatible behavior must never break. A run
opts into v0.2-rc.x or formal v0.2 explicitly. Formal v0.2 must remain
model-facing byte-identical to v0.2-rc.2; its version is provenance metadata.
Never hard-code a version import into the generator core.

Prompt v0.2 is frozen from development evidence only. Formal confirmatory
evidence does not yet exist, and no held-out case may be authored or inspected
until the Prompt v0.2 confirmatory experiment protocol is separately frozen.

## Testing

Standard gate before considering work done:

```
.venv/bin/pytest -q
git diff --check
git status --short
```

Known macOS/sandbox issue: pytest `tmp_path`/basetemp can hit permission
errors. If so, use a fresh, unique basetemp (e.g. `--basetemp=/tmp/...`) rather
than mass-deleting existing temp dirs. Run `LOGNAME=<user>` if sandboxed.
Do not fix by `rm -rf` on shared caches.

## Destructive actions

- Do **not** run large-scale `rm -rf`.
- Do **not** delete historical experiment results under `results/`.
- Do **not** delete canonical runs or frozen evaluation runs.
- Do **not** overwrite recorded experiment artifacts.
- `.pytest-basetemp/`, `results/.pytest-basetemp/`, `.pytest_cache/` are local
  temp — they may be cleaned, but never commit them.

If a large deletion seems necessary, **stop and report to the user** instead of
proceeding.

## Experiment principles

- `results/` is immutable evidence — never edit recorded runs.
- Failed calls are not silently dropped; operational failures and semantic
  quality are recorded and reported separately.
- Do not rerun merely because a result is unfavorable.
- Baseline results are not regenerated merely to improve pairing.
- Record provenance for every run: run ID, model, prompt version, evaluator
  version, protocol document SHA, dataset SHA.
- Development evidence != confirmatory (held-out) evidence.

## Workflow

When starting a task, in order:

1. `git status` and `git log`
2. Read `docs/CODEX_HANDOFF.md`
3. Read the frozen protocol relevant to the task
4. Verify actual repo state against the handoff

The repository and its artifacts are the final source of truth. Do not trust a
handoff summary blindly — re-verify paths, hashes, and run IDs before acting.
