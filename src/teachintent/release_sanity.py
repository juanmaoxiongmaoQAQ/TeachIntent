"""Lightweight Prompt v0.1 vs frozen Prompt v0.2 release-sanity workflow.

This module deliberately implements descriptive release evidence, not the
deferred research-grade confirmatory protocol.  It reuses the frozen Generator
and Evaluator services and the frozen outer Judge-attempt policy.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from pydantic import ValidationError

from .evaluator import JudgeCompleter
from .generator import generate_speech_plan
from .generator.errors import (
    GeneratorError,
    Hy3APIError,
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from .generator_evaluation.baseline_v0_1 import (
    DIMENSION_LABELS,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    GENERATOR_VERSION,
    CanonicalCase,
    build_frozen_judge_config,
)
from .generator_evaluation.baseline_v0_2 import (
    MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    RETRY_BACKOFF_SECONDS,
    RETRYABLE_FAILURE_TYPES,
    backoff_seconds,
    build_attempt_record,
    evaluate_attempt,
)
from .models import TeachIntentInput
from .prompts.registry import build_speech_plan_prompt_for_version
from .validators import iter_input_errors


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = REPO_ROOT / "cases" / "release_sanity" / "release_sanity_v1.jsonl"
DATASET_MANIFEST_PATH = DATASET_PATH.with_name("manifest.json")
DATASET_QC_PATH = DATASET_PATH.with_name("QC_SUMMARY.md")
RESULTS_ROOT = REPO_ROOT / "results" / "release_sanity"

EVIDENCE_LABEL = "RELEASE SANITY EVIDENCE — NOT FORMAL CONFIRMATORY EVIDENCE"
DATASET_VERSION = "release_sanity_v1"
PROMPT_VERSIONS: tuple[str, str] = ("v0.1", "v0.2")
GENERATOR_PROVIDER = "openrouter"
GENERATOR_BASE_URL = "https://openrouter.ai/api/v1"
GENERATOR_MODEL = "tencent/hy3"
GENERATOR_TEMPERATURE = 0.0
GENERATOR_TIMEOUT_SECONDS = 120.0
JUDGE_TIMEOUT_SECONDS = 120.0
SEMANTIC_REPEATS_PER_PLAN = 1
PLANNED_GENERATIONS = 24
PLANNED_SEMANTIC_EVALUATIONS = 24

INTENTS: tuple[str, ...] = (
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
)
INTENT_CODES: dict[str, str] = {
    "elicitation": "ELI",
    "scaffolding": "SCA",
    "explanation": "EXP",
    "corrective_feedback": "COR",
    "supportive_feedback": "SUP",
    "extension": "EXT",
}
CHALLENGE_BY_INTENT: dict[str, str] = {
    "elicitation": "cross_domain",
    "scaffolding": "hard_adversarial",
    "explanation": "cross_domain",
    "corrective_feedback": "hard_adversarial",
    "supportive_feedback": "cross_domain",
    "extension": "hard_adversarial",
}
CHALLENGE_CODE = {"cross_domain": "CHX", "hard_adversarial": "CHA"}

DEVELOPMENT_DATASETS: tuple[Path, ...] = (
    REPO_ROOT / "cases" / "pilot" / "blocks" / "block_a_controlled_contrast.jsonl",
    REPO_ROOT
    / "cases"
    / "pilot"
    / "blocks"
    / "block_b_cross_domain_generalization.jsonl",
    REPO_ROOT / "cases" / "pilot" / "blocks" / "block_c_hard_adversarial.jsonl",
)

# Full frozen dimension IDs in the same order as D1..D6.
DIMENSION_IDS: tuple[str, ...] = (
    "pedagogical_intent_fidelity",
    "content_faithfulness_boundary",
    "learner_state_compatibility",
    "intent_specific_instructional_adequacy",
    "delivery_necessity_sparsity",
    "delivery_pedagogy_alignment",
)
LABEL_TO_DIM = dict(zip(DIMENSION_LABELS, DIMENSION_IDS))


class ReleaseSanityError(RuntimeError):
    """Release-sanity preflight or execution error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _round4(value: float | int | None) -> float | None:
    return None if value is None else round(float(value), 4)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    path.write_text(text, encoding="utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReleaseSanityError(
                f"{path}:{line_number}: invalid JSON: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ReleaseSanityError(f"{path}:{line_number}: record must be an object")
        records.append(value)
    return records


def expected_case_ids() -> set[str]:
    ids: set[str] = set()
    for intent in INTENTS:
        code = INTENT_CODES[intent]
        ids.add(f"RS-V1-{code}-STD-01")
        ids.add(f"RS-V1-{code}-{CHALLENGE_CODE[CHALLENGE_BY_INTENT[intent]]}-01")
    return ids


def _normalize_for_duplicate_check(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def _comparison_text(record: dict[str, Any]) -> str:
    input_doc = record["input"]
    fields = (
        input_doc["instructional_content"]["content_anchor"],
        input_doc["pedagogical_context"]["scenario"],
        input_doc["pedagogical_context"].get("learner_utterance", ""),
    )
    return "".join(_normalize_for_duplicate_check(value) for value in fields)


def _comparison_fields(record: dict[str, Any]) -> tuple[str, ...]:
    input_doc = record["input"]
    values = (
        input_doc["instructional_content"]["content_anchor"],
        input_doc["pedagogical_context"]["scenario"],
        input_doc["pedagogical_context"].get("learner_utterance", ""),
    )
    return tuple(_normalize_for_duplicate_check(value) for value in values if value)


def _ngrams(text: str, n: int = 5) -> set[str]:
    if len(text) < n:
        return {text} if text else set()
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return 0.0 if not union else len(left & right) / len(union)


def duplicate_screen(
    release_records: Sequence[dict[str, Any]],
    comparison_records: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Screen exact duplicates and obvious lexical near-copies.

    The screen is intentionally conservative and mechanical. Human semantic
    near-copy QC remains recorded separately in ``QC_SUMMARY.md``.
    """

    failures: list[dict[str, Any]] = []
    closest: list[dict[str, Any]] = []
    for release in release_records:
        release_text = _comparison_text(release)
        release_fields = set(_comparison_fields(release))
        release_grams = _ngrams(release_text)
        best: dict[str, Any] | None = None
        for previous in comparison_records:
            previous_text = _comparison_text(previous)
            previous_fields = set(_comparison_fields(previous))
            ratio = SequenceMatcher(
                None, release_text, previous_text, autojunk=False
            ).ratio()
            jaccard = _jaccard(release_grams, _ngrams(previous_text))
            exact_field = bool(release_fields & previous_fields)
            exact_input = canonical_sha256(release["input"]) == canonical_sha256(
                previous["input"]
            )
            item = {
                "release_case_id": release["case_id"],
                "comparison_case_id": previous["case_id"],
                "sequence_ratio": _round4(ratio),
                "char_5gram_jaccard": _round4(jaccard),
                "exact_normalized_field": exact_field,
                "exact_input": exact_input,
            }
            if best is None or ratio > best["sequence_ratio"]:
                best = item
            if exact_input or exact_field or ratio >= 0.70 or jaccard >= 0.50:
                failures.append(item)
        if best is not None:
            closest.append(best)

    return {
        "passed": not failures,
        "algorithm": {
            "normalization": "Unicode NFKC, case-fold, retain alphanumeric characters",
            "exact_checks": ["canonical input", "normalized full text field"],
            "near_copy_thresholds": {
                "sequence_matcher_ratio_gte": 0.70,
                "character_5gram_jaccard_gte": 0.50,
            },
        },
        "failure_count": len(failures),
        "failures": failures,
        "closest_development_match_per_release_case": sorted(
            closest, key=lambda item: item["release_case_id"]
        ),
    }


def validate_release_sanity_dataset(
    dataset_path: str | Path = DATASET_PATH,
    *,
    check_manifest: bool = True,
) -> dict[str, Any]:
    dataset_path = Path(dataset_path)
    records = load_jsonl(dataset_path)
    errors: list[str] = []

    ids = [record.get("case_id") for record in records]
    if len(records) != 12:
        errors.append(f"expected exactly 12 records, got {len(records)}")
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate case IDs: {duplicates}")
    expected = expected_case_ids()
    actual = {case_id for case_id in ids if isinstance(case_id, str)}
    if actual != expected:
        errors.append(
            f"case ID set mismatch; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )

    intent_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    block_counts: Counter[str] = Counter()
    challenge_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        case_id = record.get("case_id", f"line-{index}")
        input_doc = record.get("input")
        if not isinstance(input_doc, dict):
            errors.append(f"{case_id}: input must be an object")
            continue
        schema_errors = iter_input_errors(input_doc)
        if schema_errors:
            errors.extend(
                f"{case_id}: input schema {error.json_path}: {error.message}"
                for error in schema_errors
            )
        try:
            TeachIntentInput.model_validate(input_doc)
        except ValidationError as exc:
            errors.append(f"{case_id}: input Pydantic validation failed: {exc}")

        intent = ((input_doc.get("pedagogical_intent") or {}).get("primary"))
        role = (record.get("tags") or {}).get("release_sanity_role")
        challenge = (record.get("tags") or {}).get("challenge_type")
        block = record.get("block")
        intent_counts[intent] += 1
        role_counts[role] += 1
        block_counts[block] += 1
        language_counts[input_doc.get("output_language")] += 1
        if role == "challenging":
            challenge_counts[challenge] += 1

        expected_block = "standard" if role == "standard" else challenge
        if block != expected_block:
            errors.append(
                f"{case_id}: block={block!r} does not match role/challenge metadata"
            )
        if role == "standard" and challenge != "standard":
            errors.append(f"{case_id}: standard case must use challenge_type=standard")
        if role == "challenging" and challenge != CHALLENGE_BY_INTENT.get(intent):
            errors.append(
                f"{case_id}: challenging type must be "
                f"{CHALLENGE_BY_INTENT.get(intent)!r} for intent {intent!r}"
            )

    expected_intents = {intent: 2 for intent in INTENTS}
    if dict(intent_counts) != expected_intents:
        errors.append(f"intent balance mismatch: {dict(intent_counts)}")
    if dict(role_counts) != {"standard": 6, "challenging": 6}:
        errors.append(f"role balance mismatch: {dict(role_counts)}")
    if dict(block_counts) != {
        "standard": 6,
        "cross_domain": 3,
        "hard_adversarial": 3,
    }:
        errors.append(f"block balance mismatch: {dict(block_counts)}")
    if dict(challenge_counts) != {"cross_domain": 3, "hard_adversarial": 3}:
        errors.append(f"challenging balance mismatch: {dict(challenge_counts)}")
    if dict(language_counts) != {"zh-CN": 12}:
        errors.append(f"output-language mismatch: {dict(language_counts)}")

    development_records: list[dict[str, Any]] = []
    for path in DEVELOPMENT_DATASETS:
        development_records.extend(load_jsonl(path))
    duplicate_report = duplicate_screen(records, development_records)
    if not duplicate_report["passed"]:
        errors.append(
            f"duplicate/near-copy screen failed for "
            f"{duplicate_report['failure_count']} comparison(s)"
        )

    file_digest = sha256_file(dataset_path)
    canonical_digest = canonical_sha256(records)
    input_hashes = {
        record["case_id"]: canonical_sha256(record["input"]) for record in records
    }

    if check_manifest and DATASET_MANIFEST_PATH.is_file():
        manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_file = manifest.get("dataset_sha256")
        expected_canonical = manifest.get("canonical_dataset_sha256")
        if expected_file and expected_file != file_digest:
            errors.append(
                f"manifest dataset_sha256 mismatch: expected {expected_file}, got {file_digest}"
            )
        if expected_canonical and expected_canonical != canonical_digest:
            errors.append(
                "manifest canonical_dataset_sha256 mismatch: "
                f"expected {expected_canonical}, got {canonical_digest}"
            )

    return {
        "valid": not errors,
        "errors": errors,
        "dataset_version": DATASET_VERSION,
        "dataset_path": str(dataset_path.relative_to(REPO_ROOT)),
        "dataset_sha256": file_digest,
        "canonical_dataset_sha256": canonical_digest,
        "case_count": len(records),
        "unique_case_ids": len(actual),
        "case_ids": sorted(actual),
        "input_sha256_by_case": input_hashes,
        "intent_counts": dict(sorted(intent_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "block_counts": dict(sorted(block_counts.items())),
        "challenging_type_counts": dict(sorted(challenge_counts.items())),
        "output_language_counts": dict(sorted(language_counts.items())),
        "development_population_case_count": len(development_records),
        "development_dataset_sha256": {
            str(path.relative_to(REPO_ROOT)): sha256_file(path)
            for path in DEVELOPMENT_DATASETS
        },
        "duplicate_screen": duplicate_report,
    }


def generation_schedule(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic 24-call schedule with balanced condition-first ordering."""

    schedule: list[dict[str, Any]] = []
    for index, record in enumerate(sorted(records, key=lambda row: row["case_id"])):
        order = PROMPT_VERSIONS if index % 2 == 0 else tuple(reversed(PROMPT_VERSIONS))
        for position, prompt_version in enumerate(order, start=1):
            schedule.append(
                {
                    "call_index": len(schedule) + 1,
                    "case_id": record["case_id"],
                    "intent": record["input"]["pedagogical_intent"]["primary"],
                    "block": record["block"],
                    "prompt_version": prompt_version,
                    "within_case_position": position,
                }
            )
    return schedule


def _generation_validation(exc: Exception | None) -> dict[str, Any]:
    stages: dict[str, Any] = {
        "input_json_schema": "not_reached",
        "input_pydantic": "not_reached",
        "response_parsing": "not_reached",
        "speech_plan_json_schema": "not_reached",
        "speech_plan_pydantic": "not_reached",
    }
    if exc is None:
        for stage in stages:
            stages[stage] = "passed"
    elif isinstance(exc, InputContractError):
        if exc.layer == "jsonschema":
            stages["input_json_schema"] = {
                "status": "failed",
                "errors": exc.error_summary,
            }
        else:
            stages["input_json_schema"] = "passed"
            stages["input_pydantic"] = {
                "status": "failed",
                "errors": exc.error_summary,
            }
    elif isinstance(exc, Hy3APIError):
        stages["input_json_schema"] = "passed"
        stages["input_pydantic"] = "passed"
    elif isinstance(exc, ResponseParsingError):
        stages.update(
            input_json_schema="passed",
            input_pydantic="passed",
            response_parsing={"status": "failed", "error": str(exc)},
        )
    elif isinstance(exc, SpeechPlanStructuralError):
        stages.update(
            input_json_schema="passed",
            input_pydantic="passed",
            response_parsing="passed",
            speech_plan_json_schema={
                "status": "failed",
                "errors": exc.error_summary,
            },
        )
    elif isinstance(exc, SpeechPlanSemanticError):
        stages.update(
            input_json_schema="passed",
            input_pydantic="passed",
            response_parsing="passed",
            speech_plan_json_schema="passed",
            speech_plan_pydantic={"status": "failed", "error": exc.error_text},
        )
    stages["outcome"] = "success" if exc is None else type(exc).__name__
    return stages


def _extract_generation_payload(
    result: Any, exc: Exception | None
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    if result is not None:
        return result.raw_response, result.plan_doc, None
    if isinstance(exc, ResponseParsingError):
        return exc.raw_text, None, None
    if isinstance(exc, (SpeechPlanStructuralError, SpeechPlanSemanticError)):
        return exc.raw_text, exc.plan_doc, None
    if isinstance(exc, Hy3APIError):
        return None, None, exc.response_text
    return None, None, None


def _generation_case_dir(
    run_dir: Path, case_id: str, prompt_version: str
) -> Path:
    return run_dir / "generation" / case_id / prompt_version.replace(".", "_")


def execute_generations(
    records: Sequence[dict[str, Any]],
    client: Any,
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    """Execute exactly one Generator call per case-condition and persist it."""

    run_dir = Path(run_dir)
    by_id = {record["case_id"]: record for record in records}
    schedule = generation_schedule(records)
    _write_json(run_dir / "generation_schedule.json", schedule)
    outputs: list[dict[str, Any]] = []

    for item in schedule:
        row = by_id[item["case_id"]]
        input_doc = row["input"]
        version = item["prompt_version"]
        prompt = build_speech_plan_prompt_for_version(input_doc, version=version)
        started_at = _utc_now()
        started_monotonic = time.monotonic()
        result = None
        exc: Exception | None = None
        try:
            result = generate_speech_plan(
                input_doc, client, prompt_version=version
            )
        except Exception as caught:  # preserve one-call failures; continue schedule
            exc = caught
        completed_at = _utc_now()
        duration = time.monotonic() - started_monotonic
        raw_response, parsed, http_response = _extract_generation_payload(result, exc)
        validation = _generation_validation(exc)
        outcome = "success" if exc is None else type(exc).__name__
        reported_model = result.reported_model if result is not None else None
        finish_reason = None

        case_dir = _generation_case_dir(run_dir, row["case_id"], version)
        _write_json(case_dir / "input.json", input_doc)
        _write_json(
            case_dir / "prompt.json",
            {"prompt_version": version, "system": prompt.system, "user": prompt.user},
        )
        if raw_response is not None:
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "raw_response.txt").write_text(raw_response, encoding="utf-8")
        if parsed is not None:
            _write_json(case_dir / "parsed.json", parsed)
        if http_response is not None:
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "http_response.txt").write_text(
                http_response, encoding="utf-8"
            )
        _write_json(case_dir / "validation.json", validation)
        if exc is not None:
            _write_json(
                case_dir / "error.json",
                {
                    "exception_class": type(exc).__name__,
                    "summary": str(exc),
                    "generator_error": isinstance(exc, GeneratorError),
                },
            )

        record = {
            **item,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": round(duration, 3),
            "outcome": outcome,
            "valid_plan": exc is None,
            "raw_response_available": raw_response is not None,
            "parsed_plan_available": parsed is not None,
            "requested_model": getattr(client, "model", GENERATOR_MODEL),
            "reported_model": reported_model,
            "finish_reason": finish_reason,
            "prompt_system_sha256": hashlib.sha256(
                prompt.system.encode("utf-8")
            ).hexdigest(),
            "prompt_user_sha256": hashlib.sha256(
                prompt.user.encode("utf-8")
            ).hexdigest(),
            "raw_response": raw_response,
            "parsed_plan": parsed,
            "validation": validation,
            "artifact_path": str(case_dir.relative_to(run_dir)),
        }
        _write_json(case_dir / "metadata.json", {k: v for k, v in record.items() if k not in {"raw_response", "parsed_plan", "validation"}})
        outputs.append(record)
    return outputs


@dataclass
class CapturingJudge:
    """Per-attempt wrapper preserving raw Judge completions and HTTP errors."""

    inner: JudgeCompleter
    completion: Any = None
    error_response_text: str | None = None

    @property
    def provider(self) -> str:
        return self.inner.provider

    @property
    def model(self) -> str:
        return self.inner.model

    @property
    def structured_output_enabled(self) -> bool:
        return self.inner.structured_output_enabled

    def reset(self) -> None:
        self.completion = None
        self.error_response_text = None

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        try:
            self.completion = self.inner.complete(
                system, user, temperature=temperature
            )
            return self.completion
        except Exception as exc:
            self.error_response_text = getattr(exc, "response_text", None)
            raise


def _canonical_case(
    row: dict[str, Any], generation: dict[str, Any], run_dir: Path
) -> CanonicalCase:
    return CanonicalCase(
        case_id=row["case_id"],
        block=row["block"],
        block_name=row["block"],
        intent=row["input"]["pedagogical_intent"]["primary"],
        source_run_id=run_dir.name,
        source_path=str(
            _generation_case_dir(
                run_dir, row["case_id"], generation["prompt_version"]
            )
        ),
        input_doc=row["input"],
        raw_response=generation["raw_response"],
        prompt_version=generation["prompt_version"],
        generator_version=GENERATOR_VERSION,
        requested_model=generation["requested_model"],
        reported_model=generation["reported_model"],
        generation_outcome=generation["outcome"],
    )


def acquire_one_semantic_artifact(
    case: CanonicalCase,
    judge: JudgeCompleter,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Acquire one legal Evaluator artifact using the frozen attempt policy."""

    capturing = CapturingJudge(judge)
    judge_config = build_frozen_judge_config(capturing)
    attempts: list[dict[str, Any]] = []
    successful_index: int | None = None
    final_artifact: dict[str, Any] | None = None
    stopped_reason = "exhausted_max_attempts"

    for attempt_index in range(1, MAX_ATTEMPTS_PER_SEMANTIC_REPEAT + 1):
        capturing.reset()
        started_at = _utc_now()
        result = evaluate_attempt(
            case, 1, attempt_index, capturing, judge_config
        )
        completed_at = _utc_now()
        attempt = build_attempt_record(
            case, 1, attempt_index, result, started_at, completed_at
        )
        attempt_dict = attempt.to_dict()
        attempt_dict["judge_raw_response"] = (
            capturing.completion.content if capturing.completion is not None else None
        )
        attempt_dict["judge_finish_reason"] = (
            capturing.completion.finish_reason
            if capturing.completion is not None
            else None
        )
        attempt_dict["judge_http_response"] = capturing.error_response_text
        attempts.append(attempt_dict)

        if attempt.failure_type is None:
            successful_index = attempt_index
            final_artifact = attempt.artifact
            stopped_reason = "valid_artifact"
            break
        if not attempt.retryable:
            stopped_reason = "non_retryable_failure"
            break
        if attempt_index < MAX_ATTEMPTS_PER_SEMANTIC_REPEAT:
            delay = backoff_seconds(attempt.failure_type, attempt_index)
            if delay:
                sleep_fn(delay)

    return {
        "case_id": case.case_id,
        "block": case.block,
        "intent": case.intent,
        "prompt_version": case.prompt_version,
        "semantic_repeat_index": 1,
        "semantic_repeat_success": successful_index is not None,
        "successful_attempt_index": successful_index,
        "attempt_count": len(attempts),
        "attempt_failure_types": [
            attempt["failure_type"]
            for attempt in attempts
            if attempt["failure_type"] is not None
        ],
        "stopped_reason": stopped_reason,
        "final_artifact": final_artifact,
        "attempts": attempts,
    }


def execute_evaluations(
    records: Sequence[dict[str, Any]],
    generations: Sequence[dict[str, Any]],
    judge: JudgeCompleter,
    run_dir: str | Path,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Evaluate each generated raw response once semantically (up to 3 attempts)."""

    run_dir = Path(run_dir)
    rows = {row["case_id"]: row for row in records}
    evaluations: list[dict[str, Any]] = []
    for generation in generations:
        row = rows[generation["case_id"]]
        if generation["raw_response"] is None:
            evaluations.append(
                {
                    "case_id": row["case_id"],
                    "block": row["block"],
                    "intent": row["input"]["pedagogical_intent"]["primary"],
                    "prompt_version": generation["prompt_version"],
                    "semantic_repeat_index": 1,
                    "semantic_repeat_success": False,
                    "successful_attempt_index": None,
                    "attempt_count": 0,
                    "attempt_failure_types": ["generation_no_raw_response"],
                    "stopped_reason": "generation_no_raw_response",
                    "final_artifact": None,
                    "attempts": [],
                }
            )
            continue
        case = _canonical_case(row, generation, run_dir)
        evaluations.append(
            acquire_one_semantic_artifact(case, judge, sleep_fn=sleep_fn)
        )
    _write_jsonl(run_dir / "evaluations.jsonl", evaluations)
    return evaluations


def _artifact_scores(evaluation: dict[str, Any]) -> dict[str, int] | None:
    artifact = evaluation.get("final_artifact")
    if not evaluation.get("semantic_repeat_success") or not artifact:
        return None
    return {
        label: artifact["scores"][dimension]["score"]
        for label, dimension in LABEL_TO_DIM.items()
    }


def _mean(values: Sequence[float]) -> float | None:
    return None if not values else statistics.mean(values)


def _condition_score_summary(
    evaluations: Sequence[dict[str, Any]], prompt_version: str
) -> dict[str, Any]:
    score_maps = [
        scores
        for evaluation in evaluations
        if evaluation["prompt_version"] == prompt_version
        and (scores := _artifact_scores(evaluation)) is not None
    ]
    return {
        "n_available": len(score_maps),
        "means": {
            label: _round4(_mean([scores[label] for scores in score_maps]))
            for label in DIMENSION_LABELS
        },
    }


def _paired_summary(
    evaluations: Sequence[dict[str, Any]], *, intent: str | None = None
) -> dict[str, Any]:
    by_case: dict[str, dict[str, dict[str, int]]] = {}
    for evaluation in evaluations:
        if intent is not None and evaluation["intent"] != intent:
            continue
        scores = _artifact_scores(evaluation)
        if scores is not None:
            by_case.setdefault(evaluation["case_id"], {})[
                evaluation["prompt_version"]
            ] = scores
    paired = {
        case_id: conditions
        for case_id, conditions in by_case.items()
        if set(PROMPT_VERSIONS).issubset(conditions)
    }
    dimensions: dict[str, Any] = {}
    for label in DIMENSION_LABELS:
        deltas = [
            conditions["v0.2"][label] - conditions["v0.1"][label]
            for conditions in paired.values()
        ]
        dimensions[label] = {
            "n": len(deltas),
            "mean_delta": _round4(_mean(deltas)),
            "improved": sum(delta > 0 for delta in deltas),
            "tied": sum(delta == 0 for delta in deltas),
            "worsened": sum(delta < 0 for delta in deltas),
        }
    return {
        "pair_eligible_count": len(paired),
        "pair_eligible_case_ids": sorted(paired),
        "dimensions": dimensions,
    }


def _atomic_delivery_controls(plan: dict[str, Any]) -> list[str]:
    controls: list[str] = []
    delivery = plan.get("delivery_plan") or {}
    global_plan = delivery.get("global") or {}
    for name in ("attitudinal_tone", "emotion"):
        if name in global_plan:
            controls.append(f"global.{name}")
    for name in (global_plan.get("prosody") or {}):
        controls.append(f"global.prosody.{name}")
    for override in delivery.get("segment_overrides") or []:
        for name in ("attitudinal_tone", "emotion"):
            if name in override:
                controls.append(f"segment.{name}")
        for name in (override.get("prosody") or {}):
            controls.append(f"segment.prosody.{name}")
        if "contour_shape" in override:
            controls.append("segment.contour_shape")
        for _target in override.get("prominence_targets") or []:
            controls.append("segment.prominence_target")
        if "boundary_after" in override:
            controls.append("segment.boundary_after")
    return controls


def summarize_delivery_behavior(
    generations: Sequence[dict[str, Any]], prompt_version: str
) -> dict[str, Any]:
    selected = [
        generation
        for generation in generations
        if generation["prompt_version"] == prompt_version
        and generation["valid_plan"]
        and generation["parsed_plan"] is not None
    ]
    empty: list[str] = []
    non_empty: list[str] = []
    controls_by_case: dict[str, int] = {}
    control_types: Counter[str] = Counter()
    for generation in selected:
        plan = generation["parsed_plan"]
        if plan.get("delivery_plan"):
            non_empty.append(generation["case_id"])
            controls = _atomic_delivery_controls(plan)
            controls_by_case[generation["case_id"]] = len(controls)
            control_types.update(controls)
        else:
            empty.append(generation["case_id"])
    counts = list(controls_by_case.values())
    return {
        "prompt_version": prompt_version,
        "valid_plan_count": len(selected),
        "empty_count": len(empty),
        "non_empty_count": len(non_empty),
        "empty_case_ids": sorted(empty),
        "non_empty_case_ids": sorted(non_empty),
        "controls_per_non_empty_plan": dict(sorted(controls_by_case.items())),
        "mean_controls_per_non_empty_plan": _round4(_mean(counts)),
        "control_count_range": (
            [min(counts), max(counts)] if counts else None
        ),
        "control_type_distribution": dict(sorted(control_types.items())),
        "obvious_all_empty_collapse": bool(selected) and not non_empty,
        "obvious_all_non_empty_over_control": bool(selected) and not empty,
        "stacking_review": (
            "Inspect controls_per_non_empty_plan and control_type_distribution; "
            "no automatic stacking threshold is imposed."
        ),
    }


def analyze_release_sanity(
    records: Sequence[dict[str, Any]],
    generations: Sequence[dict[str, Any]],
    evaluations: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    generation_by_condition: dict[str, Any] = {}
    evaluation_by_condition: dict[str, Any] = {}
    critical: dict[str, Any] = {}

    for version in PROMPT_VERSIONS:
        condition_generations = [
            generation
            for generation in generations
            if generation["prompt_version"] == version
        ]
        condition_evaluations = [
            evaluation
            for evaluation in evaluations
            if evaluation["prompt_version"] == version
        ]
        generation_by_condition[version] = {
            "planned": 12,
            "valid_plan_count": sum(
                generation["valid_plan"] for generation in condition_generations
            ),
            "failure_count": sum(
                not generation["valid_plan"] for generation in condition_generations
            ),
            "outcome_counts": dict(
                sorted(
                    Counter(
                        generation["outcome"]
                        for generation in condition_generations
                    ).items()
                )
            ),
            "reported_models": sorted(
                {
                    generation["reported_model"]
                    for generation in condition_generations
                    if generation["reported_model"]
                }
            ),
        }
        evaluation_by_condition[version] = {
            "planned_semantic_evaluations": 12,
            "successful_artifacts": sum(
                evaluation["semantic_repeat_success"]
                for evaluation in condition_evaluations
            ),
            "unavailable": sum(
                not evaluation["semantic_repeat_success"]
                for evaluation in condition_evaluations
            ),
            "physical_attempts": sum(
                evaluation["attempt_count"] for evaluation in condition_evaluations
            ),
            "attempt_failure_types": dict(
                sorted(
                    Counter(
                        failure
                        for evaluation in condition_evaluations
                        for failure in evaluation["attempt_failure_types"]
                    ).items()
                )
            ),
        }
        flag_counts: Counter[str] = Counter()
        flag_cases: list[dict[str, str]] = []
        for evaluation in condition_evaluations:
            artifact = evaluation.get("final_artifact")
            if not artifact:
                continue
            for flag in artifact.get("critical_flags") or []:
                flag_name = flag["flag"]
                flag_counts[flag_name] += 1
                flag_cases.append(
                    {"case_id": evaluation["case_id"], "flag": flag_name}
                )
        critical[version] = {
            "total_flags": sum(flag_counts.values()),
            "flag_counts": dict(sorted(flag_counts.items())),
            "flagged_cases": flag_cases,
        }

    per_intent: dict[str, Any] = {}
    for intent in INTENTS:
        intent_evaluations = [
            evaluation for evaluation in evaluations if evaluation["intent"] == intent
        ]
        per_intent[intent] = {
            version: _condition_score_summary(intent_evaluations, version)
            for version in PROMPT_VERSIONS
        }
        per_intent[intent]["paired"] = _paired_summary(
            intent_evaluations, intent=intent
        )

    paired = _paired_summary(evaluations)
    candidate_regressions: list[dict[str, Any]] = []
    evaluation_lookup = {
        (evaluation["case_id"], evaluation["prompt_version"]): evaluation
        for evaluation in evaluations
    }
    for case_id in paired["pair_eligible_case_ids"]:
        base = _artifact_scores(evaluation_lookup[(case_id, "v0.1")])
        candidate = _artifact_scores(evaluation_lookup[(case_id, "v0.2")])
        assert base is not None and candidate is not None
        worsened = {
            label: candidate[label] - base[label]
            for label in DIMENSION_LABELS
            if candidate[label] < base[label]
        }
        if worsened:
            candidate_regressions.append(
                {"case_id": case_id, "worsened_dimensions": worsened}
            )

    delivery = {
        version: summarize_delivery_behavior(generations, version)
        for version in PROMPT_VERSIONS
    }
    concerns = {
        "generation_failures": [
            {
                "case_id": generation["case_id"],
                "prompt_version": generation["prompt_version"],
                "outcome": generation["outcome"],
            }
            for generation in generations
            if not generation["valid_plan"]
        ],
        "evaluation_unavailable": [
            {
                "case_id": evaluation["case_id"],
                "prompt_version": evaluation["prompt_version"],
                "failure_types": evaluation["attempt_failure_types"],
            }
            for evaluation in evaluations
            if not evaluation["semantic_repeat_success"]
        ],
        "candidate_critical_flags": critical["v0.2"]["flagged_cases"],
        "candidate_case_level_regressions": candidate_regressions,
    }

    return {
        "evidence_label": EVIDENCE_LABEL,
        "is_formal_confirmatory_evidence": False,
        "formal_pass_fail": None,
        "dataset": {
            "version": DATASET_VERSION,
            "case_count": len(records),
            "intents": 6,
            "cases_per_intent": 2,
        },
        "generation": generation_by_condition,
        "evaluation": evaluation_by_condition,
        "dimension_means": {
            version: _condition_score_summary(evaluations, version)
            for version in PROMPT_VERSIONS
        },
        "paired_comparison": paired,
        "per_intent": per_intent,
        "critical_flags": critical,
        "delivery_behavior": delivery,
        "concerning_cases": concerns,
        "interpretation_note": (
            "Descriptive release sanity only: one generation and one successful "
            "semantic Judge artifact per plan. No confidence interval, hypothesis "
            "test, p-value, statistical significance claim, or global PASS/FAIL."
        ),
    }


def _markdown_table(summary: dict[str, Any]) -> str:
    means = summary["dimension_means"]
    paired = summary["paired_comparison"]["dimensions"]
    lines = [
        "| Dimension | v0.1 mean | v0.2 mean | Paired mean Δ | Improved | Tied | Worsened |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in DIMENSION_LABELS:
        stats = paired[label]
        lines.append(
            f"| {label} | {means['v0.1']['means'][label]} | "
            f"{means['v0.2']['means'][label]} | {stats['mean_delta']} | "
            f"{stats['improved']} | {stats['tied']} | {stats['worsened']} |"
        )
    return "\n".join(lines)


def render_report(summary: dict[str, Any], run_id: str) -> str:
    generation = summary["generation"]
    evaluation = summary["evaluation"]
    delivery = summary["delivery_behavior"]
    flags = summary["critical_flags"]
    concerns = summary["concerning_cases"]
    return f"""# TeachIntent Release Sanity Report

**Evidence label:** {EVIDENCE_LABEL}  
**Run ID:** `{run_id}`  
**Formal PASS/FAIL:** none

## Scope

This is a lightweight unseen release-sanity comparison of frozen Prompt v0.1
and frozen Prompt v0.2 on 12 newly authored zh-CN cases. It is descriptive and
must not be presented as formal confirmatory evidence.

## Generation

- v0.1 valid plans: {generation['v0.1']['valid_plan_count']}/12
- v0.2 valid plans: {generation['v0.2']['valid_plan_count']}/12
- Exactly one generation call was scheduled per case-condition; failures were not regenerated.

## Evaluation availability

- v0.1 successful artifacts: {evaluation['v0.1']['successful_artifacts']}/12; physical attempts: {evaluation['v0.1']['physical_attempts']}
- v0.2 successful artifacts: {evaluation['v0.2']['successful_artifacts']}/12; physical attempts: {evaluation['v0.2']['physical_attempts']}
- Pair-eligible cases: {summary['paired_comparison']['pair_eligible_count']}/12
- Each plan had one semantic evaluation target and at most three acquisition attempts.

## Descriptive D1-D6 comparison

{_markdown_table(summary)}

## Delivery behavior

- v0.1: empty {delivery['v0.1']['empty_count']} / non-empty {delivery['v0.1']['non_empty_count']}
- v0.2: empty {delivery['v0.2']['empty_count']} / non-empty {delivery['v0.2']['non_empty_count']}
- v0.1 controls per non-empty plan: `{json.dumps(delivery['v0.1']['controls_per_non_empty_plan'], ensure_ascii=False)}`
- v0.2 controls per non-empty plan: `{json.dumps(delivery['v0.2']['controls_per_non_empty_plan'], ensure_ascii=False)}`
- v0.1 control types: `{json.dumps(delivery['v0.1']['control_type_distribution'], ensure_ascii=False)}`
- v0.2 control types: `{json.dumps(delivery['v0.2']['control_type_distribution'], ensure_ascii=False)}`
- v0.2 obvious all-empty collapse: {str(delivery['v0.2']['obvious_all_empty_collapse']).lower()}
- v0.2 obvious all-non-empty over-control: {str(delivery['v0.2']['obvious_all_non_empty_over_control']).lower()}

No automatic control-stacking threshold is imposed. The per-plan counts and
types above are the locked inspection surface.

## Critical flags

- v0.1: {flags['v0.1']['total_flags']} — `{json.dumps(flags['v0.1']['flag_counts'], ensure_ascii=False)}`
- v0.2: {flags['v0.2']['total_flags']} — `{json.dumps(flags['v0.2']['flag_counts'], ensure_ascii=False)}`

## Concerning-case inventory

- Generation failures: `{json.dumps(concerns['generation_failures'], ensure_ascii=False)}`
- Evaluation unavailable: `{json.dumps(concerns['evaluation_unavailable'], ensure_ascii=False)}`
- Candidate critical flags: `{json.dumps(concerns['candidate_critical_flags'], ensure_ascii=False)}`
- Candidate case-level D1-D6 regressions: `{json.dumps(concerns['candidate_case_level_regressions'], ensure_ascii=False)}`

## Interpretation boundary

{summary['interpretation_note']}
"""


def _write_paired_csv(
    run_dir: Path, evaluations: Sequence[dict[str, Any]]
) -> None:
    lookup = {
        (evaluation["case_id"], evaluation["prompt_version"]): evaluation
        for evaluation in evaluations
    }
    case_ids = sorted({evaluation["case_id"] for evaluation in evaluations})
    path = run_dir / "paired_scores.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["case_id", "pair_eligible"]
        for label in DIMENSION_LABELS:
            fieldnames.extend([f"v0_1_{label}", f"v0_2_{label}", f"delta_{label}"])
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for case_id in case_ids:
            base = _artifact_scores(lookup[(case_id, "v0.1")])
            candidate = _artifact_scores(lookup[(case_id, "v0.2")])
            row: dict[str, Any] = {
                "case_id": case_id,
                "pair_eligible": base is not None and candidate is not None,
            }
            for label in DIMENSION_LABELS:
                row[f"v0_1_{label}"] = None if base is None else base[label]
                row[f"v0_2_{label}"] = None if candidate is None else candidate[label]
                row[f"delta_{label}"] = (
                    None
                    if base is None or candidate is None
                    else candidate[label] - base[label]
                )
            writer.writerow(row)


def _git_provenance() -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    return {
        "git_commit": run("git", "rev-parse", "HEAD"),
        "git_branch": run("git", "branch", "--show-current"),
        "working_tree_status_at_start": run("git", "status", "--short"),
    }


def run_release_sanity(
    generator_client: Any,
    judge: JudgeCompleter,
    *,
    dataset_path: str | Path = DATASET_PATH,
    output_dir: str | Path | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[Path, dict[str, Any]]:
    """Validate, execute 24 generations + 24 semantic acquisitions, and report."""

    validation = validate_release_sanity_dataset(dataset_path)
    if not validation["valid"]:
        raise ReleaseSanityError(
            "dataset validation failed: " + "; ".join(validation["errors"])
        )
    if getattr(generator_client, "model", None) != GENERATOR_MODEL:
        raise ReleaseSanityError(
            f"generator model must be {GENERATOR_MODEL!r}, got "
            f"{getattr(generator_client, 'model', None)!r}"
        )
    if judge.provider != FROZEN_JUDGE_PROVIDER or judge.model != FROZEN_JUDGE_MODEL_REQUESTED:
        raise ReleaseSanityError("Judge backend does not match the frozen condition")

    run_id = _utc_run_id()
    run_dir = Path(output_dir) if output_dir is not None else RESULTS_ROOT / run_id
    if run_dir.exists():
        raise ReleaseSanityError(f"refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    started_at = _utc_now()

    dataset_copy_dir = run_dir / "dataset"
    dataset_copy_dir.mkdir()
    shutil.copyfile(dataset_path, dataset_copy_dir / Path(dataset_path).name)
    if DATASET_MANIFEST_PATH.is_file():
        shutil.copyfile(DATASET_MANIFEST_PATH, dataset_copy_dir / "manifest.json")
    if DATASET_QC_PATH.is_file():
        shutil.copyfile(DATASET_QC_PATH, dataset_copy_dir / "QC_SUMMARY.md")
    _write_json(run_dir / "dataset_validation.json", validation)

    records = load_jsonl(dataset_path)
    generations = execute_generations(records, generator_client, run_dir)
    evaluations = execute_evaluations(
        records, generations, judge, run_dir, sleep_fn=sleep_fn
    )
    summary = analyze_release_sanity(records, generations, evaluations)
    summary.update({"run_id": run_id, "started_at": started_at, "completed_at": _utc_now()})
    _write_json(run_dir / "summary.json", summary)
    _write_paired_csv(run_dir, evaluations)
    (run_dir / "REPORT.md").write_text(
        render_report(summary, run_id), encoding="utf-8"
    )

    provenance = _git_provenance()
    manifest = {
        "run_id": run_id,
        "evidence_label": EVIDENCE_LABEL,
        "is_formal_confirmatory_evidence": False,
        "started_at": started_at,
        "completed_at": summary["completed_at"],
        "dataset": validation,
        "generation_condition": {
            "provider": GENERATOR_PROVIDER,
            "base_url": GENERATOR_BASE_URL,
            "requested_model": GENERATOR_MODEL,
            "temperature": GENERATOR_TEMPERATURE,
            "structured_output_enabled": False,
            "generator_retry_enabled": False,
            "self_repair_enabled": False,
            "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
            "max_tokens": "omitted",
            "prompt_versions": list(PROMPT_VERSIONS),
            "one_generation_per_case_condition": True,
            "planned_generation_calls": PLANNED_GENERATIONS,
        },
        "evaluation_condition": {
            "evaluator_version": "v0.1",
            "judge_prompt_version": "v0.1",
            "judge_provider": judge.provider,
            "judge_model_requested": judge.model,
            "judge_model_reported": sorted(
                {
                    attempt["judge_model_reported"]
                    for evaluation in evaluations
                    for attempt in evaluation["attempts"]
                    if attempt["judge_model_reported"]
                }
            ),
            "temperature": 0,
            "structured_output_enabled": False,
            "evaluator_retry_enabled": False,
            "self_repair_enabled": False,
            "semantic_repeats_per_plan": SEMANTIC_REPEATS_PER_PLAN,
            "planned_semantic_evaluations": PLANNED_SEMANTIC_EVALUATIONS,
            "max_physical_attempts_per_semantic_evaluation": MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
            "retryable_failure_types": list(RETRYABLE_FAILURE_TYPES),
            "retry_backoff_seconds": {
                key: list(value) for key, value in RETRY_BACKOFF_SECONDS.items()
            },
            "timeout_seconds": JUDGE_TIMEOUT_SECONDS,
            "max_tokens": "omitted",
        },
        "analysis": {
            "descriptive_only": True,
            "confidence_intervals": False,
            "hypothesis_tests": False,
            "p_values": False,
            "formal_pass_fail": None,
        },
        "provenance": provenance,
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    return run_dir, summary

