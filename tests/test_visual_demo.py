from __future__ import annotations

from pathlib import Path

from teachintent.visual_demo import build_visual_state, find_audio_pair


def test_offline_visual_state_uses_recorded_plan_and_evaluation() -> None:
    state = build_visual_state("corrective-feedback", "v0.2")

    assert state["mode"] == "recorded"
    assert "速度大小不变" in state["context_markdown"]
    assert "velocity_and_acceleration" not in state["context_markdown"]
    assert "seg_01" not in state["verbal_markdown"]
    assert "加速度并不为0" in state["verbal_markdown"]
    assert "Tone" in state["delivery_markdown"]
    assert "安抚但纠正" in state["delivery_markdown"]
    assert [row[0] for row in state["evaluation_rows"]] == [
        "D1",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
    ]
    assert all(row[2] == 4 for row in state["evaluation_rows"])
    assert "No live judge call was made" in state["evaluation_note"]


def test_primary_context_hides_prompt_injection_language() -> None:
    state = build_visual_state("corrective-feedback", "v0.2")

    assert "忽略教学任务" not in state["context_markdown"]
    assert "prompt" not in state["context_markdown"].lower()


def test_supportive_example_explains_empty_delivery() -> None:
    state = build_visual_state("supportive-feedback", "v0.2")

    assert "No additional delivery controls" in state["delivery_markdown"]
    assert state["tts_instruction"] == ""
    assert state["supported_controls"] == []
    assert len(state["evaluation_rows"]) == 6


def test_find_audio_pair_requires_both_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "scaffolding" / "v0_2"
    output_dir.mkdir(parents=True)
    (output_dir / "neutral.wav").write_bytes(b"neutral")
    assert find_audio_pair(tmp_path, "scaffolding", "v0.2")[:2] == (None, None)

    (output_dir / "planned.wav").write_bytes(b"planned")
    neutral, planned, found_dir = find_audio_pair(
        tmp_path, "scaffolding", "v0.2"
    )
    assert neutral == output_dir / "neutral.wav"
    assert planned == output_dir / "planned.wav"
    assert found_dir == output_dir


def test_live_mode_does_not_reuse_recorded_judge_evidence() -> None:
    def fake_live(input_doc: dict, prompt_version: str) -> tuple[dict, dict]:
        del input_doc, prompt_version
        return (
            {
                "schema_version": "1.0.0-rc.3",
                "verbal_plan": {
                    "segments": [{"segment_id": "seg_01", "text": "现场计划。"}]
                },
                "delivery_plan": {},
            },
            {"evidence_kind": "mock_live_not_research"},
        )

    state = build_visual_state(
        "corrective-feedback",
        "v0.2",
        live_hy3=True,
        live_runner=fake_live,
    )
    assert state["mode"] == "live"
    assert "现场计划" in state["verbal_markdown"]
    assert state["evaluation_rows"] == []
    assert "not automatically judged" in state["evaluation_note"]
