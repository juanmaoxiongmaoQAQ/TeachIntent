"""Offline-first single-page demo helpers and optional Gradio application."""

from __future__ import annotations

import inspect
import html
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from . import demo
from .evaluator import DIMENSIONS, EvaluationRunContext
from .evaluator import JudgeCompleter, evaluate_speech_plan
from .evaluator_diagnostic.confirmatory_runner import (
    build_confirmatory_judge,
    build_frozen_judge_config,
)
from .generator import SpeechPlanGenerationResult
from .models import SpeechPlan, TeachIntentInput
from .renderers.qwen3_tts import (
    AB_STATEMENT,
    DEFAULT_QWEN3_TTS_MODEL,
    Qwen3CustomVoiceBackend,
    build_qwen3_tts_instruction,
    render_ab_comparison,
)
from .validators import iter_input_errors, iter_speech_plan_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIO_ROOT = REPO_ROOT / "results" / "tts_demo"
PRIMARY_EXAMPLE = "corrective-feedback"
PRIMARY_PROMPT_VERSION = "v0.2"
SHOWCASE_BADGE = "Recommended showcase"
SHOWCASE_SCENARIO_EXAMPLE = "corrective-feedback"
REVIEWER_EXAMPLES = (
    "corrective-feedback",
    "scaffolding",
    "supportive-feedback",
)
PEDAGOGICAL_INTENTS = (
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
)
CUSTOM_AUDIO_MESSAGE = "Audio rendering is available for curated demo cases only."
CUSTOM_EMPTY_DELIVERY_MESSAGE = (
    "No extra delivery control selected.\n\n"
    "Default voice rendering is recommended for this case."
)
CUSTOM_DELIVERY_STATUS = "Selective delivery control added"
EVALUATOR_VALIDATION_NOTE = (
    "Evaluator v0.1 was independently validated on 24 frozen "
    "reference/degraded pairs: 95.83% directional accuracy · "
    "99.62% within-one repeatability."
)
CUSTOM_EVALUATION_PLACEHOLDER = (
    "Evaluation unavailable\n\nGenerate a Speech Plan first, then click "
    "Evaluate this plan."
)
EVALUATION_NOT_RUN_MESSAGE = (
    "Evaluation not run yet\n\nGenerate the Speech Plan first,\nthen run the "
    "independent Evaluator."
)
SAFE_ERROR_PATTERNS = (
    (re.compile(r"Authorization:\s*Bearer\s+\S+"), "Authorization: [redacted]"),
    (re.compile(r"Bearer\s+\S+"), "Bearer [redacted]"),
    (re.compile(r"sk-[A-Za-z0-9_-]+"), "sk-[redacted]"),
    (re.compile(r"HY3_API_KEY=\S*"), "HY3_API_KEY=[redacted]"),
    (re.compile(r"\.env"), "[env-file]"),
)
DEMO_CSS = """
.ti-wrap {max-width: 1320px; margin: 0 auto;}
.ti-header {padding: 26px 0 12px;}
.ti-header h1 {font-size: 42px; line-height: 1.05; margin: 0;}
.ti-header p {font-size: 18px; margin: 8px 0 0; color: #424242;}
.ti-section h2 {font-size: 22px; margin-top: 20px;}
.ti-card {
    border: 1px solid #e4e4e7;
    border-radius: 12px;
    padding: 18px;
    background: #ffffff;
    min-height: 120px;
}
.ti-card h3 {margin-top: 0;}
.ti-workbench h3,
.ti-evidence h3,
.ti-context h3 {margin: 0 0 10px;}
.ti-context-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
.ti-context-item,
.ti-segment,
.ti-delivery-item,
.ti-evidence-item {
    border: 1px solid #ececef;
    border-radius: 10px;
    padding: 12px;
    background: #fcfcfd;
}
.ti-label {
    color: #6b7280;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: .04em;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.ti-value {white-space: pre-wrap;}
.ti-segment-id {
    color: #6b7280;
    font-size: 12px;
    margin-bottom: 4px;
}
.ti-panel-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #374151;
    margin: 4px 0 10px;
}
.ti-default-decision {
    border-left: 4px solid #16a34a;
}
.ti-scoreline {
    font-weight: 700;
    margin-bottom: 8px;
}
.ti-critical {
    border-top: 1px solid #ececef;
    margin-top: 14px;
    padding-top: 12px;
}
mark {background: #fff3a3; padding: 0 2px; border-radius: 3px;}
.ti-audio-card {
    border: 1px solid #d8d8dd;
    border-radius: 12px;
    padding: 18px;
    background: #fbfbfc;
}
.ti-ab-line {
    text-align: center;
    font-size: 18px;
    font-weight: 600;
    margin: 20px 0 14px;
}
.ti-muted {color: #666; font-size: 14px;}
.ti-showcase-badge {
    display: inline-block;
    color: #4b5563;
    font-size: 13px;
    margin-top: -4px;
}
"""

EVALUATION_DIMENSIONS = {
    "D1": "Pedagogical Intent Fidelity",
    "D2": "Content Faithfulness & Boundary",
    "D3": "Learner-State Compatibility",
    "D4": "Intent-Specific Instructional Adequacy",
    "D5": "Delivery Necessity & Sparsity",
    "D6": "Delivery–Pedagogy Alignment",
}
DIMENSION_DISPLAY = tuple(
    (f"D{index}", dimension_id, label)
    for index, (dimension_id, label) in enumerate(DIMENSIONS, start=1)
)
DIMENSION_LABELS = {
    "pedagogical_intent_fidelity": "Pedagogical Intent Fidelity",
    "content_faithfulness_boundary": "Content Faithfulness / Boundary",
    "learner_state_compatibility": "Learner-State Compatibility",
    "intent_specific_instructional_adequacy": "Instructional Adequacy",
    "delivery_necessity_sparsity": "Delivery Necessity / Sparsity",
    "delivery_pedagogy_alignment": "Delivery–Pedagogy Alignment",
}
DIMENSION_SHORT_LABELS = {
    "pedagogical_intent_fidelity": "Intent Fidelity",
    "content_faithfulness_boundary": "Content Faithfulness",
    "learner_state_compatibility": "Learner Compatibility",
    "intent_specific_instructional_adequacy": "Instructional Adequacy",
    "delivery_necessity_sparsity": "Delivery Sparsity",
    "delivery_pedagogy_alignment": "Delivery Alignment",
}
D_KEY_TO_DIMENSION = {d_key: dimension_id for d_key, dimension_id, _ in DIMENSION_DISPLAY}
PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR = (
    REPO_ROOT / "public_demo" / "evaluator_artifacts"
)
PUBLIC_DEMO_ARTIFACT_VERSION = "public-demo-evaluator-artifact-v1"

LiveRunner = Callable[[dict[str, Any], str], Any]
EvaluationRunner = Callable[
    [dict[str, Any], dict[str, Any], str, str, dict[str, Any]], dict[str, Any]
]


class CustomInputError(ValueError):
    """Raised when the custom live demo input is incomplete or invalid."""


def _pedagogical_goal(intent: str) -> str:
    if intent == "corrective_feedback":
        return (
            "Repair the misconception while keeping the student engaged and "
            "respected."
        )
    if intent == "scaffolding":
        return (
            "Give a focused hint that helps the student take the next reasoning "
            "step without taking over the work."
        )
    if intent == "supportive_feedback":
        return (
            "Recognize the student's progress and rebuild confidence without "
            "turning the moment into a full explanation."
        )
    return f"Use {intent.replace('_', ' ')} to support the next learning move."


def _context_markdown(input_doc: dict[str, Any]) -> str:
    context = input_doc["pedagogical_context"]
    intent = input_doc["pedagogical_intent"]["primary"]
    lines = [
        "**Learner situation**",
        "",
        context["scenario"],
    ]
    if context.get("learner_utterance"):
        lines.extend(["", f"> {context['learner_utterance']}"])
    lines.extend(
        [
            "",
            "**Pedagogical goal**",
            "",
            _pedagogical_goal(intent),
        ]
    )
    return "\n".join(lines)


