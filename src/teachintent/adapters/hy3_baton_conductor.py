"""Hy3 pedagogical conductor for the BatonVoice quantitative contract."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from ..generator.client import Hy3Client, Hy3Completion
from ..generator.parser import _FENCE_RE

BATON_KEYS = (
    "word", "pitch_mean", "pitch_slope", "energy_rms", "energy_slope",
    "spectral_centroid",
)
BASELINE = {"pitch_mean": 226, "energy_rms": 0.008, "spectral_centroid": 1885}
ENERGY_RMS_MILLI = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
BATON_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_baton_plan",
        "description": "Return the executable BatonTTS quantitative vocal plan for the immutable spoken text.",
        "parameters": {
            "type": "object", "additionalProperties": False,
            "properties": {"plan": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "word": {"type": "string", "minLength": 1},
                    "pitch_mean": {"type": "integer"}, "pitch_slope": {"type": "integer"},
                    "energy_rms_milli": {"type": "integer", "enum": list(ENERGY_RMS_MILLI)},
                    "energy_slope": {"type": "integer"}, "spectral_centroid": {"type": "integer", "exclusiveMinimum": 0},
                }, "required": ["word", "pitch_mean", "pitch_slope", "energy_rms_milli", "energy_slope", "spectral_centroid"],
            }}}, "required": ["plan"],
        },
    },
}


class BatonPlanValidationError(ValueError):
    """Raised when a Hy3 response is not an executable Baton plan."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_LEXICAL_TOKEN_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)


def lexical_tokens(text: str) -> list[str]:
    """Extract ordered lexical tokens while retaining apostrophes and hyphens."""
    return _LEXICAL_TOKEN_RE.findall(text)


