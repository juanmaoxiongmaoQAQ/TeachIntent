from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from teachintent import app_service
from teachintent.evaluator import DIMENSION_IDS
from teachintent.generator import SpeechPlanGenerationResult
from teachintent.web_api import create_app


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


@pytest.fixture
def client() -> TestClient:
    app_service.LIVE_SESSION_STORE.clear()
    return TestClient(create_app())


VALID_GENERATE_REQUEST = {
    "content_anchor": "加速度描述速度大小或方向随时间的变化。",
    "teaching_scenario": "学生混淆速度大小不变和零加速度。",
    "learner_utterance": "速度大小没变，所以加速度为0。",
    "learner_level": "high_school",
    "knowledge_state": "misconception",
    "affective_state": "slightly_frustrated",
    "pedagogical_intent": "corrective_feedback",
}

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
    "delivery_plan": {"global": {"attitudinal_tone": "安抚但纠正"}},
}


def _generation_result(raw_response: str = "TRUE RAW") -> SpeechPlanGenerationResult:
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
        duration_seconds=0.25,
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
                "brief_justification": f"{dimension} grounded.",
            }
            for dimension in DIMENSION_IDS
        },
        "critical_flags": [],
    }


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "TeachIntent"}


def test_examples(client: TestClient) -> None:
    response = client.get("/api/examples")

    assert response.status_code == 200
    examples = response.json()
    assert [example["id"] for example in examples] == [
        "corrective-feedback",
        "scaffolding",
        "supportive-feedback",
    ]
    assert examples[0]["recommended"] is True


def test_get_corrective_feedback_workbench(client: TestClient) -> None:
    response = client.get("/api/examples/corrective-feedback")

    assert response.status_code == 200
    payload = response.json()
    assert payload["example"]["id"] == "corrective-feedback"
    assert payload["prompt_version"] == "v0.2"
    assert payload["input"]["schema_version"] == "1.0.0-rc.2"
    assert payload["speech_plan"]["schema_version"] == "1.0.0-rc.3"
    assert payload["evaluation"]["available"] is True
    assert payload["evaluation"]["source_run_id"] == "20260901T043729Z"
    assert set(payload["evaluation"]["scores"]) == set(DIMENSION_IDS)
    for judgment in payload["evaluation"]["scores"].values():
        assert judgment["score"] == 4
        assert judgment["evidence"]
        assert judgment["brief_justification"]


def test_unknown_example_returns_404(client: TestClient) -> None:
    response = client.get("/api/examples/unknown")

    assert response.status_code == 404


def test_critical_flags_are_preserved(client: TestClient) -> None:
    response = client.get("/api/examples/supportive-feedback")

    assert response.status_code == 200
    assert response.json()["evaluation"]["critical_flags"] == []


def test_response_contains_no_private_or_secret_fields(client: TestClient) -> None:
    response = client.get("/api/examples/corrective-feedback")

    assert response.status_code == 200
    text = json.dumps(response.json(), ensure_ascii=False)
    for forbidden in FORBIDDEN:
        assert forbidden not in text


def test_results_unavailable_still_returns_recorded_evaluation(
    client: TestClient,
) -> None:
    response = client.get("/api/examples/corrective-feedback")

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation"]["available"] is True
    assert len(payload["evaluation"]["scores"]) == 6


def test_public_artifact_missing_returns_explicit_unavailable_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    monkeypatch.setattr(
        app_service,
        "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
        tmp_path / "public_demo" / "evaluator_artifacts",
    )

    response = client.get("/api/examples/corrective-feedback")

    assert response.status_code == 200
    evaluation = response.json()["evaluation"]
    assert evaluation["available"] is False
    assert evaluation["reason"] == "Recorded evaluator artifact unavailable."
    assert evaluation["scores"] == {}


def test_generate_endpoint_creates_live_session_without_returning_raw_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_service,
        "_default_generation_runner",
        lambda _input, _prompt: _generation_result("REAL RAW RESPONSE"),
    )

    response = client.post("/api/generate", json=VALID_GENERATE_REQUEST)

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "live"
    assert payload["session_id"]
    assert payload["evaluation"] is None
    assert payload["generation"]["prompt_version"] == "v0.2"
    assert payload["speech_plan"] == VALID_PLAN
    text = json.dumps(payload, ensure_ascii=False)
    assert "REAL RAW RESPONSE" not in text
    assert "raw_response" not in text


def test_generate_endpoint_omits_empty_optional_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_service,
        "_default_generation_runner",
        lambda _input, _prompt: _generation_result(),
    )
    request = {
        **VALID_GENERATE_REQUEST,
        "learner_utterance": "",
        "affective_state": "",
    }

    response = client.post("/api/generate", json=request)

    assert response.status_code == 200
    input_doc = response.json()["input"]
    assert "learner_utterance" not in input_doc["pedagogical_context"]
    assert "affective_state" not in input_doc["learner"]


