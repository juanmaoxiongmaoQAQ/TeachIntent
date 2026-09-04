from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from teachintent.evaluator import DIMENSIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "export_public_demo_artifacts.py"
SPEC = importlib.util.spec_from_file_location(
    "export_public_demo_artifacts", SCRIPT_PATH
)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _dimension_scores(case_text: str, *, multiple_evidence: bool = False) -> dict:
    scores = {}
    for dimension_id, _label in DIMENSIONS:
        evidence = [
            {
                "source": "plan.verbal_plan.segments[0].text",
                "text": case_text,
            }
        ]
        if multiple_evidence and dimension_id == "delivery_pedagogy_alignment":
            evidence.append(
                {
                    "source": "plan.delivery_plan.seg_01.tone",
                    "text": "warm and focused",
                }
            )
        scores[dimension_id] = {
            "score": 4,
            "evidence": evidence,
            "brief_justification": f"{dimension_id} grounded justification.",
        }
    return scores


def _evaluation_record(
    *,
    case_id: str,
    run_prompt_version: str,
    top_level_prompt_version: str | None = "v0.2",
    critical_flags: list[dict] | None = None,
    multiple_evidence: bool = False,
) -> dict:
    record = {
        "case_id": case_id,
        "final_artifact": {
            "critical_flags": critical_flags or [],
            "evaluator_version": "v0.1",
            "run_metadata": {
                "judge_prompt_version": "v0.1",
                "prompt_version": run_prompt_version,
            },
            "scores": _dimension_scores(
                f"public evidence for {case_id}",
                multiple_evidence=multiple_evidence,
            ),
        },
    }
    if top_level_prompt_version is not None:
        record["prompt_version"] = top_level_prompt_version
    return record


def _write_synthetic_sources(tmp_path: Path) -> tuple[Path, Path]:
    examples_root = tmp_path / "examples"
    results_root = tmp_path / "results"
    cases = {
        "corrective_feedback.json": (
            "PILOT-A-COR-01",
            "20260901T043729Z",
        ),
        "scaffolding.json": ("RS-V1-SCA-CHA-01", "20260901T093114Z"),
        "supportive_feedback.json": ("RS-V1-SUP-CHX-01", "20260901T093114Z"),
    }
    for file_name, (case_id, run_id) in cases.items():
        _write_json(
            examples_root / file_name,
            {
                "source": {"case_id": case_id},
                "recorded_evaluations": {
                    "v0.2": {
                        "run_id": run_id,
                        "evaluator_version": "v0.1",
                        "judge_prompt_version": "v0.1",
                    }
                },
            },
        )

    rc2_path = (
        results_root
        / "prompt_v0_2_rc2_development_evaluation"
        / "20260901T043729Z"
        / "evaluations.jsonl"
    )
    rc2_path.parent.mkdir(parents=True, exist_ok=True)
    rc2_path.write_text(
        json.dumps(
            _evaluation_record(
                case_id="PILOT-A-COR-01",
                run_prompt_version="v0.2-rc.2",
                top_level_prompt_version=None,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    release_path = (
        results_root / "release_sanity" / "20260901T093114Z" / "evaluations.jsonl"
    )
    release_path.parent.mkdir(parents=True, exist_ok=True)
    release_records = [
        _evaluation_record(
            case_id="RS-V1-SCA-CHA-01",
            run_prompt_version="v0.2",
            multiple_evidence=True,
        ),
        _evaluation_record(
            case_id="RS-V1-SUP-CHX-01",
            run_prompt_version="v0.2",
            critical_flags=[
                {
                    "flag": "content_boundary_violation",
                    "evidence": [
                        {
                            "source": "plan.verbal_plan.segments[0].text",
                            "text": "public evidence for RS-V1-SUP-CHX-01",
                        }
                    ],
                    "brief_justification": "Flag preserved from source.",
                }
            ],
        ),
    ]
    release_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True)
            for record in release_records
        )
        + "\n",
        encoding="utf-8",
    )
    return examples_root, results_root


