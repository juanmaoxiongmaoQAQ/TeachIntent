# TeachIntent submission dry-run checklist

## Final release update — 2026-09-14

The owner has approved the complete source release and public retention of the
six synthetic Explore WAVs; see [THIRD_PARTY.md](THIRD_PARTY.md). Retired
`scripts/run_k0_ef.py` and `scripts/run_k0_i.py` remain local and are excluded.
The current publication inventory is [FINAL_STAGING_PLAN.md](FINAL_STAGING_PLAN.md).
The interactive `/showcase` and safe Linux start/stop scripts are now included.
The earlier P0-1 approval and P0-2 audio decision below are **resolved** by this
new instruction. P0-3 (a separate submission recording and destination links)
is outside the GitHub + running Showcase deliverable, not a push blocker.
Current service binding follows the approved `0.0.0.0` demonstration setup.

## Historical dry-run record (superseded decisions)

Audit date: 2026-09-14. Decision: **YES, after manual P0 items**.
**Three P0 items remain** for the submission package. No new functional regression
or missing implementation dependency was found in the complete working-tree
candidate. This is not a certification of external acceptance or media rights.

At audit start: HEAD `8f877fd`, 256 tracked files, 39 modified tracked files and
34 non-ignored untracked files: 290 candidate files in total. This checklist adds
one new untracked document. Existing untracked source must be deliberately
included in the final release; a tracked-only diff is incomplete. No staging,
commit, push, reset, checkout, clean, stash, deletion or artifact move was done.

## P0 Before submission

- [ ] **P0-1 — approve the complete publication contents.** Review the current
  tracked changes and every untracked file using the inventory below. Include
  required source/config/tests/docs together, exclude all private/generated
  directories, and resolve the two retired K0 source files' publication status.
  Review the actual staged diff later in the owner's submission workflow.
  `.gitignore` does not remove files already tracked or present in history.
- [ ] **P0-2 — resolve included-audio redistribution permission.** The six
  already-tracked Explore WAVs are small intentional demo assets with matching
  manifests, but the repository does not contain sufficient evidence granting
  redistribution rights for these exact outputs. Record the applicable terms
  and owner approval before publishing them. If approval cannot be established,
  an owner-approved distribution plan is required; simply omitting a new
  `git add` does not exclude already-tracked audio from a push. No audio or Git
  history was removed or rewritten in this dry-run. Any separately proposed
  Baton reference audio or recording containing it must also pass this review.
- [ ] **P0-3 — supply the final submission media and links.** Record/export the
  ≤2 minute walkthrough, review readable Chinese text and recorded/live labels,
  check that no credentials/private paths are visible, and provide the final
  public repository and demo/submission links. Store local media preparations
  inside `outputs/submission/`; do not bulk-publish that generated directory.

P0-2 is a permission-evidence blocker for publishing the current media-containing
candidate, not a detected license violation. An external `prompt.wav` that is
not being distributed does not by itself block the source-only application.
Missing historical frozen runs, unavailable optional GPU runtime and renderer
pronunciation limitations are not additional P0 items.

## P1 Recommended

- Follow README setup on the submission machine. Existing verification uses an
  installed Python 3.10 environment; dependency ranges are not a lockfile and
  this dry-run did not install dependencies or test provider availability.
- Review Explore, Live Studio and Intent Compare at the recording resolution.
  Confirm the v0.4 selector, recorded evaluator evidence and Experimental label.
- Preserve historical artifacts separately; restore exact original runs only
  if historical verification is requested. Never regenerate them to make tests
  green. A public clone's core gate must not depend on them.
- Keep review services on loopback. The current application is not a hardened
  public multi-user deployment. Default ports 8000 and 5173 were occupied at
  audit time; README now explains alternate ports and the matching Vite proxy.
- Verify the eventual repository/archive, including reachable history, against
  the owner's approved file and media list. This pass scans current candidates;
  the preceding release audit separately scanned locally reachable Git history.

