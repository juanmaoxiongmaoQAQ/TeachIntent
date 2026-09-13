"""Fixed-condition repeats and diagnostic-only token observation, entirely offline."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from teachintent.renderers.batonvoice import (
    BatonVoiceConfig, BatonVoiceRenderError, BatonVoiceRenderResult,
    _ExecutorObservation,
)
# Reuse the existing fake vLLM/tokenizer/audio fixture, without editing production code.
from test_batonvoice_renderer import fake_unified, observed_backend  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("seg04_repeat_cli", ROOT / "scripts/diagnose_baton_seg04_repeatability.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def tmp_path(project_tmp_path):
    return project_tmp_path


@pytest.fixture
def config(tmp_path):
    paths = [tmp_path / name for name in ("model", "cosy", "source", "fst")]
    for path in paths:
        path.mkdir()
    for lang in ("zh", "en"):
        folder = paths[3] / lang / "tn"
        folder.mkdir(parents=True)
        for name in ("tagger.fst", "verbalizer.fst"):
            (folder / name).write_bytes(b"offline FST")
    (paths[0] / "generation_config.json").write_text(json.dumps({
        "temperature": 0.6, "top_p": 0.95, "top_k": 20, "eos_token_id": [151645, 151643],
    }))
    prompt = tmp_path / "prompt.wav"
    prompt.write_bytes(b"unchanged offline speaker fixture")
    return BatonVoiceConfig(*paths, prompt_audio_path=prompt, speech_speed=0.85)


@pytest.fixture
def fake_backend():
    state = SimpleNamespace(loads=0, closes=0, calls=[], configs=[], fail_at=None,
                            load_error=False, close_error=False, bad_sampling=False,
                            interrupt_at=None, bad_roundtrip=False)

    class Backend:
        def __init__(self, config):
            state.loads += 1
            state.configs.append(config)
            if state.load_error:
                raise RuntimeError("PRIVATE_LOAD_ERROR")

        def render(self, text, plan, output_path):
            state.calls.append((text, copy.deepcopy(plan), output_path))
            if len(state.calls) == state.interrupt_at:
                raise KeyboardInterrupt()
            observer = _ExecutorObservation(text, json.dumps(plan, ensure_ascii=False), len(plan))
            hashes = dict.fromkeys(cli.HASH_FIELDS)
            proxy = cli._HashObserver(observer, hashes)
            sampling = dict(cli.SAMPLING)
            if state.bad_sampling:
                sampling["top_k"] = 99
            proxy.observe("sampling", SimpleNamespace(**sampling))
            raw = [0, 3, len(state.calls)]  # Different scheduled observations, not a seed change.
            proxy.observe("generation", [SimpleNamespace(outputs=[SimpleNamespace(
                token_ids=[151645] + [151769 + t for t in raw], finish_reason="stop", stop_reason=None,
            )])])
            if len(state.calls) == state.fail_at:
                raise BatonVoiceRenderError("PRIVATE_RENDER_ERROR", executor_diagnostics={**observer.snapshot(), **hashes})
            proxy.observe("extraction", [9] if state.bad_roundtrip else raw)
            output_path.write_bytes(b"unchanged offline WAV")
            return BatonVoiceRenderResult(output_path, 24000, 5.16, 1, 0.1, False, False,
                executor_diagnostics={**observer.snapshot(), **hashes,
                                      "token_ids": raw, "api_key": "PRIVATE_KEY", "generated_text": "PRIVATE_TEXT"})

        def close(self):
            state.closes += 1
            if state.close_error:
                raise RuntimeError("PRIVATE_CLOSE_ERROR")

    return state, Backend


def test_eight_fixed_calls_one_backend_unique_paths_complete_report(config, fake_backend, tmp_path):
    state, backend = fake_backend
    sample, _ = cli.fixed_sample(cli.DEFAULT_PLAN)
    assert cli.DEFAULT_REPEATS == 8
    assert cli.DEFAULT_OUTPUT_ROOT == ROOT / "outputs/baton-seg04-repeatability"
    path, report = cli.run_repeatability(config, output_root=tmp_path / "runs", backend_factory=backend)
    assert state.loads == state.closes == 1 and len(state.calls) == 8
    assert state.configs == [config]
    assert all(text == sample["text"] and plan == sample["plan"] for text, plan, _ in state.calls)
    assert sample["plan"] == [{"word": sample["text"], "pitch_mean": 232, "pitch_slope": 0,
                                "energy_rms": 0.008, "energy_slope": 0, "spectral_centroid": 1885}]
    assert hashlib.sha256(sample["text"].encode()).hexdigest() == cli.TEXT_SHA256
    names = [f"repeat_{i:02d}.wav" for i in range(1, 9)]
    assert [p.name for _, _, p in state.calls] == names
    assert all(p.resolve().is_relative_to(ROOT) for _, _, p in state.calls)
    assert {p.name for p in path.iterdir()} == {*names, "diagnostics.json", "LISTENING_TEMPLATE.md"}
    assert report["status"] == "completed" and report["repeats"] == 8
    assert report["speech_speed"] == 0.85 and report["expected_sampling_parameters"] == cli.SAMPLING
    assert report["speech_token_hash_encoding"] == cli.TOKEN_HASH_ENCODING
    assert report["prompt_audio_sha256"] == hashlib.sha256(config.prompt_audio_path.read_bytes()).hexdigest()
    for i, record in enumerate(report["samples"], 1):
        assert record["repeat_id"] == f"repeat_{i:02d}"
        assert record["text_sha256"] == cli.TEXT_SHA256
        assert record["feature_plan_sha256"] == hashlib.sha256(json.dumps(sample["plan"], ensure_ascii=False).encode()).hexdigest()
        assert set((*cli.EXECUTOR_FIELDS, *cli.HASH_FIELDS, *cli.WAV_FIELDS, "sampling_parameters")) <= record.keys()
        assert record["generation_finish_reason"] == "stop" and record["generation_stop_reason"] is None
        assert record["generation_token_count"] == 4 and record["raw_speech_token_count"] == 3
        assert record["raw_speech_token_sha256"] == record["extracted_speech_token_sha256"] == cli.token_sequence_sha256([0, 3, i])
        assert record["sampling_parameters"] == cli.SAMPLING
        assert record["sampling_matches_expected"] and record["executor_input_matches_expected"]
        assert record["speech_token_roundtrip_match"] is True and record["is_truncated"] is False
        assert record["duration_seconds"] == 5.16 and record["peak"] == 0.1
    serialized = (path / "diagnostics.json").read_text()
    assert json.loads(serialized) == report
    for forbidden in ("PRIVATE_", '"token_ids"', '"generated_text"', '"api_key"'):
        assert forbidden not in serialized
    template = (path / "LISTENING_TEMPLATE.md").read_text()
    for i in range(1, 9):
        assert f"## repeat_{i:02d}" in template
    for field in ("内容完整", "“所以”是否清楚：", "末尾“变化”是否完整：", "其他错字/漏字/重复："):
        assert template.count(field) == 8
    before = {p: p.read_bytes() for p in path.iterdir()}
    second, _ = cli.run_repeatability(config, repeats=1, output_root=tmp_path / "runs", backend_factory=backend)
    assert path != second and all(p.read_bytes() == data for p, data in before.items())


def test_token_hash_has_fixed_encoding_and_preserves_order():
    tokens = [0, 7, 123]
    before = tokens.copy()
    expected = hashlib.sha256(b"[0,7,123]").hexdigest()
    assert cli.token_sequence_sha256(tokens) == cli.token_sequence_sha256(tokens.copy()) == expected
    assert tokens == before
    assert cli.token_sequence_sha256([0, 7, 124]) != expected
    assert cli.token_sequence_sha256([7, 0, 123]) != expected
    assert cli.token_sequence_sha256([]) == hashlib.sha256(b"[]").hexdigest()
    with pytest.raises(ValueError):
        cli.token_sequence_sha256([True])


def test_hash_backend_preserves_real_wrapper_calls_and_path_b(observed_backend, tmp_path):
    # Reuse the fake upstream instance; run the subclass's actual render/observer methods.
    backend = cli.RepeatabilityBackend.__new__(cli.RepeatabilityBackend)
    backend._tts = observed_backend._tts
    backend._speech_speed = observed_backend._speech_speed
    sample, _ = cli.fixed_sample(cli.DEFAULT_PLAN)
    result = backend.render(sample["text"], sample["plan"], tmp_path / "observed.wav")
    tts = backend._tts
    d = result.executor_diagnostics
    assert d["raw_speech_token_sha256"] == d["extracted_speech_token_sha256"] == cli.token_sequence_sha256([0, 7])
    assert tts.tokens_sent_to_audio is tts.extracted
    assert len(tts.llm.calls) == len(tts.tokenizer_calls) == 1
    assert tts.returned_outputs is tts.llm.outputs
    assert tts.llm.completion.token_ids == [10, 151768, 151769, 151776, 151645]
    assert tts.calls[0][3] == {"speed": 0.85}
    assert {k: getattr(tts.sampling_params, k) for k in cli.SAMPLING} == cli.SAMPLING
    assert tts._executor_observer is None and "generate" not in vars(tts.llm)
    tts.reencoded_ids = [151769, 151778]
    changed = backend.render(sample["text"], sample["plan"], tmp_path / "mismatch.wav").executor_diagnostics
    assert changed["raw_speech_token_sha256"] != changed["extracted_speech_token_sha256"]
    assert tts.tokens_sent_to_audio == [0, 9]  # No substitution with Path A.
    assert len(tts.llm.calls) == len(tts.tokenizer_calls) == 2
    tts.extraction_error = RuntimeError("PRIVATE_EXTRACTION")
    with pytest.raises(RuntimeError) as error:
        backend.render(sample["text"], sample["plan"], tmp_path / "failed.wav")
    assert error.value.executor_diagnostics["raw_speech_token_sha256"] == d["raw_speech_token_sha256"]
    assert error.value.executor_diagnostics["extracted_speech_token_sha256"] is None
    assert tts._executor_observer is None and "generate" not in vars(tts.llm)
    tts.extraction_error = None
    del tts.llm.completion.token_ids
    missing = backend.render(sample["text"], sample["plan"], tmp_path / "missing.wav").executor_diagnostics
    assert missing["raw_speech_token_sha256"] is None  # Never carry a prior repeat's hash.
    assert missing["extracted_speech_token_sha256"] == cli.token_sequence_sha256([0, 9])
    # The ordinary backend still exports exactly its original diagnostics fields.
    normal = observed_backend.render(sample["text"], sample["plan"], tmp_path / "normal.wav")
    assert not set(cli.HASH_FIELDS) & normal.executor_diagnostics.keys()


def test_hash_failure_does_not_break_observation_or_change_extracted_values():
    observer = _ExecutorObservation("x", "[]", 0)
    hashes = dict.fromkeys(cli.HASH_FIELDS)
    extracted = [1.5]
    cli._HashObserver(observer, hashes).observe("extraction", extracted)
    assert extracted == [1.5] and observer.data["extracted_speech_token_count"] == 1
    assert hashes["extracted_speech_token_sha256"] is None and hashes["token_hash_error_type"] == "ValueError"


def test_failed_attempt_consumes_its_slot_without_retry(config, fake_backend, tmp_path):
    state, backend = fake_backend
    state.fail_at = 3
    path, report = cli.run_repeatability(config, output_root=tmp_path / "runs", backend_factory=backend)
    assert report["status"] == "incomplete" and len(state.calls) == 8
    assert state.loads == state.closes == 1
    assert report["samples"][2]["status"] == "error" and report["samples"][3]["status"] == "success"
    assert report["samples"][2]["raw_speech_token_sha256"] is not None
    assert report["samples"][2]["extracted_speech_token_sha256"] is None
    assert "PRIVATE_" not in (path / "diagnostics.json").read_text()


def test_actual_sampling_drift_stops_without_changing_parameters(config, fake_backend, tmp_path):
    state, backend = fake_backend
    state.bad_sampling = True
    _, report = cli.run_repeatability(config, output_root=tmp_path / "runs", backend_factory=backend)
    assert report["status"] == "condition_mismatch" and len(state.calls) == 1
    assert report["samples"][0]["sampling_parameters"]["top_k"] == 99
    assert report["samples"][1]["status"] == "not_run" and state.closes == 1


@pytest.mark.parametrize("attribute,status", [("load_error", "incomplete"), ("close_error", "cleanup_error"), ("bad_roundtrip", "incomplete")])
def test_lifecycle_and_diagnostic_failures_remain_explicit(config, fake_backend, tmp_path, attribute, status):
    state, backend = fake_backend
    setattr(state, attribute, True)
    path, report = cli.run_repeatability(config, output_root=tmp_path / "runs", backend_factory=backend)
    assert report["status"] == status and state.loads == 1
    assert "PRIVATE_" not in (path / "diagnostics.json").read_text()


def test_interrupt_preserves_evidence_and_template(config, fake_backend, tmp_path):
    state, backend = fake_backend
    state.interrupt_at = 2
    with pytest.raises(KeyboardInterrupt):
        cli.run_repeatability(config, output_root=tmp_path / "runs", backend_factory=backend)
    path = next((tmp_path / "runs").iterdir())
    report = json.loads((path / "diagnostics.json").read_bytes())
    assert report["status"] == "interrupted" and state.closes == 1 and len(state.calls) == 2
    assert report["samples"][1]["status"] == "interrupted"
    assert "## repeat_08" in (path / "LISTENING_TEMPLATE.md").read_text()


@pytest.mark.parametrize("change", ["speed", "sampling", "text", "features", "outside", "repeats"])
def test_fixed_condition_drift_rejected_before_loading(config, fake_backend, tmp_path, change):
    from dataclasses import replace
    state, backend = fake_backend
    kwargs = {"output_root": tmp_path / "runs", "backend_factory": backend}
    if change == "speed":
        config = replace(config, speech_speed=1.0)
    elif change == "sampling":
        p = config.model_path / "generation_config.json"
        generation = json.loads(p.read_bytes())
        generation["top_k"] = 99
        p.write_text(json.dumps(generation))
    elif change == "outside":
        kwargs["output_root"] = ROOT.parent / "outputs/forbidden"
    elif change == "repeats":
        kwargs["repeats"] = 0
    else:
        doc = json.loads(cli.DEFAULT_PLAN.read_bytes())
        if change == "text":
            doc["verbal_plan"]["segments"][3]["text"] += "改写"
        else:
            doc["delivery_plan"]["segment_overrides"][1]["prosody"]["pitch_level"] = "low"
        p = tmp_path / "changed.json"
        p.write_text(json.dumps(doc))
        kwargs["plan_path"] = p
    with pytest.raises(ValueError):
        cli.run_repeatability(config, **kwargs)
    assert state.loads == 0 and not (tmp_path / "runs").exists()


def test_cli_default_preview_never_reads_runtime_or_writes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: pytest.fail("No runtime in preview"))
    out = tmp_path / "preview"
    assert cli.main(["--output-root", str(out)]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "preview" and preview["repeats"] == 8
    assert preview["sampling_parameters"] == cli.SAMPLING and not out.exists()


def test_execute_delegates_to_one_instrumented_backend(config, fake_backend, tmp_path, monkeypatch):
    state, backend = fake_backend
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: config)
    monkeypatch.setattr(cli, "RepeatabilityBackend", backend)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HY3_API_KEY", raising=False)
    assert cli.main(["--execute", "--output-root", str(tmp_path / "runs")]) == 0
    assert state.loads == state.closes == 1 and len(state.calls) == 8
