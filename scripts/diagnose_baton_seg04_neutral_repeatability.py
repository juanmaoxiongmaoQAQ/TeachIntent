#!/usr/bin/env python3
"""seg_04 neutral-only diagnostic: pitch_mean 232 -> 226, all else fixed.

Default previews without loading a runtime or writing files. --execute reuses
the verified high-condition environment and one hash-instrumented backend for
eight planned neutral trials. No high generation, seeds, retries or processing.
Historical high evidence is read-only; human listening decides content fidelity.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
from uuid import uuid4

# Load the sibling diagnostic without editing it or changing global import paths.
# Its helpers and hash backend are model-free until render is explicitly called.
_spec = importlib.util.spec_from_file_location(
    "seg04_high_diagnostic_helpers", Path(__file__).with_name("diagnose_baton_seg04_repeatability.py"),
)
high = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(high)

DEFAULT_REPEATS = high.DEFAULT_REPEATS
DEFAULT_PLAN = high.DEFAULT_PLAN
DEFAULT_OUTPUT_ROOT = high.PROJECT_ROOT / "outputs/baton-seg04-neutral-repeatability"
DEFAULT_HIGH_DIAGNOSTICS = high.PROJECT_ROOT / (
    "outputs/baton-seg04-repeatability/"
    "20260913T081841.027956Z-91688aa826fd430cb9f980d57421049e/diagnostics.json"
)
FEATURES = {**high.FEATURES, "pitch_mean": 226}
RepeatabilityBackend = high.RepeatabilityBackend


def neutral_sample(plan_path: Path = DEFAULT_PLAN) -> tuple[dict, str, str]:
    sample, source_sha = high.fixed_sample(plan_path)
    original_feature_sha = high.sha256(json.dumps(sample["plan"], ensure_ascii=False).encode("utf-8"))
    sample = copy.deepcopy(sample)
    sample["plan"][0]["pitch_mean"] = 226  # The sole model-input intervention.
    return sample, source_sha, original_feature_sha


def _runtime(config) -> dict:
    return {
        **{k: str(getattr(config, k)) if getattr(config, k) is not None else None
           for k in ("model_path", "cosyvoice_model_dir", "batonvoice_source_dir", "wetext_fst_dir", "prompt_audio_path")},
        "tensor_parallel_size": config.tensor_parallel_size,
        "gpu_memory_utilization": config.gpu_memory_utilization, "fp16": config.fp16,
    }


def check_high_reference(path: Path, config, provenance: dict, source_sha: str, feature_sha: str) -> dict:
    """Reject a changed control condition before constructing/loading a backend."""
    content = path.read_bytes()
    baseline = json.loads(content)
    expected = {
        "status": "completed", "repeats": 8, "segment_id": "seg_04",
        "mapped": high.FEATURES, "speech_speed": high.SPEED,
        "expected_sampling_parameters": high.SAMPLING,
        "speech_token_hash_encoding": high.TOKEN_HASH_ENCODING,
        "source_plan_sha256": source_sha, "runtime": _runtime(config), **provenance,
        "renderer_source_sha256": high.sha256((high.PROJECT_ROOT / "src/teachintent/renderers/batonvoice.py").read_bytes()),
        "diagnostic_script_sha256": high.sha256(Path(high.__file__).read_bytes()),
    }
    if any(baseline.get(k) != v for k, v in expected.items()):
        raise ValueError("Runtime or reference evidence differs from the completed high condition")
    samples = baseline.get("samples", [])
    if len(samples) != 8 or any(
        sample.get("text_sha256") != high.TEXT_SHA256
        or sample.get("feature_plan_sha256") != feature_sha
        or sample.get("sampling_parameters") != high.SAMPLING
        or sample.get("executor_input_matches_expected") is not True
        or sample.get("sampling_matches_expected") is not True
        or sample.get("generation_finish_reason") != "stop"
        or sample.get("is_truncated") is not False
        or sample.get("speech_token_roundtrip_match") is not True
        for sample in samples
    ):
        raise ValueError("High reference does not contain eight matching fixed-condition trials")
    return {"run_id": baseline["run_id"], "diagnostics_sha256": high.sha256(content),
            "feature_plan_sha256": feature_sha, "condition": "high", "pitch_mean": 232}


def run_neutral_repeatability(
    config, *, repeats: int = DEFAULT_REPEATS, plan_path: Path = DEFAULT_PLAN,
    output_root: Path = DEFAULT_OUTPUT_ROOT, high_diagnostics_path: Path = DEFAULT_HIGH_DIAGNOSTICS,
    backend_factory=None,
) -> tuple[Path, dict]:
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    output_root = high.project_output_root(output_root)
    sample, source_sha, original_feature_sha = neutral_sample(plan_path)
    provenance = high.check_config(config)
    reference = check_high_reference(high_diagnostics_path, config, provenance, source_sha, original_feature_sha)
    feature_sha = high.sha256(json.dumps(sample["plan"], ensure_ascii=False).encode("utf-8"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    records = [{
        "repeat_id": f"neutral_repeat_{i:02d}", "audio_filename": f"neutral_repeat_{i:02d}.wav",
        "condition": "neutral", "pitch_mean": 226, "status": "not_run", "error_type": None,
        "text_sha256": high.TEXT_SHA256, "text_char_count": len(sample["text"]),
        "feature_plan_sha256": feature_sha, "feature_item_count": 1,
        **dict.fromkeys((*high.EXECUTOR_FIELDS, *high.HASH_FIELDS, *high.WAV_FIELDS, "token_hash_error_type")),
        "sampling_parameters": dict.fromkeys(high.SAMPLING),
        "sampling_matches_expected": None, "executor_input_matches_expected": None,
    } for i in range(1, repeats + 1)]
    report = {
        "schema_version": "1.0", "experiment": "seg_04_neutral_condition_repeatability",
        "evidence_kind": "diagnostic_non_confirmatory", "run_id": run_id,
        "condition": "neutral", "pitch_mean": 226, "mapped": FEATURES.copy(),
        "repeats": repeats, "segment_id": "seg_04", "source_plan_sha256": source_sha,
        "reference_prompt_version": "v0.4", "evaluator_version": None,
        "speech_speed": high.SPEED, "expected_sampling_parameters": copy.deepcopy(high.SAMPLING),
        "speech_token_hash_encoding": high.TOKEN_HASH_ENCODING,
        "feature_plan_hash_encoding": "SHA-256 of json.dumps(plan, ensure_ascii=False).encode('utf-8'); existing executor serialization",
        "seed_policy": "Runtime unchanged; this tool never sets or changes a random seed",
        "high_reference": reference, "only_feature_change": {"pitch_mean": {"from": 232, "to": 226}},
        "diagnostic_script_sha256": high.sha256(Path(__file__).read_bytes()),
        "high_helper_source_sha256": high.sha256(Path(high.__file__).read_bytes()),
        "renderer_source_sha256": high.sha256((high.PROJECT_ROOT / "src/teachintent/renderers/batonvoice.py").read_bytes()),
        "runtime": _runtime(config), **provenance,
        "status": "running", "setup_error_type": None, "cleanup_error_type": None,
        "content_fidelity_assessment": "human_listening_required", "samples": records,
    }
    template = "# seg_04 neutral condition：人工听评\n\npitch_mean=226；条目留空，由人工听评。Token count 不用于自动判定内容正确。\n\n"
    template += "\n".join(
        f"## {r['repeat_id']}\n\n- 音频：{r['audio_filename']}\n- 内容完整：是/否（待填写）\n"
        "- “所以”是否清楚：\n- 末尾“方向的变化”是否完整：\n- 其他错字/漏字/重复：\n"
        for r in records
    )
    with (run_dir / "LISTENING_TEMPLATE.md").open("x", encoding="utf-8") as handle:
        handle.write(template)
    renderer = None
    try:
        renderer = high.BatonVoiceRenderer(config, backend_factory=backend_factory or RepeatabilityBackend)
        for record in records:
            try:
                result = renderer.render(text=sample["text"], plan=copy.deepcopy(sample["plan"]),
                                         output_path=run_dir / record["audio_filename"])
                high._capture(record, result.executor_diagnostics)
                for key in high.WAV_FIELDS:
                    value = getattr(result, key)
                    record[key] = None if isinstance(value, float) and not math.isfinite(value) else value
                record["status"] = "success"
                if (record["is_truncated"] is not False or record["speech_token_roundtrip_match"] is not True
                        or any(record[k] is None for k in (*high.HASH_FIELDS, *high.WAV_FIELDS, "generation_finish_reason",
                                                          "generation_token_count", "raw_speech_token_count", "extracted_speech_token_count"))
                        or record["raw_speech_token_sha256"] != record["extracted_speech_token_sha256"]
                        or not result.output_path.is_file() or record["nan"] or record["inf"]):
                    record["status"] = "diagnostic_failure"
            except KeyboardInterrupt:
                record["status"] = "interrupted"
                raise
            except Exception as exc:
                record["status"] = "error"
                record["error_type"] = type(exc).__name__
                high._capture(record, getattr(exc, "executor_diagnostics", None))
                if isinstance(exc, high.BatonVoiceUnavailable):
                    break
            if record["sampling_matches_expected"] is False or record["executor_input_matches_expected"] is False:
                report["status"] = "condition_mismatch"
                break
        if report["status"] == "running":
            report["status"] = "completed" if all(r["status"] == "success" for r in records) else "incomplete"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        raise
    except Exception as exc:
        report["status"] = "setup_error"
        report["setup_error_type"] = type(exc).__name__
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
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--high-diagnostics", type=Path, default=DEFAULT_HIGH_DIAGNOSTICS)
    parser.add_argument("--execute", action="store_true", help="Generate neutral trials; default previews only")
    args = parser.parse_args(argv)
    try:
        root = high.project_output_root(args.output_root)
        if args.repeats < 1:
            raise ValueError("repeats must be positive")
        if not args.execute:
            sample, _, _ = neutral_sample(args.plan)
            print(json.dumps({"mode": "preview", "condition": "neutral", "pitch_mean": 226,
                              "repeats": args.repeats, "output_root": str(root), "speech_speed": high.SPEED,
                              "sampling_parameters": high.SAMPLING, "speech_token_hash_encoding": high.TOKEN_HASH_ENCODING,
                              "high_diagnostics": str(args.high_diagnostics), **sample}, ensure_ascii=False, indent=2))
            return 0
        run_dir, report = run_neutral_repeatability(high.BatonVoiceConfig.from_env(), repeats=args.repeats,
            plan_path=args.plan, output_root=root, high_diagnostics_path=args.high_diagnostics)
        print(f"{report['status']}: {run_dir}")
        return 0 if report["status"] == "completed" else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Neutral setup failed ({type(exc).__name__}); check the high-reference diagnostics, fixed plan and original BATONVOICE_* settings.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
