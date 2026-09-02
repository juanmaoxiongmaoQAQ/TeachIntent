#!/usr/bin/env python3
"""Export public, sanitized Task-1 result tables from fixed local artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


EXPORT_VERSION = "public-results-v1"
DEFAULT_RESULTS_ROOT = Path("results")
DEFAULT_OUTPUT_DIR = Path("public_results")

SOURCE_RUNS = {
    "evaluator": Path("evaluator_diagnostic_confirmatory/20260829T154127Z"),
    "v0_1_baseline": Path(
        "generator_v0_1_baseline_evaluation_v0_2/20260830T095934Z"
    ),
    "rc_1_development": Path(
        "prompt_v0_2_rc1_development_evaluation/20260831T103707Z"
    ),
    "rc_2_development": Path(
        "prompt_v0_2_rc2_development_evaluation/20260901T043729Z"
    ),
    "release_sanity": Path("release_sanity/20260901T093114Z"),
}

PUBLIC_COPIES = {
    "evaluator_validation_pairs.csv": (
        "evaluator",
        "pair_metrics.csv",
    ),
    "evaluator_validation_families.csv": (
        "evaluator",
        "family_metrics.csv",
    ),
    "generator_v0_1_baseline_results.csv": (
        "v0_1_baseline",
        "case_metrics.csv",
    ),
    "prompt_v0_2_rc1_development_results.csv": (
        "rc_1_development",
        "paired_comparison.csv",
    ),
    "prompt_v0_2_rc2_development_results.csv": (
        "rc_2_development",
        "paired_comparison.csv",
    ),
}

DIMENSIONS = {
    "D1": "pedagogical_intent_fidelity",
    "D2": "content_faithfulness_boundary",
    "D3": "learner_state_compatibility",
    "D4": "intent_specific_instructional_adequacy",
    "D5": "delivery_necessity_sparsity",
    "D6": "delivery_pedagogy_alignment",
}

RELEASE_FIELDS = [
    "case_id",
    "block",
    "difficulty",
    "intent",
    "v0_1_generation_valid",
    "v0_2_generation_valid",
    "v0_1_finish_reason",
    "v0_2_finish_reason",
    "v0_1_evaluation_available",
    "v0_2_evaluation_available",
    "pair_eligible",
    "v0_1_D1",
    "v0_1_D2",
    "v0_1_D3",
    "v0_1_D4",
    "v0_1_D5",
    "v0_1_D6",
    "v0_2_D1",
    "v0_2_D2",
    "v0_2_D3",
    "v0_2_D4",
    "v0_2_D5",
    "v0_2_D6",
    "delta_D1",
    "delta_D2",
    "delta_D3",
    "delta_D4",
    "delta_D5",
    "delta_D6",
    "v0_1_critical_flags",
    "v0_2_critical_flags",
    "v0_1_delivery_empty",
    "v0_2_delivery_empty",
    "v0_1_delivery_control_count",
    "v0_2_delivery_control_count",
    "failure_reason",
]

FORBIDDEN_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"/Users/",
        r"/mnt/",
        r"HY3_API_KEY=",
        r"Authorization:",
        r"Bearer ",
        r"sk-",
        r"raw_response",
        r"judge_raw_response",
        r"http_response",
        r"prompt_system",
        r"prompt_user",
        r"\.env",
    )
]


@dataclass(frozen=True)
class ExportResult:
    output_dir: Path
    row_counts: dict[str, int]
    manifest: dict


def repo_relative(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict]) -> int:
    materialized = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def copy_public_csv(source: Path, destination: Path) -> int:
    fieldnames, rows = read_csv_rows(source)
    return write_csv(destination, fieldnames, rows)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_prompt_version(version: str) -> str:
    return version.replace("_", ".")


def release_prompt_version(record: dict) -> str | None:
    if record.get("prompt_version"):
        return normalize_prompt_version(record["prompt_version"])
    artifact = record.get("final_artifact") or {}
    metadata = artifact.get("run_metadata") or {}
    if metadata.get("prompt_version"):
        return normalize_prompt_version(metadata["prompt_version"])
    for attempt in record.get("attempts") or []:
        attempt_metadata = attempt.get("run_metadata") or {}
        if attempt_metadata.get("prompt_version"):
            return normalize_prompt_version(attempt_metadata["prompt_version"])
    return None


def release_scores(record: dict | None) -> dict[str, str]:
    artifact = (record or {}).get("final_artifact") or {}
    scores = artifact.get("scores") or {}
    values: dict[str, str] = {}
    for short_name, full_name in DIMENSIONS.items():
        score = (scores.get(full_name) or {}).get("score")
        values[short_name] = "" if score is None else str(score)
    return values


def release_critical_flags(record: dict | None) -> str:
    artifact = (record or {}).get("final_artifact") or {}
    flags = artifact.get("critical_flags")
    if not flags:
        return ""
    return "|".join(str(flag) for flag in flags)


def release_failure_reason(
    eval_by_side: dict[str, dict | None],
    metadata_by_side: dict[str, dict],
    error_by_side: dict[str, dict],
) -> str:
    reasons: list[str] = []
    for side in ("v0.1", "v0.2"):
        metadata = metadata_by_side.get(side) or {}
        error = error_by_side.get(side) or {}
        evaluation = eval_by_side.get(side) or {}
        side_label = side.replace(".", "_")
        if metadata.get("valid_plan") is False:
            reasons.append(
                f"{side_label}_generation_failure:{metadata.get('outcome', '')}"
            )
        if error.get("exception_class"):
            reasons.append(
                f"{side_label}_generation_error:{error['exception_class']}"
            )
        if evaluation.get("semantic_repeat_success") is False:
            reasons.append(
                f"{side_label}_evaluation_unavailable:"
                f"{evaluation.get('stopped_reason', '')}"
            )
    return "|".join(reason for reason in reasons if reason)


def sanitize_failure_reason(reason: str) -> str:
    return (
        reason.replace("generation_no_raw_response", "generation_no_response")
        .replace("raw_response", "response")
        .replace("http_response", "http_body")
        .replace("prompt_system", "prompt_hash")
        .replace("prompt_user", "prompt_hash")
    )


def delivery_summary(parsed_path: Path) -> tuple[str, str]:
    if not parsed_path.exists():
        return "", ""
    plan = read_json(parsed_path)
    delivery = plan.get("delivery_plan") or {}
    if not delivery:
        return "true", "0"
    return "false", str(count_delivery_controls(delivery))


def count_delivery_controls(value: object) -> int:
    if isinstance(value, dict):
        if not value:
            return 0
        return sum(count_delivery_controls(item) for item in value.values())
    if isinstance(value, list):
        if not value:
            return 0
        return sum(count_delivery_controls(item) for item in value)
    if value in (None, ""):
        return 0
    return 1


def load_release_dataset(path: Path) -> list[dict]:
    rows = []
    for record in read_jsonl(path):
        rows.append(
            {
                "case_id": record["case_id"],
                "block": record["block"],
                "difficulty": record["difficulty"],
                "intent": record["input"]["pedagogical_intent"]["primary"],
            }
        )
    return rows


def load_release_evaluations(path: Path) -> dict[tuple[str, str], dict]:
    indexed: dict[tuple[str, str], dict] = {}
    for record in read_jsonl(path):
        version = release_prompt_version(record)
        if version:
            indexed[(record["case_id"], version)] = record
    return indexed


def load_release_paired_scores(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_csv_rows(path)
    return {row["case_id"]: row for row in rows}


def release_side_dir(run_dir: Path, case_id: str, side: str) -> Path:
    return run_dir / "generation" / case_id / side.replace(".", "_")


def load_side_metadata(run_dir: Path, case_id: str, side: str) -> dict:
    path = release_side_dir(run_dir, case_id, side) / "metadata.json"
    return read_json(path) if path.exists() else {}


def load_side_error(run_dir: Path, case_id: str, side: str) -> dict:
    path = release_side_dir(run_dir, case_id, side) / "error.json"
    return read_json(path) if path.exists() else {}


def export_release_sanity(run_dir: Path, destination: Path) -> int:
    dataset_rows = load_release_dataset(run_dir / "dataset" / "release_sanity_v1.jsonl")
    evaluations = load_release_evaluations(run_dir / "evaluations.jsonl")
    paired_scores = load_release_paired_scores(run_dir / "paired_scores.csv")

    output_rows = []
    for dataset_row in dataset_rows:
        case_id = dataset_row["case_id"]
        paired = paired_scores.get(case_id, {})
        metadata_by_side = {
            side: load_side_metadata(run_dir, case_id, side)
            for side in ("v0.1", "v0.2")
        }
        error_by_side = {
            side: load_side_error(run_dir, case_id, side)
            for side in ("v0.1", "v0.2")
        }
        eval_by_side = {
            side: evaluations.get((case_id, side))
            for side in ("v0.1", "v0.2")
        }

        row = dict(dataset_row)
        for side in ("v0.1", "v0.2"):
            prefix = side.replace(".", "_")
            metadata = metadata_by_side[side]
            evaluation = eval_by_side[side]
            delivery_empty, delivery_count = delivery_summary(
                release_side_dir(run_dir, case_id, side) / "parsed.json"
            )
            row[f"{prefix}_generation_valid"] = str(
                metadata.get("valid_plan") is True
            ).lower()
            row[f"{prefix}_finish_reason"] = metadata.get("finish_reason") or ""
            row[f"{prefix}_evaluation_available"] = str(
                bool(evaluation and evaluation.get("final_artifact"))
            ).lower()
            for short_name, score in release_scores(evaluation).items():
                row[f"{prefix}_{short_name}"] = score
            row[f"{prefix}_critical_flags"] = release_critical_flags(evaluation)
            row[f"{prefix}_delivery_empty"] = delivery_empty
            row[f"{prefix}_delivery_control_count"] = delivery_count

        row["pair_eligible"] = paired.get("pair_eligible", "")
        for short_name in DIMENSIONS:
            row[f"delta_{short_name}"] = paired.get(f"delta_{short_name}", "")
        row["failure_reason"] = sanitize_failure_reason(
            release_failure_reason(eval_by_side, metadata_by_side, error_by_side)
        )
        output_rows.append(row)

    return write_csv(destination, RELEASE_FIELDS, output_rows)


def collect_source_files(results_root: Path) -> list[Path]:
    files = []
    for _, relative_run_dir in SOURCE_RUNS.items():
        run_dir = results_root / relative_run_dir
        files.append(run_dir / "run_manifest.json")
    for _, (run_name, source_name) in PUBLIC_COPIES.items():
        files.append(results_root / SOURCE_RUNS[run_name] / source_name)
    release_dir = results_root / SOURCE_RUNS["release_sanity"]
    files.extend(
        [
            release_dir / "dataset" / "release_sanity_v1.jsonl",
            release_dir / "evaluations.jsonl",
            release_dir / "paired_scores.csv",
        ]
    )
    files.extend(sorted((release_dir / "generation").glob("*/*/metadata.json")))
    files.extend(sorted((release_dir / "generation").glob("*/*/parsed.json")))
    files.extend(sorted((release_dir / "generation").glob("*/*/error.json")))
    return sorted(set(files))


def require_sources(paths: Iterable[Path]) -> None:
    missing = [path for path in paths if not path.exists()]
    if missing:
        formatted = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Required source artifact(s) missing:\n{formatted}")


def scan_public_results(output_dir: Path) -> None:
    hits = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                hits.append(f"{path.name}: {pattern.pattern}")
    if hits:
        raise ValueError(
            "Forbidden sensitive pattern(s) found in public export:\n"
            + "\n".join(hits)
        )


def write_public_readme(path: Path, row_counts: dict[str, int]) -> None:
    path.write_text(
        "\n".join(
            [
                "# TeachIntent Public Results Export",
                "",
                "This directory contains sanitized public tables exported from "
                "existing local experiment artifacts. The exporter does not rerun "
                "Hy3 generation, Judge evaluation, or Qwen3-TTS rendering.",
                "",
                "The tables intentionally exclude provider raw bodies, full prompt "
                "text, local absolute paths, environment files, and credentials.",
                "",
                "## Files",
                "",
                "| CSV | Experiment | Evidence role | Rows |",
                "| --- | --- | --- | ---: |",
                (
                    "| evaluator_validation_pairs.csv | Evaluator diagnostic "
                    "confirmatory run 20260829T154127Z | evaluator confirmatory "
                    f"evidence | {row_counts['evaluator_validation_pairs.csv']} |"
                ),
                (
                    "| evaluator_validation_families.csv | Evaluator diagnostic "
                    "confirmatory family summary | evaluator confirmatory "
                    f"evidence | {row_counts['evaluator_validation_families.csv']} |"
                ),
                (
                    "| generator_v0_1_baseline_results.csv | Generator v0.1 "
                    "baseline evaluation 20260830T095934Z | generator baseline "
                    f"descriptive evidence | {row_counts['generator_v0_1_baseline_results.csv']} |"
                ),
                (
                    "| prompt_v0_2_rc1_development_results.csv | Prompt v0.2-rc.1 "
                    "paired development evaluation 20260831T103707Z | prompt "
                    f"development evidence, not held-out confirmatory | {row_counts['prompt_v0_2_rc1_development_results.csv']} |"
                ),
                (
                    "| prompt_v0_2_rc2_development_results.csv | Prompt v0.2-rc.2 "
                    "paired development evaluation 20260901T043729Z | prompt "
                    f"development evidence, not held-out confirmatory | {row_counts['prompt_v0_2_rc2_development_results.csv']} |"
                ),
                (
                    "| release_sanity_results.csv | Release sanity run "
                    "20260901T093114Z | release sanity evidence, NOT FORMAL "
                    f"CONFIRMATORY EVIDENCE | {row_counts['release_sanity_results.csv']} |"
                ),
                "",
                "## Evidence Boundaries",
                "",
                "- Evaluator validation tables are confirmatory evidence for "
                "Evaluator v0.1 under the frozen diagnostic protocol.",
                "- Generator v0.1 baseline results are descriptive baseline evidence "
                "over the canonical 30-case Pilot.",
                "- Prompt v0.2-rc.1 and v0.2-rc.2 tables are development evidence "
                "on the same Pilot cases. They are not held-out confirmatory "
                "evidence.",
                "- Release sanity is a final integration check and is explicitly "
                "NOT FORMAL CONFIRMATORY EVIDENCE.",
                "",
                "## Related Documentation",
                "",
                "- [Results summary](../docs/RESULTS.md)",
                "- [Evaluation method](../docs/EVALUATION_METHOD.md)",
                "- [Failure analysis](../docs/FAILURE_ANALYSIS.md)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_manifest(
    output_dir: Path,
    results_root: Path,
    row_counts: dict[str, int],
    repo_root: Path,
) -> dict:
    source_files = collect_source_files(results_root)
    source_hashes = {
        repo_relative(path, repo_root): sha256_file(path) for path in source_files
    }
    output_files = {
        path.name: {
            "path": repo_relative(path, repo_root),
            "sha256": sha256_file(path),
        }
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "export_version": EXPORT_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "source_run_ids": {
            name: relative.parts[-1] for name, relative in SOURCE_RUNS.items()
        },
        "source_file_sha256": source_hashes,
        "output_files": output_files,
        "output_row_counts": row_counts,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def export_public_results(
    results_root: Path = DEFAULT_RESULTS_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    repo_root: Path | None = None,
) -> ExportResult:
    repo_root = (repo_root or Path.cwd()).resolve()
    results_root = results_root.resolve()
    output_dir = output_dir.resolve()
    source_files = collect_source_files(results_root)
    require_sources(source_files)

    output_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}

    for output_name, (run_name, source_name) in PUBLIC_COPIES.items():
        source = results_root / SOURCE_RUNS[run_name] / source_name
        row_counts[output_name] = copy_public_csv(source, output_dir / output_name)

    release_dir = results_root / SOURCE_RUNS["release_sanity"]
    row_counts["release_sanity_results.csv"] = export_release_sanity(
        release_dir, output_dir / "release_sanity_results.csv"
    )
    write_public_readme(output_dir / "README.md", row_counts)
    manifest = write_manifest(output_dir, results_root, row_counts, repo_root)
    scan_public_results(output_dir)
    return ExportResult(output_dir=output_dir, row_counts=row_counts, manifest=manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export sanitized public TeachIntent Task-1 result tables."
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
        help="Root containing fixed historical results runs (default: ./results).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for public result tables (default: ./public_results).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = export_public_results(
            results_root=args.results_root,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"public results export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Exported public results to {result.output_dir}")
    for name, count in sorted(result.row_counts.items()):
        print(f"{name}: {count} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
