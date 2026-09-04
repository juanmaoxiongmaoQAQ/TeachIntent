from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from teachintent import app_service
from teachintent.evaluator import DIMENSION_IDS
from teachintent.generator import SpeechPlanGenerationResult
from teachintent.web_models import GenerateRequest, IntentCompareRequest


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

VOICE_MANIFEST = {
    "artifact_version": "1.0",
    "example_name": "corrective-feedback",
    "prompt_version": "v0.2",
    "exact_verbal_text": "先确认速度是否包含方向变化。",
    "exact_verbal_text_sha256": "text-sha",
    "language": "Chinese",
    "speaker": "Vivian",
    "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "seed": 20260901,
    "delivery_adapter": {
        "instruct": "整体采用“安抚但纠正”的态度语气。",
        "supported_controls": [
            {
                "path": "delivery_plan.global.attitudinal_tone",
                "value": "安抚但纠正",
                "instruction_fragment": "整体采用“安抚但纠正”的态度语气。",
                "realization": "best_effort_natural_language_instruction",
            }
        ],
        "unsupported_controls": [
            {
                "path": "delivery_plan.segment_overrides[0].prominence_targets",
                "value": [{"text": "方向在变化", "level": "moderate"}],
                "reason": "Not realized by current adapter.",
            }
        ],
    },
    "ab_invariants": {"same_exact_verbal_text": True},
    "conditions": {
        "neutral": {
            "instruct": "",
            "audio_file": "neutral.wav",
            "audio_sha256": "neutral-sha",
            "duration_seconds": 1.0,
        },
        "planned": {
            "instruct": "整体采用“安抚但纠正”的态度语气。",
            "audio_file": "planned.wav",
            "audio_sha256": "planned-sha",
            "duration_seconds": 1.2,
        },
    },
    "limitations": ["No exact acoustic control is claimed."],
}


def _write_public_voice_fixture(
    root: Path,
    example_name: str = "corrective-feedback",
    manifest_overrides: dict | None = None,
) -> None:
    artifact_dir = root / example_name / "v0_2"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "neutral.wav").write_bytes(b"neutral wav")
    (artifact_dir / "planned.wav").write_bytes(b"planned wav")
    manifest = {**VOICE_MANIFEST, "example_name": example_name}
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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


def _compare_request(**overrides: object) -> IntentCompareRequest:
    payload = {
        "content_anchor": "加速度描述速度大小或方向随时间的变化。",
        "teaching_scenario": "学生混淆速度大小不变和零加速度。",
        "learner_utterance": "速度大小没变，所以加速度为0。",
        "learner_level": "high_school",
        "knowledge_state": "misconception",
        "affective_state": "slightly_frustrated",
        "left_intent": "corrective_feedback",
        "right_intent": "scaffolding",
    }
    payload.update(overrides)
    return IntentCompareRequest.model_validate(payload)


def _generation_result(
    raw_response: str = '{"ok": true}',
    plan_doc: dict | None = None,
    requested_model: str = "tencent/hy3",
) -> SpeechPlanGenerationResult:
    return SpeechPlanGenerationResult(
        speech_plan=None,
        plan_doc=plan_doc or VALID_PLAN,
        prompt_system="must not leak",
        prompt_user="must not leak",
        prompt_version="v0.2",
        raw_response=raw_response,
        requested_model=requested_model,
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


def test_compare_live_intents_calls_generator_twice_and_controls_only_intent() -> None:
    calls: list[dict] = []
    left_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "纠正这个判断。"}]
        },
        "delivery_plan": {"global": {"attitudinal_tone": "安抚但纠正"}},
    }
    right_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [
                {"segment_id": "seg_01", "text": "先拆成一个小问题。"},
                {"segment_id": "seg_02", "text": "请学生判断方向是否变化。"},
            ]
        },
        "delivery_plan": {},
    }

    def fake_runner(input_doc: dict, prompt_version: str) -> SpeechPlanGenerationResult:
        calls.append(input_doc)
        plan = left_plan if len(calls) == 1 else right_plan
        return _generation_result(
            raw_response=f"RAW {len(calls)}",
            plan_doc=plan,
        )

    response = app_service.compare_live_intents(
        _compare_request(),
        generation_runner=fake_runner,
    )

    assert len(calls) == 2
    assert calls[0]["pedagogical_intent"]["primary"] == "corrective_feedback"
    assert calls[1]["pedagogical_intent"]["primary"] == "scaffolding"
    assert app_service.strip_primary_intent(calls[0]) == app_service.strip_primary_intent(
        calls[1]
    )
    assert response.mode == "intent_compare"
    assert response.comparison.all_other_input_fields_equal is True
    assert response.comparison.same_prompt_version is True
    assert response.comparison.same_requested_model is True
    assert response.left.speech_plan == left_plan
    assert response.right.speech_plan == right_plan
    text = json.dumps(response.model_dump(), ensure_ascii=False)
    assert "RAW 1" not in text
    assert "RAW 2" not in text
    assert "raw_response" not in text


