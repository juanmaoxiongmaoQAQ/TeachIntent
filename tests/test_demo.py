from __future__ import annotations

import json

import pytest

from teachintent import demo


@pytest.mark.parametrize("example_name", sorted(demo.EXAMPLE_FILES))
@pytest.mark.parametrize("prompt_version", demo.PUBLIC_PROMPT_VERSIONS)
def test_bundled_recorded_examples_validate(example_name, prompt_version):
    example = demo.load_recorded_example(example_name, prompt_version)

    assert example["prompt_version"] == prompt_version
    assert example["source"]["reported_model"] == "tencent/hy3"
    assert example["speech_plan"]["verbal_plan"]["segments"]


def test_default_demo_is_offline_and_shows_required_sections(capsys):
    assert demo.main([]) == 0

    output = capsys.readouterr().out
    assert "recorded Hy3 artifact (offline; no API call)" in output
    assert "[Input context]" in output
    assert "[Pedagogical intent]" in output
    assert "corrective_feedback" in output
    assert "[Generated Speech Plan]" in output
    assert "verbal_plan:" in output
    assert "delivery_plan:" in output
    assert "firm but supportive" in output


def test_json_demo_payload_is_machine_readable(capsys):
    assert (
        demo.main(
            [
                "--example",
                "elicitation",
                "--prompt-version",
                "v0.1",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "recorded"
    assert payload["prompt_version"] == "v0.1"
    assert payload["pedagogical_intent"] == "elicitation"
    assert payload["generated_speech_plan"]["delivery_plan"]


def test_live_mode_uses_requested_prompt_version(monkeypatch, capsys):
    captured = {}

    def fake_run_live(input_doc, prompt_version):
        captured["intent"] = input_doc["pedagogical_intent"]["primary"]
        captured["prompt_version"] = prompt_version
        recorded = demo.load_recorded_example("scaffolding", prompt_version)
        return recorded["speech_plan"], {
            "evidence_kind": "live_demo_not_research_evidence",
            "requested_model": "tencent/hy3",
            "reported_model": "tencent/hy3",
            "prompt_version": prompt_version,
        }

    monkeypatch.setattr(demo, "_run_live", fake_run_live)

    assert (
        demo.main(
            [
                "--example",
                "scaffolding",
                "--prompt-version",
                "v0.2",
                "--live",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert captured == {
        "intent": "scaffolding",
        "prompt_version": "v0.2",
    }
    assert payload["mode"] == "live"
    assert payload["source"]["evidence_kind"] == "live_demo_not_research_evidence"
