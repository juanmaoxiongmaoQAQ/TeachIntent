from __future__ import annotations

from pathlib import Path

import pytest

from teachintent.visual_demo import (
    CUSTOM_DELIVERY_STATUS,
    CUSTOM_EMPTY_DELIVERY_MESSAGE,
    CustomInputError,
    PEDAGOGICAL_INTENTS,
    REVIEWER_EXAMPLES,
    build_custom_input,
    build_visual_state,
    find_audio_pair,
    generate_custom_ui,
    generate_custom_visual_state,
    is_recommended_showcase,
    load_showcase_scenario_fields,
    switch_recorded_example,
)


@pytest.mark.parametrize("example_name", REVIEWER_EXAMPLES)
def test_reviewer_examples_build_visual_state(example_name: str) -> None:
    state = build_visual_state(example_name, "v0.2")

    assert state["mode"] == "recorded"
    assert state["example_name"] == example_name
    assert state["prompt_version"] == "v0.2"
    assert state["context_markdown"]
    assert state["verbal_markdown"]
    assert state["delivery_markdown"]


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
    assert "no additional delivery instruction" in state["audio_status"]
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


def test_switch_recorded_example_refreshes_text_and_audio_paths(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "scaffolding" / "v0_2"
    output_dir.mkdir(parents=True)
    neutral_path = output_dir / "neutral.wav"
    planned_path = output_dir / "planned.wav"
    neutral_path.write_bytes(b"neutral")
    planned_path.write_bytes(b"planned")

    (
        state,
        context,
        verbal,
        delivery,
        raw_json,
        evaluation_rows,
        evaluation_note,
        neutral_audio,
        planned_audio,
        audio_status,
        mapping_report,
    ) = switch_recorded_example("scaffolding", tmp_path)

    assert state["example_name"] == "scaffolding"
    assert state["prompt_version"] == "v0.2"
    assert "有限支架" in context
    assert verbal
    assert "How to say" not in delivery
    assert '"pedagogical_intent": "scaffolding"' in raw_json
    assert len(evaluation_rows) == 6
    assert "No live judge call was made" in evaluation_note
    assert neutral_audio == str(neutral_path)
    assert planned_audio == str(planned_path)
    assert "Loaded an existing local A/B pair" in audio_status
    assert "planned_instruct" in mapping_report


def test_switch_rejects_non_reviewer_example() -> None:
    with pytest.raises(ValueError):
        switch_recorded_example("elicitation")


def test_corrective_feedback_is_recommended_showcase() -> None:
    assert is_recommended_showcase("corrective-feedback") is True
    assert is_recommended_showcase("scaffolding") is False
    assert is_recommended_showcase("supportive-feedback") is False


def test_load_showcase_scenario_fills_input_fields_only() -> None:
    (
        content_anchor,
        teaching_scenario,
        learner_utterance,
        learner_level,
        knowledge_state,
        affective_state,
        pedagogical_intent,
    ) = load_showcase_scenario_fields()

    assert "加速度描述速度随时间的变化" in content_anchor
    assert "速度大小不变" in teaching_scenario
    assert "加速度就是0" in learner_utterance
    assert learner_level == "high_school"
    assert knowledge_state == "misconception"
    assert affective_state == "slightly_frustrated"
    assert pedagogical_intent == "corrective_feedback"


def test_custom_fields_build_valid_input_doc() -> None:
    input_doc = build_custom_input(
        content_anchor="加速度描述速度变化。",
        teaching_scenario="学生正在判断转弯车辆是否有加速度。",
        learner_utterance="速度大小没变，所以没有加速度。",
        learner_level="high_school",
        knowledge_state="confuses speed magnitude with acceleration",
        affective_state="slightly frustrated",
        pedagogical_intent="corrective_feedback",
    )

    assert input_doc == {
        "schema_version": "1.0.0-rc.2",
        "output_language": "zh-CN",
        "instructional_content": {"content_anchor": "加速度描述速度变化。"},
        "pedagogical_context": {
            "scenario": "学生正在判断转弯车辆是否有加速度。",
            "learner_utterance": "速度大小没变，所以没有加速度。",
        },
        "learner": {
            "level": "high_school",
            "knowledge_state": "confuses speed magnitude with acceleration",
            "affective_state": "slightly frustrated",
        },
        "pedagogical_intent": {"primary": "corrective_feedback"},
    }


def test_custom_optional_fields_are_omitted_when_empty() -> None:
    input_doc = build_custom_input(
        content_anchor="比例表示两个数量的相对关系。",
        teaching_scenario="学生正在学习比例。",
        learner_utterance="  ",
        learner_level="middle_school",
        knowledge_state="partial understanding",
        affective_state="",
        pedagogical_intent="scaffolding",
    )

    assert "learner_utterance" not in input_doc["pedagogical_context"]
    assert "affective_state" not in input_doc["learner"]


@pytest.mark.parametrize("intent", PEDAGOGICAL_INTENTS)
def test_custom_input_accepts_all_six_intents(intent: str) -> None:
    input_doc = build_custom_input(
        content_anchor="核心知识点。",
        teaching_scenario="学生正在学习。",
        learner_utterance="",
        learner_level="middle_school",
        knowledge_state="partial understanding",
        affective_state="",
        pedagogical_intent=intent,
    )

    assert input_doc["pedagogical_intent"]["primary"] == intent


def test_custom_empty_required_field_fails_before_live_runner() -> None:
    calls = 0

    def fake_live(input_doc: dict, prompt_version: str) -> tuple[dict, dict]:
        nonlocal calls
        calls += 1
        del input_doc, prompt_version
        return {}, {}

    with pytest.raises(CustomInputError):
        generate_custom_visual_state(
            content_anchor="",
            teaching_scenario="学生正在学习。",
            learner_utterance="",
            learner_level="middle_school",
            knowledge_state="partial understanding",
            affective_state="",
            pedagogical_intent="explanation",
            live_runner=fake_live,
        )
    assert calls == 0


def test_custom_generation_with_mock_live_runner_renders_speech_plan() -> None:
    captured = {}

    def fake_live(input_doc: dict, prompt_version: str) -> tuple[dict, dict]:
        captured["input_doc"] = input_doc
        captured["prompt_version"] = prompt_version
        return (
            {
                "schema_version": "1.0.0-rc.3",
                "verbal_plan": {
                    "segments": [
                        {"segment_id": "seg_01", "text": "先看速度是否变化。"}
                    ]
                },
                "delivery_plan": {
                    "global": {
                        "attitudinal_tone": "calm",
                        "emotion": "focused",
                        "prosody": {"speaking_rate": "slow"},
                    }
                },
            },
            {
                "evidence_kind": "mock_live_not_research",
                "prompt_version": "v0.2",
            },
        )

    state = generate_custom_visual_state(
        content_anchor="加速度描述速度大小或方向的变化。",
        teaching_scenario="学生把速度大小不变等同于没有加速度。",
        learner_utterance="转弯时速度没变，所以加速度是0。",
        learner_level="high_school",
        knowledge_state="misconception",
        affective_state="slightly frustrated",
        pedagogical_intent="corrective_feedback",
        live_runner=fake_live,
    )

    assert captured["prompt_version"] == "v0.2"
    assert captured["input_doc"]["schema_version"] == "1.0.0-rc.2"
    assert state["status"] == "Generated live with Hy3 · Prompt v0.2"
    assert "**Pedagogical intent**" in state["context_markdown"]
    assert "`corrective_feedback`" in state["context_markdown"]
    assert "Pedagogical goal" not in state["context_markdown"]
    assert "Repair the misconception" not in state["context_markdown"]
    assert "先看速度是否变化" in state["verbal_markdown"]
    assert CUSTOM_DELIVERY_STATUS in state["delivery_markdown"]
    assert "Tone" in state["delivery_markdown"]
    assert "Audio rendering is available" in state["audio_status"]
    assert '"prompt_version": "v0.2"' in state["source_json"]


def test_custom_empty_delivery_is_explained_as_control_choice() -> None:
    def fake_live(input_doc: dict, prompt_version: str) -> tuple[dict, dict]:
        del input_doc, prompt_version
        return (
            {
                "schema_version": "1.0.0-rc.3",
                "verbal_plan": {
                    "segments": [{"segment_id": "seg_01", "text": "继续保持。"}]
                },
                "delivery_plan": {},
            },
            {"evidence_kind": "mock_live_not_research"},
        )

    state = generate_custom_visual_state(
        content_anchor="比例表示两个数量的相对关系。",
        teaching_scenario="学生已经正确完成一道比例题。",
        learner_utterance="我这次好像算对了。",
        learner_level="middle_school",
        knowledge_state="emerging confidence",
        affective_state="",
        pedagogical_intent="supportive_feedback",
        live_runner=fake_live,
    )

    assert state["delivery_markdown"] == CUSTOM_EMPTY_DELIVERY_MESSAGE
    assert "failure" not in state["delivery_markdown"].lower()


def test_custom_ui_live_runner_failure_returns_safe_error() -> None:
    def fake_live(input_doc: dict, prompt_version: str) -> tuple[dict, dict]:
        del input_doc, prompt_version
        raise RuntimeError(
            "Authorization: Bearer sk-test-token from .env should not leak"
        )

    outputs = generate_custom_ui(
        "知识点。",
        "学生正在学习。",
        "",
        "middle_school",
        "partial understanding",
        "",
        "elicitation",
        live_runner=fake_live,
    )

    assert outputs[0].startswith("Hy3 generation failed:")
    assert "Authorization: [redacted]" in outputs[0]
    assert "sk-" not in outputs[0]
    assert ".env" not in outputs[0]
    assert outputs[2] == ""


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
