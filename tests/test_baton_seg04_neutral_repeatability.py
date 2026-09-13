"""Offline single-variable neutral diagnostic; never regenerate real high evidence."""

import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from test_baton_seg04_repeatability import config, fake_backend  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("seg04_neutral_cli", ROOT / "scripts/diagnose_baton_seg04_neutral_repeatability.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def tmp_path(project_tmp_path):
    return project_tmp_path


@pytest.fixture
def reference(config, tmp_path):
    # Synthetic reference metadata only; no high renderer invocation or historical writes.
    _, source_sha, feature_sha = cli.neutral_sample()
    doc = {
        "run_id": "offline-high-reference", "status": "completed", "repeats": 8,
        "segment_id": "seg_04", "mapped": cli.high.FEATURES,
        "speech_speed": 0.85, "expected_sampling_parameters": cli.high.SAMPLING,
        "speech_token_hash_encoding": cli.high.TOKEN_HASH_ENCODING,
        "source_plan_sha256": source_sha, "runtime": cli._runtime(config),
        **cli.high.check_config(config),
        "renderer_source_sha256": cli.high.sha256((ROOT / "src/teachintent/renderers/batonvoice.py").read_bytes()),
        "diagnostic_script_sha256": cli.high.sha256(Path(cli.high.__file__).read_bytes()),
        "samples": [{
            "repeat_id": f"repeat_{i:02d}", "text_sha256": cli.high.TEXT_SHA256,
            "feature_plan_sha256": feature_sha, "sampling_parameters": cli.high.SAMPLING,
            "executor_input_matches_expected": True, "sampling_matches_expected": True,
            "generation_finish_reason": "stop", "is_truncated": False,
            "speech_token_roundtrip_match": True,
        } for i in range(1, 9)],
    }
    path = tmp_path / "high-reference.json"
    path.write_text(json.dumps(doc))
    return path


def run(config, fake_backend, reference, tmp_path, **kwargs):
    return cli.run_neutral_repeatability(config, high_diagnostics_path=reference,
        output_root=tmp_path / "neutral-runs", backend_factory=fake_backend[1], **kwargs)


def test_only_pitch_changes_and_shared_hash_backend_is_unchanged():
    old, _ = cli.high.fixed_sample(cli.DEFAULT_PLAN)
    before = copy.deepcopy(old)
    neutral, _, original_sha = cli.neutral_sample()
    assert neutral["text"] == old["text"]
    assert neutral["plan"][0]["word"] == old["plan"][0]["word"]
    assert {k for k in old["plan"][0] if old["plan"][0][k] != neutral["plan"][0][k]} == {"pitch_mean"}
    assert old["plan"][0]["pitch_mean"] == 232 and neutral["plan"][0]["pitch_mean"] == 226
    assert neutral["plan"] == [{"word": old["text"], "pitch_mean": 226, "pitch_slope": 0,
                                "energy_rms": 0.008, "energy_slope": 0, "spectral_centroid": 1885}]
    assert old == before and cli.high.FEATURES["pitch_mean"] == 232
    assert original_sha == hashlib.sha256(json.dumps(old["plan"], ensure_ascii=False).encode()).hexdigest()
    assert cli.RepeatabilityBackend is cli.high.RepeatabilityBackend
    assert cli.high.token_sequence_sha256([0, 7, 123]) == hashlib.sha256(b"[0,7,123]").hexdigest()


def test_eight_neutral_calls_one_load_report_template_and_immutable_reference(config, fake_backend, reference, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Must not run the high baseline")
    monkeypatch.setattr(cli.high, "run_repeatability", forbidden)
    state, _ = fake_backend
    original = reference.read_bytes()
    path, report = run(config, fake_backend, reference, tmp_path)
    assert cli.DEFAULT_REPEATS == 8
    assert cli.DEFAULT_OUTPUT_ROOT == ROOT / "outputs/baton-seg04-neutral-repeatability"
    assert state.loads == state.closes == 1 and len(state.calls) == 8
    assert state.configs == [config] and config.speech_speed == 0.85
    sample, _, _ = cli.neutral_sample()
    assert all(text == sample["text"] and plan == sample["plan"] for text, plan, _ in state.calls)
    names = [f"neutral_repeat_{i:02d}.wav" for i in range(1, 9)]
    assert [p.name for _, _, p in state.calls] == names
    assert all(p.resolve().is_relative_to(ROOT) for _, _, p in state.calls)
    assert {p.name for p in path.iterdir()} == {*names, "diagnostics.json", "LISTENING_TEMPLATE.md"}
    assert report["status"] == "completed" and report["condition"] == "neutral" and report["pitch_mean"] == 226
    assert report["speech_speed"] == 0.85 and report["expected_sampling_parameters"] == cli.high.SAMPLING
    assert report["speech_token_hash_encoding"] == cli.high.TOKEN_HASH_ENCODING
    assert report["only_feature_change"] == {"pitch_mean": {"from": 232, "to": 226}}
    assert report["high_reference"]["diagnostics_sha256"] == hashlib.sha256(original).hexdigest()
    feature_sha = hashlib.sha256(json.dumps(sample["plan"], ensure_ascii=False).encode()).hexdigest()
    for i, record in enumerate(report["samples"], 1):
        assert record["repeat_id"] == f"neutral_repeat_{i:02d}"
        assert record["text_sha256"] == cli.high.TEXT_SHA256
        assert record["feature_plan_sha256"] == feature_sha != report["high_reference"]["feature_plan_sha256"]
        assert record["condition"] == "neutral" and record["pitch_mean"] == 226
        assert set((*cli.high.EXECUTOR_FIELDS, *cli.high.HASH_FIELDS, *cli.high.WAV_FIELDS)) <= record.keys()
        assert record["sampling_parameters"] == cli.high.SAMPLING
        assert record["sampling_matches_expected"] and record["executor_input_matches_expected"]
        assert record["raw_speech_token_sha256"] == record["extracted_speech_token_sha256"] == cli.high.token_sequence_sha256([0, 3, i])
    serialized = (path / "diagnostics.json").read_text()
    assert json.loads(serialized) == report
    for forbidden in ("PRIVATE_", '"token_ids"', '"generated_text"', '"api_key"'):
        assert forbidden not in serialized
    template = (path / "LISTENING_TEMPLATE.md").read_text()
    for i in range(1, 9):
        assert f"## neutral_repeat_{i:02d}" in template
    for field in ("内容完整：是/否（待填写）", "“所以”是否清楚：", "末尾“方向的变化”是否完整：", "其他错字/漏字/重复："):
        assert template.count(field) == 8
    assert reference.read_bytes() == original
    before = {p: p.read_bytes() for p in path.iterdir()}
    second, _ = run(config, fake_backend, reference, tmp_path, repeats=1)
    assert second != path and all(p.read_bytes() == b for p, b in before.items())


@pytest.mark.parametrize("change", ["speed", "speaker", "fst", "sampling", "model_path", "source", "high_feature"])
def test_non_pitch_condition_changes_rejected_before_backend(config, fake_backend, reference, tmp_path, change):
    if change == "speed":
        config = replace(config, speech_speed=1.0)
    elif change == "speaker":
        config.prompt_audio_path.write_bytes(b"different speaker fixture")
    elif change == "fst":
        (config.wetext_fst_dir / "zh/tn/tagger.fst").write_bytes(b"changed FST")
    elif change == "sampling":
        path = config.model_path / "generation_config.json"
        data = json.loads(path.read_bytes())
        data["temperature"] = 0.7
        path.write_text(json.dumps(data))
    else:
        data = json.loads(reference.read_bytes())
        if change == "model_path":
            data["runtime"]["model_path"] = "different model"
        elif change == "source":
            data["renderer_source_sha256"] = "changed source"
        else:
            data["samples"][0]["feature_plan_sha256"] = "different feature"
        reference.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run(config, fake_backend, reference, tmp_path)
    assert fake_backend[0].loads == 0 and not (tmp_path / "neutral-runs").exists()


def test_sampling_drift_during_execution_stops_without_repair(config, fake_backend, reference, tmp_path):
    fake_backend[0].bad_sampling = True
    _, report = run(config, fake_backend, reference, tmp_path)
    assert report["status"] == "condition_mismatch" and len(fake_backend[0].calls) == 1
    assert report["samples"][0]["sampling_parameters"]["top_k"] == 99
    assert report["samples"][1]["status"] == "not_run" and fake_backend[0].closes == 1


def test_failure_consumes_slot_without_retry(config, fake_backend, reference, tmp_path):
    fake_backend[0].fail_at = 3
    _, report = run(config, fake_backend, reference, tmp_path)
    assert report["status"] == "incomplete" and len(fake_backend[0].calls) == 8
    assert report["samples"][2]["status"] == "error" and report["samples"][3]["status"] == "success"
    assert fake_backend[0].loads == fake_backend[0].closes == 1


@pytest.mark.parametrize("attribute,status", [("load_error", "incomplete"), ("close_error", "cleanup_error"), ("bad_roundtrip", "incomplete")])
def test_cleanup_and_failure_metadata(config, fake_backend, reference, tmp_path, attribute, status):
    setattr(fake_backend[0], attribute, True)
    path, report = run(config, fake_backend, reference, tmp_path)
    assert report["status"] == status and fake_backend[0].loads == 1
    assert "PRIVATE_" not in (path / "diagnostics.json").read_text()


def test_interrupt_still_cleans_up_and_records_remaining_trials(config, fake_backend, reference, tmp_path):
    fake_backend[0].interrupt_at = 2
    with pytest.raises(KeyboardInterrupt):
        run(config, fake_backend, reference, tmp_path)
    path = next((tmp_path / "neutral-runs").iterdir())
    report = json.loads((path / "diagnostics.json").read_bytes())
    assert report["status"] == "interrupted" and fake_backend[0].closes == 1
    assert report["samples"][1]["status"] == "interrupted" and report["samples"][2]["status"] == "not_run"


@pytest.mark.parametrize("escape", ["absolute", "symlink"])
def test_outside_output_rejected(config, fake_backend, reference, tmp_path, escape):
    output = ROOT.parent / "outputs/forbidden"
    if escape == "symlink":
        output = tmp_path / "escape"
        output.symlink_to(ROOT.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        cli.run_neutral_repeatability(config, output_root=output, high_diagnostics_path=reference,
                                     backend_factory=fake_backend[1])
    assert fake_backend[0].loads == 0


def test_default_preview_never_reads_runtime_or_generates_high(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.high.BatonVoiceConfig, "from_env", lambda: pytest.fail("No runtime"))
    monkeypatch.setattr(cli.high, "run_repeatability", lambda *a, **k: pytest.fail("No high execution"))
    out = tmp_path / "preview"
    assert cli.main(["--output-root", str(out)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["repeats"] == 8 and data["condition"] == "neutral"
    assert data["plan"][0]["pitch_mean"] == 226 and not out.exists()


def test_execute_uses_existing_backend_for_neutral_only(config, fake_backend, reference, tmp_path, monkeypatch):
    monkeypatch.setattr(cli.high.BatonVoiceConfig, "from_env", lambda: config)
    monkeypatch.setattr(cli, "RepeatabilityBackend", fake_backend[1])
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HY3_API_KEY", raising=False)
    assert cli.main(["--execute", "--high-diagnostics", str(reference), "--output-root", str(tmp_path / "neutral")]) == 0
    assert fake_backend[0].loads == fake_backend[0].closes == 1
    assert len(fake_backend[0].calls) == 8
    assert all(call[1][0]["pitch_mean"] == 226 for call in fake_backend[0].calls)
