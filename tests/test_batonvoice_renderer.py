import copy
import hashlib
import json
import sys
from dataclasses import replace
from types import SimpleNamespace
from pathlib import Path

import pytest

from teachintent.models.speech_plan import SpeechPlan
from teachintent.renderers.batonvoice import (
    BatonVoiceConfig,
    BatonVoiceRenderError,
    BatonVoiceRenderResult,
    BatonVoiceRenderer,
    BatonVoiceUnavailable,
    quantitative_plan_from_speech_plan,
    _UnifiedTTSBackend,
    _patch_local_wetext_frontend,
)


PLAN = [{
    "word": "Hello world.",
    "pitch_mean": 226,
    "pitch_slope": 0,
    "energy_rms": 0.008,
    "energy_slope": 0,
    "spectral_centroid": 1885,
}]


@pytest.fixture
def fake_unified(monkeypatch):
    class Unified:
        def __init__(self, **kwargs):
            self.sampling_params = None

        def _setup_sampling_params(self):
            self.sampling_params = SimpleNamespace(
                temperature=0.6, top_p=1, stop_token_ids=[151645],
                max_tokens=2048, repetition_penalty=1.1,
            )

        def text_features_to_speech(self, *args, **kwargs):
            self._setup_sampling_params()

    monkeypatch.setitem(sys.modules, "unified_tts", SimpleNamespace(UnifiedTTS=Unified))
    monkeypatch.setitem(sys.modules, "cosyvoice.cli.frontend", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "wetext", SimpleNamespace(Normalizer=lambda **kwargs: None))
    monkeypatch.setattr(sys, "path", list(sys.path))


@pytest.mark.parametrize("eos", [[151645, 151643], 151645])
def test_model_sampling_config_is_loaded_lazily(tmp_path, fake_unified, eos):
    cfg = config(tmp_path)
    backend = _UnifiedTTSBackend(cfg)
    assert backend._tts.sampling_params is None
    generation = {
        "temperature": 0.6, "top_k": 20, "top_p": 0.95,
        "eos_token_id": eos, "max_tokens": 999,
    }
    (cfg.model_path / "generation_config.json").write_text(json.dumps(generation))
    backend._tts._setup_sampling_params()
    params = backend._tts.sampling_params
    assert params.stop_token_ids == (eos if isinstance(eos, list) else [eos])
    assert (params.temperature, params.top_k, params.top_p) == (0.6, 20, 0.95)
    assert params.max_tokens == 2048
    assert params.repetition_penalty == 1.1


def test_missing_model_sampling_config_is_render_error(tmp_path, fake_unified):
    renderer = BatonVoiceRenderer(config(tmp_path))
    assert renderer.available
    assert renderer._backend is None
    with pytest.raises(BatonVoiceRenderError, match="BatonVoice render failed"):
        renderer.render(text="Hello world.", plan=PLAN, output_path=tmp_path / "out.wav")


@pytest.mark.parametrize("speed", [1.0, 0.92, 0.85, 1.15])
def test_speed_is_forwarded_to_mode2_without_changing_plan(tmp_path, fake_unified, speed):
    cfg = replace(config(tmp_path), speech_speed=speed)
    backend = _UnifiedTTSBackend(cfg)
    calls = []

    def capture(text, features, output, **kwargs):
        calls.append((text, json.loads(features), kwargs))
        return False

    backend._tts.text_features_to_speech = capture
    with pytest.raises(BatonVoiceRenderError, match="did not produce a WAV"):
        backend.render("Hello world.", PLAN, tmp_path / "out.wav")
    assert calls == [("Hello world.", PLAN, {"speed": speed})]
    assert backend._tts.sampling_params is None


@pytest.mark.parametrize("value", ["nan", "inf", "0", "0.5", "2", "invalid"])
def test_invalid_speed_env_is_unavailable(monkeypatch, tmp_path, value):
    for key in ("MODEL_PATH", "COSYVOICE_MODEL_DIR", "SOURCE_DIR", "WETEXT_FST_DIR"):
        monkeypatch.setenv("BATONVOICE_" + key, str(tmp_path))
    monkeypatch.setenv("BATONVOICE_SPEECH_SPEED", value)
    with pytest.raises(BatonVoiceUnavailable):
        BatonVoiceConfig.from_env()