## P2 Known limitations

Do not reopen pronunciation, swallowed sounds/tail characters, Mandarin
punctuation pauses, synthetic quality or stochastic speech-token research.
BatonVoice is an optional reference renderer; segmented browser playback remains
Experimental. Precise duration, word-level prosody and production-grade expressive
TTS are not claimed. No sampling/seed/pitch/energy/speed tuning, prompt v0.5, ASR
retry, waveform processing, silence insertion or splice is needed for submission.
Independent evaluator scores concern the Speech Plan, not audio or learning gains.

## Files to include

### A. MUST INCLUDE

Preserve the following as a coherent candidate, including their unchanged
existing dependencies. Do not interpret this as permission to stage files now.

| Category | Actual files / directories and reason |
|---|---|
| Package and review setup | `LICENSE`, `README.md`, `.env.example`, `.gitignore`, `pyproject.toml`; `.env.example` contains empty private values. |
| Planning / contracts | `src/teachintent/generator/`, `src/teachintent/prompts/`, `src/teachintent/models/`, `src/teachintent/validators/`, `schemas/`; retain explicit version registration and compatibility defaults. |
| Independent evaluation | `src/teachintent/evaluator/` including changed `evidence.py`, `service.py` and untracked `normalization.py`; retain the frozen rubric, Judge prompt and other existing dependencies. |
| Web application | `src/teachintent/app_service.py`, `web_api.py`, `web_models.py`, `segmented_web_service.py`; retain the existing package modules they import. |
| Optional renderer source | `src/teachintent/renderers/` including `batonvoice.py`, `batonvoice_segmented.py`, `_project_outputs.py` and exports; `src/teachintent/adapters/` including `hy3_baton_conductor.py`. Source is required by imports/tests; external models are not. |
| Frontend source/config | `frontend/src/`, `frontend/index.html`, package manifest **and lockfile**, TypeScript/Vite/configuration files and `frontend/.gitignore`; retain segmented component, API client/types and tests together. Exclude installed dependencies/build output. |
| Runnable documented entries | `scripts/run_web_api.py`, existing recorded demo entry points and their imported modules. |
| Offline regression dependencies | `tests/`, especially `conftest.py`, `historical_artifacts.py`, `test_historical_artifact_boundary.py` and renderer/Web/normalization tests. Keep diagnostic scripts imported by these tests; their experimental identity does not make their source dispensable for the advertised core gate. |
| Diagnostic source required by retained tests | `scripts/diagnose_baton_seg04_neutral_repeatability.py`, `diagnose_baton_seg04_repeatability.py`, `diagnose_baton_segment_isolation.py`, `run_baton_segmented_candidate.py`. They are not reviewer startup commands. |
| Portable plans/evaluator evidence | `examples/`, `public_demo/evaluator_artifacts/`, existing canonical `cases/`, including `cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json`. These JSON files are intentional source/static evidence, not disposable temporary JSON. |
| Public audio provenance | Existing `public_demo/voice/*/v0_2/manifest.json`; WAV publication is conditional on MANUAL REVIEW below, not automatically approved by their small size. |
| Documentation / frozen specs | `docs/TESTING.md`, `THIRD_PARTY.md`, `RELEASE_AUDIT.md`, this checklist, `DEMO_SCRIPT.md`, `TASK1_COMPLIANCE.md`, segmented docs and README-linked contracts/protocols/results/legacy TTS notes. Preserve frozen files needed by integrity tests. |

### Recent capability completeness check

