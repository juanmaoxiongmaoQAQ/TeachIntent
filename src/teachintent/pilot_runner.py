"""Reproducible batch runner for the frozen Block A Hy3 baseline generation.

Loads the frozen 12-case Block A JSONL, runs each case sequentially through the
existing Generator service (``generate_speech_plan``) with the frozen experimental
condition (OpenRouter, ``tencent/hy3``, temperature=0, no structured output, no
retry, no self-repair), and saves per-case + run-level artifacts.

This module reuses the frozen Generator stack (Prompt v0.1, Hy3Client, parser,
validators, models, exception classes) and does NOT duplicate generator logic.
A :class:`CapturingClient` wrapper transparently captures the
:class:`Hy3Completion` (for ``finish_reason``) without modifying the Generator.

Token usage is NOT exposed by the current :class:`Hy3Completion` / client layer;
it is recorded as ``null`` in metadata. When a future client extension exposes
usage, the wrapper will pick it up automatically via ``getattr``.

This module does NOT call Hy3 on its own — the caller injects the client. Tests
use mock/fake clients; the real run is driven by ``scripts/run_pilot_block_a.py``.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .generator import Hy3Completion
from .generator.errors import (
    GeneratorError,
    Hy3APIError,
    Hy3ConfigError,
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from .generator.service import generate_speech_plan
from .pilot_validation import validate_pilot_cases

__all__ = [
    "BLOCK_A_DATASET_PATH",
    "FROZEN_CONDITIONS",
    "PreflightError",
    "CapturingClient",
    "CaseResult",
    "RunManifest",
    "load_pilot_cases",
    "run_pilot_block_a",
]

# Repository-relative path to the frozen Block A dataset.
BLOCK_A_DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "cases"
    / "pilot"
    / "blocks"
    / "block_a_controlled_contrast.jsonl"
)

# Frozen experimental condition for the Block A Hy3 baseline.
FROZEN_CONDITIONS: dict[str, Any] = {
    "api_gateway": "openrouter",
    "model": "tencent/hy3",
    "temperature": 0,
    "structured_output": False,
    "retry": False,
    "self_repair": False,
}

# The expected OpenRouter base URL (the /v1 prefix is part of HY3_BASE_URL).
EXPECTED_BASE_URL = "https://openrouter.ai/api/v1"


class PreflightError(Exception):
    """Raised when a preflight safeguard fails, aborting the batch before any
    Hy3 API call."""


# ---------------------------------------------------------------------------
# Preflight safeguards.
# ---------------------------------------------------------------------------
def _run_structural_preflight(dataset_path: Path) -> None:
    """Run the existing pilot structural-validation logic on the dataset.

    If validation does not fully pass, raise :class:`PreflightError` to abort
    before any Hy3 API call.
    """
    report = validate_pilot_cases(dataset_path)
    if not report.all_passed:
        # Collect a concise summary of what failed.
        failed_checks = [
            name for name, detail in report.dataset_checks.items() if detail
        ]
        case_err_count = len(report.case_errors)
        raise PreflightError(
            f"structural preflight failed for {dataset_path}: "
            f"{len(failed_checks)} dataset-level check(s) failed "
            f"({failed_checks}), {case_err_count} case error(s); "
            "aborting before any Hy3 API call"
        )


def _run_config_preflight(client: Any) -> dict[str, Any]:
    """Verify the actual client configuration matches the frozen baseline.

    Checks the actual client's model, endpoint (OpenRouter), and
    response_format (structured output disabled). Temperature=0, retry=False,
    and self_repair=False are guaranteed by the frozen Generator v0.1 service
    code and the runner implementation respectively (not client-configurable).

    Returns the *actual* verified conditions dict (not hardcoded) so the
    manifest reflects what was really used. Raises :class:`PreflightError` on
    mismatch.
    """
    problems: list[str] = []

    # Model.
    actual_model = getattr(client, "model", None)
    if actual_model != FROZEN_CONDITIONS["model"]:
        problems.append(
            f"model: expected {FROZEN_CONDITIONS['model']!r}, "
            f"got {actual_model!r}"
        )

    # Base URL / gateway — check the client's endpoint.
    endpoint = getattr(client, "endpoint", None)
    if endpoint is None:
        problems.append("client has no 'endpoint' attribute; cannot verify gateway")
    elif not str(endpoint).startswith(EXPECTED_BASE_URL):
        problems.append(
            f"base URL: expected {EXPECTED_BASE_URL!r} (OpenRouter), "
            f"endpoint was {endpoint!r}"
        )

    # Structured output — response_format must be None (disabled).
    response_format = getattr(client, "_response_format", None)
    if response_format is not None:
        problems.append(
            f"structured_output: expected disabled (None), "
            f"got {response_format!r}"
        )

    if problems:
        raise PreflightError(
            "configuration preflight failed; aborting before any Hy3 API call: "
            + "; ".join(problems)
        )

    # Build the actual-conditions dict from verified client attributes.
    # Temperature=0 is guaranteed by the Generator service (hardcoded
    # temperature=0.0 in generate_speech_plan). Retry=False and
    # self_repair=False are guaranteed by the runner implementation (no retry
    # loop, no self-repair logic exists).
    return {
        "api_gateway": FROZEN_CONDITIONS["api_gateway"],
        "base_url": EXPECTED_BASE_URL,
        "model": actual_model,
        "temperature": 0,
        "structured_output": response_format is not None,
        "retry": False,
        "self_repair": False,
    }


# ---------------------------------------------------------------------------
# CapturingClient — transparent wrapper that captures finish_reason without
# modifying the Generator.
# ---------------------------------------------------------------------------
class CapturingClient:
    """Wraps a :class:`Hy3Completer` and captures the last :class:`Hy3Completion`.

    The pilot runner reads ``last_completion.finish_reason`` after
    ``generate_speech_plan`` returns or raises. If the API call itself failed
    (``complete`` raised), ``last_completion`` remains ``None``.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.last_completion: Hy3Completion | None = None

    @property
    def model(self) -> str:
        return self._inner.model

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0
    ) -> Hy3Completion:
        completion = self._inner.complete(system, user, temperature=temperature)
        self.last_completion = completion
        return completion


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CaseResult:
    """Per-case generation result (success or failure)."""

    case_id: str
    attempt_index: int
    outcome: str  # "success" or the exception class name
    exception_class: str | None
    started_at: str
    finished_at: str
    duration_seconds: float
    prompt_version: str | None
    requested_model: str | None
    reported_model: str | None
    temperature: float
    finish_reason: str | None
    token_usage: dict | None
    # Artifacts (stored for the runner to write; not serialized into the manifest
    # summary directly — written as separate files).
    input_doc: dict | None = None
    prompt_system: str | None = None
    prompt_user: str | None = None
    raw_response: str | None = None
    parsed_doc: dict | None = None
    http_response_text: str | None = None
    validation: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RunManifest:
    """Run-level manifest summarising the whole batch."""

    run_id: str
    started_at: str
    finished_at: str
    actual_conditions: dict[str, Any]
    dataset_path: str
    case_count: int
    pass_count: int
    fail_count: int
    cases: list[dict]  # per-case summary: case_id, outcome, duration, exception_class