@pytest.mark.parametrize("speed", [0.92, 0.85, 1.15])
def test_speed_env_default_and_opt_in(monkeypatch, tmp_path, speed):
    for key in ("MODEL_PATH", "COSYVOICE_MODEL_DIR", "SOURCE_DIR", "WETEXT_FST_DIR"):
        monkeypatch.setenv("BATONVOICE_" + key, str(tmp_path))
    monkeypatch.delenv("BATONVOICE_SPEECH_SPEED", raising=False)
    assert BatonVoiceConfig.from_env().speech_speed == 1.0
    monkeypatch.setenv("BATONVOICE_SPEECH_SPEED", str(speed))
    assert BatonVoiceConfig.from_env().speech_speed == speed


def test_local_wetext_fst_paths_are_installed_without_snapshot_download(tmp_path, monkeypatch):
    fst = tmp_path / "fst"
    for lang in ("zh", "en"):
        (fst / lang / "tn").mkdir(parents=True)
        for name in ("tagger.fst", "verbalizer.fst"):
            (fst / lang / "tn" / name).write_text("")
    captured = []
    class Normalizer:
        def __init__(self, **kwargs): captured.append(kwargs)
    frontend = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "cosyvoice.cli.frontend", frontend)
    monkeypatch.setitem(sys.modules, "wetext", SimpleNamespace(Normalizer=Normalizer))
    cfg = replace(config(tmp_path / "runtime"), wetext_fst_dir=fst)
    _patch_local_wetext_frontend(cfg)
    frontend.ZhNormalizer()
    frontend.EnNormalizer()
    assert {item["lang"] for item in captured} == {"zh", "en"}
    assert all("modelscope" not in str(item.values()) for item in captured)


def test_local_wetext_fst_missing_is_unavailable(tmp_path):
    with pytest.raises(BatonVoiceUnavailable, match="FST files are missing"):
        _patch_local_wetext_frontend(replace(config(tmp_path), wetext_fst_dir=tmp_path / "missing"))


def config(tmp_path: Path) -> BatonVoiceConfig:
    paths = [tmp_path / name for name in ("model", "cosy", "source", "fst")]
    for path in paths:
        path.mkdir(parents=True)
    for lang in ("zh", "en"):
        (paths[3] / lang / "tn").mkdir(parents=True)
        for name in ("tagger.fst", "verbalizer.fst"):
            (paths[3] / lang / "tn" / name).write_text("")
    return BatonVoiceConfig(paths[0], paths[1], paths[2], paths[3])


class FakeBackend:
    def __init__(self, cfg):
        self.calls = []

    def render(self, text, plan, output_path):
        self.calls.append((text, copy.deepcopy(plan), output_path))
        return BatonVoiceRenderResult(output_path, 24000, 0.5, 1, 0.2, False, False)

    def close(self):
        pass


