"""Offline candidate tests through the real lazy facade and a fake backend."""

import copy
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from teachintent.renderers import batonvoice_segmented as candidate
from teachintent.renderers.batonvoice import (
    BatonVoiceConfig, BatonVoiceRenderer, BatonVoiceRenderResult,
    BatonVoiceRenderError, BatonVoiceUnavailable, quantitative_plan_from_speech_plan,
)


@pytest.fixture
def tmp_path(project_tmp_path):
    return project_tmp_path


@pytest.fixture
def plan():
    return json.loads((candidate.PROJECT_ROOT / "cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json").read_bytes())


@pytest.fixture
def runtime(tmp_path):
    paths = [tmp_path / name for name in ("model", "cosy", "source", "fst")]
    for path in paths:
        path.mkdir()
    prompt = tmp_path / "prompt.wav"
    prompt.write_bytes(b"offline speaker fixture")
    return BatonVoiceConfig(*paths, prompt_audio_path=prompt, speech_speed=0.85)


@pytest.fixture
def fake():
    state = SimpleNamespace(
        factories=0, loads=0, closes=0, calls=[], configs=[], error_at=None,
        error_type=BatonVoiceRenderError, diagnostics_override={}, diagnostics_at=None, bad_audio=False,
        skip_audio=False, cleanup_error=False, load_error=False,
    )

    class Backend:
        def __init__(self, config):
            state.loads += 1
            state.configs.append(config)
            if state.load_error:
                raise RuntimeError("PRIVATE_LOAD")

        def render(self, text, plan, output_path):
            state.calls.append((text, copy.deepcopy(plan), output_path))
            if len(state.calls) == state.error_at:
                if state.error_type is KeyboardInterrupt:
                    raise KeyboardInterrupt()
                raise state.error_type("PRIVATE_EXCEPTION", executor_diagnostics={
                    "is_truncated": True, "generation_finish_reason": "length",
                    "api_key": "PRIVATE_DIAGNOSTIC",
                })
            diagnostics = {
                "input_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "input_text_char_count": len(text),
                "feature_plan_sha256": hashlib.sha256(json.dumps(plan, ensure_ascii=False).encode()).hexdigest(),
                "feature_item_count": len(plan), "generation_finish_reason": "stop",
                "generation_stop_reason": None, "generation_token_count": len(state.calls) + 30,
                "is_truncated": False, "raw_speech_token_count": 30,
                "extracted_speech_token_count": 30, "speech_token_roundtrip_match": True,
                "speech_token_roundtrip_first_mismatch": None,
                "sampling_parameters": {
                    "temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 2048,
                    "repetition_penalty": 1.1, "stop_token_ids": [151645, 151643],
                    "api_key": "PRIVATE_SAMPLING",
                },
                "api_key": "PRIVATE_DIAGNOSTIC", "raw_token_ids": [151769],
                "generated_text": "PRIVATE_GENERATION",
            }
            if state.diagnostics_at is None or len(state.calls) == state.diagnostics_at:
                diagnostics.update(state.diagnostics_override)
            if not state.skip_audio:
                output_path.write_bytes(b"untouched backend WAV fixture")
            return BatonVoiceRenderResult(
                output_path, 24000, 1.5, 1, float("nan") if state.bad_audio else 0.2,
                state.bad_audio, False, executor_diagnostics=diagnostics,
            )

        def close(self):
            state.closes += 1
            if state.cleanup_error:
                raise RuntimeError("PRIVATE_CLEANUP")

    def factory(config):
        state.factories += 1
        return BatonVoiceRenderer(config, backend_factory=Backend)

    return state, factory


def run(plan, runtime, fake, tmp_path):
    return candidate.SegmentedBatonVoiceRenderer(runtime, renderer_factory=fake[1]).render(
        speech_plan=plan, prompt_version="v0.4", output_root=tmp_path / "runs",
    )