| Capability | Verified implementation / wiring |
|---|---|
| v0.4 | `src/teachintent/prompts/speech_plan_v0_4.py`; `registry.py` imports/registers it; `__init__.py` exports; Live Studio offers v0.4; matching prompt/Web tests exist. |
| Baton fixes, local WeText, executor diagnostics | All live in **`src/teachintent/renderers/batonvoice.py`**, including `_patch_local_wetext_frontend` and `_ExecutorObservation`; there is no separate missing local-WeText module to add. |
| Segmented renderer / project output utility | `batonvoice_segmented.py` imports `_project_outputs.py` and delegates existing Baton execution. |
| Segmented Web | `segmented_web_service.py`, route registration in `web_api.py`, response models in `web_models.py`, and the existing-session bridge. |
| Segmented player | `frontend/src/components/workbench/SegmentedBatonCandidate.tsx`, its test, Live Studio wiring, API client and types. |
| Structured grounding / normalization | `evaluator/evidence.py`, `normalization.py`, `service.py`, with existing evidence/service regression tests. |
| Release test boundary | `tests/historical_artifacts.py`, `tests/conftest.py`, `pyproject.toml`, seven decorated historical test modules and the boundary regression test. |

### B. SHOULD INCLUDE

`docs/CODEX_HANDOFF.md`, existing project/proposal/history explanations and
retired-experiment context help explain provenance but are not new runtime
features. Preserve clear dates and the superseding release notice. Do not use
old next-experiment instructions as submission requirements. Additional raw
experiment output is not needed to support this documentation.

### Per-file working-tree inventory

The lists below cover every modified tracked file and every non-ignored
untracked file present at the start of this dry-run. Unchanged tracked files
remain subject to the category rules above, especially already-tracked WAVs.

#### Modified tracked files

| Classification | Path |
|---|---|
| A — MUST INCLUDE | `.env.example` |
| A — MUST INCLUDE | `.gitignore` |
| A — MUST INCLUDE | `README.md` |
| B — SHOULD INCLUDE | `docs/CODEX_HANDOFF.md` |
| A — MUST INCLUDE | `docs/DEMO_SCRIPT.md` |
| A — MUST INCLUDE | `docs/TASK1_COMPLIANCE.md` |
| A — MUST INCLUDE | `docs/TTS_RENDERER.md` |
| A — MUST INCLUDE | `frontend/src/api/teachintent.ts` |
| A — MUST INCLUDE | `frontend/src/components/evaluation/EvaluationPanel.tsx` |
| A — MUST INCLUDE | `frontend/src/components/workbench/Workbench.tsx` |
| A — MUST INCLUDE | `frontend/src/pages/LiveStudioPage.test.tsx` |
| A — MUST INCLUDE | `frontend/src/pages/LiveStudioPage.tsx` |
| A — MUST INCLUDE | `frontend/src/types/teachintent.ts` |
| A — MUST INCLUDE | `frontend/vite.config.ts` |
| A — MUST INCLUDE | `pyproject.toml` |
| A — MUST INCLUDE | `scripts/run_web_api.py` |
| A — MUST INCLUDE | `src/teachintent/app_service.py` |
| A — MUST INCLUDE | `src/teachintent/evaluator/evidence.py` |
| A — MUST INCLUDE | `src/teachintent/evaluator/service.py` |
| A — MUST INCLUDE | `src/teachintent/generator/client.py` |
| A — MUST INCLUDE | `src/teachintent/prompts/__init__.py` |
| A — MUST INCLUDE | `src/teachintent/prompts/registry.py` |
| A — MUST INCLUDE | `src/teachintent/renderers/__init__.py` |
| A — MUST INCLUDE | `src/teachintent/web_api.py` |
| A — MUST INCLUDE | `src/teachintent/web_models.py` |
| A — MUST INCLUDE | `tests/conftest.py` |
| A — MUST INCLUDE | `tests/test_evaluator_evidence.py` |
| A — MUST INCLUDE | `tests/test_evaluator_service.py` |
| A — MUST INCLUDE | `tests/test_generator_v0_1_baseline_evaluation.py` |
| A — MUST INCLUDE | `tests/test_generator_v0_1_baseline_evaluation_v0_2.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc1.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc1_development.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc1_development_cli.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc1_development_evaluation.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc2.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc2_development.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_2_rc2_development_evaluation.py` |
| A — MUST INCLUDE | `tests/test_web_api.py` |

