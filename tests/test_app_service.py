from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from teachintent import app_service
from teachintent.evaluator import DIMENSION_IDS
from teachintent.generator import SpeechPlanGenerationResult
from teachintent.web_models import GenerateRequest


FORBIDDEN = (
    "/Users/",
    "/mnt/",
    "Authorization:",
    "Bearer ",
    "sk-",
    "raw_response",
    "judge_raw_response",
    "prompt_system",
    "prompt_user",
)

VALID_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [
            {
                "segment_id": "seg_01",
                "text": "先确认速度是否包含方向变化。",
            }
        ]
    },
    "delivery_plan": {
        "global": {
            "attitudinal_tone": "安抚但纠正",
        }
    },
}


def _generate_request(**overrides: object) -> GenerateRequest:
    payload = {
        "content_anchor": "加速度描述速度大小或方向随时间的变化。",
        "teaching_scenario": "学生混淆速度大小不变和零加速度。",
        "learner_utterance": "速度大小没变，所以加速度为0。",
        "learner_level": "high_school",
        "knowledge_state": "misconception",
        "affective_state": "slightly_frustrated",
        "pedagogical_intent": "corrective_feedback",
    }
    payload.update(overrides)
    return GenerateRequest.model_validate(payload)


def _generation_result(raw_response: str = '{"ok": true}') -> SpeechPlanGenerationResult:
    return SpeechPlanGenerationResult(
        speech_plan=None,
        plan_doc=VALID_PLAN,
        prompt_system="must not leak",
        prompt_user="must not leak",
        prompt_version="v0.2",
        raw_response=raw_response,
        requested_model="tencent/hy3",
        reported_model="tencent/hy3",
        started_at="2026-09-04T00:00:00+00:00",
        duration_seconds=0.1234,
    )


def _evaluation_artifact() -> dict:
    return {
        "structural_valid": True,
        "evaluator_version": "v0.1",
        "run_metadata": {"judge_prompt_version": "v0.1"},
        "scores": {
            dimension: {
                "score": 4,
                "evidence": [
                    {
                        "source": "plan.verbal_plan.segments[0].text",
                        "text": "先确认速度是否包含方向变化。",
                    }
                ],
                "brief_justification": f"{dimension} live grounded.",
            }
            for dimension in DIMENSION_IDS
        },
        "critical_flags": [],
    }


def test_list_examples_returns_three_public_examples() -> None:
    examples = app_service.list_examples()

    assert [example.id for example in examples] == [
        "corrective-feedback",
        "scaffolding",
        "supportive-feedback",
    ]
    assert examples[0].recommended is True
    assert all(example.title for example in examples)
    assert all(example.description for example in examples)


def test_build_recorded_workbench_preserves_public_evaluator_artifact() -> None:
    workbench = app_service.build_recorded_workbench("corrective-feedback")

    assert workbench.example.id == "corrective-feedback"
    assert workbench.prompt_version == "v0.2"
    assert "content_anchor" in workbench.input["instructional_content"]
    assert workbench.speech_plan["schema_version"] == "1.0.0-rc.3"
    assert workbench.evaluation.available is True
    assert workbench.evaluation.evaluator_version == "v0.1"
    assert workbench.evaluation.judge_prompt_version == "v0.1"
    assert workbench.evaluation.source_run_id == "20260901T043729Z"
    assert set(workbench.evaluation.scores) == set(DIMENSION_IDS)
    for judgment in workbench.evaluation.scores.values():
        assert judgment.score == 4
        assert judgment.evidence
        assert judgment.brief_justification


def test_extract_dimension_evidence_accepts_model_and_dict() -> None:
    workbench = app_service.build_recorded_workbench("supportive-feedback")

    model_evidence = app_service.extract_dimension_evidence(
        workbench.evaluation,
        "pedagogical_intent_fidelity",
    )
    dict_evidence = app_service.extract_dimension_evidence(
        workbench.evaluation.model_dump(),
        "pedagogical_intent_fidelity",
    )

    assert model_evidence
    assert dict_evidence
    assert model_evidence[0].text == dict_evidence[0].text


def test_classify_evidence_source_is_conservative() -> None:
    assert (
        app_service.classify_evidence_source(
            "input.instructional_content.content_anchor"
        )
        == "context"
    )
    assert (
        app_service.classify_evidence_source(
            "plan.delivery_plan.global.attitudinal_tone"
        )
        == "speech_plan"
    )
    assert app_service.classify_evidence_source("unexpected.path") == "unknown"