def test_four_calls_exact_mapping_single_backend_and_manifest(plan, runtime, fake, tmp_path, monkeypatch):
    original = copy.deepcopy(plan)
    state, factory = fake
    renderer = candidate.SegmentedBatonVoiceRenderer(runtime, renderer_factory=factory)
    assert state.factories == state.loads == 0
    monkeypatch.setenv("OPENROUTER_API_KEY", "PRIVATE_ENV")
    path, manifest = renderer.render(speech_plan=plan, prompt_version="v0.4", output_root=tmp_path / "runs")
    assert state.factories == state.loads == state.closes == 1
    assert state.configs == [runtime]  # Includes local FST, speaker audio, speed and resource settings.
    assert len(state.calls) == 4
    assert manifest["renderer"] == "batonvoice_segmented"
    assert manifest["schema_version"] == "1.0" and manifest["prompt_version"] == "v0.4"
    assert manifest["speech_speed"] == 0.85 and manifest["status"] == "success"
    assert manifest["content_fidelity_assessment"] == "human_listening_required"
    mapped = quantitative_plan_from_speech_plan(plan)
    for order, (segment, item, call, record) in enumerate(zip(
        plan["verbal_plan"]["segments"], mapped, state.calls, manifest["segments"],
    ), start=1):
        text, features, wav_path = call
        assert text == segment["text"] and features == [item]
        assert wav_path == path / record["audio_filename"]
        assert wav_path.resolve().is_relative_to(candidate.PROJECT_ROOT)
        assert wav_path.read_bytes() == b"untouched backend WAV fixture"
        assert record["segment_id"] == segment["segment_id"] and record["order"] == order
        assert record["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert record["text_char_count"] == len(text)
        assert record["mapped"] == {k: item[k] for k in candidate.MAPPED_FIELDS}
        diagnostics = record["executor_diagnostics"]
        assert diagnostics["generation_token_count"] == order + 30
        assert diagnostics["generation_finish_reason"] == "stop"
        assert diagnostics["generation_stop_reason"] is None
        assert diagnostics["is_truncated"] is False
        assert diagnostics["speech_token_roundtrip_match"] is True
        assert diagnostics["speech_token_roundtrip_first_mismatch"] is None
        assert diagnostics["raw_speech_token_count"] == diagnostics["extracted_speech_token_count"] == 30
        assert diagnostics["sampling_parameters"] == {
            "temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 2048,
            "repetition_penalty": 1.1, "stop_token_ids": [151645, 151643],
        }
        assert record["wav"] == {"sample_rate": 24000, "duration_seconds": 1.5,
                                 "channels": 1, "peak": 0.2, "nan": False, "inf": False}
    assert len({call[2] for call in state.calls}) == 4
    assert {p.name for p in path.iterdir()} == {"manifest.json", "seg_01.wav", "seg_02.wav", "seg_03.wav", "seg_04.wav"}
    content = (path / "manifest.json").read_text()
    assert json.loads(content) == manifest
    assert "PRIVATE_" not in content and "raw_token_ids" not in content and "generated_text" not in content
    assert plan == original
    before = {p: p.read_bytes() for p in path.iterdir()}
    second, _ = renderer.render(speech_plan=plan, prompt_version="v0.4", output_root=tmp_path / "runs")
    assert second != path and state.factories == state.loads == state.closes == 2
    assert all(p.read_bytes() == data for p, data in before.items())


def test_id_alignment_survives_reordering_and_identical_text(plan, runtime, fake, tmp_path):
    plan["verbal_plan"]["segments"] = list(reversed(plan["verbal_plan"]["segments"]))
    for segment in plan["verbal_plan"]["segments"]:
        segment["text"] = "  同一句话，保留标点。 "
    plan["delivery_plan"] = {
        "global": {"prosody": {"pitch_level": "low", "volume": "soft"}},
        "segment_overrides": [
            {"segment_id": "seg_02", "prosody": {"pitch_level": "high"}},
            {"segment_id": "seg_04", "prosody": {"volume": "loud"}},
        ],
    }
    _, manifest = run(plan, runtime, fake, tmp_path)
    assert [r["segment_id"] for r in manifest["segments"]] == ["seg_04", "seg_03", "seg_02", "seg_01"]
    assert [r["mapped"]["pitch_mean"] for r in manifest["segments"]] == [220, 220, 232, 220]
    assert [r["mapped"]["energy_rms"] for r in manifest["segments"]] == [0.0084, 0.0076, 0.0076, 0.0076]
    assert [call[1][0] for call in fake[0].calls] == quantitative_plan_from_speech_plan(plan)
    assert all(call[0] == "  同一句话，保留标点。 " for call in fake[0].calls)
    assert manifest["segments"][0]["mapping_diagnostics"]["segment_override"] == {"volume": "loud"}


@pytest.mark.parametrize("error_type,call_count", [(BatonVoiceRenderError, 4), (BatonVoiceUnavailable, 2)])
def test_render_failure_retained_without_retry(plan, runtime, fake, tmp_path, error_type, call_count):
    state, _ = fake
    state.error_at, state.error_type = 2, error_type
    path, manifest = run(plan, runtime, fake, tmp_path)
    assert manifest["status"] == "partial_failure"
    assert len(state.calls) == call_count and state.loads == state.closes == 1
    assert len({p for _, _, p in state.calls}) == call_count
    record = manifest["segments"][1]
    assert record["status"] == "failed" and record["error_type"] == error_type.__name__
    assert record["executor_diagnostics"]["is_truncated"] is True
    assert record["executor_diagnostics"]["generation_finish_reason"] == "length"
    assert "PRIVATE_" not in (path / "manifest.json").read_text()
    if error_type is BatonVoiceUnavailable:
        assert manifest["segments"][2]["status"] == "not_run"


@pytest.mark.parametrize("override,reason", [
    ({"is_truncated": True}, "generation_truncated"),
    ({"speech_token_roundtrip_match": False, "speech_token_roundtrip_first_mismatch": 2}, "speech_token_roundtrip_mismatch"),
    ({"is_truncated": None}, "executor_diagnostics_incomplete"),
    ({"sampling_parameters": {}}, "executor_diagnostics_incomplete"),
    ({"input_text_sha256": "wrong"}, "executor_input_mismatch"),
])
def test_bad_diagnostics_never_report_success(plan, runtime, fake, tmp_path, override, reason):
    fake[0].diagnostics_override = override
    path, manifest = run(plan, runtime, fake, tmp_path)
    assert manifest["status"] == "failed" and len(fake[0].calls) == 4
    assert all(reason in r["failure_reasons"] for r in manifest["segments"])
    assert len(list(path.glob("*.wav"))) == 4  # Preserve failed evidence.


@pytest.mark.parametrize("override", [{"is_truncated": True}, {"speech_token_roundtrip_match": False}])
def test_one_bad_segment_marks_partial_failure(plan, runtime, fake, tmp_path, override):
    fake[0].diagnostics_override, fake[0].diagnostics_at = override, 2
    _, manifest = run(plan, runtime, fake, tmp_path)
    assert manifest["status"] == "partial_failure" and len(fake[0].calls) == 4
    assert [r["status"] for r in manifest["segments"]] == ["success", "failed", "success", "success"]


@pytest.mark.parametrize("attribute,reason", [("bad_audio", "invalid_audio_metrics"), ("skip_audio", "audio_missing")])
def test_invalid_audio_cannot_succeed(plan, runtime, fake, tmp_path, attribute, reason):
    setattr(fake[0], attribute, True)
    _, manifest = run(plan, runtime, fake, tmp_path)
    assert manifest["status"] == "failed"
    assert reason in manifest["segments"][0]["failure_reasons"]
    json.dumps(manifest, allow_nan=False)


def test_load_failure_attempted_once(plan, runtime, fake, tmp_path):
    fake[0].load_error = True
    _, manifest = run(plan, runtime, fake, tmp_path)
    assert manifest["status"] == "failed" and fake[0].loads == 1 and not fake[0].calls
    assert manifest["segments"][0]["error_type"] == "BatonVoiceUnavailable"
    assert all(r["status"] == "not_run" for r in manifest["segments"][1:])


def test_cleanup_failure_preserves_manifest(plan, runtime, fake, tmp_path):
    fake[0].cleanup_error = True
    path, manifest = run(plan, runtime, fake, tmp_path)
    assert manifest["status"] == "partial_failure" and manifest["cleanup_error_type"] == "RuntimeError"
    assert len(fake[0].calls) == 4 and fake[0].closes == 1
    assert "PRIVATE_" not in (path / "manifest.json").read_text()


def test_interrupt_still_cleans_up_and_writes_manifest(plan, runtime, fake, tmp_path):
    fake[0].error_at, fake[0].error_type = 2, KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        run(plan, runtime, fake, tmp_path)
    assert len(fake[0].calls) == 2 and fake[0].closes == 1
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_bytes())
    assert manifest["status"] == "interrupted" and manifest["segments"][0]["status"] == "success"
    assert manifest["segments"][1]["status"] == "interrupted"


