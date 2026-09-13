"""Offline experimental API tests; existing renderer implementation is delegated."""

from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from teachintent import app_service, segmented_web_service as service
from teachintent.renderers.batonvoice import quantitative_plan_from_speech_plan
from teachintent.web_api import create_app
from teachintent.web_models import GenerationMetadata


@pytest.fixture
def setup(monkeypatch):
    store = app_service.LIVE_SESSION_STORE
    store.clear()
    plan = json.loads((app_service.REPO_ROOT / "cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json").read_bytes())
    session = app_service.LiveSession(
        input_doc={"saved": True}, plan_doc=plan, raw_response="PRIVATE_RAW_RESPONSE",
        prompt_version="v0.4", generation=GenerationMetadata(
            prompt_version="v0.4", requested_model="saved-model", duration_seconds=1,
        ),
    )
    session_id = store.create(session)
    def forbidden(*args, **kwargs):
        pytest.fail("No generation, evaluation or single-pass render in this path")
    for name in ("_default_generation_runner", "_default_evaluation_runner", "render_live_speech_plan"):
        monkeypatch.setattr(app_service, name, forbidden)
    state = SimpleNamespace(calls=[], created=0, status="success", bad_segment=None,
                            exception=None, extra_diagnostics={}, bad_path=False)

    class Candidate:
        def __init__(self):
            state.created += 1

        def render(self, **kwargs):
            state.calls.append(deepcopy(kwargs))
            if state.exception:
                raise state.exception
            run_id = "offline-web-" + uuid4().hex
            run_dir = kwargs["output_root"] / run_id
            run_dir.mkdir(parents=True)
            records = []
            for order, (segment, mapped) in enumerate(zip(
                kwargs["speech_plan"]["verbal_plan"]["segments"],
                quantitative_plan_from_speech_plan(kwargs["speech_plan"]),
            ), 1):
                filename = segment["segment_id"] + ".wav"
                (run_dir / filename).write_bytes(b"offline untouched WAV")
                diagnostics = {
                    "generation_finish_reason": "stop", "generation_stop_reason": None,
                    "generation_token_count": 31, "raw_speech_token_count": 30,
                    "extracted_speech_token_count": 30, "is_truncated": False,
                    "speech_token_roundtrip_match": True,
                    "sampling_parameters": {"temperature": 0.6, "top_p": 0.95, "top_k": 20,
                        "max_tokens": 2048, "repetition_penalty": 1.1,
                        "stop_token_ids": [151645, 151643], "api_key": "PRIVATE_SAMPLING"},
                    "raw_token_ids": [151769], "generated_text": "PRIVATE_GENERATION",
                    **state.extra_diagnostics,
                }
                records.append({
                    "segment_id": segment["segment_id"], "order": order,
                    "audio_filename": filename, "status": "failed" if order == state.bad_segment else "success",
                    "wav": {"duration_seconds": order + 0.5},
                    "text_sha256": hashlib.sha256(segment["text"].encode()).hexdigest(),
                    "text_char_count": len(segment["text"]),
                    "mapped": {k: v for k, v in mapped.items() if k != "word"},
                    "mapping_diagnostics": {"global_prosody": {}, "api_key": "PRIVATE_MAPPING"},
                    "executor_diagnostics": diagnostics, "failure_reasons": [],
                })
            manifest = {"run_id": run_id, "status": state.status, "speech_speed": 0.85,
                        "schema_version": "1.0", "prompt_version": "v0.4", "segments": records,
                        "runtime": {"model_path": "/PRIVATE_PATH"}, "api_key": "PRIVATE_KEY"}
            (run_dir / "manifest.json").write_text(json.dumps(manifest))
            return (run_dir.parent.parent if state.bad_path else run_dir), manifest

    monkeypatch.setattr(service, "SegmentedBatonVoiceRenderer", Candidate)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HY3_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        yield client, session_id, session, state
    store.clear()


def render(setup):
    client, session_id, _, _ = setup
    response = client.post("/api/render/batonvoice-segmented", json={"session_id": session_id})
    assert response.status_code == 200
    return response.json()


def test_current_plan_delegated_once_four_ordered_urls_and_safe_response(setup):
    client, session_id, session, state = setup
    before = deepcopy(session.plan_doc)
    payload = render(setup)
    assert payload["status"] == "success" and payload["speech_speed"] == 0.85
    assert payload["renderer"] == "batonvoice_segmented"
    assert state.created == len(state.calls) == 1
    assert state.calls[0] == {"speech_plan": before, "prompt_version": "v0.4", "output_root": service.DEFAULT_OUTPUT_ROOT}
    assert session.plan_doc == before and session.evaluation is None
    assert [s["segment_id"] for s in payload["segments"]] == [s["segment_id"] for s in before["verbal_plan"]["segments"]]
    assert [s["order"] for s in payload["segments"]] == [1, 2, 3, 4]
    assert session.batonvoice_segmented_run["run_id"] == payload["run_id"]
    assert session.batonvoice_segmented_run["run_dir"].resolve().is_relative_to(app_service.REPO_ROOT)
    for segment in payload["segments"]:
        audio = client.get(segment["audio_url"])
        assert audio.status_code == 200 and audio.content == b"offline untouched WAV"
        assert audio.headers["content-type"] == "audio/wav"
        assert segment["executor_diagnostics"]["sampling_parameters"]["top_k"] == 20
    public = json.dumps(payload)
    assert "PRIVATE_" not in public and "raw_token_ids" not in public and "generated_text" not in public
    assert "runtime" not in public and session_id == payload["session_id"]