def _custom_context_markdown(input_doc: dict[str, Any]) -> str:
    context = input_doc["pedagogical_context"]
    intent = input_doc["pedagogical_intent"]["primary"]
    lines = [
        "**Learner situation**",
        "",
        context["scenario"],
    ]
    if context.get("learner_utterance"):
        lines.extend(["", f"> {context['learner_utterance']}"])
    lines.extend(
        [
            "",
            "**Pedagogical intent**",
            "",
            f"`{intent}`",
        ]
    )
    return "\n".join(lines)


def _verbal_markdown(plan_doc: dict[str, Any]) -> str:
    return " ".join(
        segment["text"] for segment in plan_doc["verbal_plan"]["segments"]
    )


def _delivery_markdown(plan_doc: dict[str, Any]) -> str:
    delivery = plan_doc["delivery_plan"]
    if not delivery:
        return "No additional delivery controls."

    global_delivery = delivery.get("global", {})
    prosody = global_delivery.get("prosody", {})
    rows = []
    if global_delivery.get("attitudinal_tone"):
        rows.append(("Tone", global_delivery["attitudinal_tone"]))
    if global_delivery.get("emotion"):
        rows.append(("Emotion", global_delivery["emotion"]))
    if prosody.get("speaking_rate"):
        rows.append(("Speaking rate", prosody["speaking_rate"]))
    if prosody.get("volume"):
        rows.append(("Volume", prosody["volume"]))

    if not rows:
        return "No primary-page delivery controls. See technical details."
    return "\n".join(f"- **{label}:** {value}" for label, value in rows)


def _custom_delivery_markdown(plan_doc: dict[str, Any]) -> str:
    if not plan_doc["delivery_plan"]:
        return CUSTOM_EMPTY_DELIVERY_MESSAGE
    return f"{CUSTOM_DELIVERY_STATUS}\n\n{_delivery_markdown(plan_doc)}"