def test_factory_failure_records_setup_error(plan, runtime, tmp_path):
    def fail(_):
        raise RuntimeError("PRIVATE_SETUP")
    path, manifest = candidate.SegmentedBatonVoiceRenderer(runtime, renderer_factory=fail).render(
        speech_plan=plan, prompt_version="v0.4", output_root=tmp_path / "runs",
    )
    assert manifest["status"] == "failed" and manifest["setup_error_type"] == "RuntimeError"
    assert all(r["status"] == "not_run" for r in manifest["segments"])
    assert "PRIVATE_" not in (path / "manifest.json").read_text()


@pytest.mark.parametrize("change", ["duplicate", "unknown_override", "unsafe_id", "mapper_length", "mapper_text"])
def test_invalid_alignment_rejected_before_output(plan, runtime, fake, tmp_path, monkeypatch, change):
    segments = plan["verbal_plan"]["segments"]
    if change == "duplicate":
        segments[1]["segment_id"] = segments[0]["segment_id"]
    elif change == "unknown_override":
        plan["delivery_plan"]["segment_overrides"][0]["segment_id"] = "seg_999"
    elif change == "unsafe_id":
        segments[0]["segment_id"] = "../../escape"
    else:
        mapped = quantitative_plan_from_speech_plan(plan)
        if change == "mapper_length":
            mapped.pop()
        else:
            mapped[0]["word"] = "rewritten"
        monkeypatch.setattr(candidate, "quantitative_plan_from_speech_plan", lambda _: mapped)
    with pytest.raises(Exception):
        run(plan, runtime, fake, tmp_path)
    assert fake[0].factories == 0 and not (tmp_path / "runs").exists()


@pytest.mark.parametrize("kind", ["absolute", "relative", "symlink"])
def test_output_escape_rejected_before_backend_or_write(plan, runtime, fake, tmp_path, kind):
    root = candidate.PROJECT_ROOT
    if kind == "absolute":
        output = root.parent / "outputs/forbidden"
    elif kind == "relative":
        output = "../outputs/forbidden"
    else:
        output = tmp_path / "escape"
        output.symlink_to(root.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="inside the TeachIntent"):
        candidate.SegmentedBatonVoiceRenderer(runtime, renderer_factory=fake[1]).render(
            speech_plan=plan, prompt_version="v0.4", output_root=output,
        )
    assert fake[0].factories == 0
    assert candidate.DEFAULT_OUTPUT_ROOT == root / "outputs/baton-segmented"


def test_speed_default_is_not_changed(plan, runtime, fake, tmp_path):
    config = replace(runtime, speech_speed=1.0)
    _, manifest = run(plan, config, fake, tmp_path)
    assert fake[0].configs == [config] and manifest["speech_speed"] == 1.0