#### Untracked files at audit start

| Classification | Path |
|---|---|
| A — MUST INCLUDE | `cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json` |
| A — MUST INCLUDE | `docs/RELEASE_AUDIT.md` |
| A — MUST INCLUDE | `docs/TESTING.md` |
| A — MUST INCLUDE | `docs/THIRD_PARTY.md` |
| A — MUST INCLUDE | `docs/batonvoice_segmented_candidate.md` |
| A — MUST INCLUDE | `docs/batonvoice_segmented_web.md` |
| A — MUST INCLUDE | `frontend/src/components/workbench/SegmentedBatonCandidate.test.tsx` |
| A — MUST INCLUDE | `frontend/src/components/workbench/SegmentedBatonCandidate.tsx` |
| A — MUST INCLUDE | `scripts/diagnose_baton_seg04_neutral_repeatability.py` |
| A — MUST INCLUDE | `scripts/diagnose_baton_seg04_repeatability.py` |
| A — MUST INCLUDE | `scripts/diagnose_baton_segment_isolation.py` |
| A — MUST INCLUDE | `scripts/run_baton_segmented_candidate.py` |
| D — MANUAL REVIEW | `scripts/run_k0_ef.py` |
| D — MANUAL REVIEW | `scripts/run_k0_i.py` |
| A — MUST INCLUDE | `src/teachintent/adapters/hy3_baton_conductor.py` |
| A — MUST INCLUDE | `src/teachintent/evaluator/normalization.py` |
| A — MUST INCLUDE | `src/teachintent/prompts/speech_plan_v0_3.py` |
| A — MUST INCLUDE | `src/teachintent/prompts/speech_plan_v0_4.py` |
| A — MUST INCLUDE | `src/teachintent/renderers/_project_outputs.py` |
| A — MUST INCLUDE | `src/teachintent/renderers/batonvoice.py` |
| A — MUST INCLUDE | `src/teachintent/renderers/batonvoice_segmented.py` |
| A — MUST INCLUDE | `src/teachintent/segmented_web_service.py` |
| A — MUST INCLUDE | `tests/historical_artifacts.py` |
| A — MUST INCLUDE | `tests/test_baton_seg04_neutral_repeatability.py` |
| A — MUST INCLUDE | `tests/test_baton_seg04_repeatability.py` |
| A — MUST INCLUDE | `tests/test_baton_segment_isolation.py` |
| A — MUST INCLUDE | `tests/test_baton_segmented_candidate_runner.py` |
| A — MUST INCLUDE | `tests/test_batonvoice_renderer.py` |
| A — MUST INCLUDE | `tests/test_batonvoice_segmented.py` |
| A — MUST INCLUDE | `tests/test_historical_artifact_boundary.py` |
| A — MUST INCLUDE | `tests/test_hy3_baton_conductor.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_3.py` |
| A — MUST INCLUDE | `tests/test_prompt_v0_4.py` |
| A — MUST INCLUDE | `tests/test_segmented_web_api.py` |

New in this dry-run: `docs/SUBMISSION_CHECKLIST.md` — **A, MUST INCLUDE**.

## Files / directories to exclude

### C. MUST EXCLUDE

Do not delete these local files; leave them outside the publication set.

- `outputs/` in its entirety: real renderer/diagnostic WAVs and JSON, repeatability
  observations, logs, source exports, test fixtures and this audit's working
  reports. An export nested under outputs is not an extra source tree to commit.
- `results/`: immutable local historical experiment evidence. It is not the
  portable `public_demo/` showcase and is not needed by core tests.
- `frontend/node_modules/`, `frontend/dist/`, coverage/Vite caches, `.pytest_cache/`,
  every `__pycache__/`, `.pyc`, virtual environments and package/build caches.
