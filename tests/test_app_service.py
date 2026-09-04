from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from teachintent import app_service
from teachintent.evaluator import DIMENSION_IDS


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
