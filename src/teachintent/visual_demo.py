"""Offline-first single-page demo helpers and optional Gradio application."""

from __future__ import annotations

import json
import os
import inspect
from pathlib import Path
from typing import Any, Callable

from . import demo
from .renderers.qwen3_tts import (
    AB_STATEMENT,
    DEFAULT_QWEN3_TTS_MODEL,
    Qwen3CustomVoiceBackend,
    build_qwen3_tts_instruction,
    render_ab_comparison,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIO_ROOT = REPO_ROOT / "results" / "tts_demo"
PRIMARY_EXAMPLE = "corrective-feedback"
PRIMARY_PROMPT_VERSION = "v0.2"
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


def _context_markdown(input_doc: dict[str, Any]) -> str:
    context = input_doc["pedagogical_context"]
    intent = input_doc["pedagogical_intent"]["primary"].replace("_", " ")
    return "\n".join(
        [
            "**Learner situation**",
            "",
            context["scenario"],
            "",
            f"> {context.get('learner_utterance', '')}",
            "",
            "**Pedagogical goal**",
            "",
            (
                f"Use {intent} to repair the misconception while keeping the "
                "student engaged and respected."
            ),
        ]
    )


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
        runner = live_runner or demo._run_live
        plan_doc, source = runner(example["input"], prompt_version)
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
    if neutral and planned:
        audio_status = (
            f"Loaded an existing local A/B pair from `{output_dir}`. {AB_STATEMENT}"
        )
    else:
        audio_status = (
            "No local A/B WAV pair exists for this selection. Audio is optional; "
            "install the TTS extra and render it explicitly on a compatible GPU."
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
        "raw_json": json.dumps(raw_payload, ensure_ascii=False, indent=2),
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

        gr.Markdown("## Teaching scenario", elem_classes=["ti-section"])
        context = gr.Markdown(
            initial["context_markdown"], elem_classes=["ti-card"]
        )

        gr.Markdown("## Generated Speech Plan", elem_classes=["ti-section"])
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
                "Offline recorded artifact. No Hy3 or Judge call is made by "
                "default. The TTS adapter is a downstream demo aid, not research "
                "evidence."
            )
            raw_json = gr.Code(
                value=initial["raw_json"],
                language="json",
                label="Validated payload",
            )
            evaluation = gr.Dataframe(
                headers=["Dimension", "Operational meaning", "Score", "Max"],
                value=initial["evaluation_rows"],
                interactive=False,
                label="Recorded evaluator scores",
            )
            evaluation_note = gr.Markdown(initial["evaluation_note"])
            mapping_report = gr.Code(
                value=json.dumps(
                    {
                        "planned_instruct": initial["tts_instruction"],
                        "supported_controls": initial["supported_controls"],
                        "unsupported_controls": initial["unsupported_controls"],
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
                return None, None, f"Audio render unavailable: {type(exc).__name__}: {exc}"

        render_button.click(
            render_ui,
            inputs=[state, speaker, model, audio_root_box],
            outputs=[neutral_audio, planned_audio, audio_status],
        )

    return app


__all__ = [
    "DEFAULT_AUDIO_ROOT",
    "DEMO_CSS",
    "EVALUATION_DIMENSIONS",
    "build_gradio_app",
    "build_visual_state",
    "find_audio_pair",
]