- `.vscode/`, real `.env` files, `auth.json`, SSH/private keys, shell history,
  access tokens, cookie stores, remote credentials and browser caches. Preserve
  `.env.example` with empty credential/path values as a reviewed exception.
- Model checkpoints/weights, model-cache metadata, downloaded archives, ZIPs,
  temporary debug dumps/JSON, generated logs, and raw/private provider responses.
- Newly proposed reference/prompt audio until an explicit approved distribution
  decision exists. The six existing small public WAVs follow MANUAL REVIEW,
  not a blanket rule that every WAV is automatically safe to publish.

Observed ignored inventory at scan time (sizes are logical bytes, not allocated
storage; contents were not deleted or copied):

| Directory/category | Files | Approximate MiB |
|---|---:|---:|
| `outputs/` | 35,555 | 95.77 |
| `results/` | 9 | 5.19 |
| `frontend/node_modules/` | 13,260 | 190.94 |
| `frontend/dist/` | 3 | 0.37 |
| `__pycache__/` outside those categories | 187 | 3.99 |
| `.pytest_cache/` | 5 | 0.13 |
| `.vscode/` | 1 | <0.01 |

No candidate file exceeds 10 MiB; no candidate checkpoint, ZIP or generated
output/cache file was found. Two ignored esbuild executables exceed 10 MiB:
`frontend/node_modules/@esbuild/linux-x64/bin/esbuild` and
`frontend/node_modules/esbuild/bin/esbuild`, each 11,427,952 bytes. They are
installed dependencies, not submission assets. No `outputs/` or `results/`
file is tracked.

## Manual licensing review

### D. MANUAL REVIEW

| Item | Current evidence | Decision required |
|---|---|---|
| Six tracked Explore WAVs below | Qwen3-TTS model/speaker/text/condition and WAV hashes are recorded; all six file hashes match their manifests. | P0-2: establish redistribution permission for these exact outputs. Small static-demo status alone is insufficient. |
| External Baton reference prompt audio | `BATONVOICE_PROMPT_AUDIO_PATH` supplies it; current candidate contains no `prompt.wav` or bundled reference recording. | If proposed for redistribution or use in submitted media, verify source/consent/license. Existing repo materials alone do not establish this permission. |
| `scripts/run_k0_ef.py`, `scripts/run_k0_i.py` | Retired `main()` entry points; old implementation retains personal machine and project-external paths. | Owner chooses whether archival source belongs in the public candidate. They are not required by current core tests or startup. Do not reactivate them. |
| Final screen/audio recording | Not created by this task. | Review third-party audio permissions, private paths and truthful recorded/live labels before sharing. |

The six already-tracked files total **5,433,864 bytes (5.18 MiB)**:

| Path | Bytes |
|---|---:|
| `public_demo/voice/corrective-feedback/v0_2/neutral.wav` | 760,364 |
| `public_demo/voice/corrective-feedback/v0_2/planned.wav` | 645,164 |
| `public_demo/voice/scaffolding/v0_2/neutral.wav` | 1,075,244 |
| `public_demo/voice/scaffolding/v0_2/planned.wav` | 971,564 |
| `public_demo/voice/supportive-feedback/v0_2/neutral.wav` | 990,764 |
| `public_demo/voice/supportive-feedback/v0_2/planned.wav` | 990,764 |

TeachIntent has an explicit **MIT LICENSE**, copyright 2026 TeachIntent
contributors. README and `docs/THIRD_PARTY.md` clearly identify Tencent
`digitalhuman/BatonVoice`, CosyVoice2, Hy3 and Qwen3-TTS as external components.
BatonTTS/CosyVoice/FST assets are supplied by local environment paths; weights
and upstream source are absent from the candidate. README does not imply that
TeachIntent publishes or trained those models. Attribution is present; this
local-only audit cannot turn attribution into a third-party license grant.

