"""Experimental independent Mode 2 synthesis; no API or waveform composition.

Each render owns one lazy BatonVoiceRenderer, uses it sequentially, and closes
it before returning (run_dir, manifest). Importing this module loads no models.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from teachintent.models.speech_plan import SpeechPlan
from teachintent.validators import validate_speech_plan_document

from ._project_outputs import PROJECT_ROOT, project_output_root
from .batonvoice import (
    BatonVoiceConfig,
    BatonVoiceRenderer,
    BatonVoiceUnavailable,
    quantitative_plan_from_speech_plan,
)

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs/baton-segmented"
MAPPED_FIELDS = ("pitch_mean", "energy_rms", "pitch_slope", "energy_slope", "spectral_centroid")
EXECUTOR_FIELDS = (
    "generation_finish_reason", "generation_stop_reason", "generation_token_count",
    "is_truncated", "raw_speech_token_count", "extracted_speech_token_count",
    "speech_token_roundtrip_match", "speech_token_roundtrip_first_mismatch",
    "input_text_sha256", "input_text_char_count", "feature_plan_sha256", "feature_item_count",
)
SAMPLING_FIELDS = (
    "temperature", "top_p", "top_k", "max_tokens", "repetition_penalty", "stop_token_ids",
)
WAV_FIELDS = ("sample_rate", "duration_seconds", "channels", "peak", "nan", "inf")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    # Identical feature serialization to the existing Mode 2 executor.
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _record_executor(record: dict, diagnostics: dict | None) -> None:
    diagnostics = diagnostics or {}
    record["executor_diagnostics"] = {
        key: copy.deepcopy(diagnostics.get(key)) for key in EXECUTOR_FIELDS
    }
    sampling = diagnostics.get("sampling_parameters") or {}
    record["executor_diagnostics"]["sampling_parameters"] = {
        key: copy.deepcopy(sampling.get(key)) for key in SAMPLING_FIELDS
    }


class SegmentedBatonVoiceRenderer:
    """Candidate only. Every call creates fresh evidence; never retries/falls back.

    The optional factory is an offline test seam. Production construction uses
    the existing Baton facade unchanged, including its sampling, local FST,
    prompt audio/speaker conditioning, speed, diagnostics and lazy backend.
    """

    def __init__(
        self, config: BatonVoiceConfig | None = None, *,
        renderer_factory: Callable[[BatonVoiceConfig], BatonVoiceRenderer] | None = None,
    ) -> None:
        self._config = config
        self._renderer_factory = renderer_factory or BatonVoiceRenderer

    def render(
        self, *, speech_plan: dict, prompt_version: str,
        output_root: Path = DEFAULT_OUTPUT_ROOT,
    ) -> tuple[Path, dict]:
        """Return a persisted manifest, including partial failures and cleanup errors.

        Invalid plans/paths/configuration fail before a run is created. Once a
        run exists, its manifest is written even on interruption (then re-raised).
        `success` describes execution diagnostics, not verified spoken content.
        """
        output_root = project_output_root(output_root)
        doc = copy.deepcopy(speech_plan)
        validate_speech_plan_document(doc)
        SpeechPlan.model_validate(doc)  # Includes ID uniqueness/reference integrity.
        if not isinstance(prompt_version, str) or not prompt_version.strip():
            raise ValueError("Explicit source prompt_version is required")
        segments = doc["verbal_plan"]["segments"]
        mapped = quantitative_plan_from_speech_plan(doc)
        # The existing mapper returns verbal order, without IDs. Bind its output
        # once to validated unique IDs, then retrieve only by ID during execution.
        if len(mapped) != len(segments) or any(
            item["word"] != segment["text"] for segment, item in zip(segments, mapped)
        ):
            raise ValueError("Quantitative mapper did not preserve the verbal segments")
        by_id = {s["segment_id"]: item for s, item in zip(segments, mapped)}
        config = self._config or BatonVoiceConfig.from_env()
        delivery = doc.get("delivery_plan", {})
        overrides = {s["segment_id"]: s for s in delivery.get("segment_overrides", [])}
        records = []
        for order, segment in enumerate(segments, start=1):
            segment_id = segment["segment_id"]
            item = by_id[segment_id]
            record = {
                "segment_id": segment_id, "order": order,
                "text_sha256": _sha(segment["text"].encode("utf-8")),
                "text_char_count": len(segment["text"]),
                "audio_filename": f"{segment_id}.wav",
                "feature_plan_sha256": _sha(_json_bytes([item])), "feature_item_count": 1,
                "mapped": {key: item[key] for key in MAPPED_FIELDS},
                "mapping_diagnostics": {
                    "global_prosody": copy.deepcopy(delivery.get("global", {}).get("prosody", {})),
                    "segment_override": copy.deepcopy(overrides.get(segment_id, {}).get("prosody", {})),
                    "prominence_targets": copy.deepcopy(overrides.get(segment_id, {}).get("prominence_targets", [])),
                },
                "status": "not_run", "failure_reasons": [], "error_type": None,
                "wav": {key: None for key in WAV_FIELDS},
            }
            _record_executor(record, None)
            records.append(record)

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex
        run_dir = output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            "schema_version": "1.0", "run_id": run_id,
            "renderer": "batonvoice_segmented", "evidence_kind": "experimental_non_confirmatory",
            "prompt_version": prompt_version, "speech_speed": config.speech_speed,
            "source_plan_sha256": _sha(_json_bytes(doc)),
            "source_plan_hash_encoding": "json.dumps(ensure_ascii=False, allow_nan=False), UTF-8",
            "renderer_source_sha256": _sha(Path(__file__).read_bytes()),
            "base_renderer_source_sha256": _sha(Path(__file__).with_name("batonvoice.py").read_bytes()),
            "runtime": {
                **{key: str(getattr(config, key)) if getattr(config, key) is not None else None
                   for key in ("model_path", "cosyvoice_model_dir", "batonvoice_source_dir",
                               "wetext_fst_dir", "prompt_audio_path")},
                "tensor_parallel_size": config.tensor_parallel_size,
                "gpu_memory_utilization": config.gpu_memory_utilization, "fp16": config.fp16,
            },
            "status": "running", "setup_error_type": None, "cleanup_error_type": None,
            "content_fidelity_assessment": "human_listening_required", "segments": records,
        }
        renderer = None
        try:
            renderer = self._renderer_factory(config)
            for segment, record in zip(segments, records):
                try:
                    result = renderer.render(
                        text=segment["text"], plan=[copy.deepcopy(by_id[segment["segment_id"]])],
                        output_path=run_dir / record["audio_filename"],
                    )
                    _record_executor(record, result.executor_diagnostics)
                    record["wav"] = {
                        key: value if not isinstance(value := getattr(result, key), float) or math.isfinite(value) else None
                        for key in WAV_FIELDS
                    }
                    diagnostics = record["executor_diagnostics"]
                    if diagnostics["is_truncated"] is True:
                        record["failure_reasons"].append("generation_truncated")
                    if diagnostics["speech_token_roundtrip_match"] is False:
                        record["failure_reasons"].append("speech_token_roundtrip_mismatch")
                    if any(diagnostics[key] is None for key in (
                        "is_truncated", "speech_token_roundtrip_match", "generation_finish_reason",
                        "generation_token_count", "raw_speech_token_count", "extracted_speech_token_count",
                    )) or any(value is None for value in diagnostics["sampling_parameters"].values()):
                        record["failure_reasons"].append("executor_diagnostics_incomplete")
                    if any(diagnostics[key] != record[expected] for key, expected in (
                        ("input_text_sha256", "text_sha256"), ("input_text_char_count", "text_char_count"),
                        ("feature_plan_sha256", "feature_plan_sha256"), ("feature_item_count", "feature_item_count"),
                    )):
                        record["failure_reasons"].append("executor_input_mismatch")
                    if not (run_dir / record["audio_filename"]).is_file():
                        record["failure_reasons"].append("audio_missing")
                    if record["wav"]["nan"] or record["wav"]["inf"] or any(
                        record["wav"][key] is None for key in WAV_FIELDS
                    ):
                        record["failure_reasons"].append("invalid_audio_metrics")
                    record["status"] = "failed" if record["failure_reasons"] else "success"
                except KeyboardInterrupt:
                    record["status"] = "interrupted"
                    record["failure_reasons"].append("interrupted")
                    raise
                except Exception as exc:
                    record["status"] = "failed"
                    record["failure_reasons"].append("render_failure")
                    record["error_type"] = type(exc).__name__
                    _record_executor(record, getattr(exc, "executor_diagnostics", None))
                    if isinstance(exc, BatonVoiceUnavailable):
                        break  # A failed load must not be attempted again for each segment.
                    # Continue with the next distinct segment; never retry this one.
        except BaseException as exc:
            manifest["setup_error_type"] = type(exc).__name__
            if not isinstance(exc, Exception):
                manifest["status"] = "interrupted"
                raise
        finally:
            try:
                if renderer is not None:
                    renderer.close()
            except Exception as exc:
                manifest["cleanup_error_type"] = type(exc).__name__
            finally:
                if manifest["status"] != "interrupted":
                    successes = sum(r["status"] == "success" for r in records)
                    complete = successes == len(records) and not manifest["cleanup_error_type"] and not manifest["setup_error_type"]
                    manifest["status"] = "success" if complete else "partial_failure" if successes else "failed"
                with (run_dir / "manifest.json").open("x", encoding="utf-8") as handle:
                    json.dump(manifest, handle, ensure_ascii=False, indent=2, allow_nan=False)
                    handle.write("\n")
        return run_dir, manifest
