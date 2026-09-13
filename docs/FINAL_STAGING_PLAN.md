# Final TeachIntent GitHub staging plan

Date: 2026-09-14. Base commit: `8f877fd1aeaa8b0258913e91b71b877b5af3955c`.
The owner approved publication, retention of the six synthetic demo WAVs,
interactive Showcase, precise staging and commit/push. This final inventory
supersedes the earlier A/B proposal; **option A (retain WAVs) is selected**.

## Files to stage

**43 modified tracked files + 41 new source/docs/test files = 84 explicit paths.**
This includes the previously approved 39 modified + 34 new release paths and
11 additional Showcase paths (four tracked files and seven new files).
Stage only the paths below, never the project root or generated directories.
The two retired K0 files remain local and excluded.

### Modified tracked files — 43

```text
.env.example
.gitignore
README.md
docs/CODEX_HANDOFF.md
docs/DEMO_SCRIPT.md
docs/TASK1_COMPLIANCE.md
docs/TTS_RENDERER.md
frontend/src/App.test.tsx
frontend/src/App.tsx
frontend/src/api/teachintent.ts
frontend/src/components/evaluation/EvaluationPanel.tsx
frontend/src/components/layout/AppHeader.tsx
frontend/src/components/layout/AppNavigation.tsx
frontend/src/components/workbench/Workbench.tsx
frontend/src/pages/LiveStudioPage.test.tsx
frontend/src/pages/LiveStudioPage.tsx
frontend/src/types/teachintent.ts
frontend/vite.config.ts
pyproject.toml
scripts/run_web_api.py
src/teachintent/app_service.py
src/teachintent/evaluator/evidence.py
src/teachintent/evaluator/service.py
src/teachintent/generator/client.py
src/teachintent/prompts/__init__.py
src/teachintent/prompts/registry.py
src/teachintent/renderers/__init__.py
src/teachintent/web_api.py
src/teachintent/web_models.py
tests/conftest.py
tests/test_evaluator_evidence.py
tests/test_evaluator_service.py
tests/test_generator_v0_1_baseline_evaluation.py
tests/test_generator_v0_1_baseline_evaluation_v0_2.py
tests/test_prompt_v0_2.py
tests/test_prompt_v0_2_rc1.py
tests/test_prompt_v0_2_rc1_development.py
tests/test_prompt_v0_2_rc1_development_cli.py
tests/test_prompt_v0_2_rc1_development_evaluation.py
tests/test_prompt_v0_2_rc2.py
tests/test_prompt_v0_2_rc2_development.py
tests/test_prompt_v0_2_rc2_development_evaluation.py
tests/test_web_api.py
```

### New source / docs / tests / runtime scripts — 41

```text
cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json
docs/FINAL_STAGING_PLAN.md
docs/GROUP_MEETING_SHOWCASE.md
docs/RELEASE_AUDIT.md
docs/SUBMISSION_CHECKLIST.md
docs/TESTING.md
docs/THIRD_PARTY.md
docs/batonvoice_segmented_candidate.md
docs/batonvoice_segmented_web.md
frontend/src/components/workbench/SegmentedBatonCandidate.test.tsx
frontend/src/components/workbench/SegmentedBatonCandidate.tsx
frontend/src/pages/ShowcasePage.test.tsx
frontend/src/pages/ShowcasePage.tsx
scripts/diagnose_baton_seg04_neutral_repeatability.py
scripts/diagnose_baton_seg04_repeatability.py
scripts/diagnose_baton_segment_isolation.py
scripts/run_baton_segmented_candidate.py
scripts/showcase_runtime.py
scripts/start_showcase.sh
scripts/stop_showcase.sh
src/teachintent/adapters/hy3_baton_conductor.py
src/teachintent/evaluator/normalization.py
src/teachintent/prompts/speech_plan_v0_3.py
src/teachintent/prompts/speech_plan_v0_4.py
src/teachintent/renderers/_project_outputs.py
src/teachintent/renderers/batonvoice.py
src/teachintent/renderers/batonvoice_segmented.py
src/teachintent/segmented_web_service.py
tests/historical_artifacts.py
tests/test_baton_seg04_neutral_repeatability.py
tests/test_baton_seg04_repeatability.py
tests/test_baton_segment_isolation.py
tests/test_baton_segmented_candidate_runner.py
tests/test_batonvoice_renderer.py
tests/test_batonvoice_segmented.py
tests/test_historical_artifact_boundary.py
tests/test_hy3_baton_conductor.py
tests/test_prompt_v0_3.py
tests/test_prompt_v0_4.py
tests/test_segmented_web_api.py
tests/test_showcase_runtime.py
```

## Files already tracked and retained

All 256 previously tracked files are retained. The final tree contains
**297 tracked files**. Existing unchanged files need no new staging:

- Core `src/teachintent/` modules; explicit prompt versions and registry;
  input/Speech Plan models, parsers, validation and frozen evaluator contracts.
