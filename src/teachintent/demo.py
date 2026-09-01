"""Small public demo for recorded or live TeachIntent Speech Plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .generator import GeneratorError, Hy3Client, generate_speech_plan
from .models import SpeechPlan, TeachIntentInput
from .validators import iter_input_errors, iter_speech_plan_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_FILES = {
    "elicitation": REPO_ROOT / "examples" / "elicitation.json",
    "corrective-feedback": REPO_ROOT / "examples" / "corrective_feedback.json",
    "scaffolding": REPO_ROOT / "examples" / "scaffolding.json",
}
PUBLIC_PROMPT_VERSIONS = ("v0.1", "v0.2")


class DemoDataError(ValueError):
    """Raised when a bundled recorded example violates a public contract."""


def load_recorded_example(example_name: str, prompt_version: str) -> dict:
    """Load and validate one bundled example and its selected recorded plan."""
    try:
        path = EXAMPLE_FILES[example_name]
    except KeyError as exc:
        raise DemoDataError(f"Unknown example: {example_name}") from exc

    doc = json.loads(path.read_text(encoding="utf-8"))
    input_doc = doc.get("input")
    recorded_outputs = doc.get("recorded_outputs")
    if not isinstance(input_doc, dict) or not isinstance(recorded_outputs, dict):
        raise DemoDataError(f"Malformed example package: {path}")
    if prompt_version not in recorded_outputs:
        raise DemoDataError(
            f"Example {example_name!r} has no recorded {prompt_version!r} output"
        )

    input_errors = iter_input_errors(input_doc)
    if input_errors:
        raise DemoDataError(f"Bundled input failed JSON Schema validation: {path}")
    TeachIntentInput.model_validate(input_doc)

    plan_doc = recorded_outputs[prompt_version]
    plan_errors = iter_speech_plan_errors(plan_doc)
    if plan_errors:
        raise DemoDataError(f"Bundled plan failed JSON Schema validation: {path}")
    SpeechPlan.model_validate(plan_doc)

    return {
        "title": doc["title"],
        "description": doc["description"],
        "source": doc["source"],
        "input": input_doc,
        "speech_plan": plan_doc,
        "prompt_version": prompt_version,
    }


def _run_live(input_doc: dict, prompt_version: str) -> tuple[dict, dict]:
    """Generate one plan through the real Hy3 pipeline."""
    load_dotenv(REPO_ROOT / ".env")
    client = Hy3Client.from_env()
    result = generate_speech_plan(
        input_doc,
        client,
        prompt_version=prompt_version,
    )
    source = {
        "evidence_kind": "live_demo_not_research_evidence",
        "requested_model": result.requested_model,
        "reported_model": result.reported_model,
        "prompt_version": result.prompt_version,
        "temperature": 0,
        "duration_seconds": round(result.duration_seconds, 3),
    }
    return result.plan_doc, source


def build_demo_payload(example: dict, *, mode: str) -> dict:
    """Build a stable, machine-readable public demo payload."""
    input_doc = example["input"]
    plan_doc = example["speech_plan"]
    return {
        "application": "TeachIntent",
        "mode": mode,
        "prompt_version": example["prompt_version"],
        "example": {
            "title": example["title"],
            "description": example["description"],
        },
        "input_context": {
            "output_language": input_doc["output_language"],
            "instructional_content": input_doc["instructional_content"],
            "pedagogical_context": input_doc["pedagogical_context"],
            "learner": input_doc["learner"],
        },
        "pedagogical_intent": input_doc["pedagogical_intent"]["primary"],
        "generated_speech_plan": plan_doc,
        "verbal_plan": plan_doc["verbal_plan"],
        "delivery_plan": plan_doc["delivery_plan"],
        "source": example["source"],
    }


def render_demo(payload: dict) -> str:
    """Render the demo payload for a terminal or screen recording."""
    context = payload["input_context"]
    content = context["instructional_content"]
    pedagogical_context = context["pedagogical_context"]
    learner = context["learner"]
    mode_label = (
        "recorded Hy3 artifact (offline; no API call)"
        if payload["mode"] == "recorded"
        else "live Hy3 generation"
    )
    learner_fields = ", ".join(
        f"{key}={value}" for key, value in learner.items()
    )
    lines = [
        "TeachIntent — Pedagogical Intent Driven Speech Planning",
        f"Mode: {mode_label}",
        f"Prompt version: {payload['prompt_version']}",
        "",
        "[Input context]",
        f"Subject / topic: {content.get('subject', 'n/a')} / {content.get('topic', 'n/a')}",
        f"Content anchor: {content['content_anchor']}",
        f"Scenario: {pedagogical_context['scenario']}",
        f"Learner utterance: {pedagogical_context.get('learner_utterance', 'n/a')}",
        f"Learner: {learner_fields}",
        "",
        "[Pedagogical intent]",
        payload["pedagogical_intent"],
        "",
        "[Generated Speech Plan]",
        f"schema_version: {payload['generated_speech_plan']['schema_version']}",
        "",
        "verbal_plan:",
        json.dumps(payload["verbal_plan"], ensure_ascii=False, indent=2),
        "",
        "delivery_plan:",
        json.dumps(payload["delivery_plan"], ensure_ascii=False, indent=2),
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Show a validated recorded Hy3 Speech Plan, or add --live to make "
            "one real Hy3 call using local .env configuration."
        )
    )
    parser.add_argument(
        "--example",
        choices=sorted(EXAMPLE_FILES),
        default="corrective-feedback",
        help="Representative teaching scenario (default: corrective-feedback).",
    )
    parser.add_argument(
        "--prompt-version",
        choices=PUBLIC_PROMPT_VERSIONS,
        default="v0.2",
        help="Recorded or live prompt version (default: v0.2).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call Hy3 once. Without this flag the demo is offline and deterministic.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete demo payload as JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        example = load_recorded_example(args.example, args.prompt_version)
        mode = "recorded"
        if args.live:
            plan_doc, source = _run_live(example["input"], args.prompt_version)
            example["speech_plan"] = plan_doc
            example["source"] = source
            mode = "live"
        payload = build_demo_payload(example, mode=mode)
    except (DemoDataError, GeneratorError, OSError, ValueError) as exc:
        print(f"TeachIntent demo failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_demo(payload))
    return 0


__all__ = [
    "DemoDataError",
    "EXAMPLE_FILES",
    "PUBLIC_PROMPT_VERSIONS",
    "build_demo_payload",
    "build_parser",
    "load_recorded_example",
    "main",
    "render_demo",
]