def test_invalid_generate_request_fails_before_hy3(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def forbidden(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        nonlocal called
        called = True
        raise AssertionError("Hy3 must not be called")

    monkeypatch.setattr(app_service, "_default_generation_runner", forbidden)

    response = client.post(
        "/api/generate",
        json={**VALID_GENERATE_REQUEST, "content_anchor": ""},
    )

    assert response.status_code == 400
    assert called is False
    assert response.json()["detail"]["error"]["type"] == "input_validation_error"


def test_hy3_failure_response_is_safe(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(_input: dict, _prompt: str) -> SpeechPlanGenerationResult:
        raise RuntimeError("Bearer sk-secret /Users/person/.env")

    monkeypatch.setattr(app_service, "_default_generation_runner", failing)

    response = client.post("/api/generate", json=VALID_GENERATE_REQUEST)

    assert response.status_code == 502
    text = json.dumps(response.json(), ensure_ascii=False)
    for forbidden in FORBIDDEN:
        assert forbidden not in text


def test_evaluate_endpoint_uses_stored_raw_response_and_returns_all_dimensions(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_service,
        "_default_generation_runner",
        lambda _input, _prompt: _generation_result("STORED RAW"),
    )
    seen = {}

    def fake_evaluator(input_doc: dict, raw_response: str, run_context):
        seen["input_doc"] = input_doc
        seen["raw_response"] = raw_response
        seen["input_case_id"] = run_context.input_case_id
        return {"artifact": _evaluation_artifact()}

    monkeypatch.setattr(app_service, "_default_evaluation_runner", fake_evaluator)
    generated = client.post("/api/generate", json=VALID_GENERATE_REQUEST).json()

    response = client.post("/api/evaluate", json={"session_id": generated["session_id"]})

    assert response.status_code == 200
    payload = response.json()
    assert seen["raw_response"] == "STORED RAW"
    assert seen["raw_response"] != json.dumps(VALID_PLAN, ensure_ascii=False)
    assert seen["input_case_id"] == f"live-{generated['session_id']}"
    assert payload["evaluation"]["available"] is True
    assert set(payload["evaluation"]["scores"]) == set(DIMENSION_IDS)
    text = json.dumps(payload, ensure_ascii=False)
    assert "STORED RAW" not in text
    assert "raw_response" not in text


def test_evaluate_endpoint_failure_is_unavailable_not_zero(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_service,
        "_default_generation_runner",
        lambda _input, _prompt: _generation_result(),
    )
    monkeypatch.setattr(
        app_service,
        "_default_evaluation_runner",
        lambda _input, _raw, _ctx: {
            "available": False,
            "failure_type": "judge_api_error",
            "failure_summary": "Judge unavailable.",
        },
    )
    generated = client.post("/api/generate", json=VALID_GENERATE_REQUEST).json()

    response = client.post("/api/evaluate", json={"session_id": generated["session_id"]})

    assert response.status_code == 200
    evaluation = response.json()["evaluation"]
    assert evaluation["available"] is False
    assert evaluation["failure_type"] == "judge_api_error"
    assert evaluation["scores"] == {}


def test_evaluate_unknown_session_returns_404(client: TestClient) -> None:
    response = client.post("/api/evaluate", json={"session_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["type"] == "unknown_session"


def test_repeated_evaluate_endpoint_uses_cached_evaluation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_service,
        "_default_generation_runner",
        lambda _input, _prompt: _generation_result(),
    )
    calls = 0

    def fake_evaluator(_input: dict, _raw: str, _ctx):
        nonlocal calls
        calls += 1
        return {"artifact": _evaluation_artifact()}

    monkeypatch.setattr(app_service, "_default_evaluation_runner", fake_evaluator)
    generated = client.post("/api/generate", json=VALID_GENERATE_REQUEST).json()

    first = client.post("/api/evaluate", json={"session_id": generated["session_id"]})
    second = client.post("/api/evaluate", json={"session_id": generated["session_id"]})

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


def test_live_endpoints_do_not_modify_results_or_public_artifacts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked = sorted(
        list(Path("public_demo").rglob("*"))
        + list(Path("results").rglob("evaluations.jsonl"))
    )
    before = {
        path: path.stat().st_mtime_ns
        for path in tracked
        if path.is_file()
    }
    monkeypatch.setattr(
        app_service,
        "_default_generation_runner",
        lambda _input, _prompt: _generation_result(),
    )
    monkeypatch.setattr(
        app_service,
        "_default_evaluation_runner",
        lambda _input, _raw, _ctx: {"artifact": _evaluation_artifact()},
    )

    generated = client.post("/api/generate", json=VALID_GENERATE_REQUEST).json()
    client.post("/api/evaluate", json={"session_id": generated["session_id"]})

    after = {
        path: path.stat().st_mtime_ns
        for path in tracked
        if path.is_file()
    }
    assert before == after