On disk, 754 files named `prompt.wav` or `reference.wav` were found only under
ignored `outputs/offline-tests/` and `outputs/release-hardening/` test/export
areas. These are not candidate reference recordings or proof of permission to
redistribute a real speaker reference. No directory symlinks were followed in
the metadata inventory; ignored targets are not candidate assets.

### Secrets / sensitive data result

No confirmed operational credential was found in tracked candidates, all
non-ignored untracked source/config/docs, or the ignored local VS Code config.
The scan covered key/token/private-key patterns and credential assignments,
filenames and local path references. Twenty-two broad literal matches were
reviewed as offline-test credentials/sanitization fixtures or a dependency
version, not operational secrets. No credential value is included in this report.

Local absolute paths remain in retired K0 source, ignored IDE configuration,
sanitization patterns and negative-test fixtures. They are not required README
installation paths. Raw ignored debug/cache/provider files were inventoried by
metadata only, not approved for publication. A pattern scan is not proof that
arbitrary secrets cannot exist: P0-1 still requires final content review.

## Reviewer from-zero path audit

| Step | Result / boundary |
|---|---|
| Clone and install | README specifies a repository checkout, Python venv and `pip install -e '.[dev]'`; frontend lockfile supports `npm ci`. The final owner-approved repository URL remains a submission deliverable. |
| Credentials | Empty `.env.example`, server-side Hy3/Judge variables, model/base URL, optional Baton paths/resources and output configuration are documented. No key belongs in frontend `VITE_*`. |
| Backend / frontend | Actual entry point and npm scripts exist. Defaults are distinct (8000/5173), but both were occupied on this machine during audit. Added alternate-port/proxy guidance only; no existing server was stopped. |
| Core tests | README separates green offline core from optional historical prerequisites; current source/config/fixture hashes match the previously tested portable copy. |
| Explore | Three existing scenarios have plans and matching six-dimensional recorded evaluator artifacts; no key/GPU/private results needed. |
| Live Studio / v0.4 | Actual selector and registry wiring exist; scenario load fills input only. Selecting v0.4 does not fabricate a v0.4 output or relabel a saved result. |
| Evaluator | README and UI explicitly evaluate the Speech Plan, not a WAV. |
| Baton boundary | Optional reference backend, separate existing environment and Experimental segmented player are explicit. |
| Links / paths | README local file links resolved; documented command files exist; no machine-specific absolute installation root is required. External hyperlinks were not checked because networking was prohibited. |

No fresh environment install, live model call or browser listening experiment
was performed. The core quick-start path is complete for a reviewer with the
listed prerequisites; clean-machine dependency resolution remains a P1 check.

## Final test commands

From the repository root, with the installed Python environment activated:

```bash
mkdir -p outputs/tmp outputs/cache/npm
export TMPDIR="$PWD/outputs/tmp"
export npm_config_cache="$PWD/outputs/cache/npm"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -m 'not historical_artifacts'
```

From `frontend/`, inheriting the project-local environment above:

```bash
npm test
npm run build
```

