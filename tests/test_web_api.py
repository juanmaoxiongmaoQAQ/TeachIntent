from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from teachintent import app_service
from teachintent.evaluator import DIMENSION_IDS
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
    return TestClient(create_app())


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
