from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from teachintent import visual_demo as visual_demo_module
from teachintent.evaluator import DIMENSION_IDS, JudgeAPIError, JudgeCompletion
from teachintent.generator import SpeechPlanGenerationResult
from teachintent.visual_demo import (
    CUSTOM_DELIVERY_STATUS,
    CUSTOM_EMPTY_DELIVERY_MESSAGE,
    CUSTOM_EVALUATION_PLACEHOLDER,
    EVALUATION_NOT_RUN_MESSAGE,
    CustomInputError,
    PEDAGOGICAL_INTENTS,
    REVIEWER_EXAMPLES,
    build_delivery_plan_view,
    build_evidence_trace,
    build_custom_input,
    build_evaluation_workbench_state,
    build_visual_state,
    clear_custom_evaluation_on_input_change,
    classify_evidence_source,
    evaluate_custom_workbench_state,
    evaluate_custom_visual_state,
    find_audio_pair,
    generate_custom_ui,
    generate_custom_visual_state,
    highlight_exact_text,
    is_recommended_showcase,
    load_showcase_scenario_fields,
    render_evidence_trace,
    load_public_demo_evaluator_artifact,
    select_evidence_trace,
    switch_recorded_example,
)


VALID_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [{"segment_id": "seg_01", "text": "先看速度是否变化。"}]
    },
    "delivery_plan": {},
}


def _generation_result(raw_response: str) -> SpeechPlanGenerationResult:
    return SpeechPlanGenerationResult(
        speech_plan=None,
        plan_doc=VALID_PLAN,
        prompt_system="not exposed",
        prompt_user="not exposed",
        prompt_version="v0.2",
        raw_response=raw_response,
        requested_model="tencent/hy3",
        reported_model="tencent/hy3",
        started_at="2026-09-03T00:00:00+00:00",
        duration_seconds=0.1,
    )


def _judge_payload(
    *,
    score: int = 4,
    flag: str | None = None,
) -> dict:
    payload = {
        "scores": {
            dimension: {
                "score": score,
                "evidence": [
                    {
                        "source": "plan.verbal_plan.segments[0].text",
                        "text": "先看速度是否变化。",
                    }
                ],
                "brief_justification": f"{dimension} is grounded.",
            }
            for dimension in DIMENSION_IDS
        },
        "critical_flags": [],
    }
    if flag:
        payload["critical_flags"] = [
            {
                "flag": flag,
                "evidence": [
                    {
                        "source": "plan.verbal_plan.segments[0].text",
                        "text": "先看速度是否变化。",
                    }
                ],
                "brief_justification": "Flag evidence is grounded.",
            }
        ]
    return payload


