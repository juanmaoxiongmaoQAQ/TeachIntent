# Experimental segmented Baton in Live Studio

## Release status (2026-09-14)

The project owner has since confirmed real GPU synthesis and browser sequential
playback: appropriate pauses, no obvious separation into recordings, continuous
speaker/loudness, and a clear improvement over the observed single-pass response.
Local swallowed sounds, missing final characters, unstable Mandarin punctuation,
synthetic quality and stochastic token variation remain reference-renderer
limitations. TTS research is now stopped; no further tuning or waveform work is
part of submission preparation. The player remains Experimental.

The implementation details and validation procedure below describe the earlier
integration stage; they are not a request to rerun that experiment.

This opt-in path tests whether independent segment WAVs form a natural complete
teaching response when played sequentially in the browser. It preserves the
single-pass endpoint, button, player, mapper, prompts and renderer implementations.
No real model or GPU was run during this Web implementation.

## Starting evidence

The user reports the first real candidate run preserved content in all four
Golden Case 1 segments: speech-token counts 107/87/102/110 and WAV durations
5.02/4.08/4.80/5.16 seconds. Totals are 406 tokens and 19.06 seconds, versus
216 and 10.16 seconds for the single-pass run (about 1.88 times each).
Single-pass had later content drift/compression despite normal stopping and
matching roundtrip. This is diagnostic evidence for the candidate's content
fidelity. Browser playback was unverified at that stage; the later owner-reported
listening result is recorded in the release status above.
Weak first commas in segments 2/3, slight “所以” slurring in segment 4, and the
synthetic voice quality remain observations; this integration does not correct them.

## API and session state

`POST /api/render/batonvoice-segmented` accepts only `{"session_id": "..."}`.
Unknown sessions return 404; extra properties such as filesystem paths return
422. A simultaneous segmented request for the same session returns 409.

The framework-independent `segmented_web_service.render_live_segmented()` reads
the current `LIVE_SESSION_STORE` session, copies `session.plan_doc`, and passes it
and the session's saved prompt version to one `SegmentedBatonVoiceRenderer.render()`
call. It never calls Generate, Hy3, Evaluate or single-pass rendering. The
existing renderer owns mapping, one backend per request, sequential synthesis,
per-segment diagnostics and cleanup. It reads existing BATONVOICE_* configuration;
the Web bridge does not change sampling, FST, speed or speaker conditioning.

The output root is fixed to `TeachIntent/outputs/baton-segmented/`. Neither request
JSON nor an audio URL can select an output root or arbitrary input file.

The response includes `session_id`, `renderer="batonvoice_segmented"`, `status`,
`run_id`, `speech_speed`, safe `manifest_metadata`, and verbal-order `segments`.
Each segment carries ID, one-based order, status, optional audio URL, duration,
text hash/count, numeric mapping, mapping diagnostics, typed executor/sampling
diagnostics and failure reasons. Metadata omits local runtime paths. Executor
and sampling models drop unknown fields: no raw token arrays, generated text,
API keys or exception messages are returned. The configured stop-token IDs
remain legitimate sampling metadata.

Returned candidate statuses `success`, `partial_failure`, `failed`, and
`interrupted` remain explicit, including non-success responses with HTTP 200.
The client must check the body status. The bridge additionally refuses to expose
a success URL if required execution diagnostics or its registered file are
unavailable. Setup exceptions yield a generic `failed` response. An interrupt
propagating from the candidate yields `interrupted` without a run registration;
the candidate still owns writing its interrupted manifest. There is no retry or
fallback. Cleanup/setup failure types are included when available in metadata.

`LiveSession.batonvoice_segmented_run` holds the current run ID, internal run
directory, registered successful segment paths and response metadata. A per-session
lock serializes access to render initiation. Old registration is invalidated when
a new attempt starts, even if the new attempt fails. Historical files remain
untouched. These registrations share the existing bounded in-memory session
lifetime: eviction or process restart makes URLs unavailable without deleting
the on-disk evidence. This adds no persistent or cross-worker session store.

