# Release hardening audit — 2026-09-14

## Final release update — 2026-09-14

The owner approved source publication, six existing synthetic demo WAVs and
commit/push. K0 scripts are retained locally and excluded from Git. See the
current [staging inventory](FINAL_STAGING_PLAN.md) and
[audio statement](THIRD_PARTY.md). The Showcase addition and its verification
are documented in that inventory; the audit below records the earlier hardening
and dry-run state. Its pending approval and loopback-only recommendations are
superseded for this authorized `0.0.0.0` demonstration. No model experiment
or change to frozen artifacts is part of this release follow-up.

TeachIntent is now in submission preparation. Baton/TTS research is stopped.
The project-owner-reported real GPU/browser outcome is accepted as prior
evidence; this audit made no Hy3/Judge request, used no GPU and generated no
speech. It changed no sampling, seed, speed implementation, mapper, prompt,
schema, evaluator rubric, Tencent upstream or site-packages file.

## Readiness assessment

The working tree provides a reviewable local open-source application: its main
architecture is documented, the core offline gate is green, the frontend builds,
and the actual local backend/Vite path serves three complete recorded showcases.
**The submission package is not yet finished.** The owner still needs to select
and review the complete uncommitted source set, supply the final public repository
and demo media/link, and confirm redistribution permissions for included media.
This is an engineering readiness assessment, not an external acceptance decision.

The initial HEAD was `8f877fd`. Substantial tracked and untracked changes already
existed before hardening and were preserved. No reset, checkout, clean, stash,
commit or push was performed. `.vscode/` is retained and now ignored as local
IDE configuration. Existing experiments were not moved, removed or regenerated.

## Findings and disposition

| Audit finding | Release action |
|---|---|
| README centered an older demo and Qwen-only voice flow. | Reframed around Hy3 planning, WHAT/HOW, plan evidence, interchangeable adapters, three current Web pages and optional Baton speech. |
| Prior full test run: 1325 passed, 121 failed, 30 errors because original Pilot/baseline/rc artifacts were absent. | Added per-test named prerequisites, explicit skip reasons and strict mode. Assertions, experiment implementations and pure tests are preserved. |
| A historical rc.2 test could pass accidentally when a missing baseline raised the expected exception before checking version routing. | Its baseline dependency is now explicit. This explains why 152 cases are marked, versus 151 former failures/errors. No assertion was changed. |
| Single-pass Web output defaulted to the system temp directory. | Default is now `outputs/teachintent-batonvoice/`; relative paths resolve from the project and project-external/symlink escapes are rejected on write and serving. Synthesis behavior is unchanged. |
| Root `.env` loading was not explicit at Web startup. | `run_web_api.py` loads it without overriding exported variables. Keys and optional local paths in `.env.example` are empty. |
| Live Studio's asynchronous scenario load could reject without a visible error. | Added an explicit load-failure message and a frontend regression test. |
| Evaluator/audio boundary needed clearer page copy. | The evaluation panel explicitly says it evaluates the Speech Plan, not audio. |
| Early K0 scripts hardcoded project-external outputs/model paths. | Disabled their `main()` entry points before experiment work; retained the old implementation for provenance. They are retired source, not release configuration. |
| Demo instructions referenced a scenario different from current Explore data. | Replaced with a two-minute React walkthrough of existing physics/biology/supportive examples. |
| Existing public A/B WAVs are Qwen3-TTS recordings. | Preserved manifests and clarified attribution; no relabeling as Baton or promise of an audible difference for empty delivery. |
| Ignore rules lacked common local credential/weight patterns. | Added focused ignore rules without deleting any user files or evidence. |

## Product and experiment boundary

**Product:** generator and explicit prompt registry; input/Speech Plan models and
validation; independent evaluator; Web application service/API; Explore, Live
Studio and Intent Compare. Core defaults and frozen contracts remain intact.

