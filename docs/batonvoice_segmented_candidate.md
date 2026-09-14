# BatonVoice segmented candidate

> **历史研发记录**
>
> 本文记录 segmented renderer candidate 的研发验证过程，不代表当前网页操作入口。当前支持范围与使用方式请参见 [renderer.md](renderer.md)。

The initial renderer design below is now complemented by the opt-in
[experimental Live Studio integration](batonvoice_segmented_web.md). That page
records the subsequently reported candidate GPU result and current web behavior;
the renderer's synthesis and waveform behavior remain unchanged.

Status: experimental implementation; offline tested. This is not a frozen
experiment protocol, a replacement for the production renderer, or confirmatory
evidence. No candidate GPU run was performed during implementation.

## Motivation and evidence boundary

The user-reported Golden Case 1 isolation experiment rendered four segments
independently with one loaded backend. All four preserved content in human
listening. The remaining observations were weak first-comma pauses in segments
2/3 and slight slurring of “所以” in segment 4. The corresponding single-pass
experience had later content drift despite normal stop, no truncation, correct
sampling and a matching speech-token roundtrip. This supports testing independent
generation as a candidate; it does not prove a general causal mechanism or that
sequential playback will sound natural across other plans.

Historical isolation evidence remains at its original location. All new candidate
and isolation-tool outputs must resolve inside the TeachIntent repository.

## Python interface and lifecycle

`teachintent.renderers.batonvoice_segmented.SegmentedBatonVoiceRenderer` exposes:

```python
run_dir, manifest = renderer.render(
    speech_plan=saved_plan,
    prompt_version="v0.4",  # Explicit provenance, no planner invocation.
    output_root=Path("outputs/baton-segmented"),
)
```

Each request validates the existing JSON Schema and Pydantic semantic rules,
then calls `quantitative_plan_from_speech_plan()` once on the complete plan.
The mapper returns verbal order without IDs. The candidate checks cardinality
and exact `word` equality, binds each item to its validated unique segment ID,
and subsequently retrieves features by that ID. Overrides retain global
inheritance and are independent of override-list order. Repeated text and
nonascending IDs are supported. No text, punctuation, or prosody is rewritten.

One existing `BatonVoiceRenderer(config)` is created per request. Its backend
loads lazily on the first segment and is reused for all sequential calls:

```text
verbal segment ID → unchanged complete text + [unchanged mapped item]
                 → existing renderer.render(...) → independent Mode 2 → its WAV
```

The facade's `close()` is called in `finally`. A subsequent request gets a fresh
facade and run directory. There is no shared concurrent backend or per-segment
reload. A backend initialization/unavailability failure stops pending segments
so it cannot trigger repeated loading attempts. An ordinary render failure is
recorded and execution continues to the next distinct segment. No retry or
fallback occurs. Cleanup errors and interrupts retain the manifest; interrupts
are re-raised after cleanup. A hard process kill or filesystem failure cannot
guarantee a complete manifest.

The original renderer, numeric mapper, sampling override, local WeText FST,
prompt audio, speaker conditioning, executor observer and configured speed are
used unchanged. The default speed remains 1.0. The next comparison must explicitly
use the reference experiment's 0.85. Existing mapper limitations also remain:
numeric features are approximations, and speaking-rate categories, boundaries,
contours and other unsupported controls gain no new realization here.

The candidate is imported explicitly from its own module. Neither
`POST /api/render/batonvoice`, its service implementation nor the current
“Render with BatonVoice” button calls it. The production path still performs
one full-text render and returns one WAV.

## Artifacts and manifest v1.0

Default directory:
`TeachIntent/outputs/baton-segmented/<UTC timestamp>-<UUID>/`.
The directory is created exclusively; prior runs are never reused. Files use
validated segment IDs (`seg_01.wav`, etc.), with `manifest.json` written once.
There is no full-response WAV. Output roots are resolved relative to the project,
and paths escaping it through `..`, absolute paths or existing symlinks are
rejected before any output or backend construction. This assumes the local
filesystem is not concurrently replacing directories or symlinks during a run.
The repository layout is required; this experimental path is not a standalone
installed-package storage API. `outputs/` is git-ignored.