Optional historical verification from the repository root:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -m historical_artifacts -rs
# Only after restoring the exact original runs:
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -m historical_artifacts --require-historical-artifacts
```

**Results reused, not rerun in this dry-run:** core **1335 passed / 152
deselected**; full suite **1335 passed / 152 skipped**; frontend **54 passed**;
TypeScript/Vite build **PASS**. The previous portable source export also passed
1335 core tests without private files or historical results. This pass compared
all current source, tests, scripts, frontend/config, schemas, cases, examples and
public-demo files against that tested copy: **no differences**. Only README and
this checklist change now, so a repeated model-free full build/test cycle would
add no coverage. Three prior Python warnings remain documented in TESTING/release
notes. Current checks rerun local link resolution, artifact hashes, content
inventory, credential review and `git diff --check`.

## Demo recording checklist

Use **Explore with v0.2 recorded artifacts** for all three scenarios. No typing
or model calls are needed: selecting the scenario loads its saved input. If
preparing a Live Studio form for explanation only, copy the exact fields from
`examples/<name>.json` → `input` (content anchor, scenario, learner utterance,
level, knowledge state, affective state and primary intent); stop before Generate.
The full existing inputs are already displayed in Explore, not new demo fixtures.

| Scenario / source | Input to show | Speech Plan difference to inspect | Evaluator focus |
|---|---|---|---|
| Corrective feedback — `examples/corrective_feedback.json` | Physics; frustrated learner says unchanged speed while turning implies zero acceleration; intent `corrective_feedback`. | Acknowledge the correct speed observation, correct the missing direction component; restrained reassuring/corrective tone. | D1 requested move, D2 content anchor, D6 tone alignment and grounded highlights. |
| Focused guidance / hint — `examples/scaffolding.json` | Biology Tt × tt; frustrated learner asks for every combination/ratio; intent `scaffolding`. | Ask for each parent's possible gametes as the next step, instead of providing the whole answer; gentle but firm delivery. | D3 learner fit, D4 calibrated scaffold, D5 minimal controls. |
| Positive feedback / encouragement — `examples/supportive_feedback.json` | Successful coordinate-axis reading transferred from geography to chemistry; learner seeks confirmation; intent `supportive_feedback`. | Recognize the specific successful strategy; recorded delivery is `{}`, demonstrating justified omission. | D1 supportive intent, D3 learner fit, D5/D6 appropriateness of empty delivery. |

Suggested timing: 0–15 s motivation/Hy3 role; 15–60 s corrective plan + grounded
evaluator; 60–80 s scaffolding and supportive contrast; 80–100 s Live Studio v0.4
selector and Intent Compare form; 100–115 s architecture and optional renderer
boundary; 115–120 s personal/non-official-project disclaimer. Use
[DEMO_SCRIPT.md](DEMO_SCRIPT.md) for narration.

- [ ] Show all three existing scenarios without generating replacement output.
- [ ] Do not describe different-context recorded examples as an intent-only
  controlled experiment. Intent Compare is the separate same-context workflow.
- [ ] Do not click Generate, Evaluate or Render during an offline recording.
- [ ] Present recorded evaluator evidence as recorded, with matching prompt labels.
- [ ] Baton segmented audio is an **optional bonus**, only from existing verified
  recordings/session audio with approved permission. Do not synthesize new audio.
- [ ] Explore audio is Qwen3-TTS, not Baton. Supportive feedback has identical
  A/B audio because the delivery plan is empty; no audible difference is claimed.
- [ ] A server restart loses live audio session registrations; the player cannot
  import an arbitrary historical CLI run. Use a prior approved screen recording
  if no existing session is available, or omit audio.
- [ ] Keep the export ≤2 minutes, Chinese text readable, credentials/private paths
  absent, and save preparations under project-local `outputs/submission/`.

## Final git review commands

Run from the repository root. These are review commands only, not staging or
publishing instructions:

```bash
git status --short
git diff --stat
git diff --check
git diff
git ls-files
git ls-files --others --exclude-standard
git status --short --ignored=matching
git ls-files outputs results frontend/node_modules frontend/dist .vscode
# Review anything already staged by the owner, if applicable:
git diff --cached --stat
git diff --cached --check
git diff --cached
```

`git diff` alone omits untracked file contents. Inspect every untracked path in
the inventory explicitly. Do not use `git add .` as a substitute for an approved
file list. Existing tracked public WAVs need review even if absent from today's
diff. Preserve working files and historical evidence; this dry-run does not
stage, remove, commit or push anything.

This task changed README documentation and added this checklist only. Audit
working reports are ignored under `outputs/submission-dry-run/20260914/`.
Confirmed: no Hy3/OpenRouter request, GPU use, model download, upstream or
site-packages modification, commit or push; no functional/prompt/schema/evaluator/
mapper/sampling/Web behavior change.