# ---------------------------------------------------------------------------
# JSONL loader.
# ---------------------------------------------------------------------------
def load_pilot_cases(path: Path) -> list[dict]:
    """Load JSONL cases from *path* in file order. Skips blank lines."""
    cases: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


# ---------------------------------------------------------------------------
# Stage-outcome derivation (mirrors scripts/run_smoke.py logic).
# ---------------------------------------------------------------------------
def _stage_outcome(exc: GeneratorError | None) -> dict:
    record: dict[str, object] = {
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
# Main batch runner.
# ---------------------------------------------------------------------------
def run_pilot_block_a(
    client: Any,
    dataset_path: Path,
    output_dir: Path,
) -> RunManifest:
    """Run the frozen Block A batch through the Generator service.

    *client* must satisfy the :class:`Hy3Completer` Protocol. It is wrapped in a
    :class:`CapturingClient` to capture ``finish_reason``. Artifacts are written
    under *output_dir*. Returns a :class:`RunManifest`.

    A failure in one case is recorded and does NOT stop the remaining cases.
    Exactly one first-call generation attempt per case (no retry, no self-repair).
    """
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ---- Preflight safeguards (before any Hy3 API call) ----
    # 1. Structural: validate the frozen dataset through the existing pilot
    #    structural-validation logic. Abort if it does not fully pass.
    _run_structural_preflight(dataset_path)
    # 2. Configuration: verify the actual client matches the frozen baseline
    #    (OpenRouter, tencent/hy3, structured output disabled). Returns the
    #    actual verified conditions for the manifest (not hardcoded).
    actual_conditions = _run_config_preflight(client)

    cases = load_pilot_cases(dataset_path)
    capturing = CapturingClient(client)

    results: list[CaseResult] = []
    for index, case in enumerate(cases):
        case_id = case.get("case_id", f"<line-{index + 1}>")
        input_doc = case.get("input", {})

        case_started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        t0 = time.monotonic()
        capturing.last_completion = None

        exc: GeneratorError | None = None
        result = None
        try:
            result = generate_speech_plan(input_doc, capturing)
        except GeneratorError as caught:
            exc = caught
        except Exception as caught:  # noqa: BLE001 — bugs must not crash the batch.
            exc = caught

        case_finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        duration = time.monotonic() - t0

        # Extract metadata from result or exception.
        completion = capturing.last_completion
        finish_reason = completion.finish_reason if completion else None
        reported_model = completion.reported_model if completion else None
        # token_usage is not exposed by the current Hy3Completion; use getattr
        # for forward-compatibility if a future client adds it.
        token_usage = getattr(completion, "usage", None) if completion else None
        requested_model = capturing.model

        raw_response: str | None = None
        parsed_doc: dict | None = None
        http_response_text: str | None = None
        prompt_version: str | None = None
        prompt_system: str | None = None
        prompt_user: str | None = None

        if result is not None:
            raw_response = result.raw_response
            parsed_doc = result.plan_doc
            prompt_version = result.prompt_version
            prompt_system = result.prompt_system
            prompt_user = result.prompt_user
        elif isinstance(exc, ResponseParsingError):
            raw_response = exc.raw_text
        elif isinstance(exc, (SpeechPlanStructuralError, SpeechPlanSemanticError)):
            raw_response = exc.raw_text
            parsed_doc = exc.plan_doc
        elif isinstance(exc, Hy3APIError):
            http_response_text = exc.response_text

        # If input validation passed, the prompt was built (even on later
        # failure). Reconstruct it for the artifact when not available from result.
        if prompt_system is None and not isinstance(exc, (InputContractError,)):
            from .prompts.speech_plan import build_speech_plan_prompt
            try:
                prompt = build_speech_plan_prompt(input_doc)
                prompt_system = prompt.system
                prompt_user = prompt.user
                from .prompts.speech_plan import PROMPT_VERSION
                prompt_version = PROMPT_VERSION
            except Exception:
                pass  # input may be invalid; prompt build can fail

        outcome = "success" if exc is None else type(exc).__name__
        exception_class = type(exc).__name__ if exc is not None else None

        case_result = CaseResult(
            case_id=case_id,
            attempt_index=1,
            outcome=outcome,
            exception_class=exception_class,
            started_at=case_started,
            finished_at=case_finished,
            duration_seconds=round(duration, 3),
            prompt_version=prompt_version,
            requested_model=requested_model,
            reported_model=reported_model,
            temperature=0.0,
            finish_reason=finish_reason,
            token_usage=token_usage,
            input_doc=input_doc,
            prompt_system=prompt_system,
            prompt_user=prompt_user,
            raw_response=raw_response,
            parsed_doc=parsed_doc,
            http_response_text=http_response_text,
            validation=_stage_outcome(exc if isinstance(exc, GeneratorError) else None),
        )
        results.append(case_result)

    run_finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pass_count = sum(1 for r in results if r.outcome == "success")
    fail_count = len(results) - pass_count

    # ---- Write artifacts ----
    run_dir = output_dir / run_id
    cases_dir = run_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    for r in results:
        case_dir = cases_dir / r.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        _write_json(case_dir / "input.json", r.input_doc)
        _write_json(
            case_dir / "prompt.json",
            {
                "prompt_version": r.prompt_version,
                "system": r.prompt_system,
                "user": r.prompt_user,
            },
        )
        if r.raw_response is not None:
            (case_dir / "raw_response.txt").write_text(
                r.raw_response, encoding="utf-8"
            )
        if r.parsed_doc is not None:
            _write_json(case_dir / "parsed.json", r.parsed_doc)
        if r.http_response_text is not None:
            (case_dir / "http_response.txt").write_text(
                r.http_response_text, encoding="utf-8"
            )
        _write_json(case_dir / "validation.json", r.validation)
        _write_json(
            case_dir / "metadata.json",
            {
                "case_id": r.case_id,
                "attempt_index": r.attempt_index,
                "prompt_version": r.prompt_version,
                "api_gateway": actual_conditions["api_gateway"],
                "requested_model": r.requested_model,
                "reported_model": r.reported_model,
                "temperature": r.temperature,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "duration_seconds": r.duration_seconds,
                "outcome": r.outcome,
                "exception_class": r.exception_class,
                "finish_reason": r.finish_reason,
                "token_usage": r.token_usage,
            },
        )

    manifest = RunManifest(
        run_id=run_id,
        started_at=run_started,
        finished_at=run_finished,
        actual_conditions=actual_conditions,
        dataset_path=str(dataset_path),
        case_count=len(results),
        pass_count=pass_count,
        fail_count=fail_count,
        cases=[
            {
                "case_id": r.case_id,
                "outcome": r.outcome,
                "duration_seconds": r.duration_seconds,
                "exception_class": r.exception_class,
            }
            for r in results
        ],
    )
    _write_json(run_dir / "manifest.json", asdict(manifest))
    return manifest


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