def test_unavailable_without_configuration(monkeypatch):
    for name in (
        "BATONVOICE_MODEL_PATH",
        "BATONVOICE_COSYVOICE_MODEL_DIR",
        "BATONVOICE_SOURCE_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    renderer = BatonVoiceRenderer()
    assert renderer.available is False
    assert renderer.status()["available"] is False
    with pytest.raises(BatonVoiceUnavailable):
        renderer.render(text="Hello world.", plan=PLAN, output_path=Path("out.wav"))


def test_render_contract_is_lazy_and_injectable(tmp_path):
    constructed = []

    def factory(cfg):
        backend = FakeBackend(cfg)
        constructed.append(backend)
        return backend

    renderer = BatonVoiceRenderer(config(tmp_path), backend_factory=factory)
    assert constructed == []
    output = tmp_path / "out.wav"
    result = renderer.render(text="Hello world.", plan=PLAN, output_path=output)
    assert constructed and result.output_path == output
    assert constructed[0].calls[0][0] == "Hello world."
    renderer.close()


@pytest.mark.parametrize("field,value", [("pitch_mean", "226"), ("energy_rms", True)])
def test_invalid_quantitative_plan_rejected_before_backend(tmp_path, field, value):
    calls = []

    def factory(cfg):
        calls.append(True)
        return FakeBackend(cfg)

    plan = copy.deepcopy(PLAN)
    plan[0][field] = value
    with pytest.raises(BatonVoiceRenderError):
        BatonVoiceRenderer(config(tmp_path), backend_factory=factory).render(
            text="Hello world.", plan=plan, output_path=tmp_path / "out.wav"
        )
    assert calls == []


def test_config_from_env_uses_no_project_specific_paths(monkeypatch, tmp_path):
    values = {
        "BATONVOICE_MODEL_PATH": tmp_path / "model",
        "BATONVOICE_COSYVOICE_MODEL_DIR": tmp_path / "cosy",
        "BATONVOICE_SOURCE_DIR": tmp_path / "source",
        "BATONVOICE_WETEXT_FST_DIR": tmp_path / "fst",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, str(value))
    parsed = BatonVoiceConfig.from_env()
    assert parsed.model_path == values["BATONVOICE_MODEL_PATH"]


def test_speech_plan_translation_preserves_segment_text():
    speech_plan = {
        "verbal_plan": {"segments": [
            {"segment_id": "seg_01", "text": "First phrase."},
            {"segment_id": "seg_02", "text": "Second phrase."},
        ]},
        "delivery_plan": {},
    }
    translated = quantitative_plan_from_speech_plan(speech_plan)
    assert [item["word"] for item in translated] == ["First phrase.", "Second phrase."]
    assert all(item["pitch_mean"] == 226 for item in translated)


def mapped_delivery(delivery):
    plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {"segments": [
            {"segment_id": "seg_01", "text": "Hello world."},
            {"segment_id": "seg_02", "text": "Don't change  spacing!"},
        ]},
        "delivery_plan": delivery,
    }
    SpeechPlan.model_validate(plan)
    original = copy.deepcopy(plan)
    result = quantitative_plan_from_speech_plan(plan)
    assert result == quantitative_plan_from_speech_plan(copy.deepcopy(plan))
    assert plan == original
    assert [item["word"] for item in result] == [
        segment["text"] for segment in plan["verbal_plan"]["segments"]
    ]
    assert all(item["pitch_slope"] == item["energy_slope"] == 0 for item in result)
    assert all(item["spectral_centroid"] == 1885 for item in result)
    return result


@pytest.mark.parametrize("prosody,pitch,energy", [
    ({"pitch_level": "medium", "volume": "medium"}, 226, 0.008),
    ({"pitch_level": "low", "volume": "soft"}, 220, 0.0076),
    ({"pitch_level": "high", "volume": "loud"}, 232, 0.0084),
    ({"pitch_level": "x-high", "volume": "x-loud"}, 226, 0.008),
    ({"pitch_level": "x-low", "volume": "x-soft"}, 226, 0.008),
    ({"speaking_rate": "slow", "pitch_range": "high"}, 226, 0.008),
])
def test_mapping_allowlist(prosody, pitch, energy):
    for item in mapped_delivery({"global": {"prosody": prosody}}):
        assert item["pitch_mean"] == pitch
        assert item["energy_rms"] == energy


def test_mapping_empty_and_unsupported_controls_are_neutral():
    assert mapped_delivery({})[0] == PLAN[0]
    result = mapped_delivery({
        "global": {"attitudinal_tone": "gentle", "emotion": "calm"},
        "segment_overrides": [{
            "segment_id": "seg_01", "contour_shape": "falling",
            "boundary_after": {"strength": "strong"},
            "prominence_targets": [{"text": "world", "level": "strong"}],
        }],
    })
    assert result[0] == PLAN[0]


@pytest.mark.parametrize("level", ["moderate", "strong"])
def test_mapping_whole_segment_emphasis_is_capped_and_local(level):
    result = mapped_delivery({"segment_overrides": [{
        "segment_id": "seg_01",
        "prominence_targets": [{"text": "Hello world.", "level": level}],
    }]})
    assert result[0] == {**PLAN[0], "pitch_mean": 232, "energy_rms": 0.0084}
    assert result[1] == {**PLAN[0], "word": "Don't change  spacing!"}


@pytest.mark.parametrize("local,pitch,energy", [
    ({"volume": "soft"}, 232, 0.0076),
    ({"pitch_level": "default", "volume": "default"}, 226, 0.008),
    ({"pitch_level": "low"}, 220, 0.0084),
])
def test_mapping_inheritance_reset_and_explicit_controls_win(local, pitch, energy):
    result = mapped_delivery({
        "global": {"prosody": {"pitch_level": "high", "volume": "loud"}},
        "segment_overrides": [{
            "segment_id": "seg_01", "prosody": local,
            "prominence_targets": [{"text": "Hello world.", "level": "strong"}],
        }],
    })
    assert result[0]["pitch_mean"] == pitch
    assert result[0]["energy_rms"] == energy
    assert result[1]["pitch_mean"] == 232
    assert result[1]["energy_rms"] == 0.0084


