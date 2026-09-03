"""Offline-first single-page demo helpers and optional Gradio application."""

from __future__ import annotations

import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

from . import demo
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
SAFE_ERROR_PATTERNS = (
    (re.compile(r"Authorization:\s*Bearer\s+\S+"), "Authorization: [redacted]"),
    (re.compile(r"Bearer\s+\S+"), "Bearer [redacted]"),
    (re.compile(r"sk-[A-Za-z0-9_-]+"), "sk-[redacted]"),
    (re.compile(r"HY3_API_KEY=\S*"), "HY3_API_KEY=[redacted]"),
    (re.compile(r"\.env"), "[env-file]"),
)
DEMO_CSS = """
.ti-wrap {max-width: 1040px; margin: 0 auto;}
.ti-header {padding: 28px 0 12px;}
.ti-header h1 {font-size: 42px; line-height: 1.05; margin: 0;}
.ti-header p {font-size: 20px; margin: 8px 0 0; color: #424242;}
.ti-section h2 {font-size: 22px; margin-top: 20px;}
.ti-card {
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    padding: 18px;
    background: #ffffff;
    min-height: 160px;
}
.ti-card h3 {margin-top: 0;}
.ti-audio-card {
    border: 1px solid #d8d8dd;
    border-radius: 8px;
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

LiveRunner = Callable[[dict[str, Any], str], tuple[dict[str, Any], dict[str, Any]]]


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
        runner = live_runner or demo.run_live_generation
        plan_doc, source = runner(example["input"], prompt_version)
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

    raw_payload = demo.build_demo_payload(example, mode=mode)
    return {
        "example_name": example_name,
        "prompt_version": prompt_version,
        "mode": mode,
        "example": example,
        "title": example["title"],
        "context_markdown": _context_markdown(example["input"]),
        "verbal_markdown": _verbal_markdown(plan_doc),
        "delivery_markdown": _delivery_markdown(plan_doc),
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
        state["context_markdown"],
        state["verbal_markdown"],
        state["delivery_markdown"],
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
    runner = live_runner or demo.run_live_generation
    plan_doc, source = runner(input_doc, PRIMARY_PROMPT_VERSION)
    validate_speech_plan_doc(plan_doc)
    return {
        "mode": "live_custom",
        "input": input_doc,
        "speech_plan": plan_doc,
        "source": source,
        "status": "Generated live with Hy3 · Prompt v0.2",
        "context_markdown": _custom_context_markdown(input_doc),
        "verbal_markdown": _verbal_markdown(plan_doc),
        "delivery_markdown": _custom_delivery_markdown(plan_doc),
        "audio_status": CUSTOM_AUDIO_MESSAGE,
        "input_json": safe_json_dumps(input_doc),
        "speech_plan_json": safe_json_dumps(plan_doc),
        "source_json": safe_json_dumps(source),
    }


def _custom_success_outputs(state: dict[str, Any]) -> tuple[Any, ...]:
    return (
        state["status"],
        state["context_markdown"],
        state["verbal_markdown"],
        state["delivery_markdown"],
        state["audio_status"],
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
            f"Input error: {sanitize_ui_text(exc)}",
            "",
            "",
            "",
            CUSTOM_AUDIO_MESSAGE,
            "",
            "",
            "",
        )
    except Exception as exc:
        return (
            f"Hy3 generation failed: {sanitize_ui_text(exc)}",
            "",
            "",
            "",
            CUSTOM_AUDIO_MESSAGE,
            "",
            "",
            "",
        )
    return _custom_success_outputs(state)


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
        gr.HTML(
            "<div class='ti-header'>"
            "<h1>TeachIntent</h1>"
            "<p>让 AI Tutor 不仅知道说什么，也知道怎么说</p>"
            "</div>"
        )
        with gr.Tabs():
            with gr.Tab("Explore examples"):
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

                gr.Markdown("## Teaching scenario", elem_classes=["ti-section"])
                context = gr.Markdown(
                    initial["context_markdown"], elem_classes=["ti-card"]
                )

                gr.Markdown(
                    "## Generated Speech Plan", elem_classes=["ti-section"]
                )
                with gr.Row():
                    with gr.Column(elem_classes=["ti-card"]):
                        gr.Markdown("### What to say")
                        verbal = gr.Markdown(initial["verbal_markdown"])
                    with gr.Column(elem_classes=["ti-card"]):
                        gr.Markdown("### How to say")
                        delivery = gr.Markdown(initial["delivery_markdown"])

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

                case_outputs = [
                    state,
                    context,
                    verbal,
                    delivery,
                    raw_json,
                    evaluation,
                    evaluation_note,
                    neutral_audio,
                    planned_audio,
                    audio_status,
                    mapping_report,
                ]
                example_picker.change(
                    switch_recorded_example,
                    inputs=[example_picker, audio_root_box],
                    outputs=case_outputs,
                )

                def showcase_badge_ui(example_name: str) -> Any:
                    return gr.update(visible=is_recommended_showcase(example_name))

                example_picker.change(
                    showcase_badge_ui,
                    inputs=[example_picker],
                    outputs=[showcase_badge],
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

            with gr.Tab("Try your own scenario"):
                gr.Markdown("## Try your own scenario", elem_classes=["ti-section"])
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
                custom_context = gr.Markdown("")
                gr.Markdown(
                    "## Generated Speech Plan", elem_classes=["ti-section"]
                )
                with gr.Row():
                    with gr.Column(elem_classes=["ti-card"]):
                        gr.Markdown("### What to say")
                        custom_verbal = gr.Markdown("")
                    with gr.Column(elem_classes=["ti-card"]):
                        gr.Markdown("### How to say")
                        custom_delivery = gr.Markdown("")
                custom_audio_status = gr.Markdown(
                    CUSTOM_AUDIO_MESSAGE, elem_classes=["ti-muted"]
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

                load_showcase_button.click(
                    load_showcase_scenario_fields,
                    outputs=[
                        custom_content,
                        custom_scenario,
                        custom_utterance,
                        custom_level,
                        custom_knowledge,
                        custom_affect,
                        custom_intent,
                    ],
                )

                custom_button.click(
                    generate_custom_ui,
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
                        custom_status,
                        custom_context,
                        custom_verbal,
                        custom_delivery,
                        custom_audio_status,
                        custom_input_json,
                        custom_plan_json,
                        custom_source_json,
                    ],
                )

    return app


__all__ = [
    "CUSTOM_AUDIO_MESSAGE",
    "CUSTOM_DELIVERY_STATUS",
    "CUSTOM_EMPTY_DELIVERY_MESSAGE",
    "CustomInputError",
    "DEFAULT_AUDIO_ROOT",
    "DEMO_CSS",
    "EVALUATION_DIMENSIONS",
    "PEDAGOGICAL_INTENTS",
    "PRIMARY_EXAMPLE",
    "PRIMARY_PROMPT_VERSION",
    "REVIEWER_EXAMPLES",
    "SHOWCASE_BADGE",
    "SHOWCASE_SCENARIO_EXAMPLE",
    "build_custom_input",
    "build_gradio_app",
    "build_visual_state",
    "find_audio_pair",
    "generate_custom_ui",
    "generate_custom_visual_state",
    "is_recommended_showcase",
    "load_showcase_scenario_fields",
    "switch_recorded_example",
]
