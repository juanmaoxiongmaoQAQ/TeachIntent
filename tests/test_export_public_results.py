from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = REPO_ROOT / "scripts" / "export_public_results.py"
SPEC = importlib.util.spec_from_file_location("export_public_results", EXPORTER_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules["export_public_results"] = exporter
SPEC.loader.exec_module(exporter)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def score_artifact(*scores: int) -> dict:
    return {
        "critical_flags": [],
        "scores": {
            full_name: {"score": score}
            for full_name, score in zip(exporter.DIMENSIONS.values(), scores)
        },
    }


def eval_record(case_id: str, prompt_version: str, artifact: dict | None) -> dict:
    return {
        "case_id": case_id,
        "prompt_version": prompt_version,
        "semantic_repeat_success": artifact is not None,
        "stopped_reason": "valid_artifact" if artifact else "generation_no_raw_response",
        "final_artifact": artifact,
    }


def create_fixture(results_root: Path) -> None:
    for run_dir in exporter.SOURCE_RUNS.values():
        write_json(results_root / run_dir / "run_manifest.json", {"run_id": run_dir.name})

    write_csv(
        results_root / exporter.SOURCE_RUNS["evaluator"] / "pair_metrics.csv",
        [
            "pair_id",
            "family",
            "eligible",
            "reference_success_count",
            "degraded_success_count",
            "D1_ref_mean",
            "D1_deg_mean",
            "D1_delta",
            "primary_dimensions",
            "collateral_dimensions",
            "protected_dimensions",
            "expected_flags",
            "degraded_critical_flags",
            "reference_critical_flags",
        ],
        [
            {
                "pair_id": "P1",
                "family": "intent_mismatch",
                "eligible": "true",
                "reference_success_count": "3",
                "degraded_success_count": "3",
                "D1_ref_mean": "4",
                "D1_deg_mean": "2",
                "D1_delta": "-2",
            },
            {
                "pair_id": "P2",
                "family": "content_error",
                "eligible": "false",
                "reference_success_count": "3",
                "degraded_success_count": "0",
                "D1_ref_mean": "",
                "D1_deg_mean": "",
                "D1_delta": "",
            },
        ],
    )
    write_csv(
        results_root / exporter.SOURCE_RUNS["evaluator"] / "family_metrics.csv",
        ["family", "total_pairs", "eligible_pairs", "directional_accuracy", "flag_tp"],
        [{"family": "intent_mismatch", "total_pairs": "2", "eligible_pairs": "1"}],
    )
    write_csv(
        results_root / exporter.SOURCE_RUNS["v0_1_baseline"] / "case_metrics.csv",
        [
            "case_id",
            "block",
            "block_name",
            "intent",
            "eligible",
            "exclusion_reason",
            "successful_repeats",
            "failed_semantic_repeats",
            "total_physical_attempts",
            "D1",
            "D2",
            "D3",
            "D4",
            "D5",
            "D6",
            "overall_mean",
            "critical_flags",
            "failure_types",
            "weak_dimensions",
            "severe_dimensions",
        ],
        [
            {"case_id": "B1", "eligible": "true", "overall_mean": "100"},
            {"case_id": "B2", "eligible": "false", "exclusion_reason": "failed"},
            {"case_id": "B3", "eligible": "true", "overall_mean": "90"},
        ],
    )
    paired_fields = [
        "case_id",
        "block",
        "intent",
        "pair_eligible",
        "exclusion_reason",
        "v0_1_D1",
        "rc_1_D1",
        "rc_2_D1",
        "delta_D1",
        "v0_1_overall_mean",
        "rc_1_overall_mean",
        "rc_2_overall_mean",
        "delta_overall_mean",
        "v0_1_critical_flags",
        "rc_1_critical_flags",
        "rc_2_critical_flags",
    ]
    for run_name in ("rc_1_development", "rc_2_development"):
        write_csv(
            results_root / exporter.SOURCE_RUNS[run_name] / "paired_comparison.csv",
            paired_fields,
            [
                {"case_id": "P1", "pair_eligible": "true"},
                {"case_id": "P2", "pair_eligible": "false", "exclusion_reason": "x"},
            ],
        )

    release_dir = results_root / exporter.SOURCE_RUNS["release_sanity"]
    write_jsonl(
        release_dir / "dataset" / "release_sanity_v1.jsonl",
        [
            {
                "case_id": "RS-OK",
                "block": "standard",
                "difficulty": "standard",
                "input": {"pedagogical_intent": {"primary": "elicitation"}},
            },
            {
                "case_id": "RS-FAIL",
                "block": "hard_adversarial",
                "difficulty": "challenging",
                "input": {"pedagogical_intent": {"primary": "extension"}},
            },
        ],
    )
    write_jsonl(
        release_dir / "evaluations.jsonl",
        [
            eval_record("RS-OK", "v0.1", score_artifact(4, 4, 4, 4, 4, 4)),
            eval_record("RS-OK", "v0.2", score_artifact(4, 4, 4, 4, 3, 4)),
            eval_record("RS-FAIL", "v0.1", score_artifact(4, 4, 4, 4, 4, 4)),
            eval_record("RS-FAIL", "v0.2", None),
        ],
    )
    write_csv(
        release_dir / "paired_scores.csv",
        ["case_id", "pair_eligible", "delta_D1", "delta_D2", "delta_D3", "delta_D4", "delta_D5", "delta_D6"],
        [
            {"case_id": "RS-OK", "pair_eligible": "true", "delta_D5": "-1"},
            {"case_id": "RS-FAIL", "pair_eligible": "false"},
        ],
    )
    for case_id in ("RS-OK", "RS-FAIL"):
        for side in ("v0_1", "v0_2"):
            side_dir = release_dir / "generation" / case_id / side
            valid = not (case_id == "RS-FAIL" and side == "v0_2")
            write_json(
                side_dir / "metadata.json",
                {
                    "case_id": case_id,
                    "prompt_version": side.replace("_", "."),
                    "valid_plan": valid,
                    "outcome": "success" if valid else "Hy3APIError",
                    "finish_reason": "stop" if valid else None,
                },
            )
            if valid:
                write_json(
                    side_dir / "parsed.json",
                    {"delivery_plan": {"global": {"attitudinal_tone": "calm"}}},
                )
            else:
                write_json(
                    side_dir / "error.json",
                    {"exception_class": "Hy3APIError", "summary": "empty response"},
                )


def test_exports_all_files_and_counts(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    output_dir = tmp_path / "public_results"
    create_fixture(results_root)

    result = exporter.export_public_results(
        results_root=results_root,
        output_dir=output_dir,
        repo_root=tmp_path,
    )

    expected_files = {
        "README.md",
        "manifest.json",
        "evaluator_validation_pairs.csv",
        "evaluator_validation_families.csv",
        "generator_v0_1_baseline_results.csv",
        "prompt_v0_2_rc1_development_results.csv",
        "prompt_v0_2_rc2_development_results.csv",
        "release_sanity_results.csv",
    }
    assert {path.name for path in output_dir.iterdir()} == expected_files
    assert result.row_counts == {
        "evaluator_validation_pairs.csv": 2,
        "evaluator_validation_families.csv": 1,
        "generator_v0_1_baseline_results.csv": 3,
        "prompt_v0_2_rc1_development_results.csv": 2,
        "prompt_v0_2_rc2_development_results.csv": 2,
        "release_sanity_results.csv": 2,
    }


def test_excluded_failed_and_unavailable_rows_are_preserved(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    output_dir = tmp_path / "public_results"
    create_fixture(results_root)

    exporter.export_public_results(results_root, output_dir, repo_root=tmp_path)

    baseline = read_csv(output_dir / "generator_v0_1_baseline_results.csv")
    assert [row["case_id"] for row in baseline] == ["B1", "B2", "B3"]
    assert baseline[1]["eligible"] == "false"

    release = {
        row["case_id"]: row for row in read_csv(output_dir / "release_sanity_results.csv")
    }
    failed = release["RS-FAIL"]
    assert failed["v0_2_generation_valid"] == "false"
    assert failed["v0_2_evaluation_available"] == "false"
    assert failed["v0_2_D1"] == ""
    assert "v0_2_generation_error:Hy3APIError" in failed["failure_reason"]
    assert "generation_no_response" in failed["failure_reason"]
    assert "raw_response" not in failed["failure_reason"]


def test_public_export_contains_no_absolute_paths(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    output_dir = tmp_path / "public_results"
    create_fixture(results_root)

    exporter.export_public_results(results_root, output_dir, repo_root=tmp_path)

    combined = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.iterdir())
    assert "/Users/" not in combined
    assert "/mnt/" not in combined
    assert str(tmp_path) not in combined


def test_secret_scanner_blocks_sensitive_strings(tmp_path: Path) -> None:
    output_dir = tmp_path / "public_results"
    output_dir.mkdir()
    (output_dir / "bad.csv").write_text("Authorization: Bearer sk-test\n", encoding="utf-8")

    with pytest.raises(ValueError):
        exporter.scan_public_results(output_dir)


def test_source_artifacts_are_not_modified(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    output_dir = tmp_path / "public_results"
    create_fixture(results_root)
    source_files = exporter.collect_source_files(results_root)
    before = {
        path: (exporter.sha256_file(path), path.stat().st_mtime_ns)
        for path in source_files
    }

    exporter.export_public_results(results_root, output_dir, repo_root=tmp_path)

    after = {
        path: (exporter.sha256_file(path), path.stat().st_mtime_ns)
        for path in source_files
    }
    assert after == before