@pytest.fixture
def observed_backend(tmp_path, monkeypatch, fake_unified):
    """Exercise the production wrappers with vLLM/tokenizer/audio substitutes."""
    base = sys.modules["unified_tts"].UnifiedTTS

    class LLM:
        def __init__(self):
            self.calls = []
            self.error = None
            self.completion = SimpleNamespace(
                text="PRIVATE_GENERATED_TEXT", finish_reason="stop", stop_reason=None,
                token_ids=[10, 151768, 151769, 151776, 151645],
                api_key="PRIVATE_COMPLETION_KEY",
            )
            self.outputs = [SimpleNamespace(outputs=[self.completion])]

        def generate(self, prompts, sampling_params):
            self.calls.append((prompts, sampling_params))
            if self.error is not None:
                raise self.error
            return self.outputs

    class Unified(base):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = []
            self.extraction_error = None
            self.render_success = True
            self.reencoded_ids = [151769, 151776, 19]
            self.tokenizer_calls = []
            self.tokenizer = SimpleNamespace(encode=self.encode)

        def encode(self, text, **kwargs):
            self.tokenizer_calls.append((text, kwargs))
            return self.reencoded_ids

        def _generate_response(self, prompt):
            # Match the upstream call/return shape; no extra generation.
            self.returned_outputs = self.llm.generate([prompt], self.sampling_params)
            completion = self.returned_outputs[0].outputs[0]
            return completion.text, completion.finish_reason == "length"

        def _extract_mode2_outputs(self, generated_text, original_prompt):
            if self.extraction_error:
                raise self.extraction_error
            ids = self.tokenizer.encode(generated_text, add_special_tokens=False)
            self.extracted = [i - 151769 for i in ids if i >= 151769]
            return self.extracted

        def text_features_to_speech(self, text, features, output, **kwargs):
            if not hasattr(self, "llm"):
                self.llm = LLM()
                self._setup_sampling_params()
            self.calls.append((text, features, output, kwargs))
            prompt = "<custom_token_0>" + text + "<custom_token_1>" + features + "<custom_token_2>"
            generated, _ = self._generate_response(prompt)
            self.tokens_sent_to_audio = self._extract_mode2_outputs(generated, prompt)
            if self.render_success:
                Path(output).write_bytes(b"offline audio fixture")
            return self.render_success

    monkeypatch.setitem(sys.modules, "unified_tts", SimpleNamespace(UnifiedTTS=Unified))
    # Avoid optional audio packages too: no audio model or real WAV is needed
    # to verify diagnostics survive the existing result construction.
    class Wave:
        shape = (24, 1)
        size = 24

        def __len__(self):
            return 24

    no_bad_samples = SimpleNamespace(any=lambda: False)
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(read=lambda *a, **k: (Wave(), 24000)))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(
        isfinite=lambda _: True, isnan=lambda _: no_bad_samples,
        isinf=lambda _: no_bad_samples, abs=lambda _: 0.1, max=lambda value: value,
    ))
    cfg = replace(config(tmp_path / "runtime"), speech_speed=0.85)
    (cfg.model_path / "generation_config.json").write_text(json.dumps({
        "temperature": 0.6, "top_k": 20, "top_p": 0.95,
        "eos_token_id": [151645, 151643],
    }))
    backend = _UnifiedTTSBackend(cfg)
    assert not hasattr(backend._tts, "llm")  # Instrumentation preserves laziness.
    return backend


