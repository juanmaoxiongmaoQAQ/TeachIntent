"""Minimal CLI checks; no real model, GPU, web service or remote credentials."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from teachintent.renderers.batonvoice_segmented import SegmentedBatonVoiceRenderer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "segmented_candidate_cli", ROOT / "scripts/run_baton_segmented_candidate.py",
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_defaults_and_real_renderer_binding():
    assert cli.DEFAULT_PLAN == ROOT / "cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json"
    assert cli.DEFAULT_PLAN.is_file()
    assert cli.DEFAULT_OUTPUT_ROOT == ROOT / "outputs/baton-segmented"
    assert cli.DEFAULT_OUTPUT_ROOT.resolve().is_relative_to(ROOT)
    assert cli.SegmentedBatonVoiceRenderer is SegmentedBatonVoiceRenderer


@pytest.mark.parametrize("status,exit_code", [("success", 0), ("partial_failure", 1), ("failed", 1)])
def test_cli_delegates_once_without_remote_credentials(monkeypatch, capsys, status, exit_code):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HY3_API_KEY", raising=False)
    config = SimpleNamespace(speech_speed=0.85)
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: config)
    calls = []

    class FakeCandidate:
        def __init__(self, actual):
            assert actual is config
            calls.append("init")

        def render(self, **kwargs):
            calls.append(kwargs)
            return cli.DEFAULT_OUTPUT_ROOT / "fake-run", {"status": status}

    monkeypatch.setattr(cli, "SegmentedBatonVoiceRenderer", FakeCandidate)
    assert cli.main([]) == exit_code
    assert calls == ["init", {
        "speech_plan": json.loads(cli.DEFAULT_PLAN.read_bytes()),
        "prompt_version": "v0.4", "output_root": cli.DEFAULT_OUTPUT_ROOT,
    }]
    output = capsys.readouterr()
    assert output.out.strip() == str(cli.DEFAULT_OUTPUT_ROOT / "fake-run")
    assert f"status: {status}" in output.err


def test_speed_drift_rejected_before_renderer(monkeypatch, capsys):
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: SimpleNamespace(speech_speed=1.0))
    monkeypatch.setattr(cli, "SegmentedBatonVoiceRenderer", lambda *_: pytest.fail("No renderer"))
    assert cli.main([]) == 2
    assert "BATONVOICE_SPEECH_SPEED=0.85" in capsys.readouterr().err


def test_outside_path_is_rejected_by_real_candidate_without_backend(monkeypatch):
    # The runner delegates path policy; the real candidate rejects before loading.
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: SimpleNamespace(speech_speed=0.85))
    assert cli.main(["--output-root", str(ROOT.parent / "outputs/forbidden")]) == 2


def test_help_does_not_read_environment_or_initialize_renderer(monkeypatch):
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: pytest.fail("No runtime"))
    monkeypatch.setattr(cli, "SegmentedBatonVoiceRenderer", lambda *_: pytest.fail("No renderer"))
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_interrupt_returns_130_without_retry(monkeypatch):
    monkeypatch.setattr(cli.BatonVoiceConfig, "from_env", lambda: SimpleNamespace(speech_speed=0.85))
    calls = []

    class InterruptedCandidate:
        def __init__(self, _):
            pass

        def render(self, **kwargs):
            calls.append(kwargs)
            raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "SegmentedBatonVoiceRenderer", InterruptedCandidate)
    assert cli.main([]) == 130 and len(calls) == 1