## Read-only WAV serving

`GET /api/live/{session_id}/batonvoice-segmented/{run_id}/{segment_id}.wav`
resolves only registered successful audio from that session's **current** run.
It compares the run ID, validates the segment ID, checks the registered filename,
resolved directory and project containment, and requires an existing file.
Unknown segments/runs/sessions, traversal attempts, missing files and symlink
escapes return 404. A prior run's URL cannot resolve to a later run's audio.
Responses use `audio/wav` and `Cache-Control: no-store`. No static mount of the
output directory or manifest filesystem access is provided.

## Browser playback

Live Studio retains “Render with BatonVoice” and its single-pass player. A
separate “Segmented Baton candidate · Experimental” panel offers “Render segmented
candidate”. The child component is keyed by session ID, so switching sessions
unmounts the previous player and discards its pending network response.

On completion, segments are sorted by `order` and every successful URL is assigned
to its own HTML Audio element with `preload="auto"`. The “Play full segmented
response” button starts segment one. Each `ended` event advances immediately to
the next segment; the final event stops the queue. Stop resets playback, and
Restart starts again at segment one. These controls only play existing URLs;
they do not call any rendering, generation or evaluation endpoint.

Play promise rejection and audio loading errors stop playback visibly without
skipping a segment. Unmounting or starting a new render pauses the old elements;
stale rejected play promises cannot stop a restarted queue. Partial/failed/
interrupted results display their status and per-segment diagnostics with full
playback disabled. No failed segment is silently skipped to simulate a complete
response. The separate single-pass player remains independently controlled.

No WAV concatenation, inserted silence, splice, fades, crossfade or time/pitch
processing exists here. Preloading is a browser hint, not a guarantee: network,
decoding and event scheduling can still introduce a gap. Original end/start
silence in each WAV remains intact. This experiment does not implement precise
boundary timing or promise gapless/natural playback.

## Historical Live Studio validation procedure

1. Restore the same verified BATONVOICE_* runtime, prompt audio/speaker and GPU
   allocation. Set `BATONVOICE_SPEECH_SPEED=0.85`. Keep sampling at temperature
   0.6, top_p 0.95, top_k 20, max_tokens 2048, repetition_penalty 1.1, stop IDs
   `[151645, 151643]`. Place new server logs, temp files and runtime caches under
   TeachIntent/outputs. Start the existing Web API and frontend in the same
   environment; use a live session already containing the intended Speech Plan.
   Existing sessions are in-memory; this change does not import historical CLI
   runs or restore sessions lost on restart.
2. Confirm the displayed plan and saved prompt version, then click only “Render
   segmented candidate”. Verify one segmented POST, no Generate/Evaluate request,
   a fresh project-internal run directory and four ordered audio URLs. Inspect
   status, speed, actual sampling, stop/truncation and roundtrip diagnostics.
3. Click “Play full segmented response”. Listen to all three boundaries for gaps
   that are too short/long, audible separation into four recordings, speaker and
   loudness continuity, and whether segment 4 sounds like a reasonable conclusion.
   Record observations separately from the execution manifest in a fresh file.
4. Check Stop, Restart and final completion. Confirm replay adds no synthesis
   requests. Compare with preserved single-pass evidence using its separate
   control when available; do not regenerate an unfavorable baseline. Verify
   missing audio/partial failure cannot masquerade as complete playback.
5. Preserve the observations and artifacts. The release decision is to stop
   further naturalness research and document the remaining renderer limitations.

Offline coverage includes session reuse, candidate delegation, URL registration,
traversal/stale-run rejection, diagnostics/failure handling and single-pass API
regressions; browser mocks cover ordered preloading, ended transitions, completion,
stop/restart, stale requests and errors. Mock media tests establish control flow,
not real browser audio timing or human-perceived naturalness.