def test_exports_all_public_demo_artifacts_from_locked_sources(tmp_path: Path) -> None:
    examples_root, results_root = _write_synthetic_sources(tmp_path)
    output_dir = tmp_path / "public_demo" / "evaluator_artifacts"

    source_files = sorted(examples_root.glob("*.json")) + sorted(
        results_root.rglob("evaluations.jsonl")
    )
    before = {path: _sha256(path) for path in source_files}
    exported = exporter.export_public_demo_artifacts(
        examples_root=examples_root,
        results_root=results_root,
        output_dir=output_dir,
    )
    after = {path: _sha256(path) for path in source_files}

    assert before == after
    assert {item.example_name for item in exported} == {
        "corrective-feedback",
        "scaffolding",
        "supportive-feedback",
    }
    assert sorted(path.name for path in output_dir.glob("*.json")) == [
        "corrective-feedback.v0_2.json",
        "scaffolding.v0_2.json",
        "supportive-feedback.v0_2.json",
    ]


def test_exported_artifact_preserves_scores_evidence_and_provenance(
    tmp_path: Path,
) -> None:
    examples_root, results_root = _write_synthetic_sources(tmp_path)
    output_dir = tmp_path / "public_demo" / "evaluator_artifacts"

    exporter.export_public_demo_artifacts(
        examples_root=examples_root,
        results_root=results_root,
        output_dir=output_dir,
    )

    scaffolding = json.loads(
        (output_dir / "scaffolding.v0_2.json").read_text(encoding="utf-8")
    )
    assert scaffolding["artifact_version"] == exporter.ARTIFACT_VERSION
    assert scaffolding["case_id"] == "RS-V1-SCA-CHA-01"
    assert scaffolding["source_run_id"] == "20260901T093114Z"
    assert scaffolding["evaluator_version"] == "v0.1"
    assert scaffolding["judge_prompt_version"] == "v0.1"
    assert set(scaffolding["scores"]) == {dimension for dimension, _ in DIMENSIONS}
    for score in scaffolding["scores"].values():
        assert score["score"] == 4
        assert score["brief_justification"]
        assert score["evidence"]
    assert (
        len(scaffolding["scores"]["delivery_pedagogy_alignment"]["evidence"]) == 2
    )


def test_exported_artifact_preserves_critical_flags(tmp_path: Path) -> None:
    examples_root, results_root = _write_synthetic_sources(tmp_path)
    output_dir = tmp_path / "public_demo" / "evaluator_artifacts"

    exporter.export_public_demo_artifacts(
        examples_root=examples_root,
        results_root=results_root,
        output_dir=output_dir,
    )

    supportive = json.loads(
        (output_dir / "supportive-feedback.v0_2.json").read_text(encoding="utf-8")
    )
    assert supportive["critical_flags"] == [
        {
            "flag": "content_boundary_violation",
            "evidence": [
                {
                    "source": "plan.verbal_plan.segments[0].text",
                    "text": "public evidence for RS-V1-SUP-CHX-01",
                }
            ],
            "brief_justification": "Flag preserved from source.",
        }
    ]


def test_export_rejects_secret_patterns_in_public_demo(tmp_path: Path) -> None:
    public_demo = tmp_path / "public_demo"
    artifact_dir = public_demo / "evaluator_artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "bad.json").write_text(
        '{"unsafe": "Authorization: Bearer token"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Forbidden public demo content"):
        exporter.scan_public_demo(public_demo)


def test_exported_artifacts_do_not_contain_absolute_paths_or_secrets(
    tmp_path: Path,
) -> None:
    examples_root, results_root = _write_synthetic_sources(tmp_path)
    output_dir = tmp_path / "public_demo" / "evaluator_artifacts"

    exporter.export_public_demo_artifacts(
        examples_root=examples_root,
        results_root=results_root,
        output_dir=output_dir,
    )

    for path in output_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert "/mnt/" not in text
        assert "Authorization:" not in text
        assert "Bearer " not in text
        assert "sk-" not in text
        assert "raw_response" not in text
        assert "judge_raw_response" not in text