def test_executor_diagnostics_capture_exact_inputs_and_raw_completion(observed_backend, tmp_path, monkeypatch):
    backend = observed_backend
    text = "你好。  Keep  spacing!"
    plan = [{**PLAN[0], "word": f"part {i}"} for i in range(4)]
    original = copy.deepcopy(plan)
    monkeypatch.setenv("OPENROUTER_API_KEY", "PRIVATE_ENV_KEY")
    result = backend.render(text, plan, tmp_path / "out.wav")
    diagnostics = result.to_dict()["executor_diagnostics"]
    tts = backend._tts
    actual_text, actual_features, _, kwargs = tts.calls[0]
    assert actual_text == text
    assert actual_features == json.dumps(plan, ensure_ascii=False)
    assert diagnostics["input_text_sha256"] == hashlib.sha256(actual_text.encode()).hexdigest()
    assert diagnostics["input_text_char_count"] == len(text)
    assert diagnostics["feature_plan_sha256"] == hashlib.sha256(actual_features.encode()).hexdigest()
    assert diagnostics["feature_item_count"] == 4
    assert diagnostics["generation_finish_reason"] == "stop"
    assert diagnostics["generation_stop_reason"] is None
    assert diagnostics["is_truncated"] is False
    assert diagnostics["generation_token_count"] == 5  # NOT the 3 re-encoded IDs.
    assert diagnostics["raw_speech_token_count"] == 2  # Includes offset exactly.
    assert diagnostics["extracted_speech_token_count"] == 2
    assert diagnostics["speech_token_roundtrip_match"] is True
    assert diagnostics["speech_token_roundtrip_first_mismatch"] is None
    assert diagnostics["sampling_parameters"] == {
        "temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 2048,
        "repetition_penalty": 1.1, "stop_token_ids": [151645, 151643],
    }
    assert kwargs == {"speed": 0.85}
    assert plan == original
    assert len(tts.calls) == len(tts.llm.calls) == len(tts.tokenizer_calls) == 1
    assert tts.llm.calls[0][1] is tts.sampling_params
    assert tts.returned_outputs is tts.llm.outputs
    assert tts.llm.completion.token_ids == [10, 151768, 151769, 151776, 151645]
    assert tts.tokens_sent_to_audio is tts.extracted
    assert tts.tokenizer_calls == [("PRIVATE_GENERATED_TEXT", {"add_special_tokens": False})]
    assert "generate" not in vars(tts.llm)  # Temporary instance patch removed.
    assert tts._executor_observer is None
    public = json.dumps(diagnostics)
    for private in ("PRIVATE_ENV_KEY", "PRIVATE_COMPLETION_KEY", "PRIVATE_GENERATED_TEXT", text):
        assert private not in public
    assert set(diagnostics) == {
        "input_text_sha256", "input_text_char_count", "feature_plan_sha256", "feature_item_count",
        "generation_finish_reason", "generation_stop_reason", "generation_token_count", "is_truncated",
        "raw_speech_token_count", "extracted_speech_token_count", "speech_token_roundtrip_match",
        "speech_token_roundtrip_first_mismatch", "sampling_parameters",
    }
    # Only the approved stop-token list is exposed; snapshots are independent.
    assert all(not isinstance(value, list) for value in diagnostics.values())
    diagnostics["sampling_parameters"]["stop_token_ids"].append(999)
    assert tts.sampling_params.stop_token_ids == [151645, 151643]
    assert result.executor_diagnostics["sampling_parameters"]["stop_token_ids"] == [151645, 151643]


@pytest.mark.parametrize("raw,extracted,match,index", [
    ([0, 7], [0, 7], True, None),
    ([0, 7], [0, 8], False, 1),
    ([0, 7], [7, 0], False, 0),
    ([0, 7], [0], False, 1),
    ([0], [0, 7], False, 1),
    ([], [0], False, 0),
    ([0], [], False, 0),
    ([], [], True, None),
])
def test_roundtrip_exact_order_and_length(observed_backend, tmp_path, raw, extracted, match, index):
    backend = observed_backend
    backend.render("warmup", PLAN, tmp_path / "warmup.wav")
    tts = backend._tts
    tts.llm.completion.token_ids = [151645] + [151769 + t for t in raw]
    tts.reencoded_ids = [151769 + t for t in extracted]
    result = backend.render("test", PLAN, tmp_path / "out.wav")
    d = result.executor_diagnostics
    assert d["raw_speech_token_count"] == len(raw)
    assert d["extracted_speech_token_count"] == len(extracted)
    assert d["speech_token_roundtrip_match"] is match
    assert d["speech_token_roundtrip_first_mismatch"] == index
    assert tts.tokens_sent_to_audio == extracted  # Even on mismatch, preserve Path B.
    assert len(tts.llm.calls) == 2  # One call per render, never a retry.


