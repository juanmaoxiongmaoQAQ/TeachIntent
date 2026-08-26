#!/usr/bin/env python3
"""Manual smoke test runner for the Hy3 Speech Plan Generator v0.1.

Runs ONE real Hy3 call against the canonical corrective-feedback case from
docs/problem_definition.md section 12, using the OpenRouter baseline
(HY3_BASE_URL=https://openrouter.ai/api/v1, Bearer auth, temperature=0).

NOT part of the pytest suite. Run manually:

    .venv/bin/python scripts/run_smoke.py

Requires a .env file (copy .env.example, fill HY3_API_KEY / HY3_BASE_URL /
HY3_MODEL). The API key is NEVER written to any artifact.

Artifacts are written to results/smoke/<local-timestamp>-canonical-corrective-feedback/:
  input.json          - the canonical input doc
  prompt.json         - {prompt_version, system, user}
  raw_response.txt    - exact model output text (when the API returned content)
  parsed.json         - the parsed dict (when parsing succeeded)
  http_response.txt   - full HTTP body (only on non-2xx Hy3APIError)
  validation.json     - stage-by-stage outcome
  meta.json           - prompt_version, requested_model, reported_model,
                        timestamp (UTC), duration_seconds, outcome
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from teachintent.generator import (
    Hy3APIError,
    Hy3Client,
    Hy3ConfigError,
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
    generate_speech_plan,
)
from teachintent.generator.errors import GeneratorError
from teachintent.prompts import PROMPT_VERSION, build_speech_plan_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results" / "smoke"

# Canonical corrective-feedback case — docs/problem_definition.md section 12
# (identical to tests/conftest.py::CANONICAL_INPUT_DOC; both frozen).
CANONICAL_INPUT_DOC = {
    "schema_version": "1.0.0-rc.2",
    "output_language": "zh-CN",
    "instructional_content": {
        "subject": "physics",
        "topic": "speed_and_acceleration",
        "content_anchor": (
            "速度表示物体运动的快慢。加速度表示速度随时间变化的快慢。"
            "速度大不意味着加速度一定大。"
        ),
    },
    "pedagogical_context": {
        "scenario": "The learner has just answered a conceptual question.",
        "learner_utterance": "速度越大，加速度一定越大。",
    },
    "learner": {
        "level": "middle_school",
        "knowledge_state": "misconception",
        "affective_state": "slightly_frustrated",
    },
    "pedagogical_intent": {"primary": "corrective_feedback"},
}


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: object) -> None:
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def _stage_outcome(exc: GeneratorError | None) -> dict:
    """Build the validation.json stage-by-stage record from the exception type."""
    record: dict[str, object] = {
        "input_json_schema": "not_reached",
        "input_pydantic": "not_reached",
        "response_parsing": "not_reached",
        "speech_plan_json_schema": "not_reached",
        "speech_plan_pydantic": "not_reached",
    }
    outcome = "success"
    if exc is None:
        for stage in record:
            record[stage] = "passed"
    elif isinstance(exc, Hy3ConfigError):
        outcome = "Hy3ConfigError"
    elif isinstance(exc, InputContractError):
        record["input_json_schema"] = "passed"
        if exc.layer == "jsonschema":
            record["input_json_schema"] = {
                "status": "failed",
                "errors": exc.error_summary,
            }
            outcome = "InputContractError(jsonschema)"
        else:
            record["input_pydantic"] = {"status": "failed", "errors": exc.error_summary}
            outcome = "InputContractError(pydantic)"
    elif isinstance(exc, Hy3APIError):
        for stage in ("input_json_schema", "input_pydantic"):
            record[stage] = "passed"
        outcome = "Hy3APIError"
    elif isinstance(exc, ResponseParsingError):
        for stage in ("input_json_schema", "input_pydantic"):
            record[stage] = "passed"
        record["response_parsing"] = {"status": "failed", "error": str(exc)}
        outcome = "ResponseParsingError"
    elif isinstance(exc, SpeechPlanStructuralError):
        for stage in ("input_json_schema", "input_pydantic", "response_parsing"):
            record[stage] = "passed"
        record["speech_plan_json_schema"] = {
            "status": "failed",
            "errors": exc.error_summary,
        }
        outcome = "SpeechPlanStructuralError"
    elif isinstance(exc, SpeechPlanSemanticError):
        for stage in (
            "input_json_schema",
            "input_pydantic",
            "response_parsing",
            "speech_plan_json_schema",
        ):
            record[stage] = "passed"
        record["speech_plan_pydantic"] = {"status": "failed", "error": exc.error_text}
        outcome = "SpeechPlanSemanticError"
    record["outcome"] = outcome
    return record


def main() -> int:
    load_dotenv()

    timestamp_local = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact_dir = RESULTS_DIR / f"{timestamp_local}-canonical-corrective-feedback"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    input_doc = CANONICAL_INPUT_DOC
    prompt = build_speech_plan_prompt(input_doc)

    # Always record input + prompt (deterministic, available before any API call).
    _write_json(artifact_dir / "input.json", input_doc)
    _write_json(
        artifact_dir / "prompt.json",
        {
            "prompt_version": PROMPT_VERSION,
            "system": prompt.system,
            "user": prompt.user,
        },
    )

    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.monotonic()

    result = None
    exc: GeneratorError | None = None
    client: Hy3Client | None = None
    try:
        client = Hy3Client.from_env()
        print(f"Endpoint: {client.endpoint}")
        print(f"Requested model: {client.model}")
        result = generate_speech_plan(input_doc, client)
    except GeneratorError as caught:
        exc = caught
    except Exception:  # noqa: BLE001 - bugs must crash loudly, not be masked.
        raise

    duration = time.monotonic() - t0

    # ---- Write stage artifacts from result or exception ----
    raw_text: str | None = None
    plan_doc: dict | None = None
    http_response_text: str | None = None
    requested_model = client.model if client is not None else None
    reported_model: str | None = None

    if result is not None:
        raw_text = result.raw_response
        plan_doc = result.plan_doc
        reported_model = result.reported_model
    elif isinstance(exc, ResponseParsingError):
        raw_text = exc.raw_text
    elif isinstance(exc, (SpeechPlanStructuralError, SpeechPlanSemanticError)):
        raw_text = exc.raw_text
        plan_doc = exc.plan_doc
    elif isinstance(exc, Hy3APIError):
        http_response_text = exc.response_text

    if raw_text is not None:
        _write(artifact_dir / "raw_response.txt", raw_text)
    if plan_doc is not None:
        _write_json(artifact_dir / "parsed.json", plan_doc)
    if http_response_text is not None:
        _write(artifact_dir / "http_response.txt", http_response_text)

    _write_json(artifact_dir / "validation.json", _stage_outcome(exc))
    _write_json(
        artifact_dir / "meta.json",
        {
            "prompt_version": PROMPT_VERSION,
            "requested_model": requested_model,
            "reported_model": reported_model,
            "timestamp": started_utc,
            "duration_seconds": round(duration, 3),
            "outcome": "success" if exc is None else type(exc).__name__,
        },
    )

    # ---- Human summary ----
    print()
    if exc is None and result is not None:
        seg_count = len(result.speech_plan.verbal_plan.segments)
        print(f"SUCCESS: validated Speech Plan with {seg_count} segment(s).")
        print(f"Reported model: {result.reported_model}")
    else:
        print(f"FAILED: {type(exc).__name__}: {exc}")
    print(f"Artifacts: {artifact_dir}")
    return 0 if exc is None else 1


if __name__ == "__main__":
    sys.exit(main())
