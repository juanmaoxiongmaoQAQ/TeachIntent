# Hy3 Open Practice Task 1 — TeachIntent Compliance Matrix

This matrix maps each Task‑1 requirement supplied for this project to current
repository evidence. `DONE` means the repository implementation/documentation
is present and offline-verifiable. `NEEDS MANUAL ACTION` identifies a submission
artifact that cannot be completed by source changes alone.

| # | Requirement | TeachIntent implementation | Evidence | Status |
|---:|---|---|---|---|
| 1 | Runnable Hy3-based AI application for a real open-ended scenario | Hy3 plans a context-sensitive AI-tutor turn from a validated input; recorded and live CLI modes are provided. | [`README.md`](../README.md), [`scripts/run_demo.py`](../scripts/run_demo.py), [`src/teachintent/demo.py`](../src/teachintent/demo.py), [`src/teachintent/generator/`](../src/teachintent/generator/) | **DONE** |
| 2 | Clear target users, problem, and why an LLM is needed | External-reviewer README defines AI-tutor developers/researchers, the open-ended mapping, template limits, and Hy3's role. | [`README.md`](../README.md#user-scenario-and-problem-definition), [`problem_definition.md`](problem_definition.md) | **DONE** |
| 3 | Custom evaluation method with at least five operational dimensions | Evaluator v0.1 defines six 0–4 dimensions plus grounded evidence and seven critical flags. | [`EVALUATION_METHOD.md`](EVALUATION_METHOD.md), [`evaluator_spec_v0.1.md`](evaluator_spec_v0.1.md), [`src/teachintent/evaluator/`](../src/teachintent/evaluator/) | **DONE** |
| 4 | Automatic or semi-automatic evaluation pipeline | Deterministic contract gate, frozen LLM Judge prompt, parser/schema/evidence validation, and machine-readable artifacts are implemented. | [`EVALUATION_METHOD.md`](EVALUATION_METHOD.md#automatic-evaluation-pipeline), [`src/teachintent/evaluator/`](../src/teachintent/evaluator/), experiment runners under [`scripts/`](../scripts/) | **DONE** |
| 5 | Self-constructed evaluation set with difficult/negative cases | 30-case Pilot includes six hard/adversarial cases; evaluator validation uses 24 controlled negative pairs; release sanity adds 12 new cases. | [`cases/pilot/`](../cases/pilot/), [`cases/evaluator_diagnostic/`](../cases/evaluator_diagnostic/), [`cases/release_sanity/`](../cases/release_sanity/) | **DONE** |
| 6 | Experimental validation of evaluator discrimination and consistency | Frozen confirmatory diagnostic: 23/24 directional, targeted drop 2.6528, protected MAE 0.2552, within-one repeatability 99.62%, semantic PASS. | [`EVALUATION_METHOD.md`](EVALUATION_METHOD.md#evaluator-discrimination-validation), [`RESULTS.md`](RESULTS.md#1-evaluator-v01-validation), [`evaluator_diagnostic_protocol_v0.2.md`](evaluator_diagnostic_protocol_v0.2.md) | **DONE** |
| 7 | Complete evaluation run, result tables, and representative case analysis | Public results consolidate evaluator, baseline, prompt development, and sanity tables with four representative cases. | [`RESULTS.md`](RESULTS.md), [`examples/`](../examples/) | **DONE** |
| 8 | Failure modes and capability boundaries | Actual generator, evaluator-acquisition, over-control, mode-collapse, judgment, dataset, and product boundaries are documented. | [`FAILURE_ANALYSIS.md`](FAILURE_ANALYSIS.md) | **DONE** |
| 9 | Open-source repository with README, environment example, and running instructions | Installable Python package, MIT license, external README, `.env.example`, offline demo, live instructions, and tests are included. | [`README.md`](../README.md#quick-start), [`.env.example`](../.env.example), [`pyproject.toml`](../pyproject.toml), [`LICENSE`](../LICENSE) | **DONE** |
| 10 | <=2 minute demo video or GIF | Exact <=2 minute screen sequence and narration are prepared; the media file itself is not recorded in the repository. | [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) | **NEEDS MANUAL ACTION** |
| 11 | No API keys or secrets in repository | Credentials are environment-only; `.env` and private-key patterns are ignored; public demo defaults offline; tracked-file audit is required before submission. | [`.gitignore`](../.gitignore), [`.env.example`](../.env.example), [`README.md`](../README.md#security-and-provenance) | **DONE** |
| 12 | State personal/activity project and not official Tencent release | Disclaimer is prominent in README and retained in project documentation. | [`README.md`](../README.md), [`PROPOSAL.md`](../PROPOSAL.md) | **DONE** |

## Submission Status

Repository deliverable: **11/12 requirements DONE**.  
Manual submission action: record/export the <=2 minute video or GIF, inspect it
for credentials and personal paths, and add the media or submission link.

Prompt v0.2 remains frozen. The abandoned 36-case confirmatory design is not
part of Task‑1 completion and has not been implemented.