def test_unknown_example_raises_not_found() -> None:
    with pytest.raises(app_service.ExampleNotFound):
        app_service.build_recorded_workbench("not-a-demo")


def test_missing_public_artifact_is_explicit_unavailable_without_results_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_service,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        tmp_path / "public_demo" / "evaluator_artifacts",
    )

    workbench = app_service.build_recorded_workbench("corrective-feedback")

    assert workbench.evaluation.available is False
    assert workbench.evaluation.reason == "Recorded evaluator artifact unavailable."
    assert workbench.evaluation.scores == {}


def test_fresh_clone_public_artifact_copy_returns_recorded_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_dir = tmp_path / "public_demo" / "evaluator_artifacts"
    shutil.copytree(app_service.PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR, artifact_dir)
    monkeypatch.setattr(
        app_service,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        artifact_dir,
    )

    workbench = app_service.build_recorded_workbench("corrective-feedback")

    assert workbench.evaluation.available is True
    assert len(workbench.evaluation.scores) == 6
    assert workbench.evaluation.source_run_id == "20260901T043729Z"


def test_malformed_public_artifact_is_explicit_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_dir = tmp_path / "public_demo" / "evaluator_artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "corrective-feedback.v0_2.json").write_text(
        '{"artifact_version": "bad"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        app_service,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        artifact_dir,
    )

    workbench = app_service.build_recorded_workbench("corrective-feedback")

    assert workbench.evaluation.available is False
    assert workbench.evaluation.reason == "Recorded evaluator artifact unavailable."


def test_non_empty_critical_flags_are_preserved_from_public_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_artifact = (
        app_service.PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR
        / "corrective-feedback.v0_2.json"
    )
    artifact = json.loads(real_artifact.read_text(encoding="utf-8"))
    artifact["critical_flags"] = [
        {
            "flag": "content_boundary_violation",
            "evidence": [
                {
                    "source": "plan.verbal_plan.segments[0].text",
                    "text": "你提到速度大小没变",
                }
            ],
            "brief_justification": "Synthetic test flag from public artifact.",
        }
    ]
    artifact_dir = tmp_path / "public_demo" / "evaluator_artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "corrective-feedback.v0_2.json").write_text(
        json.dumps(artifact, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        app_service,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        artifact_dir,
    )

    workbench = app_service.build_recorded_workbench("corrective-feedback")

    assert workbench.evaluation.critical_flags
    assert workbench.evaluation.critical_flags[0].flag == (
        "content_boundary_violation"
    )
    assert workbench.evaluation.critical_flags[0].brief_justification == (
        "Synthetic test flag from public artifact."
    )


def test_workbench_response_contains_no_private_or_secret_fields() -> None:
    workbench = app_service.build_recorded_workbench("corrective-feedback")
    text = json.dumps(workbench.model_dump(), ensure_ascii=False)

    for forbidden in FORBIDDEN:
        assert forbidden not in text


def test_build_live_input_doc_omits_empty_optional_fields() -> None:
    request = _generate_request(learner_utterance="", affective_state=None)

    input_doc = app_service.build_live_input_doc(request)

    assert "learner_utterance" not in input_doc["pedagogical_context"]
    assert "affective_state" not in input_doc["learner"]
    app_service.validate_live_input_doc(input_doc)


@pytest.mark.parametrize(
    "intent",
    [
        "elicitation",
        "scaffolding",
        "explanation",
        "corrective_feedback",
        "supportive_feedback",
        "extension",
    ],
)
def test_generate_live_workbench_accepts_six_intents(intent: str) -> None:
    store = app_service.LiveSessionStore()
    response = app_service.generate_live_workbench(
        _generate_request(pedagogical_intent=intent),
        session_store=store,
        generation_runner=lambda _input, _prompt: _generation_result(),
    )

    assert response.mode == "live"
    assert response.input["pedagogical_intent"]["primary"] == intent
    assert response.generation.prompt_version == "v0.2"
    assert response.evaluation is None