def test_rerender_invalidates_previous_urls_without_deleting_evidence(setup):
    client, _, session, _ = setup
    first = render(setup)
    old_dir = session.batonvoice_segmented_run["run_dir"]
    second = render(setup)
    assert first["run_id"] != second["run_id"]
    assert client.get(first["segments"][0]["audio_url"]).status_code == 404
    assert client.get(second["segments"][0]["audio_url"]).status_code == 200
    assert (old_dir / "seg_01.wav").read_bytes() == b"offline untouched WAV"


def test_only_current_session_registered_files_are_served(setup):
    client, session_id, session, _ = setup
    payload = render(setup)
    base = f"/api/live/{session_id}/batonvoice-segmented/{payload['run_id']}"
    for name in ("seg_99.wav", "manifest.json", "..%2Fmanifest.json", "%2e%2e%2Fseg_01.wav"):
        assert client.get(f"{base}/{name}").status_code == 404
    other = app_service.LIVE_SESSION_STORE.create(app_service.LiveSession(
        input_doc={}, plan_doc=session.plan_doc, raw_response="", prompt_version="v0.4", generation=session.generation,
    ))
    assert client.get(payload["segments"][0]["audio_url"].replace(session_id, other)).status_code == 404
    for identifier in ("../seg_01", "/seg_01", "seg_01.wav"):
        with pytest.raises(app_service.VoiceArtifactUnavailable):
            service.resolve_segmented_audio(session_id, payload["run_id"], identifier)
    path = session.batonvoice_segmented_run["audio_paths"]["seg_01"]
    path.rename(path.with_suffix(".missing"))
    assert client.get(payload["segments"][0]["audio_url"]).status_code == 404
    path.symlink_to(app_service.REPO_ROOT / "pyproject.toml")
    assert client.get(payload["segments"][0]["audio_url"]).status_code == 404


@pytest.mark.parametrize("status", ["partial_failure", "failed", "interrupted"])
def test_failure_status_preserved_with_no_failed_audio_url(setup, status):
    _, _, _, state = setup
    state.status, state.bad_segment = status, 2
    payload = render(setup)
    assert payload["status"] == status
    assert payload["segments"][1]["audio_url"] is None
    assert state.created == len(state.calls) == 1


@pytest.mark.parametrize("diagnostics", [{"is_truncated": True}, {"speech_token_roundtrip_match": False},
                                       {"generation_token_count": None}, {"sampling_parameters": {}}])
def test_invalid_diagnostics_cannot_claim_success(setup, diagnostics):
    setup[3].extra_diagnostics = diagnostics
    payload = render(setup)
    assert payload["status"] == "failed"
    assert all(s["audio_url"] is None for s in payload["segments"])


@pytest.mark.parametrize("exception,status", [(RuntimeError("PRIVATE_ERROR"), "failed"), (KeyboardInterrupt(), "interrupted")])
def test_exception_clears_old_run_and_releases_lock(setup, exception, status):
    client, _, session, state = setup
    old = render(setup)
    state.exception = exception
    payload = render(setup)
    assert payload["status"] == status and "PRIVATE_" not in json.dumps(payload)
    assert session.batonvoice_segmented_run is None
    assert not session.batonvoice_segmented_lock.locked()
    assert client.get(old["segments"][0]["audio_url"]).status_code == 404


def test_unknown_session_arbitrary_path_request_and_busy_rejected(setup):
    client, session_id, session, state = setup
    assert client.post("/api/render/batonvoice-segmented", json={"session_id": "missing"}).status_code == 404
    assert client.post("/api/render/batonvoice-segmented", json={"session_id": session_id, "output_root": "/tmp"}).status_code == 422
    session.batonvoice_segmented_lock.acquire()
    try:
        assert client.post("/api/render/batonvoice-segmented", json={"session_id": session_id}).status_code == 409
    finally:
        session.batonvoice_segmented_lock.release()
    assert state.created == 0


def test_renderer_cannot_register_an_unexpected_run_directory(setup):
    setup[3].bad_path = True
    assert render(setup)["status"] == "failed"
    assert setup[2].batonvoice_segmented_run is None


def test_symlink_loop_returns_404(setup):
    client, _, session, _ = setup
    payload = render(setup)
    path = session.batonvoice_segmented_run["audio_paths"]["seg_01"]
    path.rename(path.with_suffix(".fixture"))
    path.symlink_to(path.name)
    assert client.get(payload["segments"][0]["audio_url"]).status_code == 404