@pytest.mark.parametrize("finish,stop", [("length", None), ("stop", 151643)])
def test_finish_and_actual_sampling_observations(observed_backend, tmp_path, finish, stop):
    backend = observed_backend
    backend.render("warmup", PLAN, tmp_path / "warmup.wav")
    tts = backend._tts
    tts.llm.completion.finish_reason = finish
    tts.llm.completion.stop_reason = stop
    tts.sampling_params.top_k = 17  # Fixture only: prove this isn't a hard-coded report.
    result = backend.render("test", PLAN, tmp_path / "out.wav")
    d = result.executor_diagnostics
    assert d["generation_finish_reason"] == finish
    assert d["generation_stop_reason"] == stop
    assert d["is_truncated"] is (finish == "length")
    assert d["sampling_parameters"]["top_k"] == 17
    assert result.output_path.is_file()  # Observation does not reject truncation.


@pytest.mark.parametrize("failure", ["generate", "extraction", "wav", "unavailable"])
def test_partial_diagnostics_survive_failure_and_do_not_leak_between_renders(
    observed_backend, tmp_path, failure,
):
    backend = observed_backend
    before = backend.render("first", PLAN, tmp_path / "first.wav").executor_diagnostics
    tts = backend._tts
    if failure == "generate":
        tts.llm.error = RuntimeError("generation failed")
    elif failure == "extraction":
        tts.extraction_error = RuntimeError("extraction failed")
    elif failure == "unavailable":
        tts.llm.error = BatonVoiceUnavailable("unavailable")
    else:
        tts.render_success = False
    renderer = BatonVoiceRenderer(config(tmp_path / "outer"), backend_factory=lambda _: backend)
    error_type = BatonVoiceUnavailable if failure == "unavailable" else BatonVoiceRenderError
    with pytest.raises(error_type) as error:
        renderer.render(text="second", plan=PLAN, output_path=tmp_path / "second.wav")
    d = error.value.executor_diagnostics
    assert d["input_text_sha256"] == hashlib.sha256(b"second").hexdigest()
    assert d["sampling_parameters"]["max_tokens"] == 2048
    if failure in ("generate", "unavailable"):
        assert d["generation_token_count"] is None
        assert d["is_truncated"] is None
    if failure != "wav":
        assert d["extracted_speech_token_count"] is None
        assert d["speech_token_roundtrip_match"] is None
    else:
        assert d["speech_token_roundtrip_match"] is True
    assert "generate" not in vars(tts.llm)
    assert tts._executor_observer is None
    assert before["input_text_sha256"] == hashlib.sha256(b"first").hexdigest()
    assert before["speech_token_roundtrip_match"] is True
    assert len(tts.llm.calls) == 2


def test_missing_raw_ids_stays_unknown_without_breaking_synthesis(observed_backend, tmp_path):
    backend = observed_backend
    backend.render("warmup", PLAN, tmp_path / "warmup.wav")
    del backend._tts.llm.completion.token_ids
    d = backend.render("test", PLAN, tmp_path / "out.wav").executor_diagnostics
    assert d["generation_finish_reason"] == "stop"
    assert d["generation_token_count"] is None
    assert d["raw_speech_token_count"] is None
    assert d["extracted_speech_token_count"] == 2
    assert d["speech_token_roundtrip_match"] is None


def test_instrumentation_restores_preexisting_instance_generate(observed_backend, tmp_path):
    backend = observed_backend
    backend.render("warmup", PLAN, tmp_path / "warmup.wav")
    original = backend._tts.llm.generate
    backend._tts.llm.generate = original
    backend.render("test", PLAN, tmp_path / "out.wav")
    assert vars(backend._tts.llm)["generate"] is original


def test_read_only_generate_method_does_not_block_synthesis(observed_backend, tmp_path):
    backend = observed_backend
    backend.render("warmup", PLAN, tmp_path / "warmup.wav")

    class ReadOnlyLLM:
        __slots__ = ("delegate",)

        def __init__(self, delegate):
            self.delegate = delegate

        def generate(self, *args, **kwargs):
            return self.delegate.generate(*args, **kwargs)

    backend._tts.llm = ReadOnlyLLM(backend._tts.llm)
    d = backend.render("test", PLAN, tmp_path / "out.wav").executor_diagnostics
    assert d["generation_token_count"] is None
    assert d["speech_token_roundtrip_match"] is None
    assert d["extracted_speech_token_count"] == 2