**Optional execution:** conservative Baton adapter and single-pass renderer;
segmented renderer and its Web panel remain Experimental. Rendering receives a
saved plan and does not change the generator/evaluator workflow. Qwen remains a
legacy optional adapter and the source of the published Explore audio.

**Diagnostics:** executor observation, isolation and fixed-condition repeatability
scripts, the segmented candidate CLI and Baton diagnostic cases are preserved
and explicitly documented as experimental. They are not app startup or release
prerequisites. K0 direct execution is retired. No new experiment is proposed.

**Historical experiments:** Pilot/baseline/rc-development runners and the tests
that require exact frozen run roots. Their prerequisites, read-only reuse and
strict verification are documented in [TESTING.md](TESTING.md). No frozen input,
result, protocol or prompt was changed to make the suite pass.

## Offline verification

Logs and machine-readable reports are local, ignored artifacts under
`outputs/release-hardening/20260914/`; they are not required by a public clone.
This workspace has no `.venv`; verification used its existing Python 3.10
`batonvoice_ctt` environment with plugin autoload disabled and model/GPU access
disabled in the test shell. No environment package was installed or changed.
Frontend verification used the existing Node 20.20.2 installation.

| Check | Result |
|---|---|
| Core: `python -m pytest -q -m 'not historical_artifacts'` | **1335 passed, 152 deselected** |
| Full available offline suite: `python -m pytest -q -rs` | **1335 passed, 152 skipped** |
| Strict missing-history preflight with `--maxfail=1` | Expected failure on the first absent frozen run; no silent skip |
| Frontend: `npm test` | **54 passed, 10 test files** |
| Frontend: `npm run build` | **Passed**, TypeScript + Vite |
| Actual backend + Vite proxy smoke | Health and frontend HTTP 200; all three showcase plans and six-dimensional recorded evaluator panels available via local GET requests |
| README JSON example | Schema-valid and equal to the saved Golden Case 1 plan |
| Retired K0 CLIs | Reject execution before experiment work |
| Portable candidate source export | **1335 passed, 152 deselected** from a separate project-local source copy without `.env`, `results/`, prior `outputs/`, IDE configuration or model weights; same existing Python dependencies |
| `git diff --check` | Passed |

The Python suite retains three visible warnings: one installed Starlette/AnyIO
deprecation and two intentional malformed-model Pydantic serializer warnings in
negative tests. They do not fail the suite; dependency upgrades are not part of
this hardening. Browser media tests use mocks. No new human listening result,
real GPU result or external-provider availability is claimed here.

The seven historical test modules were also compared structurally against HEAD:
their Python ASTs are identical after removing the new prerequisite decorators.
All local file links in the changed release documentation resolved successfully.
The portable source check verifies independence from local evidence/private
files; it is not a claim that dependencies were freshly installed or locked.

## Files changed in this hardening task

This task modified 25 pre-existing files and added five source/documentation
files. These are distinct from the substantial changes already in the working
tree when the task began.

| Area | Modified files |
|---|---|
| Overview/configuration | `README.md`, `.env.example`, `.gitignore`, `pyproject.toml` |
| Delivery documentation | `docs/CODEX_HANDOFF.md`, `docs/DEMO_SCRIPT.md`, `docs/TASK1_COMPLIANCE.md`, `docs/TTS_RENDERER.md`, `docs/batonvoice_segmented_web.md` |
| Startup / retired entry points | `scripts/run_web_api.py`, `scripts/run_k0_ef.py`, `scripts/run_k0_i.py` |
| Application / UI | `src/teachintent/app_service.py`, `frontend/src/components/evaluation/EvaluationPanel.tsx`, `frontend/src/pages/LiveStudioPage.tsx` |
| Offline regression coverage | `tests/conftest.py`, `tests/test_web_api.py`, `frontend/src/pages/LiveStudioPage.test.tsx` |
| Historical prerequisites only | `tests/test_generator_v0_1_baseline_evaluation.py`, `tests/test_generator_v0_1_baseline_evaluation_v0_2.py`, `tests/test_prompt_v0_2_rc1_development.py`, `tests/test_prompt_v0_2_rc1_development_cli.py`, `tests/test_prompt_v0_2_rc1_development_evaluation.py`, `tests/test_prompt_v0_2_rc2_development.py`, `tests/test_prompt_v0_2_rc2_development_evaluation.py` |

