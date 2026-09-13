"""Optional BatonVoice renderer for validated quantitative vocal plans.

The renderer is deliberately lazy: importing TeachIntent or using the Hy3 and
Evaluator paths never imports BatonVoice, vLLM, torch, or CosyVoice.  Runtime
locations are supplied by configuration or environment variables.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Protocol


class _BatonVoiceError(RuntimeError):
    def __init__(self, message: str, *, executor_diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.executor_diagnostics = executor_diagnostics


class BatonVoiceUnavailable(_BatonVoiceError):
    """Raised only when a requested render cannot use the optional runtime."""


class BatonVoiceRenderError(_BatonVoiceError):
    """Raised when an available BatonVoice runtime fails to render audio."""


@dataclass(frozen=True)
class BatonVoiceConfig:
    """Locations and resource settings for the optional BatonVoice runtime."""

    model_path: Path
    cosyvoice_model_dir: Path
    batonvoice_source_dir: Path
    wetext_fst_dir: Path | None = None
    prompt_audio_path: Path | None = None
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.25
    fp16: bool = False
    speech_speed: float = 1.0

    def __post_init__(self) -> None:
        if isinstance(self.speech_speed, bool) or not 0.85 <= self.speech_speed <= 1.15:
            raise BatonVoiceUnavailable("BatonVoice speech speed must be between 0.85 and 1.15")

    @classmethod
    def from_env(cls) -> "BatonVoiceConfig":
        def path(name: str, required: bool = True) -> Path | None:
            value = os.environ.get(name)
            if not value:
                if required:
                    raise BatonVoiceUnavailable(
                        f"Missing required BatonVoice setting: {name}"
                    )
                return None
            return Path(value).expanduser()

        try:
            tensor_parallel_size = int(os.environ.get("BATONVOICE_TENSOR_PARALLEL_SIZE", "1"))
            gpu_memory_utilization = float(
                os.environ.get("BATONVOICE_GPU_MEMORY_UTILIZATION", "0.25")
            )
        except ValueError as exc:
            raise BatonVoiceUnavailable("Invalid BatonVoice numeric setting") from exc
        if tensor_parallel_size < 1 or not 0 < gpu_memory_utilization <= 1:
            raise BatonVoiceUnavailable("Invalid BatonVoice runtime settings")
        try:
            speech_speed = float(os.environ.get("BATONVOICE_SPEECH_SPEED", "1.0"))
        except ValueError as exc:
            raise BatonVoiceUnavailable("Invalid BatonVoice speech speed") from exc
        return cls(
            model_path=path("BATONVOICE_MODEL_PATH"),  # type: ignore[arg-type]
            cosyvoice_model_dir=path("BATONVOICE_COSYVOICE_MODEL_DIR"),  # type: ignore[arg-type]
            batonvoice_source_dir=path("BATONVOICE_SOURCE_DIR"),  # type: ignore[arg-type]
            wetext_fst_dir=path("BATONVOICE_WETEXT_FST_DIR"),
            prompt_audio_path=path("BATONVOICE_PROMPT_AUDIO_PATH", required=False),
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            fp16=os.environ.get("BATONVOICE_FP16", "0").lower() in {"1", "true", "yes"},
            speech_speed=speech_speed,
        )

    def missing_paths(self) -> list[str]:
        paths = {
            "BATONVOICE_MODEL_PATH": self.model_path,
            "BATONVOICE_COSYVOICE_MODEL_DIR": self.cosyvoice_model_dir,
            "BATONVOICE_SOURCE_DIR": self.batonvoice_source_dir,
        }
        if self.wetext_fst_dir is not None:
            paths["BATONVOICE_WETEXT_FST_DIR"] = self.wetext_fst_dir
        if self.prompt_audio_path is not None:
            paths["BATONVOICE_PROMPT_AUDIO_PATH"] = self.prompt_audio_path
        return [name for name, value in paths.items() if not value.exists()]


@dataclass(frozen=True)
class BatonVoiceRenderResult:
    """Structured result returned by a successful render."""

    output_path: Path
    sample_rate: int
    duration_seconds: float
    channels: int
    peak: float
    nan: bool
    inf: bool
    renderer: str = "batonvoice"
    executor_diagnostics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "output_path": str(self.output_path),
            "sample_rate": self.sample_rate,
            "duration_seconds": self.duration_seconds,
            "channels": self.channels,
            "peak": self.peak,
            "nan": self.nan,
            "inf": self.inf,
            "renderer": self.renderer,
        }
        if self.executor_diagnostics is not None:
            result["executor_diagnostics"] = copy.deepcopy(self.executor_diagnostics)
        return result


class _ExecutorObservation:
    """Per-render observations; token sequences never enter the public snapshot.

    Hash the exact UTF-8 text/JSON passed to UnifiedTTS, without normalizing,
    sorting keys, or changing the existing serialization. Unobserved fields are
    null; a true roundtrip match says nothing about spoken content fidelity.
    """

    def __init__(self, text: str, feature_json: str, feature_item_count: int):
        self._raw_speech_tokens: list[int] | None = None
        self.data: dict[str, Any] = {
            "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "input_text_char_count": len(text),
            "feature_plan_sha256": hashlib.sha256(feature_json.encode("utf-8")).hexdigest(),
            "feature_item_count": feature_item_count,
            "generation_finish_reason": None,
            "generation_stop_reason": None,
            "generation_token_count": None,
            "is_truncated": None,
            "raw_speech_token_count": None,
            "extracted_speech_token_count": None,
            "speech_token_roundtrip_match": None,
            "speech_token_roundtrip_first_mismatch": None,
            "sampling_parameters": {key: None for key in (
                "temperature", "top_p", "top_k", "max_tokens",
                "repetition_penalty", "stop_token_ids",
            )},
        }

    def observe(self, event: str, value: Any) -> None:
        try:
            getattr(self, "_" + event)(value)
        except Exception:
            # Observation must not fail synthesis or log potentially private
            # completion objects. Unavailable observations remain null.
            pass

    def _sampling(self, params: Any) -> None:
        for key in self.data["sampling_parameters"]:
            self.data["sampling_parameters"][key] = copy.deepcopy(getattr(params, key, None))

    def _generation(self, outputs: Any) -> None:
        completion = outputs[0].outputs[0]
        reason = completion.finish_reason
        self.data["generation_finish_reason"] = reason
        self.data["generation_stop_reason"] = getattr(completion, "stop_reason", None)
        self.data["is_truncated"] = reason == "length"
        raw_ids = completion.token_ids
        self.data["generation_token_count"] = len(raw_ids)
        # Intentionally identical to the current upstream offset rule, not a
        # new token validator or a replacement synthesis path.
        offset = 151669 + 100
        self._raw_speech_tokens = [token - offset for token in raw_ids if token >= offset]
        self.data["raw_speech_token_count"] = len(self._raw_speech_tokens)

    def _extraction(self, extracted: list[int]) -> None:
        self.data["extracted_speech_token_count"] = len(extracted)
        raw = self._raw_speech_tokens
        if raw is None:
            return
        mismatch = next((i for i, (a, b) in enumerate(zip(raw, extracted)) if a != b), None)
        if mismatch is None and len(raw) != len(extracted):
            mismatch = min(len(raw), len(extracted))
        self.data["speech_token_roundtrip_match"] = mismatch is None
        self.data["speech_token_roundtrip_first_mismatch"] = mismatch

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)


def quantitative_plan_from_speech_plan(speech_plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate an already validated Speech Plan without changing segmentation.

    Fixed renderer approximations: pitch low/medium/high -> 220/226/232;
    volume soft/medium/loud -> 0.0076/0.008/0.0084. Other categories
    (including extremes) use baseline. Overrides inherit per field; explicit
    ``default`` resets that field. Slopes and centroid stay neutral.

    Whole-segment moderate/strong prominence uses 232 and 0.0084 only where
    no explicit pitch/volume control exists; boosts never accumulate. Subspan
    prominence is unsupported because this adapter preserves segmentation.
    Rate, range, contour, boundary, tone and emotion have no mapping. These
    approximations do not promise precise local prosody or measured acoustics.
    """
    try:
        segments = speech_plan["verbal_plan"]["segments"]
    except (KeyError, TypeError) as exc:
        raise BatonVoiceRenderError("Speech Plan has no verbal_plan.segments") from exc
    if not isinstance(segments, list) or not segments:
        raise BatonVoiceRenderError("Speech Plan verbal_plan.segments must be non-empty")
    delivery = speech_plan.get("delivery_plan", {})
    global_prosody = delivery.get("global", {}).get("prosody", {})
    overrides = {
        item["segment_id"]: item for item in delivery.get("segment_overrides", [])
    }
    translated = []
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise BatonVoiceRenderError("Speech Plan contains an invalid verbal segment")
        override = overrides.get(segment.get("segment_id"), {})
        prosody = {**global_prosody, **override.get("prosody", {})}
        whole_segment_emphasis = any(
            target["text"] == segment["text"]
            and target["level"] in ("moderate", "strong")
            for target in override.get("prominence_targets", [])
        )
        pitch = {"low": 220, "medium": 226, "high": 232}.get(
            prosody.get("pitch_level"), 226
        )
        energy = {"soft": 0.0076, "medium": 0.008, "loud": 0.0084}.get(
            prosody.get("volume"), 0.008
        )
        if whole_segment_emphasis:
            if "pitch_level" not in prosody:
                pitch = 232
            if "volume" not in prosody:
                energy = 0.0084
        translated.append({
            "word": segment["text"],
            "pitch_mean": pitch,
            "pitch_slope": 0,
            "energy_rms": energy,
            "energy_slope": 0,
            "spectral_centroid": 1885,
        })
    return translated