def test_invalid_live_required_input_fails_before_hy3() -> None:
    called = False

    def forbidden_runner(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        nonlocal called
        called = True
        raise AssertionError("Hy3 must not be called")

    with pytest.raises(app_service.LiveGenerationError) as exc_info:
        app_service.generate_live_workbench(
            _generate_request(content_anchor=""),
            session_store=app_service.LiveSessionStore(),
            generation_runner=forbidden_runner,
        )

    assert called is False
    assert exc_info.value.failure_type == "input_validation_error"


def test_hy3_failure_is_sanitized() -> None:
    def failing_runner(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        raise RuntimeError(
            "Authorization: Bearer sk-secret HY3_API_KEY=abc /Users/name/.env"
        )

    with pytest.raises(app_service.LiveGenerationError) as exc_info:
        app_service.generate_live_workbench(
            _generate_request(),
            session_store=app_service.LiveSessionStore(),
            generation_runner=failing_runner,
        )

    assert "Bearer sk-secret" not in exc_info.value.summary
    assert "HY3_API_KEY=abc" not in exc_info.value.summary
    assert "/Users/" not in exc_info.value.summary


def test_generate_live_session_stores_true_raw_response_and_api_does_not_return_it() -> None:
    store = app_service.LiveSessionStore()
    true_raw = '{"schema_version":"1.0.0-rc.3","marker":"true-raw"}'

    response = app_service.generate_live_workbench(
        _generate_request(),
        session_store=store,
        generation_runner=lambda _input, _prompt: _generation_result(true_raw),
    )

    session = store.get(response.session_id)
    assert session.raw_response == true_raw
    text = json.dumps(response.model_dump(), ensure_ascii=False)
    assert "true-raw" not in text
    assert "raw_response" not in text


def test_evaluate_live_session_uses_exact_stored_raw_response() -> None:
    store = app_service.LiveSessionStore()
    true_raw = "TRUE RAW RESPONSE"
    generated = app_service.generate_live_workbench(
        _generate_request(),
        session_store=store,
        generation_runner=lambda _input, _prompt: _generation_result(true_raw),
    )
    seen: dict[str, object] = {}

    def fake_evaluator(
        input_doc: dict,
        raw_response: str,
        run_context,
    ) -> dict:
        seen["input_doc"] = input_doc
        seen["raw_response"] = raw_response
        seen["input_case_id"] = run_context.input_case_id
        return {"artifact": _evaluation_artifact()}

    evaluated = app_service.evaluate_live_session(
        generated.session_id,
        session_store=store,
        evaluation_runner=fake_evaluator,
    )

    assert seen["raw_response"] == true_raw
    assert seen["raw_response"] != json.dumps(VALID_PLAN, ensure_ascii=False)
    assert seen["input_case_id"] == f"live-{generated.session_id}"
    assert evaluated.evaluation.available is True
    assert evaluated.evaluation.evaluator_version == "v0.1"
    assert evaluated.evaluation.judge_prompt_version == "v0.1"
    assert set(evaluated.evaluation.scores) == set(DIMENSION_IDS)


def test_evaluator_failure_is_unavailable_not_zero_scores() -> None:
    store = app_service.LiveSessionStore()
    generated = app_service.generate_live_workbench(
        _generate_request(),
        session_store=store,
        generation_runner=lambda _input, _prompt: _generation_result(),
    )

    evaluated = app_service.evaluate_live_session(
        generated.session_id,
        session_store=store,
        evaluation_runner=lambda _input, _raw, _ctx: {
            "available": False,
            "failure_type": "judge_api_error",
            "failure_summary": "Judge provider unavailable.",
        },
    )

    assert evaluated.evaluation.available is False
    assert evaluated.evaluation.failure_type == "judge_api_error"
    assert evaluated.evaluation.scores == {}


def test_unknown_live_session_raises_not_found() -> None:
    with pytest.raises(app_service.LiveSessionNotFound):
        app_service.evaluate_live_session(
            "missing",
            session_store=app_service.LiveSessionStore(),
            evaluation_runner=lambda _input, _raw, _ctx: {"artifact": {}},
        )


def test_repeated_evaluate_returns_cached_result_without_second_judge_call() -> None:
    store = app_service.LiveSessionStore()
    generated = app_service.generate_live_workbench(
        _generate_request(),
        session_store=store,
        generation_runner=lambda _input, _prompt: _generation_result(),
    )
    calls = 0

    def fake_evaluator(_input: dict, _raw: str, _ctx) -> dict:
        nonlocal calls
        calls += 1
        return {"artifact": _evaluation_artifact()}

    first = app_service.evaluate_live_session(
        generated.session_id,
        session_store=store,
        evaluation_runner=fake_evaluator,
    )
    second = app_service.evaluate_live_session(
        generated.session_id,
        session_store=store,
        evaluation_runner=fake_evaluator,
    )

    assert calls == 1
    assert first.evaluation == second.evaluation
