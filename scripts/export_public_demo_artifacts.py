#!/usr/bin/env python3
"""Export portable recorded evaluator artifacts for the public visual demo.

This exporter is intentionally offline-only. It copies a small, sanitized slice
of existing immutable evaluator artifacts into ``public_demo/`` so the demo can
run in a fresh clone without depending on git-ignored ``results/`` directories.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from teachintent.evaluator import DIMENSIONS  # noqa: E402


ARTIFACT_VERSION = "public-demo-evaluator-artifact-v1"
PUBLIC_PROMPT_VERSION = "v0.2"
DEFAULT_EXAMPLES_ROOT = Path("examples")
DEFAULT_RESULTS_ROOT = Path("results")
DEFAULT_OUTPUT_DIR = Path("public_demo") / "evaluator_artifacts"

EXAMPLE_FILES = {
    "corrective-feedback": "corrective_feedback.json",
    "scaffolding": "scaffolding.json",
    "supportive-feedback": "supportive_feedback.json",
}

LOCKED_EVALUATION_RUNS = {
    "20260901T043729Z": (
        Path("prompt_v0_2_rc2_development_evaluation")
        / "20260901T043729Z"
        / "evaluations.jsonl"
    ),
    "20260901T093114Z": (
        Path("release_sanity") / "20260901T093114Z" / "evaluations.jsonl"
    ),
}

FORBIDDEN_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"/Users/",
        r"/mnt/",
        r"chengtengteng",
        r"Authorization:",
        r"Bearer ",
        r"sk-",
        r"HY3_API_KEY",
        r"OPENROUTER_API_KEY",
        r"raw_response",
        r"judge_raw_response",
    )
]


@dataclass(frozen=True)
class ExportedDemoArtifact:
    path: Path
    example_name: str
    case_id: str
    source_run_id: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_prompt_version(version: str | None) -> str | None:
    if not version:
        return None
    return version.replace("_", ".")


def prompt_version_for_record(record: dict[str, Any]) -> str | None:
    if record.get("prompt_version"):
        return normalize_prompt_version(record["prompt_version"])
    artifact = record.get("final_artifact") or {}
    metadata = artifact.get("run_metadata") or {}
    return normalize_prompt_version(metadata.get("prompt_version"))


def run_file_for_id(results_root: Path, run_id: str) -> Path:
    try:
        relative = LOCKED_EVALUATION_RUNS[run_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported recorded evaluator run_id: {run_id}") from exc
    return results_root / relative


def recorded_v0_2_metadata(example: dict[str, Any]) -> dict[str, Any]:
    recorded = (example.get("recorded_evaluations") or {}).get(PUBLIC_PROMPT_VERSION)
    if not isinstance(recorded, dict):
        raise ValueError("Example has no recorded_evaluations.v0.2 metadata")
    if recorded.get("available") is False:
        raise ValueError("Example v0.2 recorded evaluation is unavailable")
    return recorded


def find_final_artifact(
    evaluations_file: Path,
    *,
    case_id: str,
    prompt_version: str,
) -> dict[str, Any]:
    if not evaluations_file.is_file():
        raise FileNotFoundError(f"Missing evaluator source artifact: {evaluations_file}")

    accepted_versions = {prompt_version}
    if prompt_version == PUBLIC_PROMPT_VERSION:
        accepted_versions.add("v0.2-rc.2")

    for record in read_jsonl(evaluations_file):
        if record.get("case_id") != case_id:
            continue
        if prompt_version_for_record(record) not in accepted_versions:
            continue
        artifact = record.get("final_artifact")
        if isinstance(artifact, dict) and artifact.get("scores"):
            return artifact

    raise ValueError(
        f"No final evaluator artifact found for case_id={case_id!r} "
        f"prompt_version={prompt_version!r} in {evaluations_file}"
    )


def simplify_evidence(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    simplified: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        simplified.append(
            {
                "source": str(item.get("source", "")),
                "text": str(item.get("text", "")),
            }
        )
    return simplified


def simplify_scores(scores: dict[str, Any]) -> dict[str, dict[str, Any]]:
    public_scores: dict[str, dict[str, Any]] = {}
    for dimension_id, _label in DIMENSIONS:
        score_obj = scores.get(dimension_id)
        if not isinstance(score_obj, dict):
            raise ValueError(f"Missing evaluator score for {dimension_id}")
        if "score" not in score_obj:
            raise ValueError(f"Missing numeric score for {dimension_id}")
        justification = score_obj.get("brief_justification")
        if not justification:
            raise ValueError(f"Missing brief_justification for {dimension_id}")
        evidence = simplify_evidence(score_obj.get("evidence"))
        if not evidence:
            raise ValueError(f"Missing evidence for {dimension_id}")
        public_scores[dimension_id] = {
            "score": score_obj["score"],
            "evidence": evidence,
            "brief_justification": str(justification),
        }
    return public_scores


def simplify_critical_flags(flags: Any) -> list[dict[str, Any]]:
    if not flags:
        return []
    if not isinstance(flags, list):
        raise ValueError("critical_flags must be a list")
    simplified: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            raise ValueError("critical_flags entries must be objects")
        simplified.append(
            {
                "flag": str(flag.get("flag", "")),
                "evidence": simplify_evidence(flag.get("evidence")),
                "brief_justification": str(flag.get("brief_justification", "")),
            }
        )
    return simplified


def build_public_artifact(
    *,
    example_name: str,
    case_id: str,
    prompt_version: str,
    source_run_id: str,
    final_artifact: dict[str, Any],
) -> dict[str, Any]:
    metadata = final_artifact.get("run_metadata") or {}
    evaluator_version = final_artifact.get("evaluator_version")
    judge_prompt_version = metadata.get("judge_prompt_version")
    if not evaluator_version:
        raise ValueError("Missing evaluator_version in source artifact")
    if not judge_prompt_version:
        raise ValueError("Missing judge_prompt_version in source artifact")

    return {
        "artifact_version": ARTIFACT_VERSION,
        "case_id": case_id,
        "critical_flags": simplify_critical_flags(
            final_artifact.get("critical_flags")
        ),
        "evaluator_version": evaluator_version,
        "example_name": example_name,
        "judge_prompt_version": judge_prompt_version,
        "prompt_version": prompt_version,
        "scores": simplify_scores(final_artifact.get("scores") or {}),
        "source_run_id": source_run_id,
    }


def scan_public_demo(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                raise ValueError(
                    f"Forbidden public demo content matched {pattern.pattern!r} "
                    f"in {path}"
                )


def export_public_demo_artifacts(
    *,
    examples_root: Path = DEFAULT_EXAMPLES_ROOT,
    results_root: Path = DEFAULT_RESULTS_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[ExportedDemoArtifact]:
    exported: list[ExportedDemoArtifact] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for example_name, file_name in EXAMPLE_FILES.items():
        example = read_json(examples_root / file_name)
        case_id = ((example.get("source") or {}).get("case_id") or "").strip()
        if not case_id:
            raise ValueError(f"Example {file_name} has no source.case_id")
        recorded = recorded_v0_2_metadata(example)
        source_run_id = str(recorded.get("run_id") or "")
        if not source_run_id:
            raise ValueError(f"Example {file_name} has no recorded run_id")

        final_artifact = find_final_artifact(
            run_file_for_id(results_root, source_run_id),
            case_id=case_id,
            prompt_version=PUBLIC_PROMPT_VERSION,
        )
        public_artifact = build_public_artifact(
            example_name=example_name,
            case_id=case_id,
            prompt_version=PUBLIC_PROMPT_VERSION,
            source_run_id=source_run_id,
            final_artifact=final_artifact,
        )
        destination = output_dir / f"{example_name}.v0_2.json"
        destination.write_text(
            json.dumps(
                public_artifact,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        exported.append(
            ExportedDemoArtifact(
                path=destination,
                example_name=example_name,
                case_id=case_id,
                source_run_id=source_run_id,
            )
        )

    scan_public_demo(output_dir.parent)
    return exported


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export sanitized public visual-demo evaluator artifacts."
    )
    parser.add_argument("--examples-root", type=Path, default=DEFAULT_EXAMPLES_ROOT)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    exported = export_public_demo_artifacts(
        examples_root=args.examples_root,
        results_root=args.results_root,
        output_dir=args.output_dir,
    )
    for artifact in exported:
        print(
            f"{artifact.path}: {artifact.example_name} "
            f"{artifact.source_run_id}/{artifact.case_id}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