class BatonVoiceBackend(Protocol):
    def render(self, text: str, plan: list[dict[str, Any]], output_path: Path) -> BatonVoiceRenderResult: ...

    def close(self) -> None: ...


def _validate_quantitative_plan(plan: Any) -> list[dict[str, Any]]:
    """Validate the K0 quantitative plan without loading the TTS runtime."""
    if not isinstance(plan, list) or not plan:
        raise BatonVoiceRenderError("BatonVoice plan must be a non-empty list")
    required = {"word", "pitch_mean", "pitch_slope", "energy_rms", "energy_slope", "spectral_centroid"}
    result: list[dict[str, Any]] = []
    for index, segment in enumerate(plan):
        if not isinstance(segment, dict) or set(segment) != required:
            raise BatonVoiceRenderError(f"Invalid BatonVoice plan segment {index}")
        if not isinstance(segment["word"], str) or not segment["word"].strip():
            raise BatonVoiceRenderError(f"Invalid BatonVoice plan segment {index} word")
        for key in ("pitch_mean", "pitch_slope", "energy_slope", "spectral_centroid"):
            value = segment[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise BatonVoiceRenderError(f"Invalid BatonVoice plan field: {key}")
        energy = segment["energy_rms"]
        if isinstance(energy, bool) or not isinstance(energy, (int, float)):
            raise BatonVoiceRenderError("Invalid BatonVoice plan field: energy_rms")
        if not all(math.isfinite(float(segment[key])) for key in (*required - {"word"},)):
            raise BatonVoiceRenderError(f"Non-finite BatonVoice plan segment {index}")
        result.append(dict(segment))
    return result


def _patch_local_wetext_frontend(config: BatonVoiceConfig) -> None:
    """Install local FST normalizers in CosyVoice for this Python process only."""
    if config.wetext_fst_dir is None:
        raise BatonVoiceUnavailable("BATONVOICE_WETEXT_FST_DIR is required")
    root = config.wetext_fst_dir
    paths = {
        "zh": (root / "zh/tn/tagger.fst", root / "zh/tn/verbalizer.fst"),
        "en": (root / "en/tn/tagger.fst", root / "en/tn/verbalizer.fst"),
    }
    missing = [str(path) for pair in paths.values() for path in pair if not path.is_file()]
    if missing:
        raise BatonVoiceUnavailable("Local WeText FST files are missing: " + ", ".join(missing))
    try:
        import sys
        frontend = sys.modules.get("cosyvoice.cli.frontend")
        if frontend is None:
            import cosyvoice.cli.frontend as frontend
        from wetext import Normalizer
    except Exception as exc:
        raise BatonVoiceUnavailable(f"Local WeText normalizer import failed: {exc}") from exc

    def local_normalizer(lang: str):
        tagger, verbalizer = paths[lang]
        return Normalizer(
            tagger_path=str(tagger), verbalizer_path=str(verbalizer), lang=lang,
            operator="tn", remove_erhua=False,
        )

    class ZhLocalNormalizer:
        def __new__(cls, *args, **kwargs):
            return local_normalizer("zh")

    class EnLocalNormalizer:
        def __new__(cls, *args, **kwargs):
            return local_normalizer("en")

    frontend.ZhNormalizer = ZhLocalNormalizer
    frontend.EnNormalizer = EnLocalNormalizer
    frontend.use_ttsfrd = False


class BatonVoiceRenderer:
    """Lazy optional renderer; unavailable runtime never falls back to another TTS."""

    def __init__(
        self,
        config: BatonVoiceConfig | None = None,
        *,
        backend_factory: Callable[[BatonVoiceConfig], BatonVoiceBackend] | None = None,
    ) -> None:
        self._config = config
        self._backend_factory = backend_factory or _UnifiedTTSBackend
        self._backend: BatonVoiceBackend | None = None

    @property
    def available(self) -> bool:
        try:
            config = self._config or BatonVoiceConfig.from_env()
        except BatonVoiceUnavailable:
            return False
        return not config.missing_paths()

    def status(self) -> dict[str, Any]:
        try:
            config = self._config or BatonVoiceConfig.from_env()
        except BatonVoiceUnavailable as exc:
            return {"available": False, "renderer": "batonvoice", "reason": str(exc)}
        missing = config.missing_paths()
        if missing:
            return {
                "available": False,
                "renderer": "batonvoice",
                "reason": "Configured BatonVoice paths are unavailable",
                "missing": missing,
            }
        return {"available": True, "renderer": "batonvoice"}

    def render(self, *, text: str, plan: list[dict[str, Any]], output_path: Path) -> BatonVoiceRenderResult:
        if not text.strip():
            raise BatonVoiceRenderError("BatonVoice text must not be empty")
        canonical_plan = _validate_quantitative_plan(plan)
        config = self._config
        if config is None:
            config = BatonVoiceConfig.from_env()
        missing = config.missing_paths()
        if missing:
            raise BatonVoiceUnavailable(
                "BatonVoice runtime unavailable; missing: " + ", ".join(missing)
            )
        if self._backend is None:
            try:
                self._backend = self._backend_factory(config)
            except Exception as exc:
                raise BatonVoiceUnavailable(f"Unable to load BatonVoice runtime: {exc}") from exc
        try:
            result = self._backend.render(text, canonical_plan, Path(output_path))
        except BatonVoiceUnavailable:
            raise
        except Exception as exc:
            raise BatonVoiceRenderError(
                f"BatonVoice render failed: {exc}",
                executor_diagnostics=getattr(exc, "executor_diagnostics", None),
            ) from exc
        if result.output_path != Path(output_path):
            raise BatonVoiceRenderError("BatonVoice backend returned an unexpected output path")
        return result

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None


class _UnifiedTTSBackend:
    """Adapter around the verified BatonVoice ``UnifiedTTS`` implementation."""

    def __init__(self, config: BatonVoiceConfig) -> None:
        import sys

        self._speech_speed = config.speech_speed

        source = str(config.batonvoice_source_dir)
        if source not in sys.path:
            sys.path.insert(0, source)
        try:
            from unified_tts import UnifiedTTS
        except Exception as exc:
            raise BatonVoiceUnavailable(f"BatonVoice source import failed: {exc}") from exc
        _patch_local_wetext_frontend(config)
        class ModelConfiguredTTS(UnifiedTTS):
            def _generate_response(self, prompt):
                observer = getattr(self, "_executor_observer", None)
                if observer is None:
                    return super()._generate_response(prompt)
                llm = self.llm  # Already lazily initialized by upstream.
                original = llm.generate
                sentinel = object()
                previous = getattr(llm, "__dict__", {}).get("generate", sentinel)

                def generate(*args, **kwargs):
                    params = kwargs.get("sampling_params", args[1] if len(args) > 1 else None)
                    observer.observe("sampling", params)
                    outputs = original(*args, **kwargs)
                    observer.observe("generation", outputs)
                    return outputs  # Same object, IDs and ordering as upstream.

                try:
                    llm.generate = generate
                except (AttributeError, TypeError):
                    # A runtime with a read-only method can still synthesize.
                    return super()._generate_response(prompt)
                try:
                    return super()._generate_response(prompt)
                finally:
                    if previous is sentinel:
                        del llm.generate
                    else:
                        llm.generate = previous

            def _extract_mode2_outputs(self, generated_text, original_prompt):
                extracted = super()._extract_mode2_outputs(generated_text, original_prompt)
                observer = getattr(self, "_executor_observer", None)
                if observer is not None:
                    observer.observe("extraction", extracted)
                return extracted  # Never substitute the raw-ID-derived path.

            def _setup_sampling_params(self) -> None:
                with (config.model_path / "generation_config.json").open() as handle:
                    generation = json.load(handle)
                eos = generation["eos_token_id"]
                stop_ids = eos if isinstance(eos, list) else [eos]
                if not stop_ids or any(type(token) is not int or token < 0 for token in stop_ids):
                    raise BatonVoiceRenderError("Invalid model EOS configuration")
                super()._setup_sampling_params()
                previous = self.sampling_params
                # Reconstruct so vLLM also initializes its internal stop-token state.
                self.sampling_params = type(previous)(
                    temperature=generation["temperature"],
                    top_k=generation["top_k"],
                    top_p=generation["top_p"],
                    stop_token_ids=stop_ids,
                    max_tokens=previous.max_tokens,
                    repetition_penalty=previous.repetition_penalty,
                )

        self._tts = ModelConfiguredTTS(
            model_path=str(config.model_path),
            cosyvoice_model_dir=str(config.cosyvoice_model_dir),
            prompt_audio_path=str(config.prompt_audio_path) if config.prompt_audio_path else "",
            tensor_parallel_size=config.tensor_parallel_size,
            gpu_memory_utilization=config.gpu_memory_utilization,
            fp16=config.fp16,
        )

    def render(self, text: str, plan: list[dict[str, Any]], output_path: Path) -> BatonVoiceRenderResult:
        feature_json = json.dumps(plan, ensure_ascii=False)
        observer = _ExecutorObservation(text, feature_json, len(plan))
        previous = getattr(self._tts, "_executor_observer", None)
        self._tts._executor_observer = observer
        try:
            result = self._render_observed(text, feature_json, output_path)
            return replace(result, executor_diagnostics=observer.snapshot())
        except Exception as exc:
            exc.executor_diagnostics = observer.snapshot()
            raise
        finally:
            self._tts._executor_observer = previous

    def _render_observed(self, text: str, feature_json: str, output_path: Path) -> BatonVoiceRenderResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        success = self._tts.text_features_to_speech(
            text, feature_json, str(output_path), speed=self._speech_speed
        )
        if not success or not output_path.is_file():
            raise BatonVoiceRenderError("BatonVoice did not produce a WAV file")
        try:
            import soundfile as sf
            import numpy as np

            waveform, sample_rate = sf.read(str(output_path), always_2d=True)
            finite = np.isfinite(waveform)
            return BatonVoiceRenderResult(
                output_path=output_path,
                sample_rate=int(sample_rate),
                duration_seconds=round(len(waveform) / sample_rate, 4),
                channels=int(waveform.shape[1]),
                peak=float(np.max(np.abs(waveform))) if waveform.size else 0.0,
                nan=bool(np.isnan(waveform).any()),
                inf=bool(np.isinf(waveform).any()),
            )
        except Exception as exc:
            raise BatonVoiceRenderError(f"Unable to inspect BatonVoice WAV: {exc}") from exc

    def close(self) -> None:
        self._tts.cleanup()


__all__ = [
    "BatonVoiceBackend",
    "BatonVoiceConfig",
    "BatonVoiceRenderError",
    "BatonVoiceRenderResult",
    "BatonVoiceRenderer",
    "BatonVoiceUnavailable",
    "quantitative_plan_from_speech_plan",
]