Added: `docs/RELEASE_AUDIT.md`, `docs/TESTING.md`, `docs/THIRD_PARTY.md`,
`tests/historical_artifacts.py`, `tests/test_historical_artifact_boundary.py`.
Local audit/log/export files are ignored under `outputs/` and are not release
source. The task-start source hash snapshot confirms no file was deleted and
`.vscode/settings.json` is unchanged. Renderer core, mapper, prompt/schema,
evaluator and canonical/public example files remain unchanged by this task.

## Security, paths and provenance

The tracked plus non-ignored candidate files contained no API-key/private-key
signature match, credential/history filename or file over 10 MiB. No `outputs/`
or `results/` file was tracked. A scan of all locally reachable refs (45 commits,
433 eligible small text blobs) found no matching credential signatures,
credential/history filenames or files over 10 MiB. This bounded scan cannot
prove the absence of arbitrary secrets or cover remote/unreachable Git objects.
Inspect the final staged diff before publication.

Active Web model paths are environment-configured. Both single-pass and
segmented Web outputs are project-contained, with symlink escape checks. Test
bases, temp files, logs and smoke reports created by this task are inside
TeachIntent; frontend assets are inside `frontend/dist/`. Historical K0 source
still records old machine paths, but its CLI is retired; do not use its internal
functions as public runner APIs.

The local Web server has no authentication, rate limiting or shared persistent
session storage. Review over loopback. An internet-facing deployment would need
separate service hardening and is outside the submission's local-demo scope.
See [THIRD_PARTY.md](THIRD_PARTY.md) for attribution and media/license checks.

## Before-submission checklist

### P0 — required for the submission package

- Review and deliberately include the final source set: existing untracked
  renderer/prompt/Web files and tests are dependencies of the current working
  tree. Publishing only previously tracked files would omit working features.
  The owner performs any eventual commit/push; none was performed here.
- Exclude `.env`, `.vscode/`, credentials, model checkpoints, raw private runs,
  generated `outputs/` and immutable `results/`. Inspect the actual staged diff
  and public repository/archive, not only `.gitignore`.
- Confirm the exact third-party code/checkpoint and included-audio redistribution
  permissions; manifests provide provenance, not a blanket license grant.
- Produce the ≤2 minute video/GIF and final repository/submission link using
  [DEMO_SCRIPT.md](DEMO_SCRIPT.md), with visible recorded/live and model labels.

### P1 — recommended final owner checks

- On the submission machine, follow README setup and the green core/frontend
  commands; Python dependencies are version ranges rather than a locked runtime.
- Manually review Explore/Live Studio/Intent Compare layout, Chinese readability,
  evidence highlighting and error messages at the recording resolution. This
  task checked component behavior and local HTTP startup, not a new visual
  browser walkthrough.
- Verify credentials privately only if a live provider demonstration is desired.
  It is not required for the offline showcase, and no new speech experiment is
  needed. Use already preserved real listening evidence for optional audio.
- Preserve original historical artifacts separately. Restore them only when full
  historical verification is required; missing history is not a core release
  blocker and must not be regenerated just to pass tests.

### P2 — unnecessary before the deadline

- Further Baton sampling/seed/pitch/energy/speed tuning, prompt v0.5, ASR retries,
  waveform processing, silence insertion or audio splicing: explicitly stopped.
- Production deployment features, exhaustive renderer portability, additional
  showcase scenarios, new model benchmarks and broad dependency modernization.
- Eliminating every local pronunciation/punctuation variation or claiming precise
  pause/word-level control. These remain stated reference-renderer limitations.