class FakeJudge:
    def __init__(self, payload: dict | None = None, *, fail: bool = False) -> None:
        self.payload = payload or _judge_payload()
        self.fail = fail
        self.calls = 0
        self.temperatures = []

    @property
    def provider(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return "qwen/qwen3.5-plus-20260420"

    @property
    def structured_output_enabled(self) -> bool:
        return False

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        del system, user
        self.calls += 1
        self.temperatures.append(temperature)
        if self.fail:
            raise JudgeAPIError("judge API failed once")
        return JudgeCompletion(
            content=json.dumps(self.payload, ensure_ascii=False),
            reported_model=self.model,
            structured_object=None,
            finish_reason="stop",
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


def test_recorded_evaluation_is_rendered_on_primary_page() -> None:
    state = build_visual_state("corrective-feedback", "v0.2")

    markdown = state["evaluation_markdown"]
    assert "Recorded Evaluator v0.1 result" in markdown
    assert "D1 Pedagogical Intent Fidelity" in markdown
    assert "4 / 4" in markdown
    assert "The response explicitly identifies the learner's misconception" in markdown
    assert "Critical flags" in markdown
    assert "None" in markdown


def test_recorded_case_switch_does_not_call_live_judge(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("recorded case switch must not call live Judge")

    monkeypatch.setattr(visual_demo_module, "run_live_evaluation", forbidden)
    outputs = switch_recorded_example("supportive-feedback")

    assert "Recorded Evaluator v0.1 result" in outputs[5]
    assert "No live judge call was made" in outputs[12]


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
        evaluation_state,
        recorded_evaluation,
        dimension_choices,
        selected_dimension,
        evidence_trace,
        critical_flags,
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
    assert state["context_html"] == context
    assert "有限支架" in context
    assert verbal
    assert "HOW TO SAY" in delivery
    assert evaluation_state["available"] is True
    assert "Recorded Evaluator v0.1 result" in recorded_evaluation
    assert len(dimension_choices) == 6
    assert selected_dimension.startswith("D1")
    assert "Evidence Trace" in evidence_trace
    assert "Critical flags" in critical_flags
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


def test_classify_evidence_source_routes_by_path_only() -> None:
    assert classify_evidence_source("input.learner.affective_state") == "input"
    assert classify_evidence_source("learner.knowledge_state") == "input"
    assert classify_evidence_source("plan.verbal_plan.segments[0].text") == (
        "speech_plan"
    )
    assert classify_evidence_source("delivery_plan.global.attitudinal_tone") == (
        "speech_plan"
    )
    assert classify_evidence_source("external.note") == "unknown"


def test_highlight_exact_text_marks_exact_substring_only() -> None:
    rendered = highlight_exact_text(
        "汽车转弯时方向发生变化，因此加速度不为0。",
        "方向发生变化",
    )

    assert "<mark>方向发生变化</mark>" in rendered


def test_highlight_exact_text_does_not_fabricate_unmatched_highlight() -> None:
    rendered = highlight_exact_text("速度大小没变。", "方向发生变化")

    assert "<mark>" not in rendered
    assert rendered == "方向发生变化"


def test_highlight_exact_text_escapes_html() -> None:
    rendered = highlight_exact_text("<script>x</script>方向发生变化", "<script>")

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<mark>&lt;script&gt;</mark>" in rendered


def test_build_evidence_trace_keeps_multiple_evidence_groups() -> None:
    input_doc = build_custom_input(
        content_anchor="方向发生变化时，加速度不为0。",
        teaching_scenario="学生认为只要速度大小不变就没有加速度。",
        learner_utterance="速度没变，所以没有加速度。",
        learner_level="high_school",
        knowledge_state="misconception",
        affective_state="slightly frustrated",
        pedagogical_intent="corrective_feedback",
    )
    plan_doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [
                {
                    "segment_id": "seg_01",
                    "text": "速度方向发生变化，所以加速度不为0。",
                }
            ]
        },
        "delivery_plan": {"global": {"attitudinal_tone": "安抚但纠正"}},
    }
    artifact = {
        "scores": {
            "delivery_pedagogy_alignment": {
                "score": 4,
                "evidence": [
                    {
                        "source": "input.learner.affective_state",
                        "text": "slightly frustrated",
                    },
                    {
                        "source": "plan.delivery_plan.global.attitudinal_tone",
                        "text": "安抚但纠正",
                    },
                    {"source": "notes.manual", "text": "grounded note"},
                ],
                "brief_justification": "Delivery matches learner state.",
            }
        },
        "critical_flags": [],
    }

    trace = build_evidence_trace(
        input_doc, plan_doc, artifact, "delivery_pedagogy_alignment"
    )
    html = render_evidence_trace(trace)

    assert trace["score"] == 4
    assert len(trace["input_evidence"]) == 1
    assert len(trace["speech_plan_evidence"]) == 1
    assert len(trace["other_evidence"]) == 1
    assert "<mark>slightly frustrated</mark>" in html
    assert "<mark>安抚但纠正</mark>" in html
    assert "Other grounded evidence" in html
    assert "Delivery matches learner state." in html


def test_recorded_artifact_builds_evidence_trace() -> None:
    state = build_visual_state("corrective-feedback", "v0.2")
    trace = build_evidence_trace(
        state["example"]["input"],
        state["example"]["speech_plan"],
        state["evaluation_artifact"],
        "pedagogical_intent_fidelity",
    )

    assert trace["available"] is True
    assert trace["dimension_key"] == "D1"
    assert trace["score"] == 4
    assert trace["speech_plan_evidence"]


def test_public_demo_artifact_loader_reads_committed_sanitized_artifact() -> None:
    artifact = load_public_demo_evaluator_artifact("corrective-feedback", "v0.2")

    assert artifact is not None
    assert artifact["example_name"] == "corrective-feedback"
    assert artifact["case_id"] == "PILOT-A-COR-01"
    assert artifact["source_run_id"] == "20260901T043729Z"
    assert set(artifact["scores"]) == set(DIMENSION_IDS)
    for score in artifact["scores"].values():
        assert score["score"] == 4
        assert score["brief_justification"]
        assert score["evidence"]


def test_visual_demo_uses_public_artifact_when_results_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_dir = tmp_path / "public_demo" / "evaluator_artifacts"
    public_dir.mkdir(parents=True)
    source_artifact = (
        visual_demo_module.PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR
        / "corrective-feedback.v0_2.json"
    )
    shutil.copy2(source_artifact, public_dir / source_artifact.name)
    monkeypatch.setattr(
        visual_demo_module,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        public_dir,
    )

    state = build_visual_state("corrective-feedback", "v0.2")

    assert state["evaluation_state"]["available"] is True
    assert len(state["dimension_choices"]) == 6
    assert "Evidence Trace" in state["evidence_trace_html"]
    assert "The response explicitly identifies the learner's misconception" in (
        state["evaluation_markdown"]
    )


def test_visual_demo_does_not_fallback_to_private_results_for_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_public_dir = tmp_path / "missing_public_demo" / "evaluator_artifacts"
    empty_public_dir.mkdir(parents=True)
    monkeypatch.setattr(
        visual_demo_module,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        empty_public_dir,
    )

    state = build_visual_state("corrective-feedback", "v0.2")

    assert state["evaluation_artifact"] is None
    assert state["evaluation_state"]["available"] is False
    assert "Recorded evaluator artifact unavailable." in state["evaluation_markdown"]
    assert "Recorded evaluator artifact unavailable." in state["evidence_trace_html"]


def test_live_artifact_builds_same_evidence_trace_shape() -> None:
    artifact = {
        "scores": _judge_payload()["scores"],
        "critical_flags": [],
    }
    state = {
        "input": build_custom_input(
            content_anchor="加速度描述速度变化。",
            teaching_scenario="学生正在判断转弯车辆是否有加速度。",
            learner_utterance="",
            learner_level="high_school",
            knowledge_state="misconception",
            affective_state="",
            pedagogical_intent="corrective_feedback",
        ),
        "speech_plan": VALID_PLAN,
        "raw_response": json.dumps(VALID_PLAN, ensure_ascii=False),
        "prompt_version": "v0.2",
        "source": {"generator_version": "v0.1"},
    }
    evaluation_state = evaluate_custom_workbench_state(
        state,
        evaluation_runner=lambda *args: {"available": True, "artifact": artifact},
    )

    assert evaluation_state["available"] is True
    assert len(evaluation_state["dimension_choices"]) == 6
    assert "Evidence Trace" in evaluation_state["evidence_trace_html"]


def test_dimension_switch_reads_state_without_calling_judge(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("dimension switch must not call Judge")

    monkeypatch.setattr(visual_demo_module, "run_live_evaluation", forbidden)
    state = build_visual_state("corrective-feedback", "v0.2")

    for choice in state["dimension_choices"]:
        trace_html = select_evidence_trace(state["evaluation_state"], choice)
        assert "Evidence Trace" in trace_html


def test_live_evaluation_not_run_state_has_no_fake_dimension_scores() -> None:
    state = build_evaluation_workbench_state(
        None, None, None, unavailable_reason=EVALUATION_NOT_RUN_MESSAGE
    )

    assert state["available"] is False
    assert state["dimension_choices"] == []
    assert "Evaluation not run yet" in state["evidence_trace_html"]
    assert "/ 4" not in state["evidence_trace_html"]


def test_empty_delivery_renders_default_decision_not_failure() -> None:
    rendered = build_delivery_plan_view(VALID_PLAN)

    assert "Default rendering selected" in rendered
    assert "TeachIntent selected no additional delivery control" in rendered
    assert "failure" not in rendered.lower()


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


def test_custom_generation_preserves_true_raw_response_for_evaluator() -> None:
    raw_response = json.dumps(VALID_PLAN, ensure_ascii=False, indent=2)
    captured = {}

    def fake_live(input_doc: dict, prompt_version: str) -> SpeechPlanGenerationResult:
        del input_doc, prompt_version
        return _generation_result(raw_response)

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

    def fake_evaluator(input_doc, plan_doc, received_raw, prompt_version, source):
        del input_doc, plan_doc, prompt_version, source
        captured["raw_response"] = received_raw
        return {
            "available": True,
            "artifact": {
                "scores": _judge_payload()["scores"],
                "critical_flags": [],
            },
        }

    evaluate_custom_visual_state(state, evaluation_runner=fake_evaluator)
    assert state["raw_response"] == raw_response
    assert captured["raw_response"] == raw_response
    assert captured["raw_response"] != json.dumps(VALID_PLAN, ensure_ascii=False)


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

    assert outputs[0] is None
    assert outputs[1].startswith("Hy3 generation failed:")
    assert "Authorization: [redacted]" in outputs[1]
    assert "sk-" not in outputs[1]
    assert ".env" not in outputs[1]
    assert outputs[3] == ""


def test_live_evaluation_requires_generated_plan_first() -> None:
    assert evaluate_custom_visual_state(None) == CUSTOM_EVALUATION_PLACEHOLDER


def test_live_evaluation_renders_scores_justifications_and_flags() -> None:
    raw_response = json.dumps(VALID_PLAN, ensure_ascii=False)
    judge = FakeJudge(
        _judge_payload(score=3, flag="content_anchor_contradiction")
    )
    evaluation = visual_demo_module.run_live_evaluation(
        build_custom_input(
            content_anchor="加速度描述速度变化。",
            teaching_scenario="学生正在判断转弯车辆是否有加速度。",
            learner_utterance="速度大小没变，所以没有加速度。",
            learner_level="high_school",
            knowledge_state="misconception",
            affective_state="slightly frustrated",
            pedagogical_intent="corrective_feedback",
        ),
        VALID_PLAN,
        raw_response,
        "v0.2",
        {"generator_version": "v0.1"},
        judge=judge,
    )
    markdown = evaluate_custom_visual_state(
        {
            "input": build_custom_input(
                content_anchor="加速度描述速度变化。",
                teaching_scenario="学生正在判断转弯车辆是否有加速度。",
                learner_utterance="速度大小没变，所以没有加速度。",
                learner_level="high_school",
                knowledge_state="misconception",
                affective_state="slightly frustrated",
                pedagogical_intent="corrective_feedback",
            ),
            "speech_plan": VALID_PLAN,
            "raw_response": raw_response,
            "prompt_version": "v0.2",
            "source": {"generator_version": "v0.1"},
        },
        evaluation_runner=lambda *args: evaluation,
    )

    assert judge.calls == 1
    assert judge.temperatures == [0.0]
    assert evaluation["available"] is True
    assert "Live Evaluator v0.1 · Independent Judge" in markdown
    assert "D1 Pedagogical Intent Fidelity" in markdown
    assert "3 / 4" in markdown
    assert "pedagogical_intent_fidelity is grounded." in markdown
    assert "content_anchor_contradiction" in markdown
    assert "Flag evidence is grounded." in markdown
    assert "95.83% directional accuracy" in markdown


def test_live_evaluator_failure_is_unavailable_not_zero() -> None:
    raw_response = json.dumps(VALID_PLAN, ensure_ascii=False)
    judge = FakeJudge(fail=True)
    evaluation = visual_demo_module.run_live_evaluation(
        build_custom_input(
            content_anchor="加速度描述速度变化。",
            teaching_scenario="学生正在判断转弯车辆是否有加速度。",
            learner_utterance="",
            learner_level="high_school",
            knowledge_state="misconception",
            affective_state="",
            pedagogical_intent="corrective_feedback",
        ),
        VALID_PLAN,
        raw_response,
        "v0.2",
        {"generator_version": "v0.1"},
        judge=judge,
    )
    markdown = evaluate_custom_visual_state(
        {
            "input": {},
            "speech_plan": VALID_PLAN,
            "raw_response": raw_response,
            "prompt_version": "v0.2",
            "source": {},
        },
        evaluation_runner=lambda *args: evaluation,
    )

    assert judge.calls == 1
    assert evaluation["available"] is False
    assert "Evaluation unavailable" in markdown
    assert "0 / 4" not in markdown


def test_custom_input_change_clears_stale_evaluation_and_state() -> None:
    assert clear_custom_evaluation_on_input_change() == (None, "")
    showcase_outputs = visual_demo_module.load_showcase_scenario_ui()
    assert showcase_outputs[-2:] == (None, "")


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