| Scope | Fields |
| --- | --- |
| Run | `schema_version`, `run_id`, `renderer="batonvoice_segmented"`, `prompt_version`, `speech_speed`, `status`, `evidence_kind`, `content_fidelity_assessment` |
| Provenance | Source-plan SHA256 (documented JSON encoding), candidate/base renderer source SHA256, explicit runtime model/FST/source/prompt-audio paths and resource settings |
| Segment | `segment_id`, one-based `order`, `text_sha256`, `text_char_count`, `audio_filename`, feature-plan SHA256/count, `status`, `failure_reasons`, `error_type` |
| Mapping | `mapped`: pitch mean/slope, RMS energy/slope, spectral centroid; `mapping_diagnostics`: original global prosody, segment prosody override and prominence targets |
| Executor | Finish/stop reason, generation token count, truncation, raw/extracted speech-token counts, roundtrip match/first mismatch, actual text/feature hashes/counts |
| Sampling | Actual `temperature`, `top_p`, `top_k`, `max_tokens`, `repetition_penalty`, `stop_token_ids`, recorded independently per segment |
| WAV | `sample_rate`, `duration_seconds`, `channels`, `peak`, `nan`, `inf` |
| Lifecycle | Run-level `setup_error_type` and `cleanup_error_type` |

Manifest fields are explicitly selected: no environment dump, exception messages,
API keys, generated text or raw speech-token arrays are copied. The sampling
stop-token list is retained as configuration. Nonfinite WAV measurements become
JSON `null`; the original `nan`/`inf` flags remain recorded.

Any render failure, truncation or roundtrip mismatch marks that segment failed.
Missing required executor diagnostics, input hash/count mismatch, missing WAV or
invalid audio measurements also cannot report success. Failed WAVs remain as
evidence and must not be implicitly played as successful segments.

Run `status` is `success` only if all segments succeeded and cleanup completed;
`partial_failure` if at least one succeeded but the run was not wholly successful;
`failed` if none succeeded; `interrupted` for an interrupt. Pending segments remain
`not_run`. Consumers must check the run and segment statuses. Execution success
does **not** establish content fidelity: human listening is still required.

## Future sequential browser playback (design only)

A future opt-in candidate API could serve the manifest and individual audio URLs
in verbal order, using run/segment IDs to resolve files. It would not expose local
filesystem paths as URLs. With a user playback gesture, an HTML Audio controller
could play the first successful segment and advance on `ended`. It must handle
rejected play promises, audio errors, stop/cancel and stale events when switching
runs. A partial run should be shown explicitly and must not silently skip failed
segments to present an apparently complete response.

This is feasible without modifying any WAV. However, browser event scheduling,
decoding and network availability can add variable gaps, so `ended` sequencing
does not promise gapless playback or implement `boundary_after`. Preloading may
reduce loading delays but cannot establish naturalness. Subsequent listening
should assess within-segment fidelity, boundary gaps, speaker consistency and
overall teaching-response rhythm separately. No frontend playback controller,
API integration, concat, silence insertion, splice, fade, crossfade, PSOLA,
phase vocoder or duration editing is implemented in this candidate.

## Next GPU validation (not executed)

1. Reuse the saved Golden Case plan and the same BatonTTS, CosyVoice2, prompt
   audio/speaker conditioning, complete local FST and GPU resource settings.
   Set speed explicitly to 0.85. Preserve sampling 0.6 / 0.95 / 20 / 2048 / 1.1
   and stop IDs `[151645, 151643]`; do not alter defaults or upstream files.
2. Run the Python interface once. Place operator logs, temporary files and
   runtime-generated caches under a new `TeachIntent/outputs/...` directory as
   well; configure the runtime's cache/temp environment before launching it.
   Inspect actual per-segment sampling, hashes, stop/truncation, token roundtrip,
   WAV metrics and lifecycle status. Do not retry an unfavorable result.
3. Listen to all four independent WAVs and record omission/substitution/repetition,
   speed, punctuation pauses and the previously weak “所以” articulation. Record
   listening judgments separately from execution diagnostics in new files.
4. If eligible, a separately implemented opt-in browser experiment can evaluate
   ordered `ended` playback. Compare complete-response naturalness against the
   preserved single-pass/isolation evidence; do not regenerate those baselines
   or make a physical merged WAV. Only then decide whether a product experiment
   is justified.

Illustrative GPU entry point for that later run, **not an offline test**:

```python
import json
from pathlib import Path
from teachintent.renderers.batonvoice import BatonVoiceConfig
from teachintent.renderers.batonvoice_segmented import SegmentedBatonVoiceRenderer

config = BatonVoiceConfig.from_env()  # Same verified runtime environment.
assert config.speech_speed == 0.85
plan = json.loads(Path("cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json").read_bytes())
run_dir, manifest = SegmentedBatonVoiceRenderer(config).render(
    speech_plan=plan, prompt_version="v0.4",
    output_root=Path("outputs/baton-segmented"),
)
print(manifest["status"], run_dir / "manifest.json")
```

Offline verification uses fake backends only. New candidate/isolation test
artifacts live under `outputs/offline-tests/`; whole-suite `--basetemp`, `TMPDIR`,
logs and JUnit output should also be set to fresh directories within `outputs/`.