def test_compare_same_intent_rejected_before_generation() -> None:
    called = False

    def forbidden(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        nonlocal called
        called = True
        return _generation_result()

    with pytest.raises(app_service.IntentCompareError, match="different"):
        app_service.compare_live_intents(
            _compare_request(right_intent="corrective_feedback"),
            generation_runner=forbidden,
        )
    assert called is False


def test_compare_invalid_input_rejected_before_generation() -> None:
    called = False

    def forbidden(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        nonlocal called
        called = True
        return _generation_result()

    with pytest.raises(app_service.IntentCompareError) as exc_info:
        app_service.compare_live_intents(
            _compare_request(content_anchor=""),
            generation_runner=forbidden,
        )
    assert exc_info.value.failure_type == "input_validation_error"
    assert called is False


def test_compare_generation_failures_are_safe_and_complete_only() -> None:
    def first_fails(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        raise RuntimeError("Bearer sk-secret /Users/person/.env")

    with pytest.raises(app_service.IntentCompareError) as first:
        app_service.compare_live_intents(
            _compare_request(),
            generation_runner=first_fails,
        )
    assert first.value.failure_type == "comparison_generation_error"
    assert "Left generation failed" in first.value.summary
    assert "Bearer sk-secret" not in first.value.summary
    assert "/Users/" not in first.value.summary

    calls = 0

    def second_fails(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("HY3_API_KEY=secret /mnt/provider")
        return _generation_result()

    with pytest.raises(app_service.IntentCompareError) as second:
        app_service.compare_live_intents(
            _compare_request(),
            generation_runner=second_fails,
        )
    assert calls == 2
    assert "Right generation failed" in second.value.summary
    assert "HY3_API_KEY" not in second.value.summary
    assert "/mnt/" not in second.value.summary


def test_compare_structural_contrast_handles_global_segment_and_empty_delivery() -> None:
    left_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "左侧文本。"}]
        },
        "delivery_plan": {
            "global": {
                "attitudinal_tone": "reassuring",
                "prosody": {"speaking_rate": "slow"},
            },
            "segment_overrides": [
                {
                    "segment_id": "seg_01",
                    "prominence_targets": [{"text": "左侧", "level": "moderate"}],
                }
            ],
        },
    }
    right_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "右侧文本。"}]
        },
        "delivery_plan": {},
    }

    contrast = app_service.build_structural_contrast(left_plan, right_plan)

    assert contrast.verbal_segments == {"left": 1, "right": 1}
    assert contrast.delivery_decision == {"left": "selective", "right": "default"}
    assert contrast.verbal_text_identical is False
    assert contrast.delivery_plan_identical is False
    assert contrast.left_control_paths == [
        "delivery_plan.global.attitudinal_tone",
        "delivery_plan.global.prosody.speaking_rate",
        "delivery_plan.segment_overrides[0].prominence_targets[0].text",
        "delivery_plan.segment_overrides[0].prominence_targets[0].level",
    ]
    assert contrast.right_control_paths == []


def test_compare_does_not_use_judge_tts_or_write_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked = sorted(
        path
        for root in (Path("public_demo"), Path("public_results"), Path("results"))
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
    )
    before = {path: path.stat().st_mtime_ns for path in tracked}
    monkeypatch.setattr(
        app_service,
        "_default_evaluation_runner",
        lambda *_args, **_kwargs: pytest.fail("Judge must not be used"),
    )

    response = app_service.compare_live_intents(
        _compare_request(),
        generation_runner=lambda _input, _prompt: _generation_result(),
    )

    assert response.mode == "intent_compare"
    after = {path: path.stat().st_mtime_ns for path in tracked}
    assert before == after


def test_voice_realization_available_from_public_demo_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    voice_root = tmp_path / "public_demo" / "voice"
    _write_public_voice_fixture(voice_root)
    monkeypatch.setattr(app_service, "PUBLIC_DEMO_VOICE_DIR", voice_root)

    voice = app_service.get_voice_realization("corrective-feedback")

    assert voice.available is True
    assert voice.mode == "recorded"
    assert voice.neutral is not None
    assert voice.neutral.audio_url == "/api/audio/corrective-feedback/neutral"
    assert voice.planned is not None
    assert voice.planned.audio_url == "/api/audio/corrective-feedback/planned"
    assert voice.delivery_adapter is not None
    assert len(voice.delivery_adapter.supported_controls) == 1
    assert len(voice.delivery_adapter.unsupported_controls) == 1


def test_missing_public_voice_is_unavailable_without_results_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_service, "PUBLIC_DEMO_VOICE_DIR", tmp_path / "missing")

    voice = app_service.get_voice_realization("corrective-feedback")

    assert voice.available is False
    assert voice.reason == "Recorded voice artifact unavailable."


def test_voice_response_never_returns_manifest_secret_or_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    voice_root = tmp_path / "public_demo" / "voice"
    _write_public_voice_fixture(
        voice_root,
        manifest_overrides={
            "raw_response": "secret raw",
            "source_path": "/Users/chengtengteng/private",
            "Authorization": "Bearer sk-secret",
        },
    )
    monkeypatch.setattr(app_service, "PUBLIC_DEMO_VOICE_DIR", voice_root)

    payload = app_service.get_voice_realization("corrective-feedback").model_dump()
    text = json.dumps(payload, ensure_ascii=False)

    for forbidden in FORBIDDEN:
        assert forbidden not in text


def test_public_voice_audio_path_is_restricted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    voice_root = tmp_path / "public_demo" / "voice"
    _write_public_voice_fixture(voice_root)
    monkeypatch.setattr(app_service, "PUBLIC_DEMO_VOICE_DIR", voice_root)

    path = app_service.resolve_public_voice_audio_path(
        "corrective-feedback",
        "neutral",
    )

    assert path == voice_root / "corrective-feedback" / "v0_2" / "neutral.wav"
    with pytest.raises(app_service.VoiceArtifactUnavailable):
        app_service.resolve_public_voice_audio_path("corrective-feedback", "bad")
    with pytest.raises(app_service.ExampleNotFound):
        app_service.resolve_public_voice_audio_path("../bad", "neutral")