def _clean_optional(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _require_text(label: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise CustomInputError(f"{label} is required.")
    return cleaned


def build_custom_input(
    *,
    content_anchor: str,
    teaching_scenario: str,
    learner_utterance: str,
    learner_level: str,
    knowledge_state: str,
    affective_state: str,
    pedagogical_intent: str,
) -> dict[str, Any]:
    """Build and validate a custom TeachIntent input document for live demo use."""
    if pedagogical_intent not in PEDAGOGICAL_INTENTS:
        raise CustomInputError(
            f"Unsupported pedagogical intent: {pedagogical_intent}"
        )

    input_doc: dict[str, Any] = {
        "schema_version": "1.0.0-rc.2",
        "output_language": "zh-CN",
        "instructional_content": {
            "content_anchor": _require_text("Content anchor", content_anchor),
        },
        "pedagogical_context": {
            "scenario": _require_text("Teaching scenario", teaching_scenario),
        },
        "learner": {
            "level": _require_text("Learner level", learner_level),
            "knowledge_state": _require_text("Knowledge state", knowledge_state),
        },
        "pedagogical_intent": {"primary": pedagogical_intent},
    }

    optional_utterance = _clean_optional(learner_utterance)
    if optional_utterance:
        input_doc["pedagogical_context"]["learner_utterance"] = optional_utterance
    optional_affect = _clean_optional(affective_state)
    if optional_affect:
        input_doc["learner"]["affective_state"] = optional_affect

    validate_input_doc(input_doc)
    return input_doc


def load_showcase_scenario_fields(
    example_name: str = SHOWCASE_SCENARIO_EXAMPLE,
) -> tuple[str, str, str, str, str, str, str]:
    """Load a curated input into the custom form without loading its output."""
    if example_name not in REVIEWER_EXAMPLES:
        raise ValueError(f"Unsupported reviewer example: {example_name}")
    path = demo.EXAMPLE_FILES[example_name]
    doc = json.loads(path.read_text(encoding="utf-8"))
    input_doc = doc.get("input")
    if not isinstance(input_doc, dict):
        raise CustomInputError(f"Malformed showcase input: {path}")
    validate_input_doc(input_doc)

    pedagogical_context = input_doc["pedagogical_context"]
    learner = input_doc["learner"]
    return (
        input_doc["instructional_content"]["content_anchor"],
        pedagogical_context["scenario"],
        pedagogical_context.get("learner_utterance", ""),
        learner["level"],
        learner["knowledge_state"],
        learner.get("affective_state", ""),
        input_doc["pedagogical_intent"]["primary"],
    )


def validate_input_doc(input_doc: dict[str, Any]) -> None:
    errors = iter_input_errors(input_doc)
    if errors:
        first = errors[0]
        location = getattr(first, "json_path", "$")
        raise CustomInputError(
            f"Input validation failed at {location}: {first.message}"
        )
    try:
        TeachIntentInput.model_validate(input_doc)
    except ValueError as exc:
        raise CustomInputError(f"Input model validation failed: {exc}") from exc


def validate_speech_plan_doc(plan_doc: dict[str, Any]) -> None:
    errors = iter_speech_plan_errors(plan_doc)
    if errors:
        first = errors[0]
        location = getattr(first, "json_path", "$")
        raise ValueError(
            f"Speech Plan validation failed at {location}: {first.message}"
        )
    SpeechPlan.model_validate(plan_doc)


def sanitize_ui_text(value: object) -> str:
    text = str(value)
    for pattern, replacement in SAFE_ERROR_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def safe_json_dumps(value: object) -> str:
    return sanitize_ui_text(json.dumps(value, ensure_ascii=False, indent=2))


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _render_field(label: str, value: object) -> str:
    display = "Not provided" if value in (None, "") else value
    return (
        "<div class='ti-context-item'>"
        f"<div class='ti-label'>{_esc(label)}</div>"
        f"<div class='ti-value'>{_esc(display)}</div>"
        "</div>"
    )


def build_teaching_context_view(input_doc: dict[str, Any]) -> str:
    """Render original input fields as a reviewer-facing context card."""
    instructional_content = input_doc["instructional_content"]
    pedagogical_context = input_doc["pedagogical_context"]
    learner = input_doc["learner"]
    intent = input_doc["pedagogical_intent"]["primary"]
    fields = [
        ("Content anchor", instructional_content["content_anchor"]),
        ("Teaching scenario", pedagogical_context["scenario"]),
        ("Learner utterance", pedagogical_context.get("learner_utterance")),
        ("Pedagogical intent", intent),
        ("Level", learner["level"]),
        ("Knowledge state", learner["knowledge_state"]),
        ("Affective state", learner.get("affective_state")),
    ]
    return (
        "<div class='ti-card ti-context'>"
        "<h3>Teaching Context</h3>"
        "<div class='ti-context-grid'>"
        + "".join(_render_field(label, value) for label, value in fields)
        + "</div></div>"
    )


def build_verbal_plan_view(plan_doc: dict[str, Any]) -> str:
    """Render verbal_plan by segment without discarding segment identity."""
    segments = plan_doc["verbal_plan"]["segments"]
    segment_html = []
    for segment in segments:
        segment_html.append(
            "<div class='ti-segment'>"
            f"<div class='ti-segment-id'>{_esc(segment['segment_id'])}</div>"
            f"<div class='ti-value'>{_esc(segment['text'])}</div>"
            "</div>"
        )
    return (
        "<div class='ti-panel-title'>WHAT TO SAY</div>"
        + "".join(segment_html)
    )


def build_delivery_plan_view(plan_doc: dict[str, Any]) -> str:
    """Render delivery_plan as semantic decisions, never acoustic sliders."""
    delivery = plan_doc["delivery_plan"]
    if not delivery:
        return (
            "<div class='ti-panel-title'>HOW TO SAY</div>"
            "<div class='ti-delivery-item ti-default-decision'>"
            "<div class='ti-label'>Delivery decision</div>"
            "<div class='ti-value'>✓ Default rendering selected</div>"
            "<p>TeachIntent selected no additional delivery control for this case.</p>"
            "</div>"
        )

    global_delivery = delivery.get("global", {})
    prosody = global_delivery.get("prosody", {})
    rows = [("Delivery decision", CUSTOM_DELIVERY_STATUS), ("Scope", "Global")]
    if global_delivery.get("attitudinal_tone"):
        rows.append(("Attitudinal tone", global_delivery["attitudinal_tone"]))
    if global_delivery.get("emotion"):
        rows.append(("Emotion", global_delivery["emotion"]))
    if prosody.get("speaking_rate"):
        rows.append(("Speaking rate", prosody["speaking_rate"]))
    if prosody.get("volume"):
        rows.append(("Volume", prosody["volume"]))
    if len(rows) == 2:
        rows.append(("Details", "See Technical details for non-primary controls."))

    return (
        "<div class='ti-panel-title'>HOW TO SAY</div>"
        + "".join(
            "<div class='ti-delivery-item'>"
            f"<div class='ti-label'>{_esc(label)}</div>"
            f"<div class='ti-value'>{_esc(value)}</div>"
            "</div>"
            for label, value in rows
        )
    )


def classify_evidence_source(source: str) -> str:
    """Route evaluator evidence by source path only."""
    if source.startswith(
        (
            "input.",
            "instructional_content.",
            "pedagogical_context.",
            "learner.",
            "pedagogical_intent.",
        )
    ):
        return "input"
    if source.startswith(
        (
            "plan.",
            "speech_plan.",
            "verbal_plan.",
            "delivery_plan.",
        )
    ):
        return "speech_plan"
    return "unknown"


_PATH_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _path_tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for part in path.split("."):
        for match in _PATH_TOKEN_RE.finditer(part):
            key, index = match.groups()
            tokens.append(int(index) if index is not None else key)
    return tokens


def _lookup_path(doc: Any, path: str) -> Any:
    current = doc
    for token in _path_tokens(path):
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return None
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                return None
            current = current[token]
    return current


def _source_lookup_path(source: str, route: str) -> str:
    prefixes = (
        ("input.", "input"),
        ("plan.", "speech_plan"),
        ("speech_plan.", "speech_plan"),
    )
    for prefix, prefix_route in prefixes:
        if source.startswith(prefix) and route == prefix_route:
            return source[len(prefix) :]
    return source


def _source_value(
    input_doc: dict[str, Any],
    plan_doc: dict[str, Any],
    source: str,
) -> Any:
    route = classify_evidence_source(source)
    if route == "input":
        return _lookup_path(input_doc, _source_lookup_path(source, route))
    if route == "speech_plan":
        return _lookup_path(plan_doc, _source_lookup_path(source, route))
    return None


def _source_text(
    input_doc: dict[str, Any],
    plan_doc: dict[str, Any],
    source: str,
) -> str | None:
    value = _source_value(input_doc, plan_doc, source)
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def highlight_exact_text(full_text: str, evidence_text: str) -> str:
    """HTML-escape text and mark only exact raw substring matches."""
    index = full_text.find(evidence_text)
    if index < 0:
        return _esc(evidence_text)
    before = full_text[:index]
    match = full_text[index : index + len(evidence_text)]
    after = full_text[index + len(evidence_text) :]
    return f"{_esc(before)}<mark>{_esc(match)}</mark>{_esc(after)}"


def _evidence_item_state(
    input_doc: dict[str, Any],
    plan_doc: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    source = str(item.get("source", ""))
    text = str(item.get("text", ""))
    full_text = _source_text(input_doc, plan_doc, source)
    matched = full_text is not None and text in full_text
    return {
        "source": source,
        "text": text,
        "route": classify_evidence_source(source),
        "matched": matched,
        "html": highlight_exact_text(full_text, text) if matched else _esc(text),
    }


def build_evidence_trace(
    input_doc: dict[str, Any],
    plan_doc: dict[str, Any],
    evaluation_artifact: dict[str, Any] | None,
    dimension_id: str,
) -> dict[str, Any]:
    """Build a structured evidence trace from evaluator artifact fields only."""
    if not evaluation_artifact:
        return {"available": False, "reason": "No evaluator artifact is available."}
    scores = evaluation_artifact.get("scores") or {}
    dimension = scores.get(dimension_id)
    if not isinstance(dimension, dict):
        return {
            "available": False,
            "reason": f"No evaluator score is available for {dimension_id}.",
        }

    grouped = {"input": [], "speech_plan": [], "unknown": []}
    for item in dimension.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence = _evidence_item_state(input_doc, plan_doc, item)
        grouped[evidence["route"]].append(evidence)

    return {
        "available": True,
        "dimension_id": dimension_id,
        "dimension_key": _dimension_key_for_id(dimension_id),
        "label": DIMENSION_LABELS[dimension_id],
        "score": dimension.get("score"),
        "input_evidence": grouped["input"],
        "speech_plan_evidence": grouped["speech_plan"],
        "other_evidence": grouped["unknown"],
        "judge_rationale": str(dimension.get("brief_justification") or ""),
    }


def _dimension_key_for_id(dimension_id: str) -> str:
    for d_key, candidate, _label in DIMENSION_DISPLAY:
        if candidate == dimension_id:
            return d_key
    return dimension_id


def _dimension_id_from_selection(selection: str | None) -> str:
    if not selection:
        return DIMENSION_DISPLAY[0][1]
    d_key = selection.strip().split(maxsplit=1)[0]
    return D_KEY_TO_DIMENSION.get(d_key, DIMENSION_DISPLAY[0][1])


def _render_evidence_group(title: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rendered = [f"<h4>{_esc(title)}</h4>"]
    for item in items:
        evidence_label = "Highlighted source" if item["matched"] else "Evidence excerpt"
        rendered.append(
            "<div class='ti-evidence-item'>"
            f"<div class='ti-label'>{_esc(evidence_label)}</div>"
            f"<div class='ti-value'>{item['html']}</div>"
            f"<div class='ti-muted'>source: {_esc(item['source'])}</div>"
            "</div>"
        )
    return "".join(rendered)


def render_evidence_trace(trace: dict[str, Any]) -> str:
    if not trace.get("available"):
        return (
            "<div class='ti-card ti-evidence'>"
            "<h3>Evidence Trace</h3>"
            f"<p>{_esc(trace.get('reason', 'Evaluation not available.'))}</p>"
            "</div>"
        )
    return (
        "<div class='ti-card ti-evidence'>"
        "<h3>Evidence Trace</h3>"
        f"<div class='ti-scoreline'>{_esc(trace['dimension_key'])} "
        f"{_esc(trace['label'])}<br>Score: {_esc(trace['score'])} / 4</div>"
        + _render_evidence_group("Input evidence", trace["input_evidence"])
        + _render_evidence_group("Speech Plan evidence", trace["speech_plan_evidence"])
        + _render_evidence_group("Other grounded evidence", trace["other_evidence"])
        + "<h4>Judge rationale</h4>"
        f"<div class='ti-evidence-item'>{_esc(trace['judge_rationale'])}</div>"
        "</div>"
    )


def _score_for_dimension(scores: dict[str, Any], d_key: str, dimension_id: str) -> Any:
    if d_key in scores:
        return scores[d_key]
    value = scores.get(dimension_id)
    if isinstance(value, dict):
        return value.get("score")
    return value


def _justification_for_dimension(
    artifact: dict[str, Any] | None, dimension_id: str
) -> str:
    if not artifact:
        return ""
    score_obj = (artifact.get("scores") or {}).get(dimension_id)
    if isinstance(score_obj, dict):
        return str(score_obj.get("brief_justification") or "")
    return ""


def _critical_flags_for_display(
    evaluation: dict[str, Any], artifact: dict[str, Any] | None
) -> list[str]:
    if artifact is not None:
        flags = artifact.get("critical_flags") or []
        result = []
        for flag in flags:
            if isinstance(flag, dict):
                label = flag.get("flag", "")
                justification = flag.get("brief_justification", "")
                if justification:
                    result.append(f"{label}: {justification}")
                elif label:
                    result.append(str(label))
            else:
                result.append(str(flag))
        return result

    flags = evaluation.get("critical_flags") or []
    return [str(flag) for flag in flags]


def public_demo_evaluator_artifact_path(
    example_name: str,
    prompt_version: str,
) -> Path:
    """Return the committed public evaluator artifact path for a demo example."""
    safe_prompt_version = prompt_version.replace(".", "_")
    return PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR / (
        f"{example_name}.{safe_prompt_version}.json"
    )


def load_public_demo_evaluator_artifact(
    example_name: str,
    prompt_version: str = PRIMARY_PROMPT_VERSION,
) -> dict[str, Any] | None:
    """Load a portable recorded evaluator artifact without reading results/."""
    path = public_demo_evaluator_artifact_path(example_name, prompt_version)
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if artifact.get("artifact_version") != PUBLIC_DEMO_ARTIFACT_VERSION:
        return None
    if artifact.get("example_name") != example_name:
        return None
    if artifact.get("prompt_version") != prompt_version:
        return None
    scores = artifact.get("scores")
    if not isinstance(scores, dict):
        return None
    for _d_key, dimension_id, _label in DIMENSION_DISPLAY:
        score_obj = scores.get(dimension_id)
        if not isinstance(score_obj, dict):
            return None
        if "score" not in score_obj or not score_obj.get("brief_justification"):
            return None
        evidence = score_obj.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            return None
    return artifact


def _evaluation_markdown(
    evaluation: dict[str, Any] | None,
    *,
    heading: str,
    subheading: str,
    artifact: dict[str, Any] | None = None,
) -> str:
    if not evaluation or evaluation.get("available") is False:
        reason = (
            evaluation or {}
        ).get("reason", "No evaluator artifact is available.")
        return f"## Evaluation\n\nEvaluation unavailable\n\n{sanitize_ui_text(reason)}"

    scores = evaluation.get("scores") or {}
    lines = [
        "## Evaluation",
        "",
        heading,
        subheading,
        "",
    ]
    for d_key, dimension_id, _frozen_label in DIMENSION_DISPLAY:
        score = _score_for_dimension(scores, d_key, dimension_id)
        label = DIMENSION_LABELS[dimension_id]
        if score is None or score == "":
            lines.append(f"**{d_key} {label}**")
        else:
            lines.append(f"**{d_key} {label}** {score} / 4")
        justification = _justification_for_dimension(artifact, dimension_id)
        if justification:
            lines.append(f"  {justification}")
        lines.append("")

    flags = _critical_flags_for_display(evaluation, artifact)
    lines.append("**Critical flags**")
    lines.append("")
    lines.append("None" if not flags else "\n".join(f"- {flag}" for flag in flags))
    return "\n".join(lines)


def _recorded_evaluation_markdown(
    example_name: str,
    example: dict[str, Any],
) -> str:
    artifact = _recorded_evaluation_artifact(example_name, example)
    if artifact is None:
        return "## Evaluation\n\nRecorded evaluator artifact unavailable."
    recorded_evaluation = {
        "scores": artifact.get("scores") or {},
        "critical_flags": artifact.get("critical_flags") or [],
    }
    return _evaluation_markdown(
        recorded_evaluation,
        heading="Recorded Evaluator v0.1 result",
        subheading="Recorded existing evaluation evidence; no live Judge call.",
        artifact=artifact,
    )


def _recorded_evaluation_artifact(
    example_name: str,
    example: dict[str, Any],
) -> dict[str, Any] | None:
    return load_public_demo_evaluator_artifact(
        example_name,
        example["prompt_version"],
    )


def dimension_choices_for_artifact(artifact: dict[str, Any] | None) -> list[str]:
    if not artifact or not isinstance(artifact.get("scores"), dict):
        return []
    choices = []
    scores = artifact["scores"]
    for d_key, dimension_id, _label in DIMENSION_DISPLAY:
        score_obj = scores.get(dimension_id)
        if not isinstance(score_obj, dict):
            continue
        choices.append(
            f"{d_key}  {DIMENSION_SHORT_LABELS[dimension_id]}  "
            f"{score_obj.get('score', '')}/4"
        )
    return choices


def render_critical_flags(artifact: dict[str, Any] | None) -> str:
    flags = (artifact or {}).get("critical_flags") or []
    lines = [
        "<div class='ti-card ti-critical'>",
        "<h3>Critical flags</h3>",
    ]
    if not flags:
        lines.append("<p>None</p>")
    else:
        for flag in flags:
            if isinstance(flag, dict):
                lines.append(
                    "<div class='ti-evidence-item'>"
                    f"<div class='ti-label'>{_esc(flag.get('flag', ''))}</div>"
                    f"<div class='ti-value'>{_esc(flag.get('brief_justification', ''))}</div>"
                    "</div>"
                )
            else:
                lines.append(f"<div class='ti-evidence-item'>{_esc(flag)}</div>")
    lines.append("</div>")
    return "".join(lines)


def build_evaluation_workbench_state(
    input_doc: dict[str, Any] | None,
    plan_doc: dict[str, Any] | None,
    artifact: dict[str, Any] | None,
    *,
    unavailable_reason: str = EVALUATION_NOT_RUN_MESSAGE,
) -> dict[str, Any]:
    if not artifact or not isinstance(artifact.get("scores"), dict):
        return {
            "available": False,
            "input": input_doc,
            "speech_plan": plan_doc,
            "artifact": artifact,
            "dimension_choices": [],
            "selected_dimension": None,
            "evidence_trace_html": render_evidence_trace(
                {"available": False, "reason": unavailable_reason}
            ),
            "critical_flags_html": render_critical_flags(None),
        }

    choices = dimension_choices_for_artifact(artifact)
    selected = choices[0] if choices else None
    trace = build_evidence_trace(
        input_doc or {}, plan_doc or {}, artifact, _dimension_id_from_selection(selected)
    )
    return {
        "available": True,
        "input": input_doc,
        "speech_plan": plan_doc,
        "artifact": artifact,
        "dimension_choices": choices,
        "selected_dimension": selected,
        "evidence_trace_html": render_evidence_trace(trace),
        "critical_flags_html": render_critical_flags(artifact),
    }


def select_evidence_trace(
    evaluation_state: dict[str, Any] | None,
    selected_dimension: str | None,
) -> str:
    if not evaluation_state or not evaluation_state.get("available"):
        return render_evidence_trace(
            {"available": False, "reason": EVALUATION_NOT_RUN_MESSAGE}
        )
    trace = build_evidence_trace(
        evaluation_state["input"],
        evaluation_state["speech_plan"],
        evaluation_state["artifact"],
        _dimension_id_from_selection(selected_dimension),
    )
    return render_evidence_trace(trace)


def _evaluator_result_to_state(result: Any) -> dict[str, Any]:
    if result.failure is not None:
        return {
            "available": False,
            "failure_summary": result.failure.summary,
            "failure_type": result.failure.failure_type,
            "artifact": None,
            "judge_raw_response_available": result.judge_raw_response is not None,
        }
    if result.artifact is None:
        return {
            "available": False,
            "failure_summary": "Evaluator returned neither artifact nor failure.",
            "failure_type": "internal_evaluator_error",
            "artifact": None,
            "judge_raw_response_available": False,
        }
    artifact = result.artifact.model_dump(mode="json")
    if not result.artifact.structural_valid or result.artifact.scores is None:
        summary = "Generator raw response did not pass evaluator Layer-0 gate."
        if result.artifact.gate_failure is not None:
            summary = (
                f"{summary} {result.artifact.gate_failure.stage}: "
                f"{result.artifact.gate_failure.summary}"
            )
        return {
            "available": False,
            "failure_summary": summary,
            "failure_type": "evaluator_layer0_gate_failure",
            "artifact": artifact,
            "judge_raw_response_available": result.judge_raw_response is not None,
        }
    return {
        "available": True,
        "artifact": artifact,
        "judge_raw_response_available": result.judge_raw_response is not None,
    }


def _live_evaluation_markdown(evaluation: dict[str, Any]) -> str:
    if not evaluation.get("available"):
        summary = evaluation.get(
            "failure_summary", "The independent Judge did not return a usable artifact."
        )
        return (
            "## Evaluation\n\n"
            "Evaluation unavailable\n\n"
            f"{sanitize_ui_text(summary)}\n\n"
            f"{EVALUATOR_VALIDATION_NOTE}"
        )

    artifact = evaluation["artifact"]
    score_map = {
        dimension_id: value
        for dimension_id, value in (artifact.get("scores") or {}).items()
    }
    markdown = _evaluation_markdown(
        {"scores": score_map, "critical_flags": artifact.get("critical_flags", [])},
        heading="Live Evaluator v0.1 · Independent Judge",
        subheading="",
        artifact=artifact,
    )
    return f"{markdown}\n\n{EVALUATOR_VALIDATION_NOTE}"


def _evaluation_view(
    recorded_evaluation: dict[str, Any] | None,
    *,
    mode: str,
) -> tuple[list[list[Any]], str]:
    if mode == "live":
        return [], (
            "Live Hy3 output is not automatically judged in this demo. The frozen "
            "Evaluator v0.1 is shown only for matching recorded release artifacts."
        )
    if not recorded_evaluation or recorded_evaluation.get("available") is False:
        reason = (
            recorded_evaluation or {}
        ).get("reason", "No matching recorded evaluator artifact is available.")
        return [], reason

    scores = recorded_evaluation["scores"]
    rows = [
        [dimension, label, scores[dimension], "4"]
        for dimension, label in EVALUATION_DIMENSIONS.items()
    ]
    note = (
        f"Recorded evidence only — release sanity run "
        f"`{recorded_evaluation['run_id']}`, Evaluator "
        f"{recorded_evaluation['evaluator_version']} / Judge Prompt "
        f"{recorded_evaluation['judge_prompt_version']}; overall "
        f"{recorded_evaluation['overall_score']:.2f}/100. No live judge call was made."
    )
    return rows, note


def find_audio_pair(
    audio_root: Path,
    example_name: str,
    prompt_version: str,
) -> tuple[Path | None, Path | None, Path]:
    """Find a complete recorded A/B pair without inventing missing audio."""
    output_dir = (
        Path(audio_root) / example_name / prompt_version.replace(".", "_")
    )
    neutral = output_dir / "neutral.wav"
    planned = output_dir / "planned.wav"
    if neutral.is_file() and planned.is_file():
        return neutral, planned, output_dir
    return None, None, output_dir


def build_visual_state(
    example_name: str,
    prompt_version: str,
    *,
    live_hy3: bool = False,
    audio_root: Path = DEFAULT_AUDIO_ROOT,
    live_runner: LiveRunner | None = None,
) -> dict[str, Any]:
    """Build all UI content; deterministic and dependency-free offline."""
    example = demo.load_recorded_example(example_name, prompt_version)
    mode = "recorded"
    if live_hy3:
        runner = live_runner or demo.run_live_generation_result
        plan_doc, source, _raw_response = _normalize_live_generation_output(
            runner(example["input"], prompt_version)
        )
        validate_speech_plan_doc(plan_doc)
        example["speech_plan"] = plan_doc
        example["source"] = source
        example["recorded_evaluation"] = None
        mode = "live"

    plan_doc = example["speech_plan"]
    mapping = build_qwen3_tts_instruction(plan_doc["delivery_plan"])
    evaluation_rows, evaluation_note = _evaluation_view(
        example.get("recorded_evaluation"), mode=mode
    )
    neutral, planned, output_dir = find_audio_pair(
        audio_root, example_name, prompt_version
    )
    has_delivery_instruction = mapping.instruct != ""
    if neutral and planned:
        audio_status = (
            f"Loaded an existing local A/B pair from `{output_dir}`. {AB_STATEMENT}"
        )
    else:
        audio_status = (
            "No local A/B WAV pair exists for this selection. Audio is optional; "
            "install the TTS extra and render it explicitly on a compatible GPU."
        )
    if not has_delivery_instruction:
        audio_status = (
            f"{audio_status} This case has no additional delivery instruction; "
            "planned TTS uses the same empty instruction as neutral TTS."
        )

    recorded_artifact = _recorded_evaluation_artifact(example_name, example)
    evaluation_state = build_evaluation_workbench_state(
        example["input"],
        plan_doc,
        recorded_artifact,
        unavailable_reason="Recorded evaluator artifact unavailable.",
    )
    raw_payload = demo.build_demo_payload(example, mode=mode)
    return {
        "example_name": example_name,
        "prompt_version": prompt_version,
        "mode": mode,
        "example": example,
        "title": example["title"],
        "context_html": build_teaching_context_view(example["input"]),
        "context_markdown": _context_markdown(example["input"]),
        "what_to_say_html": build_verbal_plan_view(plan_doc),
        "verbal_markdown": _verbal_markdown(plan_doc),
        "how_to_say_html": build_delivery_plan_view(plan_doc),
        "delivery_markdown": _delivery_markdown(plan_doc),
        "evaluation_markdown": _recorded_evaluation_markdown(example_name, example),
        "evaluation_artifact": recorded_artifact,
        "evaluation_state": evaluation_state,
        "dimension_choices": evaluation_state["dimension_choices"],
        "selected_dimension": evaluation_state["selected_dimension"],
        "evidence_trace_html": evaluation_state["evidence_trace_html"],
        "critical_flags_html": evaluation_state["critical_flags_html"],
        "raw_json": safe_json_dumps(raw_payload),
        "evaluation_rows": evaluation_rows,
        "evaluation_note": evaluation_note,
        "tts_instruction": mapping.instruct,
        "supported_controls": list(mapping.supported_controls),
        "unsupported_controls": list(mapping.unsupported_controls),
        "neutral_audio": str(neutral) if neutral else None,
        "planned_audio": str(planned) if planned else None,
        "audio_output_dir": str(output_dir),
        "audio_status": audio_status,
    }


def _ui_outputs(state: dict[str, Any]) -> tuple[Any, ...]:
    mapping_report = {
        "planned_instruct": state["tts_instruction"],
        "supported_controls": state["supported_controls"],
        "unsupported_controls": state["unsupported_controls"],
    }
    return (
        state,
        state["context_html"],
        state["what_to_say_html"],
        state["how_to_say_html"],
        state["evaluation_state"],
        state["evaluation_markdown"],
        state["dimension_choices"],
        state["selected_dimension"],
        state["evidence_trace_html"],
        state["critical_flags_html"],
        state["raw_json"],
        state["evaluation_rows"],
        state["evaluation_note"],
        state["neutral_audio"],
        state["planned_audio"],
        state["audio_status"],
        json.dumps(mapping_report, ensure_ascii=False, indent=2),
    )


def switch_recorded_example(
    example_name: str,
    audio_root: str | Path = DEFAULT_AUDIO_ROOT,
) -> tuple[Any, ...]:
    """Build UI outputs for a reviewer case switch; prompt is fixed to v0.2."""
    if example_name not in REVIEWER_EXAMPLES:
        raise ValueError(f"Unsupported reviewer example: {example_name}")
    next_state = build_visual_state(
        example_name,
        PRIMARY_PROMPT_VERSION,
        audio_root=Path(audio_root),
    )
    return _ui_outputs(next_state)


def is_recommended_showcase(example_name: str) -> bool:
    return example_name == PRIMARY_EXAMPLE


def _source_from_generation_result(
    result: SpeechPlanGenerationResult,
) -> dict[str, Any]:
    return {
        "evidence_kind": "live_demo_not_research_evidence",
        "requested_model": result.requested_model,
        "reported_model": result.reported_model,
        "prompt_version": result.prompt_version,
        "temperature": 0,
        "duration_seconds": round(result.duration_seconds, 3),
    }


def _normalize_live_generation_output(
    value: Any,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    if isinstance(value, SpeechPlanGenerationResult):
        return value.plan_doc, _source_from_generation_result(value), value.raw_response
    if isinstance(value, tuple) and len(value) == 3:
        plan_doc, source, raw_response = value
        return plan_doc, source, raw_response
    if isinstance(value, tuple) and len(value) == 2:
        plan_doc, source = value
        return plan_doc, source, None
    raise TypeError("live runner must return SpeechPlanGenerationResult or a tuple")


def generate_custom_visual_state(
    *,
    content_anchor: str,
    teaching_scenario: str,
    learner_utterance: str,
    learner_level: str,
    knowledge_state: str,
    affective_state: str,
    pedagogical_intent: str,
    live_runner: LiveRunner | None = None,
) -> dict[str, Any]:
    """Generate one live custom Speech Plan through the existing Hy3 pipeline."""
    input_doc = build_custom_input(
        content_anchor=content_anchor,
        teaching_scenario=teaching_scenario,
        learner_utterance=learner_utterance,
        learner_level=learner_level,
        knowledge_state=knowledge_state,
        affective_state=affective_state,
        pedagogical_intent=pedagogical_intent,
    )
    runner = live_runner or demo.run_live_generation_result
    plan_doc, source, raw_response = _normalize_live_generation_output(
        runner(input_doc, PRIMARY_PROMPT_VERSION)
    )
    validate_speech_plan_doc(plan_doc)
    return {
        "mode": "live_custom",
        "input": input_doc,
        "speech_plan": plan_doc,
        "raw_response": raw_response,
        "prompt_version": PRIMARY_PROMPT_VERSION,
        "source": source,
        "status": "Generated live with Hy3 · Prompt v0.2",
        "context_html": build_teaching_context_view(input_doc),
        "context_markdown": _custom_context_markdown(input_doc),
        "what_to_say_html": build_verbal_plan_view(plan_doc),
        "verbal_markdown": _verbal_markdown(plan_doc),
        "how_to_say_html": build_delivery_plan_view(plan_doc),
        "delivery_markdown": _custom_delivery_markdown(plan_doc),
        "audio_status": CUSTOM_AUDIO_MESSAGE,
        "input_json": safe_json_dumps(input_doc),
        "speech_plan_json": safe_json_dumps(plan_doc),
        "source_json": safe_json_dumps(source),
    }


def _custom_success_outputs(state: dict[str, Any]) -> tuple[Any, ...]:
    return (
        state,
        state["status"],
        state["context_html"],
        state["what_to_say_html"],
        state["how_to_say_html"],
        state["audio_status"],
        "",
        state["input_json"],
        state["speech_plan_json"],
        state["source_json"],
    )


def generate_custom_ui(
    content_anchor: str,
    teaching_scenario: str,
    learner_utterance: str,
    learner_level: str,
    knowledge_state: str,
    affective_state: str,
    pedagogical_intent: str,
    live_runner: LiveRunner | None = None,
) -> tuple[Any, ...]:
    """Gradio-safe custom generation callback with no fallback behavior."""
    try:
        state = generate_custom_visual_state(
            content_anchor=content_anchor,
            teaching_scenario=teaching_scenario,
            learner_utterance=learner_utterance,
            learner_level=learner_level,
            knowledge_state=knowledge_state,
            affective_state=affective_state,
            pedagogical_intent=pedagogical_intent,
            live_runner=live_runner,
        )
    except CustomInputError as exc:
        return (
            None,
            f"Input error: {sanitize_ui_text(exc)}",
            "",
            "",
            "",
            CUSTOM_AUDIO_MESSAGE,
            "",
            "",
            "",
            "",
        )
    except Exception as exc:
        return (
            None,
            f"Hy3 generation failed: {sanitize_ui_text(exc)}",
            "",
            "",
            "",
            CUSTOM_AUDIO_MESSAGE,
            "",
            "",
            "",
            "",
        )
    return _custom_success_outputs(state)


def clear_custom_evaluation_on_input_change() -> tuple[None, str]:
    return None, ""


def load_showcase_scenario_ui() -> tuple[Any, ...]:
    return (*load_showcase_scenario_fields(), None, "")


def run_live_evaluation(
    input_doc: dict[str, Any],
    plan_doc: dict[str, Any],
    raw_response: str,
    prompt_version: str,
    source: dict[str, Any],
    *,
    judge: JudgeCompleter | None = None,
) -> dict[str, Any]:
    """Evaluate one live Hy3 result with the frozen Evaluator v0.1 condition."""
    del plan_doc
    load_dotenv(REPO_ROOT / ".env")
    live_judge = judge or build_confirmatory_judge()
    if live_judge is None:
        return {
            "available": False,
            "failure_summary": "OPENROUTER_API_KEY is not configured in local environment.",
            "failure_type": "setup_judge_config_error",
            "artifact": None,
            "judge_raw_response_available": False,
        }

    judge_config = build_frozen_judge_config(live_judge)
    run_context = EvaluationRunContext(
        input_case_id="visual-demo-live",
        generator_version=str(source.get("generator_version") or "v0.1"),
        prompt_version=prompt_version,
    )
    result = evaluate_speech_plan(
        input_doc, raw_response, run_context, judge_config, live_judge
    )
    return _evaluator_result_to_state(result)


def evaluate_custom_visual_state(
    state: dict[str, Any] | None,
    evaluation_runner: EvaluationRunner | None = None,
) -> str:
    if not state:
        return CUSTOM_EVALUATION_PLACEHOLDER
    raw_response = state.get("raw_response")
    if not isinstance(raw_response, str) or not raw_response.strip():
        return (
            "## Evaluation\n\n"
            "Evaluation unavailable\n\n"
            "The live Hy3 raw_response is unavailable, so the frozen Evaluator "
            "cannot evaluate this plan without fabricating Generator output."
        )
    runner = evaluation_runner or run_live_evaluation
    try:
        evaluation = runner(
            state["input"],
            state["speech_plan"],
            raw_response,
            state["prompt_version"],
            state["source"],
        )
    except Exception as exc:
        evaluation = {
            "available": False,
            "failure_summary": f"{type(exc).__name__}: {exc}",
        }
    return _live_evaluation_markdown(evaluation)


def evaluate_custom_workbench_state(
    state: dict[str, Any] | None,
    evaluation_runner: EvaluationRunner | None = None,
) -> dict[str, Any]:
    if not state:
        return build_evaluation_workbench_state(
            None, None, None, unavailable_reason=EVALUATION_NOT_RUN_MESSAGE
        )
    raw_response = state.get("raw_response")
    if not isinstance(raw_response, str) or not raw_response.strip():
        return build_evaluation_workbench_state(
            state.get("input"),
            state.get("speech_plan"),
            None,
            unavailable_reason=(
                "Evaluation unavailable\n\nThe live Hy3 raw_response is unavailable, "
                "so the frozen Evaluator cannot evaluate this plan without "
                "fabricating Generator output."
            ),
        )

    runner = evaluation_runner or run_live_evaluation
    try:
        evaluation = runner(
            state["input"],
            state["speech_plan"],
            raw_response,
            state["prompt_version"],
            state["source"],
        )
    except Exception as exc:
        evaluation = {
            "available": False,
            "failure_summary": f"{type(exc).__name__}: {exc}",
        }

    if not evaluation.get("available"):
        return build_evaluation_workbench_state(
            state["input"],
            state["speech_plan"],
            evaluation.get("artifact"),
            unavailable_reason=(
                "Evaluation unavailable\n\n"
                f"{sanitize_ui_text(evaluation.get('failure_summary', 'Unknown evaluator failure.'))}"
            ),
        )

    return build_evaluation_workbench_state(
        state["input"],
        state["speech_plan"],
        evaluation["artifact"],
    )


def _render_audio_for_state(
    state: dict[str, Any],
    speaker: str,
    model_id: str,
    audio_root: str,
) -> tuple[str | None, str | None, str]:
    neutral, planned, output_dir = find_audio_pair(
        Path(audio_root), state["example_name"], state["prompt_version"]
    )
    if neutral and planned:
        return str(neutral), str(planned), (
            f"Existing pair loaded. {AB_STATEMENT}"
        )

    backend = Qwen3CustomVoiceBackend(
        model_id=model_id or DEFAULT_QWEN3_TTS_MODEL,
        device_map=os.environ.get("QWEN3_TTS_DEVICE", "cuda:0"),
        dtype=os.environ.get("QWEN3_TTS_DTYPE", "bfloat16"),
        attn_implementation=os.environ.get("QWEN3_TTS_ATTN") or None,
    )
    render_ab_comparison(
        example=state["example"],
        backend=backend,
        speaker=speaker,
        output_dir=output_dir,
    )
    return str(output_dir / "neutral.wav"), str(output_dir / "planned.wav"), (
        f"A/B render complete. {AB_STATEMENT} Manifest: "
        f"`{output_dir / 'render_manifest.json'}`"
    )


def build_gradio_app(*, audio_root: Path = DEFAULT_AUDIO_ROOT) -> Any:
    """Create the optional Gradio app without making any model/API call."""
    try:
        import gradio as gr
    except ImportError as exc:
        raise RuntimeError(
            "The visual demo dependency is not installed. Run: "
            "pip install -e '.[demo]'"
        ) from exc

    initial = build_visual_state(
        PRIMARY_EXAMPLE, PRIMARY_PROMPT_VERSION, audio_root=audio_root
    )

    blocks_kwargs = {"title": "TeachIntent", "elem_classes": ["ti-wrap"]}
    if "css" not in inspect.signature(gr.Blocks.launch).parameters:
        blocks_kwargs["css"] = DEMO_CSS

    with gr.Blocks(**blocks_kwargs) as app:
        state = gr.State(initial)
        recorded_eval_state = gr.State(initial["evaluation_state"])
        gr.HTML(
            "<div class='ti-header'>"
            "<h1>TeachIntent</h1>"
            "<p>Pedagogical Speech Control Studio</p>"
            "<p>让 AI Tutor 不仅知道说什么，也知道怎么说</p>"
            "</div>"
        )

        def radio_update(evaluation_state: dict[str, Any]) -> Any:
            choices = evaluation_state.get("dimension_choices", [])
            return gr.update(
                choices=choices,
                value=evaluation_state.get("selected_dimension"),
                visible=bool(choices),
            )

        def hidden_radio_update() -> Any:
            return gr.update(choices=[], value=None, visible=False)

        with gr.Tabs():
            with gr.Tab("Explore"):
                example_picker = gr.Dropdown(
                    choices=list(REVIEWER_EXAMPLES),
                    value=PRIMARY_EXAMPLE,
                    label="Demo case",
                )
                showcase_badge = gr.Markdown(
                    SHOWCASE_BADGE,
                    elem_classes=["ti-showcase-badge"],
                    visible=is_recommended_showcase(PRIMARY_EXAMPLE),
                )

                context = gr.HTML(initial["context_html"])
                with gr.Row(elem_classes=["ti-workbench"]):
                    with gr.Column(scale=5):
                        speech_plan_panel = gr.HTML(
                            "<div class='ti-card'><h3>Speech Plan</h3>"
                            + initial["what_to_say_html"]
                            + initial["how_to_say_html"]
                            + "</div>",
                        )
                    with gr.Column(scale=4):
                        gr.Markdown("### Evaluation")
                        recorded_dimension = gr.Radio(
                            choices=initial["dimension_choices"],
                            value=initial["selected_dimension"],
                            label="Recorded Evaluator v0.1 result",
                            interactive=True,
                        )
                        recorded_trace = gr.HTML(initial["evidence_trace_html"])
                        recorded_flags = gr.HTML(initial["critical_flags_html"])

                gr.HTML(f"<div class='ti-ab-line'>{AB_STATEMENT}</div>")
                with gr.Row():
                    with gr.Column(elem_classes=["ti-audio-card"]):
                        gr.Markdown("### Without TeachIntent\nNeutral TTS")
                        neutral_audio = gr.Audio(
                            value=initial["neutral_audio"], label=None
                        )
                    with gr.Column(elem_classes=["ti-audio-card"]):
                        gr.Markdown("### With TeachIntent\nPlanned TTS")
                        planned_audio = gr.Audio(
                            value=initial["planned_audio"], label=None
                        )
                audio_status = gr.Markdown(
                    initial["audio_status"], elem_classes=["ti-muted"]
                )

                with gr.Accordion("Technical details", open=False):
                    gr.Markdown(
                        "Offline recorded artifact. No Hy3 or Judge call is "
                        "made by default. The TTS adapter is a downstream demo "
                        "aid, not research evidence."
                    )
                    raw_json = gr.Code(
                        value=initial["raw_json"],
                        language="json",
                        label="Validated payload",
                    )
                    evaluation = gr.Dataframe(
                        headers=[
                            "Dimension",
                            "Operational meaning",
                            "Score",
                            "Max",
                        ],
                        value=initial["evaluation_rows"],
                        interactive=False,
                        label="Recorded evaluator scores",
                    )
                    evaluation_note = gr.Markdown(initial["evaluation_note"])
                    mapping_report = gr.Code(
                        value=json.dumps(
                            {
                                "planned_instruct": initial["tts_instruction"],
                                "supported_controls": initial[
                                    "supported_controls"
                                ],
                                "unsupported_controls": initial[
                                    "unsupported_controls"
                                ],
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        language="json",
                        label="Auditable delivery mapping",
                    )
                    with gr.Row():
                        speaker = gr.Textbox(value="Vivian", label="Qwen speaker")
                        model = gr.Textbox(
                            value=os.environ.get(
                                "QWEN3_TTS_MODEL", DEFAULT_QWEN3_TTS_MODEL
                            ),
                            label="Qwen model ID or local path",
                        )
                        audio_root_box = gr.Textbox(
                            value=str(audio_root), label="Local audio root"
                        )
                    render_button = gr.Button("Render optional A/B audio locally")

                def switch_recorded_example_ui(
                    example_name: str, selected_audio_root: str
                ) -> tuple[Any, ...]:
                    outputs = switch_recorded_example(example_name, selected_audio_root)
                    next_state = outputs[0]
                    speech_panel = (
                        "<div class='ti-card'><h3>Speech Plan</h3>"
                        + next_state["what_to_say_html"]
                        + next_state["how_to_say_html"]
                        + "</div>"
                    )
                    return (
                        next_state,
                        next_state["evaluation_state"],
                        next_state["context_html"],
                        gr.update(value=speech_panel, visible=True),
                        radio_update(next_state["evaluation_state"]),
                        next_state["evidence_trace_html"],
                        next_state["critical_flags_html"],
                        next_state["raw_json"],
                        next_state["evaluation_rows"],
                        next_state["evaluation_note"],
                        next_state["neutral_audio"],
                        next_state["planned_audio"],
                        next_state["audio_status"],
                        outputs[-1],
                    )

                example_picker.change(
                    switch_recorded_example_ui,
                    inputs=[example_picker, audio_root_box],
                    outputs=[
                        state,
                        recorded_eval_state,
                        context,
                        speech_plan_panel,
                        recorded_dimension,
                        recorded_trace,
                        recorded_flags,
                        raw_json,
                        evaluation,
                        evaluation_note,
                        neutral_audio,
                        planned_audio,
                        audio_status,
                        mapping_report,
                    ],
                )

                def showcase_badge_ui(example_name: str) -> Any:
                    return gr.update(visible=is_recommended_showcase(example_name))

                example_picker.change(
                    showcase_badge_ui,
                    inputs=[example_picker],
                    outputs=[showcase_badge],
                )
                recorded_dimension.change(
                    select_evidence_trace,
                    inputs=[recorded_eval_state, recorded_dimension],
                    outputs=[recorded_trace],
                )

                def render_ui(
                    current_state: dict[str, Any],
                    selected_speaker: str,
                    selected_model: str,
                    selected_audio_root: str,
                ) -> tuple[str | None, str | None, str]:
                    try:
                        return _render_audio_for_state(
                            current_state,
                            selected_speaker,
                            selected_model,
                            selected_audio_root,
                        )
                    except Exception as exc:
                        summary = sanitize_ui_text(f"{type(exc).__name__}: {exc}")
                        return None, None, f"Audio render unavailable: {summary}"

                render_button.click(
                    render_ui,
                    inputs=[state, speaker, model, audio_root_box],
                    outputs=[neutral_audio, planned_audio, audio_status],
                )

            with gr.Tab("Live Studio"):
                custom_state = gr.State(None)
                custom_eval_state = gr.State(
                    build_evaluation_workbench_state(
                        None, None, None, unavailable_reason=EVALUATION_NOT_RUN_MESSAGE
                    )
                )
                gr.Markdown("## Live Studio", elem_classes=["ti-section"])
                with gr.Row():
                    with gr.Column():
                        custom_content = gr.Textbox(
                            label="Content anchor",
                            lines=4,
                        )
                        custom_scenario = gr.Textbox(
                            label="Teaching scenario",
                            lines=4,
                        )
                        custom_utterance = gr.Textbox(
                            label="Learner utterance",
                            lines=2,
                        )
                    with gr.Column():
                        custom_level = gr.Textbox(label="Learner level")
                        custom_knowledge = gr.Textbox(
                            label="Knowledge state",
                            lines=3,
                        )
                        custom_affect = gr.Textbox(label="Affective state")
                        custom_intent = gr.Dropdown(
                            choices=list(PEDAGOGICAL_INTENTS),
                            value="corrective_feedback",
                            label="Pedagogical intent",
                        )
                load_showcase_button = gr.Button("Load showcase scenario")
                custom_button = gr.Button("Generate with Hy3", variant="primary")
                custom_status = gr.Markdown("")
                custom_context = gr.HTML("")
                with gr.Row(elem_classes=["ti-workbench"]):
                    with gr.Column(scale=5):
                        custom_speech_plan = gr.HTML(
                            "<div class='ti-card'><h3>Speech Plan</h3></div>"
                        )
                        custom_audio_status = gr.Markdown(
                            CUSTOM_AUDIO_MESSAGE, elem_classes=["ti-muted"]
                        )
                    with gr.Column(scale=4):
                        gr.Markdown("### Evaluation")
                        evaluate_button = gr.Button("Evaluate this plan")
                        custom_dimension = gr.Radio(
                            choices=[],
                            value=None,
                            label="Live Evaluator v0.1 · Independent Judge",
                            interactive=True,
                            visible=False,
                        )
                        custom_trace = gr.HTML(
                            render_evidence_trace(
                                {
                                    "available": False,
                                    "reason": EVALUATION_NOT_RUN_MESSAGE,
                                }
                            )
                        )
                        custom_flags = gr.HTML(render_critical_flags(None))
                        gr.Markdown(
                            EVALUATOR_VALIDATION_NOTE, elem_classes=["ti-muted"]
                        )

                with gr.Accordion("Technical details", open=False):
                    custom_input_json = gr.Code(
                        value="",
                        language="json",
                        label="Validated input JSON",
                    )
                    custom_plan_json = gr.Code(
                        value="",
                        language="json",
                        label="Validated Speech Plan JSON",
                    )
                    custom_source_json = gr.Code(
                        value="",
                        language="json",
                        label="Source metadata",
                    )

                def generation_not_run_state() -> dict[str, Any]:
                    return build_evaluation_workbench_state(
                        None, None, None, unavailable_reason=EVALUATION_NOT_RUN_MESSAGE
                    )

                def generate_custom_workbench_ui(*args: Any) -> tuple[Any, ...]:
                    outputs = generate_custom_ui(*args)
                    next_state = outputs[0]
                    eval_state = generation_not_run_state()
                    if next_state is None:
                        speech_panel = "<div class='ti-card'><h3>Speech Plan</h3></div>"
                    else:
                        speech_panel = (
                            "<div class='ti-card'><h3>Speech Plan</h3>"
                            + next_state["what_to_say_html"]
                            + next_state["how_to_say_html"]
                            + "</div>"
                        )
                    return (
                        next_state,
                        eval_state,
                        outputs[1],
                        outputs[2],
                        speech_panel,
                        outputs[5],
                        hidden_radio_update(),
                        eval_state["evidence_trace_html"],
                        eval_state["critical_flags_html"],
                        outputs[7],
                        outputs[8],
                        outputs[9],
                    )

                def evaluate_custom_workbench_ui(
                    current_state: dict[str, Any] | None,
                ) -> tuple[Any, ...]:
                    eval_state = evaluate_custom_workbench_state(current_state)
                    return (
                        eval_state,
                        radio_update(eval_state),
                        eval_state["evidence_trace_html"],
                        eval_state["critical_flags_html"],
                    )

                def clear_custom_workbench_ui() -> tuple[Any, ...]:
                    eval_state = generation_not_run_state()
                    return (
                        None,
                        eval_state,
                        hidden_radio_update(),
                        eval_state["evidence_trace_html"],
                        eval_state["critical_flags_html"],
                    )

                def load_showcase_workbench_ui() -> tuple[Any, ...]:
                    eval_state = generation_not_run_state()
                    return (
                        *load_showcase_scenario_fields(),
                        None,
                        eval_state,
                        hidden_radio_update(),
                        eval_state["evidence_trace_html"],
                        eval_state["critical_flags_html"],
                    )

                load_showcase_button.click(
                    load_showcase_workbench_ui,
                    outputs=[
                        custom_content,
                        custom_scenario,
                        custom_utterance,
                        custom_level,
                        custom_knowledge,
                        custom_affect,
                        custom_intent,
                        custom_state,
                        custom_eval_state,
                        custom_dimension,
                        custom_trace,
                        custom_flags,
                    ],
                )

                custom_button.click(
                    generate_custom_workbench_ui,
                    inputs=[
                        custom_content,
                        custom_scenario,
                        custom_utterance,
                        custom_level,
                        custom_knowledge,
                        custom_affect,
                        custom_intent,
                    ],
                    outputs=[
                        custom_state,
                        custom_eval_state,
                        custom_status,
                        custom_context,
                        custom_speech_plan,
                        custom_audio_status,
                        custom_dimension,
                        custom_trace,
                        custom_flags,
                        custom_input_json,
                        custom_plan_json,
                        custom_source_json,
                    ],
                )

                evaluate_button.click(
                    evaluate_custom_workbench_ui,
                    inputs=[custom_state],
                    outputs=[
                        custom_eval_state,
                        custom_dimension,
                        custom_trace,
                        custom_flags,
                    ],
                )
                custom_dimension.change(
                    select_evidence_trace,
                    inputs=[custom_eval_state, custom_dimension],
                    outputs=[custom_trace],
                )

                custom_inputs = [
                    custom_content,
                    custom_scenario,
                    custom_utterance,
                    custom_level,
                    custom_knowledge,
                    custom_affect,
                    custom_intent,
                ]
                for custom_input in custom_inputs:
                    custom_input.change(
                        clear_custom_workbench_ui,
                        outputs=[
                            custom_state,
                            custom_eval_state,
                            custom_dimension,
                            custom_trace,
                            custom_flags,
                        ],
                    )

    return app


__all__ = [
    "CUSTOM_AUDIO_MESSAGE",
    "CUSTOM_DELIVERY_STATUS",
    "CUSTOM_EMPTY_DELIVERY_MESSAGE",
    "CUSTOM_EVALUATION_PLACEHOLDER",
    "EVALUATION_NOT_RUN_MESSAGE",
    "CustomInputError",
    "DEFAULT_AUDIO_ROOT",
    "DEMO_CSS",
    "EVALUATION_DIMENSIONS",
    "PEDAGOGICAL_INTENTS",
    "PRIMARY_EXAMPLE",
    "PRIMARY_PROMPT_VERSION",
    "PUBLIC_DEMO_ARTIFACT_VERSION",
    "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
    "REVIEWER_EXAMPLES",
    "SHOWCASE_BADGE",
    "SHOWCASE_SCENARIO_EXAMPLE",
    "build_delivery_plan_view",
    "build_evidence_trace",
    "build_custom_input",
    "build_evaluation_workbench_state",
    "build_gradio_app",
    "build_teaching_context_view",
    "build_verbal_plan_view",
    "build_visual_state",
    "clear_custom_evaluation_on_input_change",
    "classify_evidence_source",
    "dimension_choices_for_artifact",
    "evaluate_custom_workbench_state",
    "evaluate_custom_visual_state",
    "find_audio_pair",
    "generate_custom_ui",
    "generate_custom_visual_state",
    "highlight_exact_text",
    "is_recommended_showcase",
    "load_showcase_scenario_fields",
    "load_showcase_scenario_ui",
    "load_public_demo_evaluator_artifact",
    "public_demo_evaluator_artifact_path",
    "render_critical_flags",
    "render_evidence_trace",
    "run_live_evaluation",
    "select_evidence_trace",
    "switch_recorded_example",
]