- `schemas/`, canonical `cases/`, frozen protocol and specification documents.
- Existing frontend source/configuration, `frontend/package.json` and
  `frontend/package-lock.json`; tests and imported CLI/helper dependencies.
- `LICENSE`, `AGENTS.md`, project configuration and referenced documentation.
- `examples/`, `public_demo/evaluator_artifacts/`, all voice manifests and the
  six approved WAVs below. No artifact text, version, hash or audio is changed.
- Curated `public_results/` CSV/JSON summaries, distinct from ignored `results/`.

Hy3 v0.3/v0.4, Baton adapter/diagnostics, segmented renderer, experimental Web
integration, structured evidence normalization and historical-artifact boundaries
ship together with their existing tests. This task only adds Showcase/navigation,
process management, tests and release documentation; it does not revise model,
prompt/schema/evaluator/renderer behavior or recorded experiment results.

## Files to exclude

Keep files on disk. Do not stage, force-add or bulk-copy:

- `outputs/`, `results/`, GPU experiment WAV/JSON, diagnostics, temporary logs,
  debug dumps, browser screenshots/reports and local test products.
- `node_modules/`, `frontend/node_modules/`, `frontend/dist/`, coverage/build
  caches, `.pytest_cache/`, `__pycache__/`, `.pyc`, virtual environments.
- `.vscode/`, real `.env`, API keys, `auth.json`, credentials, private keys,
  shell/browser state or cookies.
- Model weights/checkpoints/cache, upstream/runtime installations and external
  reference prompt audio. None is needed for frozen Showcase.
- `scripts/run_k0_ef.py` and `scripts/run_k0_i.py`: retired, not imported by
  release source/tests; intentionally left untracked, not deleted.

Runtime PID state, lock, logs and temporary files belong exclusively under
`outputs/showcase-runtime/` inside TeachIntent; no runtime state is committed.

## Licensing decision required

**None remains for this approved publication set.** On 2026-09-14 the project
owner confirmed that these six files are self-generated synthetic demonstration
audio for TeachIntent public demo, without real participant recordings or private
user data. See [THIRD_PARTY.md](THIRD_PARTY.md). This owner statement does not
relicense any external model, checkpoint or upstream source.

### Six retained WAVs

```text
public_demo/voice/corrective-feedback/v0_2/neutral.wav
public_demo/voice/corrective-feedback/v0_2/planned.wav
public_demo/voice/scaffolding/v0_2/neutral.wav
public_demo/voice/scaffolding/v0_2/planned.wav
public_demo/voice/supportive-feedback/v0_2/neutral.wav
public_demo/voice/supportive-feedback/v0_2/planned.wav
```

Total: 5,433,864 bytes (5.18 MiB). Original bytes and manifest hashes are preserved.
The current tree and existing history retain the audio; no history rewrite or
removal is part of the release.

Option A preserves stable Explore/Showcase A/B playback. Supportive Feedback
correctly shows identical audio for its empty delivery plan. Option B is **not
selected**: without WAVs, existing backend/UI behavior already reports optional
audio unavailable while keeping plans/evaluation intact; corresponding README
and distribution wording would need adjustment. Removing tracked files alone
would not remove prior Git-history blobs. No such removal is authorized or done.

## Verification

- Backend core: **1339 passed, 152 deselected**. Python 3.10, plugin autoload
  disabled, project-local TMPDIR. This installed dependency environment needs
  `PYTHONPATH="$PWD/src"` because TeachIntent is not installed editable there.
- Frontend: **59 passed** across 11 files; `npm run build` passed (Node 20).
- Browser: Chromium at 1440×900 and 1920×1080; three recorded cases, real v0.2
  labels, WHAT/HOW, six evaluator dimensions/details, empty delivery behavior,
  six WAVs with advancing playback, Live Studio link and browser history.
  No page errors; only local GET requests; no provider/model calls.
- HTTP: `/`, `/showcase`, `/live`, `/explore`, `/compare`, health and recorded
  example routes respond successfully. Runtime startup selects nearby free
  ports, repeated start reuses owned servers, and stop verifies ownership.
- Git: inspect the exact staged file list, secret/large-file exclusions,
  `git diff --check`, `git diff --cached --check` and cached stat before commit.

Browser/HTTP/runtime evidence stays under ignored `outputs/showcase-verification/`.
The short presentation flow is [GROUP_MEETING_SHOWCASE.md](GROUP_MEETING_SHOWCASE.md).
A separate submission video is outside this GitHub + running Showcase deliverable.

## Suggested commit message

```text
feat: finalize TeachIntent pedagogical speech planning system
```

Commit the approved accumulated release and Showcase as one coherent change.
Push `feat/batonvoice-k0`; fast-forward `main` only if remote main is an ancestor
and the update can preserve remote work without conflict or force. Preserve
repository visibility and existing history; create no new release tag.
