"""Experimental web bridge to the existing segmented renderer; no synthesis logic."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from .app_service import LIVE_SESSION_STORE, LiveSessionStore, VoiceArtifactUnavailable
from .renderers._project_outputs import project_output_root
from .renderers.batonvoice_segmented import DEFAULT_OUTPUT_ROOT, SegmentedBatonVoiceRenderer
from .web_models import SegmentedBatonRenderResponse, SegmentedBatonSegment


class SegmentedRenderBusy(ValueError):
    pass


def render_live_segmented(
    session_id: str, *, session_store: LiveSessionStore = LIVE_SESSION_STORE,
    renderer: SegmentedBatonVoiceRenderer | None = None,
) -> SegmentedBatonRenderResponse:
    session = session_store.get(session_id)
    if not session.batonvoice_segmented_lock.acquire(blocking=False):
        raise SegmentedRenderBusy("A segmented render is already running for this session.")
    try:
        # Invalidate old URLs before starting; historical files remain untouched.
        session.batonvoice_segmented_run = None
        run_dir, manifest = (renderer or SegmentedBatonVoiceRenderer()).render(
            speech_plan=deepcopy(session.plan_doc), prompt_version=session.prompt_version,
            output_root=DEFAULT_OUTPUT_ROOT,
        )  # The candidate owns backend reuse, diagnostics, failure handling and cleanup.
        root = project_output_root(DEFAULT_OUTPUT_ROOT)
        run_dir = project_output_root(run_dir)
        run_id = manifest["run_id"]
        if run_dir.parent != root or run_dir.name != run_id:
            raise ValueError("Unexpected segmented run directory")
        source_segments = session.plan_doc["verbal_plan"]["segments"]
        records = manifest["segments"]
        if [r["segment_id"] for r in records] != [s["segment_id"] for s in source_segments]:
            raise ValueError("Segmented manifest order does not match the session")
        segments = []
        audio_paths = {}
        for order, record in enumerate(records, start=1):
            segment_id = record["segment_id"]
            if not re.fullmatch(r"seg_[0-9]{2,}", segment_id) or record["audio_filename"] != f"{segment_id}.wav":
                raise ValueError("Invalid segment artifact name")
            item = SegmentedBatonSegment(
                segment_id=segment_id, order=order, status=record["status"],
                duration_seconds=record["wav"]["duration_seconds"],
                text_sha256=record["text_sha256"], text_char_count=record["text_char_count"],
                mapped=record["mapped"], mapping_diagnostics={
                    key: deepcopy(record.get("mapping_diagnostics", {}).get(key))
                    for key in ("global_prosody", "segment_override", "prominence_targets")
                },
                executor_diagnostics=record["executor_diagnostics"],
                failure_reasons=record.get("failure_reasons", []),
            )
            diag = item.executor_diagnostics
            if item.status == "success" and (
                diag.is_truncated is not False or diag.speech_token_roundtrip_match is not True
                or diag.generation_finish_reason is None or diag.generation_token_count is None
                or diag.raw_speech_token_count is None or diag.extracted_speech_token_count is None
                or any(v is None for v in diag.sampling_parameters.model_dump().values())
            ):
                item.status = "failed"
                item.failure_reasons.append("executor_diagnostics_invalid")
            path = run_dir / record["audio_filename"]
            if item.status == "success":
                if path.resolve() != run_dir / record["audio_filename"] or not path.is_file():
                    item.status = "failed"
                    item.failure_reasons.append("audio_unavailable")
                else:
                    audio_paths[segment_id] = path
                    item.audio_url = f"/api/live/{session_id}/batonvoice-segmented/{run_id}/{segment_id}.wav"
            segments.append(item)
        status = manifest["status"]
        if status == "success" and (not segments or any(s.status != "success" for s in segments)):
            status = "partial_failure" if any(s.status == "success" for s in segments) else "failed"
        response = SegmentedBatonRenderResponse(
            session_id=session_id, status=status, run_id=run_id,
            speech_speed=manifest["speech_speed"], segments=segments,
            manifest_metadata={key: manifest.get(key) for key in (
                "schema_version", "prompt_version", "source_plan_sha256",
                "renderer_source_sha256", "base_renderer_source_sha256",
                "evidence_kind", "content_fidelity_assessment",
                "setup_error_type", "cleanup_error_type",
            )},
        )
        session.batonvoice_segmented_run = {
            "run_id": run_id, "run_dir": run_dir, "audio_paths": audio_paths,
            "response": response.model_dump(),
        }
        return response
    except KeyboardInterrupt:
        return SegmentedBatonRenderResponse(session_id=session_id, status="interrupted",
                                           reason="Segmented rendering was interrupted.")
    except Exception:
        # Do not expose exception messages, runtime paths or credentials.
        return SegmentedBatonRenderResponse(session_id=session_id, status="failed",
                                           reason="Segmented rendering failed; check the local diagnostics and runtime configuration.")
    finally:
        session.batonvoice_segmented_lock.release()


def resolve_segmented_audio(
    session_id: str, run_id: str, segment_id: str, *,
    session_store: LiveSessionStore = LIVE_SESSION_STORE,
) -> Path:
    run = session_store.get(session_id).batonvoice_segmented_run
    if not run or run["run_id"] != run_id or not re.fullmatch(r"seg_[0-9]{2,}", segment_id):
        raise VoiceArtifactUnavailable("Segment audio is unavailable.")
    path = run["audio_paths"].get(segment_id)
    try:
        root = project_output_root(DEFAULT_OUTPUT_ROOT)
        run_dir = project_output_root(run["run_dir"])
        if (path is None or run_dir.parent != root or run_dir.name != run_id
                or path.resolve() != run_dir / f"{segment_id}.wav" or not path.is_file()):
            raise ValueError("Unregistered or unavailable artifact")
    except (ValueError, OSError, RuntimeError):
        raise VoiceArtifactUnavailable("Segment audio is unavailable.") from None
    return path
