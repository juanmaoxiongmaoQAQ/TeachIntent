#!/usr/bin/env python3
"""Diagnostic experiment only; never used by the production render endpoint.

Default: validate/preview the supplied Speech Plan without runtime initialization
or file writes. --execute reuses ONE renderer for isolated samples; --include-full
adds one full-utterance sample first. No retries, ASR, or waveform processing.

Use the SAME BATONVOICE_* environment and GPU allocation as the reference full
render, including optional prompt audio and resource settings. Speed must already
be 0.85. This script never supplies substitute models or speaker conditioning.
The default fixture transcribes the user's latest v0.4 Golden Case 1 report.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from teachintent.models.speech_plan import SpeechPlan
from teachintent.renderers.batonvoice import (
    BatonVoiceConfig,
    BatonVoiceRenderer,
    BatonVoiceUnavailable,
    quantitative_plan_from_speech_plan,
)
from teachintent.validators import validate_speech_plan_document
from teachintent.renderers._project_outputs import project_output_root

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs/baton-segment-isolation"
SPEED = 0.85
EXPECTED_SAMPLING = {
    "temperature": 0.6, "top_p": 0.95, "top_k": 20,
    "max_tokens": 2048, "repetition_penalty": 1.1,
    "stop_token_ids": [151645, 151643],
}
EXECUTOR_FIELDS = (
    "generation_finish_reason", "generation_stop_reason", "generation_token_count",
    "is_truncated", "raw_speech_token_count", "extracted_speech_token_count",
    "speech_token_roundtrip_match", "speech_token_roundtrip_first_mismatch",
)
WAV_FIELDS = ("sample_rate", "duration_seconds", "channels", "peak", "nan", "inf")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_samples(plan_doc: dict, *, include_full: bool = False) -> list[dict]:
    """Map the whole plan once so local controls retain global inheritance."""
    validate_speech_plan_document(plan_doc)
    SpeechPlan.model_validate(plan_doc)
    mapped = quantitative_plan_from_speech_plan(plan_doc)
    segments = plan_doc["verbal_plan"]["segments"]
    samples = [
        {"segment_id": segment["segment_id"], "condition": "isolated",
         "text": segment["text"], "feature_plan": [item]}
        for segment, item in zip(segments, mapped)
    ]
    if include_full:
        samples.insert(0, {
            "segment_id": None, "condition": "full",
            "text": " ".join(s["text"] for s in segments), "feature_plan": mapped,
        })
    return samples


def _sample_record(sample: dict) -> dict:
    features = sample["feature_plan"]
    item = features[0] if sample["condition"] == "isolated" else {}
    return {
        "segment_id": sample["segment_id"], "condition": sample["condition"],
        "wav_file": f"{sample['segment_id']}.wav" if sample["segment_id"] else "full.wav",
        "status": "not_run", "failure_type": None,
        "text_sha256": sha256(sample["text"].encode("utf-8")),
        "text_char_count": len(sample["text"]),
        "feature_plan_sha256": sha256(json.dumps(features, ensure_ascii=False).encode("utf-8")),
        "feature_item_count": len(features),
        **{key: item.get(key) for key in (
            "pitch_mean", "energy_rms", "pitch_slope", "energy_slope", "spectral_centroid",
        )},
        "speech_speed": SPEED,
        **{key: None for key in EXECUTOR_FIELDS},
        "sampling_parameters": {key: None for key in EXPECTED_SAMPLING},
        "sampling_matches_expected": None,
        "executor_input_matches_expected": None,
        "wav": {key: None for key in WAV_FIELDS},
    }


def _record_executor(record: dict, diagnostics: dict | None) -> None:
    if not diagnostics:
        return
    for key in EXECUTOR_FIELDS:
        record[key] = diagnostics.get(key)
    sampling = diagnostics.get("sampling_parameters") or {}
    record["sampling_parameters"] = {
        key: copy.deepcopy(sampling.get(key)) for key in EXPECTED_SAMPLING
    }
    record["sampling_matches_expected"] = record["sampling_parameters"] == EXPECTED_SAMPLING
    record["executor_input_matches_expected"] = all(
        diagnostics.get(actual) == record[expected] for actual, expected in (
            ("input_text_sha256", "text_sha256"),
            ("input_text_char_count", "text_char_count"),
            ("feature_plan_sha256", "feature_plan_sha256"),
            ("feature_item_count", "feature_item_count"),
        )
    )


def _check_config(config: BatonVoiceConfig) -> str:
    if config.speech_speed != SPEED:
        raise ValueError("The isolation experiment requires BATONVOICE_SPEECH_SPEED=0.85")
    if config.missing_paths():
        raise ValueError("Configured Baton runtime paths must exist")
    if config.wetext_fst_dir is None or any(
        not (config.wetext_fst_dir / lang / "tn" / name).is_file()
        for lang in ("zh", "en") for name in ("tagger.fst", "verbalizer.fst")
    ):
        raise ValueError("The same complete local WeText FST is required")
    content = (config.model_path / "generation_config.json").read_bytes()
    generation = json.loads(content)
    if any(generation.get(key) != EXPECTED_SAMPLING[key] for key in ("temperature", "top_p", "top_k")):
        raise ValueError("Model sampling config differs from the reference experiment")
    if generation.get("eos_token_id") != EXPECTED_SAMPLING["stop_token_ids"]:
        raise ValueError("Model stop tokens differ from the reference experiment")
    return sha256(content)


def run_isolation(
    plan_path: Path, output_root: Path, config: BatonVoiceConfig, *,
    include_full: bool = False, prompt_version: str = "v0.4", renderer_factory=None,
) -> tuple[Path, dict]:
    """Create fresh evidence; failures remain recorded and are never retried."""
    output_root = project_output_root(output_root)
    plan_bytes = plan_path.read_bytes()
    samples = build_samples(json.loads(plan_bytes), include_full=include_full)
    generation_config_sha = _check_config(config)  # No model import/loading.
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / run_id
    run_dir.mkdir(exist_ok=False)  # Never reuse a prior run directory.
    report = {
        "schema_version": "1.0", "experiment": "baton_segment_isolation",
        "evidence_kind": "diagnostic_non_confirmatory", "run_id": run_id,
        "prompt_version": prompt_version, "source_plan_sha256": sha256(plan_bytes),
        "diagnostic_script_sha256": sha256(Path(__file__).read_bytes()),
        "renderer_source_sha256": sha256((ROOT / "src/teachintent/renderers/batonvoice.py").read_bytes()),
        "generation_config_sha256": generation_config_sha,
        "runtime": {
            **{key: str(getattr(config, key)) if getattr(config, key) is not None else None
               for key in ("model_path", "cosyvoice_model_dir", "batonvoice_source_dir",
                           "wetext_fst_dir", "prompt_audio_path")},
            "tensor_parallel_size": config.tensor_parallel_size,
            "gpu_memory_utilization": config.gpu_memory_utilization,
            "fp16": config.fp16, "speech_speed": config.speech_speed,
        },
        "expected_sampling_parameters": copy.deepcopy(EXPECTED_SAMPLING),
        "include_full": include_full, "status": "running", "cleanup_error_type": None,
        "content_fidelity_assessment": "human_listening_required",
        "samples": [_sample_record(sample) for sample in samples],
    }
    renderer = None
    try:
        renderer = (renderer_factory or BatonVoiceRenderer)(config)
        for sample, record in zip(samples, report["samples"]):
            try:
                result = renderer.render(
                    text=sample["text"], plan=sample["feature_plan"],
                    output_path=run_dir / record["wav_file"],
                )
                record["status"] = "success"
                record["wav"] = {
                    key: value if not isinstance(value := getattr(result, key), float) or math.isfinite(value) else None
                    for key in WAV_FIELDS
                }  # Invalid numeric measurements stay JSON-safe; WAV flags remain.
                _record_executor(record, result.executor_diagnostics)
            except Exception as exc:
                record["status"] = "unavailable" if isinstance(exc, BatonVoiceUnavailable) else "error"
                record["failure_type"] = type(exc).__name__
                _record_executor(record, getattr(exc, "executor_diagnostics", None))
                # Never serialize exception messages, raw output, or environment.
                if isinstance(exc, BatonVoiceUnavailable):
                    break  # Do not repeatedly attempt to load unavailable models.
                continue
            if record["sampling_matches_expected"] is not True or record["executor_input_matches_expected"] is not True:
                report["status"] = "invariant_error"
                break  # Preserve this output, but do not run more changed conditions.
        if report["status"] == "running":
            report["status"] = "completed" if all(r["status"] == "success" for r in report["samples"]) else "incomplete"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        raise
    except Exception as exc:
        report["status"] = "setup_error"
        report["failure_type"] = type(exc).__name__
    finally:
        try:
            if renderer is not None:
                renderer.close()
        except Exception as exc:
            report["cleanup_error_type"] = type(exc).__name__
            if report["status"] == "completed":
                report["status"] = "cleanup_error"
        finally:
            with (run_dir / "diagnostics.json").open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
    return run_dir, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="Saved Speech Plan JSON; never regenerated")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--prompt-version", default="v0.4", help="Source-plan provenance only; does not invoke a planner")
    parser.add_argument("--include-full", action="store_true", help="Also render the full utterance before isolated samples")
    parser.add_argument("--execute", action="store_true", help="Load the configured runtime and synthesize; default is preview only")
    args = parser.parse_args(argv)
    try:
        if not args.execute:
            samples = build_samples(json.loads(args.plan.read_bytes()), include_full=args.include_full)
            print(json.dumps({"mode": "preview", "speech_speed": SPEED, "samples": samples}, ensure_ascii=False, indent=2))
            return 0
        run_dir, report = run_isolation(
            args.plan, args.output_root, BatonVoiceConfig.from_env(),
            include_full=args.include_full, prompt_version=args.prompt_version,
        )
        print(f"{report['status']}: {run_dir / 'diagnostics.json'}")
        return 0 if report["status"] == "completed" else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Diagnostic setup failed ({type(exc).__name__}); check the plan and BATONVOICE_* settings.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