def validate_baton_plan(text: str, plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, list) or not plan:
        raise BatonPlanValidationError("plan must be a non-empty list")
    canonical: list[dict[str, Any]] = []
    for i, segment in enumerate(plan):
        if not isinstance(segment, dict):
            raise BatonPlanValidationError(f"segment {i} must be an object")
        if set(segment) != set(BATON_KEYS):
            raise BatonPlanValidationError(f"segment {i} keys must be exactly {list(BATON_KEYS)}")
        word = segment["word"]
        if not isinstance(word, str) or not word.strip():
            raise BatonPlanValidationError(f"segment {i}.word must be a non-empty string")
        integer_values: dict[str, int] = {}
        for key in ("pitch_mean", "pitch_slope", "energy_slope", "spectral_centroid"):
            value = segment[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BatonPlanValidationError(f"segment {i}.{key} must be an integer-valued number")
            if isinstance(value, float) and not value.is_integer():
                raise BatonPlanValidationError(f"segment {i}.{key} must be an integer-valued number")
            integer_values[key] = int(value)
        energy = segment["energy_rms"]
        if isinstance(energy, bool) or not isinstance(energy, (int, float)):
            raise BatonPlanValidationError(f"segment {i}.energy_rms must be numeric")
        values = [*integer_values.values(), energy]
        if not all(math.isfinite(float(v)) for v in values):
            raise BatonPlanValidationError(f"segment {i} contains non-finite numeric value")
        if integer_values["pitch_mean"] <= 0 or energy <= 0 or integer_values["spectral_centroid"] <= 0:
            raise BatonPlanValidationError(f"segment {i} has non-positive acoustic value")
        canonical.append({**segment, **integer_values, "energy_rms": round(float(energy), 3)})
    original_tokens = lexical_tokens(text)
    plan_tokens = lexical_tokens(" ".join(x["word"] for x in canonical))
    if plan_tokens != original_tokens:
        raise BatonPlanValidationError("plan lexical coverage does not match immutable text")
    return canonical


SYSTEM_PROMPT = f"""You are a pedagogical speech conductor.

Given immutable spoken text, teaching context, learner state, pedagogical intent,
and speaker acoustic baseline, produce an executable quantitative vocal plan for
BatonTTS. The spoken text is immutable: segment it, but never add, delete,
rewrite, paraphrase, or reorder content.

Each segment must contain exactly these six fields:
word, pitch_mean, pitch_slope, energy_rms, energy_slope, spectral_centroid

The fields are executable acoustic controls: pitch_mean and pitch_slope control
fundamental frequency and its contour; energy_rms and energy_slope control
amplitude and its contour; spectral_centroid controls spectral brightness.
Baseline: pitch_mean={BASELINE['pitch_mean']}, energy_rms={BASELINE['energy_rms']},
spectral_centroid={BASELINE['spectral_centroid']}.
Use phrase-level segmentation for natural spoken delivery and numeric variation for pedagogical intent. Never use one-word-per-segment unless a word is genuinely an independent semantic phrase. Prefer clause, punctuation, discourse, and pedagogical emphasis boundaries. Each segment should usually contain multiple consecutive words; for this sentence use approximately 4 to 7 natural phrases. Segment boundaries serve connected teaching expression, not word-by-word control.
Return ONLY a valid JSON array. No Markdown, explanations, or reasoning."""


@dataclass(frozen=True)
class BatonConductorResult:
    plan: list[dict[str, Any]]
    raw_response: str
    completion: Hy3Completion


def decode_tool_plan(tool_plan: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_plan, list) or not tool_plan:
        raise BatonPlanValidationError("tool plan must be a non-empty list")
    decoded: list[dict[str, Any]] = []
    for i, segment in enumerate(tool_plan):
        if not isinstance(segment, dict):
            raise BatonPlanValidationError(f"tool segment {i} must be an object")
        value = segment.get("energy_rms_milli")
        if isinstance(value, bool) or not isinstance(value, int) or value not in ENERGY_RMS_MILLI:
            raise BatonPlanValidationError(f"segment {i}.energy_rms_milli must be one of {list(ENERGY_RMS_MILLI)}")
        decoded.append({**{k: segment[k] for k in segment if k != "energy_rms_milli"}, "energy_rms": value / 1000.0})
    return decoded


class Hy3BatonConductor:
    def __init__(self, client: Hy3Client) -> None:
        self.client = client

    def conduct(self, *, content: str, pedagogical_context: str,
                learner_information: str, pedagogical_intent: str,
                goal: str = "", on_raw_response: Callable[[str], None] | None = None,
                force_tool_call: bool = False) -> BatonConductorResult:
        user = json.dumps({
            "spoken_text": content,
            "teaching_context": pedagogical_context,
            "learner_state": learner_information,
            "pedagogical_intent": pedagogical_intent,
            "goal": goal,
            "speaker_acoustic_baseline": BASELINE,
        }, ensure_ascii=False, indent=2)
        prompt = SYSTEM_PROMPT
        if force_tool_call:
            prompt = """You are a pedagogical speech conductor.
Given immutable spoken text, pedagogical context, learner state, pedagogical intent, and speaker acoustic baseline, produce an executable BatonTTS vocal plan by calling emit_baton_plan. The spoken text is immutable: only segment it; never add, delete, rewrite, paraphrase, or reorder words. Use phrase-level segmentation for natural spoken delivery. Never use one-word-per-segment unless a word is genuinely an independent semantic phrase. Prefer clause, punctuation, discourse, and pedagogical emphasis boundaries; each segment should usually contain multiple consecutive words. For this 28-word sentence, produce approximately 4 to 7 natural phrases. Segment boundaries serve connected teaching expression, not word-by-word control. Baseline pitch_mean=226, energy_rms=0.008, spectral_centroid=1885. Do not answer in prose. Call emit_baton_plan exactly once."""
            prompt += " energy_rms_milli is RMS energy expressed in thousandths (4 means 0.004, 8 means 0.008, 12 means 0.012); choose one allowed integer from the tool schema. Neutral baseline is 8."
        completion = self.client.complete(
            prompt, user, temperature=0,
            tools=[BATON_TOOL] if force_tool_call else None,
            tool_choice={"type": "function", "function": {"name": "emit_baton_plan"}} if force_tool_call else None,
            parallel_tool_calls=False if force_tool_call else None,
        )
        if on_raw_response is not None:
            on_raw_response(completion.content if not force_tool_call else json.dumps(completion.tool_calls, ensure_ascii=False))
        if force_tool_call:
            calls = completion.tool_calls
            if not isinstance(calls, list) or len(calls) != 1:
                raise BatonPlanValidationError("expected exactly one emit_baton_plan tool call")
            call = calls[0]
            function = call.get("function") if isinstance(call, dict) else None
            if not isinstance(function, dict) or function.get("name") != "emit_baton_plan":
                raise BatonPlanValidationError("unexpected tool name")
            arguments = function.get("arguments")
            if not isinstance(arguments, str):
                raise BatonPlanValidationError("tool arguments must be a JSON string")
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise BatonPlanValidationError(f"invalid tool arguments JSON: {exc}") from exc
            if not isinstance(parsed, dict) or "plan" not in parsed:
                raise BatonPlanValidationError("tool arguments must contain plan")
            return BatonConductorResult(validate_baton_plan(content, decode_tool_plan(parsed["plan"])), arguments, completion)
        raw = completion.content.strip()
        match = _FENCE_RE.match(raw)
        if match:
            raw = match.group("body").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BatonPlanValidationError(f"invalid JSON: {exc}") from exc
        return BatonConductorResult(validate_baton_plan(content, parsed), completion.content, completion)
