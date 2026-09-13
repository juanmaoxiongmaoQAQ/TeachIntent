"""Offline experiment tests: real mapper/renderer facade, fake audio backend."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from teachintent.renderers.batonvoice import (
    BatonVoiceConfig, BatonVoiceRenderer, BatonVoiceRenderResult,
    BatonVoiceRenderError, BatonVoiceUnavailable,
)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "baton_isolation_cli", ROOT / "scripts/diagnose_baton_segment_isolation.py",
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

TEXTS = [
    "你观察得很对，匀速圆周运动里速度的大小确实没有变。",
    "不过，速度不仅仅包含大小，还包含方向。",
    "物体做圆周运动时，方向在不断改变，也就是速度在变化。",
    "所以加速度并不为零，因为加速度取决于速度的变化，包括方向的变化。",
]


@pytest.fixture
def tmp_path(project_tmp_path):
    return project_tmp_path


@pytest.fixture
def plan_doc():
    return json.loads(cli.DEFAULT_PLAN.read_bytes())


@pytest.fixture
def runtime(tmp_path):
    paths = [tmp_path / name for name in ("model", "cosy", "source", "fst")]
    for path in paths:
        path.mkdir()
    for lang in ("zh", "en"):
        folder = paths[3] / lang / "tn"
        folder.mkdir(parents=True)
        for name in ("tagger.fst", "verbalizer.fst"):
            (folder / name).write_text("offline FST fixture")
    audio = tmp_path / "reference.wav"
    audio.write_bytes(b"unchanged reference fixture")
    (paths[0] / "generation_config.json").write_text(json.dumps({
        "temperature": 0.6, "top_p": 0.95, "top_k": 20,
        "eos_token_id": [151645, 151643],
    }))
    return BatonVoiceConfig(*paths, prompt_audio_path=audio, speech_speed=0.85)


@pytest.fixture
def fake_renderer():
    state = SimpleNamespace(
        renderer_count=0, backend_count=0, calls=[], close_count=0,
        failure_at=None, failure_type=BatonVoiceRenderError,
        wrong_sampling=False, bad_audio=False, configs=[], cleanup_fails=False,
    )

    class Backend:
        def __init__(self, config):
            state.backend_count += 1
            state.configs.append(config)

        def render(self, text, plan, output_path):
            state.calls.append((text, copy.deepcopy(plan), output_path))
            if len(state.calls) == state.failure_at:
                raise state.failure_type("PRIVATE_EXCEPTION_KEY", executor_diagnostics={
                    "generation_finish_reason": "length", "is_truncated": True,
                    "api_key": "PRIVATE_DIAGNOSTIC_KEY",
                })
            output_path.write_bytes(b"offline WAV fixture")
            sampling = copy.deepcopy(cli.EXPECTED_SAMPLING)
            if state.wrong_sampling:
                sampling["top_k"] = 99
            d = {
                "input_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "input_text_char_count": len(text),
                "feature_plan_sha256": hashlib.sha256(json.dumps(plan, ensure_ascii=False).encode()).hexdigest(),
                "feature_item_count": len(plan), "generation_finish_reason": "stop",
                "generation_stop_reason": None, "generation_token_count": 31,
                "is_truncated": False, "raw_speech_token_count": 30,
                "extracted_speech_token_count": 30, "speech_token_roundtrip_match": True,
                "speech_token_roundtrip_first_mismatch": None, "sampling_parameters": sampling,
                "generated_text": "PRIVATE_GENERATED_TEXT", "token_ids": [151769],
                "api_key": "PRIVATE_DIAGNOSTIC_KEY",
            }
            return BatonVoiceRenderResult(
                output_path, 24000, 1.2, 1, float("nan") if state.bad_audio else 0.08,
                state.bad_audio, False, executor_diagnostics=d,
            )

        def close(self):
            state.close_count += 1
            if state.cleanup_fails:
                raise RuntimeError("PRIVATE_CLEANUP_KEY")

    def factory(config):
        state.renderer_count += 1
        return BatonVoiceRenderer(config, backend_factory=Backend)

    return state, factory


def test_golden_case_isolation_preserves_text_mapping_and_segmentation(plan_doc):
    original = copy.deepcopy(plan_doc)
    samples = cli.build_samples(plan_doc)
    assert [s["text"] for s in samples] == TEXTS
    assert [s["segment_id"] for s in samples] == ["seg_01", "seg_02", "seg_03", "seg_04"]
    for sample, pitch, energy in zip(samples, [226, 226, 226, 232], [0.0076, 0.008, 0.008, 0.008]):
        assert sample["feature_plan"] == [{
            "word": sample["text"], "pitch_mean": pitch, "energy_rms": energy,
            "pitch_slope": 0, "energy_slope": 0, "spectral_centroid": 1885,
        }]
    assert plan_doc == original


def test_mapper_global_inheritance_is_preserved(plan_doc):
    plan_doc["delivery_plan"]["global"] = {"prosody": {"pitch_level": "low"}}
    samples = cli.build_samples(plan_doc)
    assert [s["feature_plan"][0]["pitch_mean"] for s in samples] == [220, 220, 220, 232]


def test_one_backend_four_files_diagnostics_and_no_overwrite(tmp_path, runtime, fake_renderer, monkeypatch):
    state, factory = fake_renderer
    root = tmp_path / "outputs"
    root.mkdir()
    formal = root / "seg_01.wav"
    formal.write_bytes(b"immutable formal WAV")
    monkeypatch.setenv("OPENROUTER_API_KEY", "PRIVATE_ENV_KEY")
    run_dir, report = cli.run_isolation(cli.DEFAULT_PLAN, root, runtime, renderer_factory=factory)
    assert state.renderer_count == state.backend_count == state.close_count == 1
    assert len(state.calls) == 4
    assert state.configs == [runtime]
    assert state.configs[0].speech_speed == 0.85
    assert state.configs[0].prompt_audio_path == runtime.prompt_audio_path
    assert [t for t, _, _ in state.calls] == TEXTS
    assert all(len(plan) == 1 for _, plan, _ in state.calls)
    assert {p.name for p in run_dir.iterdir()} == {
        "seg_01.wav", "seg_02.wav", "seg_03.wav", "seg_04.wav", "diagnostics.json",
    }
    assert report["schema_version"] == "1.0"
    assert report["status"] == "completed"
    assert report["content_fidelity_assessment"] == "human_listening_required"
    assert report["source_plan_sha256"] == hashlib.sha256(cli.DEFAULT_PLAN.read_bytes()).hexdigest()
    assert report["runtime"]["speech_speed"] == 0.85
    assert json.loads((run_dir / "diagnostics.json").read_bytes()) == report
    expected_fields = {
        "segment_id", "condition", "wav_file", "status", "failure_type",
        "text_sha256", "text_char_count", "feature_plan_sha256", "feature_item_count",
        "pitch_mean", "energy_rms", "pitch_slope", "energy_slope", "spectral_centroid",
        "speech_speed", "generation_finish_reason", "generation_stop_reason", "generation_token_count",
        "is_truncated", "raw_speech_token_count", "extracted_speech_token_count",
        "speech_token_roundtrip_match", "speech_token_roundtrip_first_mismatch",
        "sampling_parameters", "sampling_matches_expected", "executor_input_matches_expected", "wav",
    }
    for record, (text, plan, path) in zip(report["samples"], state.calls):
        assert set(record) == expected_fields
        assert record["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert record["text_char_count"] == len(text)
        assert record["feature_plan_sha256"] == hashlib.sha256(json.dumps(plan, ensure_ascii=False).encode()).hexdigest()
        assert record["feature_item_count"] == 1
        assert record["generation_stop_reason"] is None
        assert record["generation_token_count"] == 31
        assert record["speech_token_roundtrip_match"] is True
        assert record["sampling_parameters"] == cli.EXPECTED_SAMPLING
        assert record["sampling_matches_expected"] is True
        assert record["executor_input_matches_expected"] is True
        assert record["wav"] == {"sample_rate": 24000, "duration_seconds": 1.2,
                                  "channels": 1, "peak": 0.08, "nan": False, "inf": False}
        assert path.parent == run_dir and path != formal
    public = (run_dir / "diagnostics.json").read_text()
    for secret in ("PRIVATE_ENV_KEY", "PRIVATE_DIAGNOSTIC_KEY", "PRIVATE_GENERATED_TEXT", '"token_ids"'):
        assert secret not in public
    before = {p: p.read_bytes() for p in run_dir.iterdir()}
    next_dir, _ = cli.run_isolation(cli.DEFAULT_PLAN, root, runtime, renderer_factory=factory)
    assert next_dir != run_dir
    assert all(path.read_bytes() == data for path, data in before.items())
    assert formal.read_bytes() == b"immutable formal WAV"


def test_optional_full_is_same_text_and_features(tmp_path, runtime, fake_renderer, plan_doc):
    state, factory = fake_renderer
    _, report = cli.run_isolation(cli.DEFAULT_PLAN, tmp_path / "out", runtime, include_full=True, renderer_factory=factory)
    assert len(state.calls) == 5 and state.backend_count == 1 and state.close_count == 1
    assert state.calls[0][0] == " ".join(TEXTS)
    assert state.calls[0][1] == cli.quantitative_plan_from_speech_plan(plan_doc)
    assert state.calls[0][2].name == "full.wav"
    assert report["samples"][0]["feature_item_count"] == 4


@pytest.mark.parametrize("error_type,expected_calls", [(BatonVoiceRenderError, 4), (BatonVoiceUnavailable, 2)])
def test_failures_preserved_without_retry_and_cleanup(tmp_path, runtime, fake_renderer, error_type, expected_calls):
    state, factory = fake_renderer
    state.failure_at = 2
    state.failure_type = error_type
    run_dir, report = cli.run_isolation(cli.DEFAULT_PLAN, tmp_path / "out", runtime, renderer_factory=factory)
    assert report["status"] == "incomplete"
    assert len(state.calls) == expected_calls and state.close_count == 1
    assert state.backend_count == 1
    failed = report["samples"][1]
    assert failed["failure_type"] == error_type.__name__
    assert failed["generation_finish_reason"] == "length" and failed["is_truncated"] is True
    assert failed["wav"]["duration_seconds"] is None
    assert "PRIVATE_" not in (run_dir / "diagnostics.json").read_text()
    if error_type is BatonVoiceUnavailable:
        assert report["samples"][2]["status"] == "not_run"


def test_actual_sampling_mismatch_stops_experiment_without_fixing_it(tmp_path, runtime, fake_renderer):
    state, factory = fake_renderer
    state.wrong_sampling = True
    _, report = cli.run_isolation(cli.DEFAULT_PLAN, tmp_path / "out", runtime, renderer_factory=factory)
    assert report["status"] == "invariant_error"
    assert len(state.calls) == state.close_count == 1
    assert report["samples"][0]["status"] == "success"
    assert report["samples"][0]["sampling_parameters"]["top_k"] == 99
    assert report["samples"][1]["status"] == "not_run"


def test_invalid_audio_metrics_remain_json_safe(tmp_path, runtime, fake_renderer):
    state, factory = fake_renderer
    state.bad_audio = True
    _, report = cli.run_isolation(cli.DEFAULT_PLAN, tmp_path / "out", runtime, renderer_factory=factory)
    assert report["samples"][0]["wav"]["peak"] is None
    assert report["samples"][0]["wav"]["nan"] is True
    json.dumps(report, allow_nan=False)


def test_cleanup_failure_does_not_lose_samples(tmp_path, runtime, fake_renderer):
    state, factory = fake_renderer
    state.cleanup_fails = True
    run_dir, report = cli.run_isolation(cli.DEFAULT_PLAN, tmp_path / "out", runtime, renderer_factory=factory)
    assert report["status"] == "cleanup_error" and len(report["samples"]) == 4
    assert "PRIVATE_CLEANUP_KEY" not in (run_dir / "diagnostics.json").read_text()


@pytest.mark.parametrize("change", ["speed", "sampling", "stop", "fst"])
def test_config_drift_rejected_before_renderer_or_output(tmp_path, runtime, fake_renderer, change):
    from dataclasses import replace
    state, factory = fake_renderer
    if change == "speed":
        runtime = replace(runtime, speech_speed=1.0)
    elif change == "fst":
        runtime = replace(runtime, wetext_fst_dir=None)
    else:
        path = runtime.model_path / "generation_config.json"
        doc = json.loads(path.read_bytes())
        doc["top_k" if change == "sampling" else "eos_token_id"] = 999
        path.write_text(json.dumps(doc))
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        cli.run_isolation(cli.DEFAULT_PLAN, out, runtime, renderer_factory=factory)
    assert state.renderer_count == 0 and not out.exists()


def test_invalid_segment_ids_rejected_before_output(tmp_path, plan_doc, runtime, fake_renderer):
    _, factory = fake_renderer
    plan_doc["verbal_plan"]["segments"][0]["segment_id"] = "../../formal"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(plan_doc))
    with pytest.raises(Exception):
        cli.run_isolation(path, tmp_path / "out", runtime, renderer_factory=factory)
    assert not (tmp_path / "out").exists()


def test_cli_preview_does_not_read_runtime_or_write_outputs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: pytest.fail("No runtime in preview"))
    monkeypatch.setattr(cli, "BatonVoiceRenderer", lambda *_: pytest.fail("No renderer in preview"))
    out = tmp_path / "out"
    assert cli.main(["--output-root", str(out)]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "preview" and len(preview["samples"]) == 4
    assert not out.exists()


def test_cli_execute_uses_injected_renderer(tmp_path, runtime, fake_renderer, monkeypatch):
    state, factory = fake_renderer
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: runtime)
    monkeypatch.setattr(cli, "BatonVoiceRenderer", factory)
    assert cli.main(["--execute", "--output-root", str(tmp_path / "out")]) == 0
    assert len(state.calls) == 4 and state.renderer_count == state.close_count == 1


def test_output_root_must_remain_inside_project(runtime, fake_renderer):
    state, factory = fake_renderer
    assert cli.DEFAULT_OUTPUT_ROOT.is_relative_to(ROOT)
    with pytest.raises(ValueError, match="inside the TeachIntent"):
        cli.run_isolation(cli.DEFAULT_PLAN, ROOT.parent / "outputs/forbidden", runtime, renderer_factory=factory)
    assert state.renderer_count == 0
