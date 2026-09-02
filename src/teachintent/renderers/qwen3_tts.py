"""Conservative Speech Plan adapter for Qwen3-TTS CustomVoice.

This is an optional realization layer, not part of the frozen TeachIntent
research contracts. It supports a deliberately small global-control subset and
reports everything else as unsupported instead of inventing acoustic mappings.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

DEFAULT_QWEN3_TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
DEFAULT_TTS_SEED = 20260901
AB_STATEMENT = "Same words. Same voice. Different pedagogical delivery."

_RATE_INSTRUCTIONS = {
    "x-slow": "整体使用非常慢的语速。",
    "slow": "整体使用较慢的语速。",
    "medium": "整体使用自然、适中的语速。",
    "fast": "整体使用较快的语速。",
    "x-fast": "整体使用非常快的语速。",
}

_VOLUME_INSTRUCTIONS = {
    "x-soft": "整体使用非常轻柔的音量。",
    "soft": "整体使用较轻柔的音量。",
    "medium": "整体使用自然、适中的音量。",
    "loud": "整体使用较响亮的音量。",
    "x-loud": "整体使用非常响亮的音量。",
}

_DIMENSIONLESS_UNSUPPORTED_REASON = (
    "The current Qwen3-TTS demo adapter does not claim reliable realization "
    "for this control; it remains preserved in the source Speech Plan."
)
_SEGMENT_UNSUPPORTED_REASON = (
    "The current demo sends one utterance-level CustomVoice instruction and "
    "does not claim segment-local realization; the control remains preserved "
    "in the source Speech Plan."
)


class Qwen3TTSDependencyError(RuntimeError):
    """Raised when optional Qwen3-TTS runtime dependencies are unavailable."""


class TTSRenderError(RuntimeError):
    """Raised when a TTS A/B render cannot be completed safely."""


@dataclass(frozen=True)
class Qwen3TTSInstruction:
    """Auditable best-effort mapping from a delivery plan to `instruct`."""

    instruct: str
    supported_controls: tuple[dict[str, Any], ...]
    unsupported_controls: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class CustomVoiceBackend(Protocol):
    """Narrow backend seam used by the renderer and offline tests."""

    @property
    def model_id(self) -> str: ...

    def generate_custom_voice(
        self,
        *,
        text: str,
        language: str,
        speaker: str,
        instruct: str,
        output_path: Path,
        seed: int,
    ) -> dict[str, Any]: ...


def _supported(path: str, value: Any, fragment: str) -> dict[str, Any]:
    return {
        "path": path,
        "value": value,
        "instruction_fragment": fragment,
        "realization": "best_effort_natural_language_instruction",
    }


def _unsupported(path: str, value: Any, reason: str) -> dict[str, Any]:
    return {"path": path, "value": value, "reason": reason}


def build_qwen3_tts_instruction(delivery_plan: dict[str, Any]) -> Qwen3TTSInstruction:
    """Map the explicitly supported delivery subset to natural language.

    Supported fields are only utterance-level attitude, emotion, speaking rate,
    and volume. Pitch controls and every segment-level control are reported as
    unsupported. No F0, duration, prominence, or other acoustic value is
    fabricated.
    """
    fragments: list[str] = []
    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []

    global_plan = delivery_plan.get("global")
    if isinstance(global_plan, dict):
        tone = global_plan.get("attitudinal_tone")
        if tone is not None:
            fragment = f"整体采用“{tone}”的态度语气。"
            fragments.append(fragment)
            supported.append(
                _supported("delivery_plan.global.attitudinal_tone", tone, fragment)
            )

        emotion = global_plan.get("emotion")
        if emotion is not None:
            fragment = f"整体表达“{emotion}”的情绪。"
            fragments.append(fragment)
            supported.append(
                _supported("delivery_plan.global.emotion", emotion, fragment)
            )

        prosody = global_plan.get("prosody")
        if isinstance(prosody, dict):
            rate = prosody.get("speaking_rate")
            if rate is not None:
                if rate in _RATE_INSTRUCTIONS:
                    fragment = _RATE_INSTRUCTIONS[rate]
                    fragments.append(fragment)
                    supported.append(
                        _supported(
                            "delivery_plan.global.prosody.speaking_rate",
                            rate,
                            fragment,
                        )
                    )
                else:
                    unsupported.append(
                        _unsupported(
                            "delivery_plan.global.prosody.speaking_rate",
                            rate,
                            "Unknown schema value; no TTS instruction was invented.",
                        )
                    )

            volume = prosody.get("volume")
            if volume is not None:
                if volume in _VOLUME_INSTRUCTIONS:
                    fragment = _VOLUME_INSTRUCTIONS[volume]
                    fragments.append(fragment)
                    supported.append(
                        _supported(
                            "delivery_plan.global.prosody.volume", volume, fragment
                        )
                    )
                else:
                    unsupported.append(
                        _unsupported(
                            "delivery_plan.global.prosody.volume",
                            volume,
                            "Unknown schema value; no TTS instruction was invented.",
                        )
                    )

            for field in ("pitch_level", "pitch_range"):
                if field in prosody:
                    unsupported.append(
                        _unsupported(
                            f"delivery_plan.global.prosody.{field}",
                            prosody[field],
                            _DIMENSIONLESS_UNSUPPORTED_REASON,
                        )
                    )

    overrides = delivery_plan.get("segment_overrides")
    if isinstance(overrides, list):
        for index, override in enumerate(overrides):
            if not isinstance(override, dict):
                continue
            for field, value in override.items():
                if field == "segment_id":
                    continue
                unsupported.append(
                    _unsupported(
                        f"delivery_plan.segment_overrides[{index}].{field}",
                        value,
                        _SEGMENT_UNSUPPORTED_REASON,
                    )
                )

    return Qwen3TTSInstruction(
        instruct=" ".join(fragments),
        supported_controls=tuple(supported),
        unsupported_controls=tuple(unsupported),
    )


def verbal_text_from_plan(speech_plan: dict[str, Any]) -> str:
    """Return one exact renderer input string from ordered verbal segments."""
    segments = speech_plan["verbal_plan"]["segments"]
    text = " ".join(segment["text"] for segment in segments)
    if not text.strip():
        raise ValueError("Speech Plan verbal text must not be empty")
    return text


def qwen_language_from_bcp47(language: str) -> str:
    """Map common TeachIntent BCP-47 tags to Qwen3-TTS language names."""
    primary = language.strip().lower().split("-", 1)[0]
    return {
        "zh": "Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "de": "German",
        "fr": "French",
        "ru": "Russian",
        "pt": "Portuguese",
        "es": "Spanish",
        "it": "Italian",
    }.get(primary, "Auto")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_ab_comparison(
    *,
    example: dict[str, Any],
    backend: CustomVoiceBackend,
    speaker: str,
    output_dir: Path,
    seed: int = DEFAULT_TTS_SEED,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Render neutral/planned audio while varying only `instruct`.

    Both conditions use the same exact text, language, speaker, backend model,
    seed, and generation implementation. The neutral condition uses an empty
    instruction; the planned condition uses only the delivery-plan mapping.
    """
    speech_plan = example["speech_plan"]
    input_doc = example["input"]
    text = verbal_text_from_plan(speech_plan)
    language = qwen_language_from_bcp47(input_doc["output_language"])
    mapping = build_qwen3_tts_instruction(speech_plan["delivery_plan"])

    output_dir = Path(output_dir)
    neutral_path = output_dir / "neutral.wav"
    planned_path = output_dir / "planned.wav"
    manifest_path = output_dir / "render_manifest.json"
    existing = [p for p in (neutral_path, planned_path, manifest_path) if p.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise TTSRenderError(
            f"Refusing to overwrite existing render artifact(s): {names}. "
            "Choose a new output directory or pass overwrite=True."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    neutral_meta = backend.generate_custom_voice(
        text=text,
        language=language,
        speaker=speaker,
        instruct="",
        output_path=neutral_path,
        seed=seed,
    )
    planned_meta = backend.generate_custom_voice(
        text=text,
        language=language,
        speaker=speaker,
        instruct=mapping.instruct,
        output_path=planned_path,
        seed=seed,
    )

    if not neutral_path.is_file() or not planned_path.is_file():
        raise TTSRenderError("TTS backend did not create both required WAV files")

    text_sha = _sha256_text(text)
    manifest = {
        "manifest_version": "1.0",
        "renderer": "qwen3_tts_custom_voice",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "comparison_statement": AB_STATEMENT,
        "source": {
            "example": example.get("title"),
            "example_provenance": example.get("source", {}),
            "prompt_version": example.get("prompt_version"),
            "speech_plan": speech_plan,
        },
        "exact_verbal_text": text,
        "exact_verbal_text_sha256": text_sha,
        "language": language,
        "speaker": speaker,
        "model": backend.model_id,
        "seed_reset_before_each_condition": seed,
        "delivery_adapter": mapping.to_dict(),
        "ab_invariants": {
            "same_exact_verbal_text": True,
            "same_text_sha256": text_sha,
            "same_speaker": True,
            "same_model": True,
            "same_language": True,
            "same_seed_and_generation_path": True,
            "only_condition_difference": "instruct",
            "neutral_instruct_is_empty": True,
            "planned_instruct_comes_only_from_delivery_plan": True,
        },
        "conditions": {
            "neutral": {
                "text": text,
                "text_sha256": text_sha,
                "speaker": speaker,
                "model": backend.model_id,
                "language": language,
                "instruct": "",
                "output_file": neutral_path.name,
                "audio_sha256": _sha256_file(neutral_path),
                "backend_metadata": neutral_meta,
            },
            "planned": {
                "text": text,
                "text_sha256": text_sha,
                "speaker": speaker,
                "model": backend.model_id,
                "language": language,
                "instruct": mapping.instruct,
                "output_file": planned_path.name,
                "audio_sha256": _sha256_file(planned_path),
                "backend_metadata": planned_meta,
            },
        },
        "limitations": [
            "Qwen3-TTS instruction realization is best-effort, not deterministic acoustic control.",
            "No exact F0, timing, loudness, prominence-strength, or contour realization is claimed.",
            "Unsupported controls remain preserved in the source Speech Plan and are listed by the adapter.",
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


class Qwen3CustomVoiceBackend:
    """Lazy optional backend for `Qwen3TTSModel.generate_custom_voice`."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_QWEN3_TTS_MODEL,
        device_map: str = "cuda:0",
        dtype: str = "bfloat16",
        attn_implementation: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._device_map = device_map
        self._dtype = dtype
        self._attn_implementation = attn_implementation
        self._model: Any = None
        self._numpy: Any = None
        self._torch: Any = None
        self._soundfile: Any = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import numpy as np
            import soundfile as sf
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise Qwen3TTSDependencyError(
                "Optional Qwen3-TTS dependencies are unavailable. Install the "
                "separate TTS environment with: pip install -e '.[tts]'"
            ) from exc

        if not hasattr(torch, self._dtype):
            raise Qwen3TTSDependencyError(f"Unsupported torch dtype: {self._dtype}")
        kwargs: dict[str, Any] = {
            "device_map": self._device_map,
            "dtype": getattr(torch, self._dtype),
        }
        if self._attn_implementation:
            kwargs["attn_implementation"] = self._attn_implementation

        self._model = Qwen3TTSModel.from_pretrained(self._model_id, **kwargs)
        self._numpy = np
        self._torch = torch
        self._soundfile = sf

    def generate_custom_voice(
        self,
        *,
        text: str,
        language: str,
        speaker: str,
        instruct: str,
        output_path: Path,
        seed: int,
    ) -> dict[str, Any]:
        self._load()
        random.seed(seed)
        self._numpy.random.seed(seed)
        self._torch.manual_seed(seed)
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(seed)

        wavs, sample_rate = self._model.generate_custom_voice(
            text=text,
            language=language,
            speaker=speaker,
            instruct=instruct,
        )
        if not wavs:
            raise TTSRenderError("Qwen3-TTS returned no waveform")
        waveform = wavs[0]
        self._soundfile.write(str(output_path), waveform, sample_rate)
        sample_count = len(waveform)
        return {
            "sample_rate": int(sample_rate),
            "sample_count": int(sample_count),
            "duration_seconds": round(sample_count / sample_rate, 4),
        }


__all__ = [
    "AB_STATEMENT",
    "CustomVoiceBackend",
    "DEFAULT_QWEN3_TTS_MODEL",
    "DEFAULT_TTS_SEED",
    "Qwen3CustomVoiceBackend",
    "Qwen3TTSDependencyError",
    "Qwen3TTSInstruction",
    "TTSRenderError",
    "build_qwen3_tts_instruction",
    "qwen_language_from_bcp47",
    "render_ab_comparison",
    "verbal_text_from_plan",
]
