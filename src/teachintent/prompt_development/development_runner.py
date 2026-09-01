"""Prompt v0.2-rc.1 development generation runner.

Purpose
-------
Regenerate the *existing* 30-case Pilot population with the candidate Generator
Prompt **v0.2-rc.1** so it can later be compared, under identical Evaluator v0.1
conditions, against the canonical Generator v0.1 Pilot outputs. The v0.1 side is
NOT regenerated (the three canonical Pilot runs are reused as a fixed baseline).

Design constraints (development-phase integration step)
-------------------------------------------------------
* Inputs are recovered from the three canonical Pilot run artifacts
  (``results/pilot/block_{a,b,c}/<run_id>/cases/<case_id>/input.json``).
* The recovered case IDs are verified, offline, to match the canonical 30-case
  Pilot population exactly (A=12, B=12, C=6, unique).
* Each input is generated through the frozen Generator service with the explicit
  ``prompt_version="v0.2-rc.1"`` — never relying on the default.
* temperature=0, model ``tencent/hy3``, no retry, no self-repair (first-call
  signal preserved).
* ``--dry-run`` performs discovery + population validation and prints the plan
  without ever calling Hy3/OpenRouter. ``--execute`` performs the REAL generation
  of all 30 cases with the explicit candidate Prompt **v0.2-rc.1**; it requires a
  usable OpenRouter/Hy3 API key and aborts before any API call if the key is
  missing.

This module reuses the frozen Generator stack (``generate_speech_plan``,
the prompt registry, the parser, the validators) and does NOT duplicate generator
logic. The real-generation path is implemented in :func:`run_development_batch`
(``dry_run=False``) and is driven by the CLI ``--execute`` mode.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..generator.errors import (
    GeneratorError,
    Hy3APIError,
    Hy3ConfigError,
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from ..generator.service import generate_speech_plan
from ..pilot_runner import (
    BLOCK_A_DATASET_PATH,
    BLOCK_B_DATASET_PATH,
    BLOCK_C_DATASET_PATH,
    CapturingClient,
    load_pilot_cases,
)
from ..prompts.registry import build_speech_plan_prompt_for_version

__all__ = [
    "GENERATOR_VERSION",
    "CANDIDATE_PROMPT_VERSION",
    "PROMPT_VERSION_RC2",
    "SUPPORTED_PROMPT_VERSIONS",
    "PEDAGOGICAL_INTENTS",
    "GENERATOR_MODEL",
    "TEMPERATURE",
    "API_GATEWAY",
    "CANONICAL_PILOT_RUNS",
    "DEVELOPMENT_RESULTS_ROOT",
    "DEVELOPMENT_RESULTS_ROOT_RC2",
    "DevelopmentCase",
    "DevelopmentValidationError",
    "canonical_population_case_ids",
    "discover_canonical_inputs",
    "validate_development_inputs",
    "results_root_for_prompt_version",
    "summarize_delivery_distribution",
    "run_development_batch",
]

# ---------------------------------------------------------------------------
# Configuration (frozen experimental condition for this development comparison).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Canonical v0.1 Generator service baseline (the generation stack). The Prompt
# layer is selected separately via prompt_version; this pins the pipeline version.
GENERATOR_VERSION = "v0.1"

# Registered candidate prompt versions this runner may generate with.
#
# "v0.2-rc.1" remains the DEFAULT so the existing rc.1 path is byte-identical to
# before; "v0.2-rc.2" must be selected EXPLICITLY (``--prompt-version v0.2-rc.2``)
# and is never a silent default. Both are always passed EXPLICITLY to
# ``generate_speech_plan`` — the service default is never relied upon.
CANDIDATE_PROMPT_VERSION = "v0.2-rc.1"
PROMPT_VERSION_RC2 = "v0.2-rc.2"
SUPPORTED_PROMPT_VERSIONS: tuple[str, ...] = (
    CANDIDATE_PROMPT_VERSION,
    PROMPT_VERSION_RC2,
)

GENERATOR_MODEL = "tencent/hy3"
TEMPERATURE = 0
API_GATEWAY = "openrouter"

# The six pedagogical intents present in the canonical 30-case population
# (5 cases each). Used for the delivery-plan distribution breakdown.
PEDAGOGICAL_INTENTS: tuple[str, ...] = (
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
)

# The three canonical Pilot runs reused as the v0.1 comparison baseline.
CANONICAL_PILOT_RUNS: dict[str, str] = {
    "block_a": "20260827-002543",
    "block_b": "20260827-051547",
    "block_c": "20260827-074602",
}

PILOT_RESULTS_ROOT = _REPO_ROOT / "results" / "pilot"
DEVELOPMENT_RESULTS_ROOT = _REPO_ROOT / "results" / "prompt_v0_2_rc1_development"
DEVELOPMENT_RESULTS_ROOT_RC2 = _REPO_ROOT / "results" / "prompt_v0_2_rc2_development"

# Source-of-truth population: the same block datasets the canonical Pilot runs
# were generated from. Used only to verify the recovered case IDs match exactly.
_POPULATION_DATASETS: dict[str, Path] = {
    "block_a": BLOCK_A_DATASET_PATH,
    "block_b": BLOCK_B_DATASET_PATH,
    "block_c": BLOCK_C_DATASET_PATH,
}

_BLOCK_ORDER = ("block_a", "block_b", "block_c")
_BLOCK_LETTER = {"block_a": "A", "block_b": "B", "block_c": "C"}


class DevelopmentValidationError(Exception):
    """Raised when the recovered development inputs do not match the canonical
    population (aborts before any Hy3 API call)."""


# ---------------------------------------------------------------------------
# Data model.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DevelopmentCase:
    """A recovered Pilot input tagged with its block and case_id."""

    case_id: str
    block: str
    input_doc: dict


# ---------------------------------------------------------------------------
# Discovery + population validation.
# ---------------------------------------------------------------------------
def canonical_population_case_ids() -> dict[str, list[str]]:
    """Return ``{block: [case_id, ...]}`` for the canonical 30-case Pilot population.

    Source of truth: the three block datasets the canonical Pilot runs were made
    from.
    """
    out: dict[str, list[str]] = {}
    for block, path in _POPULATION_DATASETS.items():
        cases = load_pilot_cases(path)
        out[block] = [c.get("case_id") for c in cases]
    return out


def discover_canonical_inputs() -> list[DevelopmentCase]:
    """Read the 30 inputs from the three canonical Pilot run artifacts.

    Returns cases in block order (A, B, C), each tagged with its block and
    case_id. Raises :class:`FileNotFoundError` if a run dir or input artifact is
    missing (so generation can never silently skip a case).
    """
    recovered: list[DevelopmentCase] = []
    for block in _BLOCK_ORDER:
        run_id = CANONICAL_PILOT_RUNS[block]
        run_dir = PILOT_RESULTS_ROOT / block / run_id
        if not run_dir.is_dir():
            raise FileNotFoundError(
                f"canonical Pilot run missing for {block}: {run_dir}"
            )
        cases_dir = run_dir / "cases"
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["cases"]:
            case_id = entry["case_id"]
            input_path = cases_dir / case_id / "input.json"
            if not input_path.is_file():
                raise FileNotFoundError(f"missing input artifact: {input_path}")
            input_doc = json.loads(input_path.read_text(encoding="utf-8"))
            recovered.append(
                DevelopmentCase(case_id=case_id, block=block, input_doc=input_doc)
            )
    return recovered


def validate_development_inputs(cases: list[DevelopmentCase]) -> dict:
    """Confirm the recovered inputs match the canonical 30-case population.

    Checks: total == 30, per-block counts A/B/C == 12/12/6, unique case IDs, and
    the recovered set equals the canonical population set exactly. Raises
    :class:`DevelopmentValidationError` on any mismatch (abort before generation).
    Returns a report dict on success.
    """
    population = canonical_population_case_ids()
    expected_total = sum(len(v) for v in population.values())
    recovered_by_block = {b: [] for b in _BLOCK_ORDER}
    for c in cases:
        recovered_by_block[c.block].append(c.case_id)
    recovered_all = [c.case_id for c in cases]
    population_all = sorted(id_ for ids in population.values() for id_ in ids)

    errors: list[str] = []
    if len(cases) != expected_total:
        errors.append(f"case count {len(cases)} != population {expected_total}")
    for block in _BLOCK_ORDER:
        expected = population[block]
        got = recovered_by_block[block]
        if len(got) != len(expected):
            errors.append(
                f"{_BLOCK_LETTER[block]} count {len(got)} != {len(expected)}"
            )
        if sorted(got) != sorted(expected):
            errors.append(
                f"{_BLOCK_LETTER[block]} case IDs do not match the canonical population"
            )
    if len(set(recovered_all)) != len(recovered_all):
        errors.append("recovered case IDs are not unique")
    if sorted(recovered_all) != population_all:
        errors.append(
            "recovered case IDs do not equal the canonical 30-case population"
        )

    report = {
        "total": len(cases),
        "expected_total": expected_total,
        "block_counts": {
            _BLOCK_LETTER[b]: len(recovered_by_block[b]) for b in _BLOCK_ORDER
        },
        "unique_case_ids": len(set(recovered_all)) == len(recovered_all),
        "matches_population": sorted(recovered_all) == population_all,
        "valid": not errors,
        "errors": errors,
    }
    if errors:
        raise DevelopmentValidationError("; ".join(errors))
    return report


# ---------------------------------------------------------------------------
# Prompt-version routing.
# ---------------------------------------------------------------------------
def results_root_for_prompt_version(prompt_version: str) -> Path:
    """Return the results directory a development run for *prompt_version* writes to.

    Each supported candidate version owns a separate directory, so an rc.2 run can
    never overwrite the finished rc.1 run. Unknown versions fail fast (before any
    API call or directory creation).

    The mapping is built from the module-level roots at call time (rather than
    captured once into a dict) so each root remains individually overridable.
    """
    roots = {
        CANDIDATE_PROMPT_VERSION: DEVELOPMENT_RESULTS_ROOT,
        PROMPT_VERSION_RC2: DEVELOPMENT_RESULTS_ROOT_RC2,
    }
    try:
        return roots[prompt_version]
    except KeyError:
        raise DevelopmentValidationError(
            f"unsupported prompt_version {prompt_version!r}; "
            f"supported: {sorted(roots)}"
        ) from None


# ---------------------------------------------------------------------------
# Delivery-plan distribution diagnostic.
# ---------------------------------------------------------------------------
def summarize_delivery_distribution(case_records: list[dict]) -> dict:
    """Report empty vs. non-empty ``delivery_plan`` across a finished run.

    This is the diagnostic that exposes *delivery mode collapse* — a candidate
    prompt that mechanically emits ``delivery_plan: {}`` for every case (rc.1
    measured 30/30 empty). It reports faithfully and sets NO pass/fail threshold.

    Parameters
    ----------
    case_records:
        One dict per case, each carrying ``case_id``, ``intent`` and
        ``delivery_plan_empty`` — where the latter is ``True`` for ``{}``,
        ``False`` for a non-empty object, or ``None`` when no plan was parsed
        (generation/parsing failure). Failures are reported separately and are
        NEVER counted as "empty".

    Returns a report with total counts, a per-intent breakdown, and the explicit
    list of non-empty case IDs.
    """
    by_intent: dict[str, dict] = {
        intent: {
            "total": 0,
            "empty": 0,
            "non_empty": 0,
            "without_parsed_plan": 0,
            "non_empty_case_ids": [],
        }
        for intent in PEDAGOGICAL_INTENTS
    }

    empty_ids: list[str] = []
    non_empty_ids: list[str] = []
    without_plan_ids: list[str] = []

    for record in case_records:
        case_id = record["case_id"]
        intent = record.get("intent")
        bucket = by_intent.setdefault(
            intent or "unknown",
            {
                "total": 0,
                "empty": 0,
                "non_empty": 0,
                "without_parsed_plan": 0,
                "non_empty_case_ids": [],
            },
        )
        bucket["total"] += 1

        flag = record.get("delivery_plan_empty")
        if flag is None:
            bucket["without_parsed_plan"] += 1
            without_plan_ids.append(case_id)
        elif flag:
            bucket["empty"] += 1
            empty_ids.append(case_id)
        else:
            bucket["non_empty"] += 1
            bucket["non_empty_case_ids"].append(case_id)
            non_empty_ids.append(case_id)

    return {
        "total_cases": len(case_records),
        "with_parsed_plan": len(empty_ids) + len(non_empty_ids),
        "without_parsed_plan": len(without_plan_ids),
        "empty_count": len(empty_ids),
        "non_empty_count": len(non_empty_ids),
        "empty_case_ids": sorted(empty_ids),
        "non_empty_case_ids": sorted(non_empty_ids),
        "without_parsed_plan_case_ids": sorted(without_plan_ids),
        "by_intent": by_intent,
        "note": (
            "Diagnostic only — no pass/fail threshold is defined. "
            "Cases without a parsed plan are excluded from the empty/non-empty "
            "counts rather than being treated as empty."
        ),
    }


# ---------------------------------------------------------------------------
# Stage-outcome derivation (mirrors pilot_runner._stage_outcome; offline).
# ---------------------------------------------------------------------------
def _stage_outcome(exc: GeneratorError | None) -> dict:
    record: dict[str, Any] = {
        "input_json_schema": "not_reached",
        "input_pydantic": "not_reached",
        "response_parsing": "not_reached",
        "speech_plan_json_schema": "not_reached",
        "speech_plan_pydantic": "not_reached",
    }
    if exc is None:
        for stage in record:
            record[stage] = "passed"
    elif isinstance(exc, Hy3ConfigError):
        pass  # all not_reached
    elif isinstance(exc, InputContractError):
        record["input_json_schema"] = "passed"
        if exc.layer == "jsonschema":
            record["input_json_schema"] = {
                "status": "failed",
                "errors": exc.error_summary,
            }
        else:
            record["input_pydantic"] = {
                "status": "failed",
                "errors": exc.error_summary,
            }
    elif isinstance(exc, Hy3APIError):
        record["input_json_schema"] = "passed"
        record["input_pydantic"] = "passed"
    elif isinstance(exc, ResponseParsingError):
        record["input_json_schema"] = "passed"
        record["input_pydantic"] = "passed"
        record["response_parsing"] = {"status": "failed", "error": str(exc)}
    elif isinstance(exc, SpeechPlanStructuralError):
        record["input_json_schema"] = "passed"
        record["input_pydantic"] = "passed"
        record["response_parsing"] = "passed"
        record["speech_plan_json_schema"] = {
            "status": "failed",
            "errors": exc.error_summary,
        }
    elif isinstance(exc, SpeechPlanSemanticError):
        record["input_json_schema"] = "passed"
        record["input_pydantic"] = "passed"
        record["response_parsing"] = "passed"
        record["speech_plan_json_schema"] = "passed"
        record["speech_plan_pydantic"] = {
            "status": "failed",
            "error": exc.error_text,
        }
    record["outcome"] = "success" if exc is None else type(exc).__name__
    return record


# ---------------------------------------------------------------------------
# Main orchestrator.
# ---------------------------------------------------------------------------
def run_development_batch(
    client: Any,
    *,
    dry_run: bool = True,
    output_dir: str | Path | None = None,
    prompt_version: str = CANDIDATE_PROMPT_VERSION,
) -> dict:
    """Discover the 30 Pilot inputs, validate against the canonical population, and
    (unless ``dry_run``) regenerate them with *prompt_version* via the Generator.

    Parameters
    ----------
    client:
        A :class:`Hy3Completer`. Unused in ``dry_run`` mode (may be ``None``).
    dry_run:
        If True, only discover + validate + print the plan; no Hy3 call, no
        artifacts written. If False, regenerate all 30 cases and write artifacts.
    output_dir:
        Where to write the run. When ``None``, the directory is selected by
        *prompt_version* (rc.1 -> ``results/prompt_v0_2_rc1_development``,
        rc.2 -> ``results/prompt_v0_2_rc2_development``), so the two candidates
        can never overwrite one another.
    prompt_version:
        Passed EXPLICITLY to ``generate_speech_plan`` and selects the run's
        results directory. Defaults to the candidate ``v0.2-rc.1``; callers must
        not rely on the service default. ``v0.2-rc.2`` must be requested
        explicitly — it is never a silent default.

    Returns a summary dict (dry-run) or the run manifest dict (real run).
    """
    if prompt_version not in SUPPORTED_PROMPT_VERSIONS:
        raise DevelopmentValidationError(
            f"unsupported prompt_version {prompt_version!r}; "
            f"supported: {list(SUPPORTED_PROMPT_VERSIONS)}"
        )
    cases = discover_canonical_inputs()
    validation = validate_development_inputs(cases)

    summary = {
        "development_set": "existing 30 Pilot cases",
        "block_counts": validation["block_counts"],
        "total": validation["total"],
        "unique_case_ids": validation["unique_case_ids"],
        "matches_population": validation["matches_population"],
        "v0_1_reference_runs": dict(CANONICAL_PILOT_RUNS),
        "candidate_prompt": prompt_version,
        "generator_version": GENERATOR_VERSION,
        "generator_model": GENERATOR_MODEL,
        "temperature": TEMPERATURE,
        "retry": False,
        "self_repair": False,
        "planned_generator_calls": validation["total"],
    }

    if dry_run:
        summary["api_call_made"] = False
        _print_dry_run(summary)
        return summary

    # ----- Real generation (next phase only; not executed this integration step) -----
    if client is None:
        raise DevelopmentValidationError(
            "real generation requires a Hy3 client; none was provided"
        )
    return _generate_batch(client, cases, prompt_version, output_dir)


def _generate_batch(
    client: Any,
    cases: list[DevelopmentCase],
    prompt_version: str,
    output_dir: str | Path | None,
) -> dict:
    """Regenerate each case once (no retry, no self-repair) and write artifacts."""
    # Version-specific results directory; an unknown version fails fast before
    # anything is written.
    out_root = Path(output_dir) if output_dir else results_root_for_prompt_version(
        prompt_version
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    capturing = CapturingClient(client)

    case_records: list[dict] = []
    for case in cases:
        case_started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        t0 = time.monotonic()
        capturing.last_completion = None

        exc: GeneratorError | None = None
        result = None
        try:
            # EXPLICIT prompt_version — never the service default.
            result = generate_speech_plan(
                case.input_doc, capturing, prompt_version=prompt_version
            )
        except GeneratorError as caught:
            exc = caught
        except Exception as caught:  # noqa: BLE001 — one bad case must not stop the batch.
            exc = caught  # type: ignore[assignment]

        case_finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        duration = time.monotonic() - t0

        completion = capturing.last_completion
        finish_reason = completion.finish_reason if completion else None
        reported_model = completion.reported_model if completion else None
        token_usage = (
            getattr(completion, "usage", None) if completion else None
        )
        requested_model = capturing.model

        raw_response: str | None = None
        parsed_doc: dict | None = None
        http_response_text: str | None = None
        prompt_system: str | None = None
        prompt_user: str | None = None
        resolved_prompt_version: str | None = None

        if result is not None:
            raw_response = result.raw_response
            parsed_doc = result.plan_doc
            prompt_system = result.prompt_system
            prompt_user = result.prompt_user
            resolved_prompt_version = result.prompt_version
        elif isinstance(exc, ResponseParsingError):
            raw_response = exc.raw_text
        elif isinstance(exc, (SpeechPlanStructuralError, SpeechPlanSemanticError)):
            raw_response = exc.raw_text
            parsed_doc = exc.plan_doc
        elif isinstance(exc, Hy3APIError):
            http_response_text = exc.response_text

        # If the prompt was built but not captured from a result (later failure),
        # reconstruct it so the artifact/metadata record the correct prompt_version.
        if prompt_system is None and not isinstance(exc, InputContractError):
            try:
                prompt = build_speech_plan_prompt_for_version(
                    case.input_doc, version=prompt_version
                )
                prompt_system = prompt.system
                prompt_user = prompt.user
                resolved_prompt_version = prompt_version
            except Exception:
                pass  # input itself may be invalid; prompt build can fail

        outcome = "success" if exc is None else type(exc).__name__
        validation_record = _stage_outcome(
            exc if isinstance(exc, GeneratorError) else None
        )
        # A structurally-valid speech plan exists when the structural JSON-Schema
        # layer passed (this is true for both full-success and semantic-error cases).
        structural_passed = validation_record.get("speech_plan_json_schema") == "passed"

        case_dir = out_root / run_id / "cases" / case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        _write_json(case_dir / "input.json", case.input_doc)
        _write_json(
            case_dir / "prompt.json",
            {
                "prompt_version": resolved_prompt_version,
                "system": prompt_system,
                "user": prompt_user,
            },
        )
        if raw_response is not None:
            (case_dir / "raw_response.txt").write_text(
                raw_response, encoding="utf-8"
            )
        if parsed_doc is not None:
            _write_json(case_dir / "parsed.json", parsed_doc)
        if http_response_text is not None:
            (case_dir / "http_response.txt").write_text(
                http_response_text, encoding="utf-8"
            )
        _write_json(case_dir / "validation.json", validation_record)
        _write_json(
            case_dir / "metadata.json",
            {
                "case_id": case.case_id,
                "block": case.block,
                "attempt_index": 1,
                "generator_version": GENERATOR_VERSION,
                "prompt_version": resolved_prompt_version,
                "api_gateway": API_GATEWAY,
                "requested_model": requested_model,
                "reported_model": reported_model,
                "temperature": TEMPERATURE,
                "started_at": case_started,
                "finished_at": case_finished,
                "duration_seconds": round(duration, 3),
                "outcome": outcome,
                "exception_class": type(exc).__name__ if exc is not None else None,
                "finish_reason": finish_reason,
                "token_usage": token_usage,
            },
        )

        # Delivery-plan emptiness is derived from the parsed plan only. When no
        # plan was parsed (API/parsing failure) it stays None so the distribution
        # never mis-counts a failure as an "empty" delivery plan.
        delivery_plan_empty: bool | None = None
        if parsed_doc is not None:
            delivery_plan_empty = not parsed_doc.get("delivery_plan")

        case_records.append(
            {
                "case_id": case.case_id,
                "block": case.block,
                "intent": (case.input_doc.get("pedagogical_intent") or {}).get(
                    "primary"
                ),
                "outcome": outcome,
                "duration_seconds": round(duration, 3),
                "exception_class": type(exc).__name__ if exc is not None else None,
                "prompt_version": resolved_prompt_version,
                "structural_passed": structural_passed,
                "delivery_plan_empty": delivery_plan_empty,
            }
        )

    run_finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pass_count = sum(1 for r in case_records if r["outcome"] == "success")
    fail_count = len(case_records) - pass_count

    structural_success = sum(1 for r in case_records if r["structural_passed"])
    first_call_validity = pass_count

    manifest = {
        "run_id": run_id,
        "started_at": run_started,
        "finished_at": run_finished,
        "generator_version": GENERATOR_VERSION,
        "prompt_version": prompt_version,
        "actual_conditions": {
            "api_gateway": API_GATEWAY,
            "model": GENERATOR_MODEL,
            "temperature": TEMPERATURE,
            "structured_output": False,
            "retry": False,
            "self_repair": False,
        },
        "v0_1_reference_runs": dict(CANONICAL_PILOT_RUNS),
        "development_set": "existing 30 Pilot cases",
        "case_count": len(case_records),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "structural_report": {
            "total": len(case_records),
            "structural_success": structural_success,
            "structural_failure": len(case_records) - structural_success,
            "first_call_validity": first_call_validity,
        },
        # Delivery mode diagnostic (empty vs. non-empty delivery_plan). Reports
        # faithfully; defines no pass/fail threshold.
        "delivery_distribution": summarize_delivery_distribution(case_records),
        "cases": case_records,
    }
    _write_json(out_root / run_id / "run_manifest.json", manifest)
    return manifest


# ---------------------------------------------------------------------------
# Dry-run printer.
# ---------------------------------------------------------------------------
def _print_dry_run(s: dict) -> None:
    print("Development set = existing 30 Pilot cases")
    print()
    print(f"A = {s['block_counts']['A']}")
    print(f"B = {s['block_counts']['B']}")
    print(f"C = {s['block_counts']['C']}")
    print(f"total = {s['total']}")
    print()
    print(f"unique case IDs = {s['unique_case_ids']}")
    print()
    print("v0.1 reference runs:")
    print(f"A = {s['v0_1_reference_runs']['block_a']}")
    print(f"B = {s['v0_1_reference_runs']['block_b']}")
    print(f"C = {s['v0_1_reference_runs']['block_c']}")
    print()
    print(f"candidate prompt = {s['candidate_prompt']}")
    print(f"Generator model = {s['generator_model']}")
    print(f"temperature = {s['temperature']}")
    print(f"retry = {str(s['retry']).lower()}")
    print(f"self_repair = {str(s['self_repair']).lower()}")
    print()
    print(f"planned Generator calls = {s['planned_generator_calls']}")
    print()
    print("No API call was made.")


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
