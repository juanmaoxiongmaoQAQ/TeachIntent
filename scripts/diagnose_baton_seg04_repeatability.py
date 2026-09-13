#!/usr/bin/env python3
"""Fixed-condition seg_04 repeats; default is an offline, write-free preview.

--execute uses the SAME verified BATONVOICE_* environment/speaker as the reference
experiment, with speed 0.85. No seeds are set or changed. Each planned repeat is
attempted at most once; failures consume their slot, never cause replacement
trials. One lazy backend is reused and finally cleaned up. Token hashes are
diagnostic-only: the production renderer, sampling and API remain untouched.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from uuid import uuid4

from teachintent.models.speech_plan import SpeechPlan
from teachintent.renderers._project_outputs import PROJECT_ROOT, project_output_root
from teachintent.renderers.batonvoice import (
    BatonVoiceConfig, BatonVoiceRenderer, BatonVoiceUnavailable,
    _UnifiedTTSBackend, quantitative_plan_from_speech_plan,
)
from teachintent.validators import validate_speech_plan_document

DEFAULT_PLAN = PROJECT_ROOT / "cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs/baton-seg04-repeatability"
DEFAULT_REPEATS = 8
TEXT_SHA256 = "0454135332981793b482b110de9b1f459da97bb5a44590fddcc7f48b99e2a591"
FEATURES = {"pitch_mean": 232, "energy_rms": 0.008, "pitch_slope": 0,
            "energy_slope": 0, "spectral_centroid": 1885}
SPEED = 0.85
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 2048,
            "repetition_penalty": 1.1, "stop_token_ids": [151645, 151643]}
TOKEN_HASH_ENCODING = "SHA-256 of UTF-8 JSON integer array; separators=(',', ':'); ensure_ascii=True; no whitespace or newline"
EXECUTOR_FIELDS = (
    "generation_finish_reason", "generation_stop_reason", "generation_token_count", "is_truncated",
    "raw_speech_token_count", "extracted_speech_token_count", "speech_token_roundtrip_match",
    "speech_token_roundtrip_first_mismatch",
)
HASH_FIELDS = ("raw_speech_token_sha256", "extracted_speech_token_sha256")
WAV_FIELDS = ("sample_rate", "duration_seconds", "channels", "peak", "nan", "inf")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def token_sequence_sha256(tokens: list[int]) -> str:
    if any(type(token) is not int for token in tokens):
        raise ValueError("Token hashing requires integers")
    return sha256(json.dumps(tokens, separators=(",", ":"), ensure_ascii=True,
                             allow_nan=False).encode("utf-8"))


class _HashObserver:
    """Forward original observations, then hash their tokens without retaining arrays."""

    def __init__(self, delegate, hashes: dict):
        self.delegate = delegate
        self.hashes = hashes

    def observe(self, event, value):
        self.delegate.observe(event, value)
        try:
            if event == "generation":
                # Reuse the existing Path A restoration, including its offset rule.
                raw = self.delegate._raw_speech_tokens
                if raw is not None:
                    self.hashes[HASH_FIELDS[0]] = token_sequence_sha256(raw)
            elif event == "extraction":
                self.hashes[HASH_FIELDS[1]] = token_sequence_sha256(value)
        except Exception as exc:
            self.hashes["token_hash_error_type"] = type(exc).__name__
            # Observation must never alter the generation or extraction outcome.


class RepeatabilityBackend(_UnifiedTTSBackend):
    """Instance-only diagnostic instrumentation around the unchanged backend.

    This deliberately depends on private observer hooks; offline tests verify
    their contract. No module/global patch, additional generation, tokenizer call
    or alternative token path is used. Path B still drives audio synthesis.
    """

    def render(self, text, plan, output_path):
        self._repeat_hashes = {**dict.fromkeys(HASH_FIELDS), "token_hash_error_type": None}
        try:
            result = super().render(text, plan, output_path)
            return replace(result, executor_diagnostics={
                **(result.executor_diagnostics or {}), **self._repeat_hashes,
            })
        except Exception as exc:
            exc.executor_diagnostics = {**(getattr(exc, "executor_diagnostics", None) or {}),
                                        **self._repeat_hashes}
            raise

    def _render_observed(self, text, feature_json, output_path):
        observer = self._tts._executor_observer
        self._tts._executor_observer = _HashObserver(observer, self._repeat_hashes)
        try:
            return super()._render_observed(text, feature_json, output_path)
        finally:
            self._tts._executor_observer = observer


def fixed_sample(plan_path: Path) -> tuple[dict, str]:
    content = plan_path.read_bytes()
    doc = json.loads(content)
    validate_speech_plan_document(doc)
    SpeechPlan.model_validate(doc)
    mapped = quantitative_plan_from_speech_plan(doc)
    by_id = {segment["segment_id"]: item
             for segment, item in zip(doc["verbal_plan"]["segments"], mapped)}
    item = by_id["seg_04"]
    if sha256(item["word"].encode("utf-8")) != TEXT_SHA256:
        raise ValueError("seg_04 text differs from the fixed reference")
    if {k: v for k, v in item.items() if k != "word"} != FEATURES:
        raise ValueError("seg_04 features differ from the fixed reference")
    return {"text": item["word"], "plan": [item]}, sha256(content)


def check_config(config: BatonVoiceConfig) -> dict:
    if config.speech_speed != SPEED or config.missing_paths():
        raise ValueError("The same existing runtime and speech_speed=0.85 are required")
    if config.wetext_fst_dir is None:
        raise ValueError("Local WeText FST is required")
    fsts = [config.wetext_fst_dir / lang / "tn" / name
            for lang in ("zh", "en") for name in ("tagger.fst", "verbalizer.fst")]
    if any(not path.is_file() for path in fsts):
        raise ValueError("Complete local FST files are required")
    generation_bytes = (config.model_path / "generation_config.json").read_bytes()
    generation = json.loads(generation_bytes)
    if (any(generation.get(k) != SAMPLING[k] for k in ("temperature", "top_p", "top_k"))
            or generation.get("eos_token_id") != SAMPLING["stop_token_ids"]):
        raise ValueError("Model sampling differs from the fixed reference")
    return {
        "generation_config_sha256": sha256(generation_bytes),
        "fst_sha256": {str(p.relative_to(config.wetext_fst_dir)): sha256(p.read_bytes()) for p in fsts},
        "prompt_audio_sha256": sha256(config.prompt_audio_path.read_bytes()) if config.prompt_audio_path else None,
    }


def _capture(record: dict, diagnostics: dict | None) -> None:
    if not diagnostics:
        return
    for key in (*EXECUTOR_FIELDS, *HASH_FIELDS, "token_hash_error_type"):
        record[key] = copy.deepcopy(diagnostics.get(key))
    actual = diagnostics.get("sampling_parameters") or {}
    record["sampling_parameters"] = {key: copy.deepcopy(actual.get(key)) for key in SAMPLING}
    record["sampling_matches_expected"] = record["sampling_parameters"] == SAMPLING
    record["executor_input_matches_expected"] = all(
        diagnostics.get(actual) == record[expected] for actual, expected in (
            ("input_text_sha256", "text_sha256"), ("input_text_char_count", "text_char_count"),
            ("feature_plan_sha256", "feature_plan_sha256"), ("feature_item_count", "feature_item_count"),
        )
    )


def run_repeatability(
    config: BatonVoiceConfig, *, repeats: int = DEFAULT_REPEATS,
    plan_path: Path = DEFAULT_PLAN, output_root: Path = DEFAULT_OUTPUT_ROOT,
    backend_factory=None,
) -> tuple[Path, dict]:
    """One planned call per slot. Execution diagnostics never grade spoken content."""
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    output_root = project_output_root(output_root)
    sample, plan_sha = fixed_sample(plan_path)
    provenance = check_config(config)  # No model imports or runtime initialization.
    feature_sha = sha256(json.dumps(sample["plan"], ensure_ascii=False).encode("utf-8"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    records = [{
        "repeat_id": f"repeat_{i:02d}", "audio_filename": f"repeat_{i:02d}.wav",
        "status": "not_run", "error_type": None,
        "text_sha256": TEXT_SHA256, "text_char_count": len(sample["text"]),
        "feature_plan_sha256": feature_sha, "feature_item_count": 1,
        **dict.fromkeys((*EXECUTOR_FIELDS, *HASH_FIELDS, *WAV_FIELDS, "token_hash_error_type")),
        "sampling_parameters": dict.fromkeys(SAMPLING),
        "sampling_matches_expected": None, "executor_input_matches_expected": None,
    } for i in range(1, repeats + 1)]
    report = {
        "schema_version": "1.0", "experiment": "seg_04_fixed_condition_repeatability",
        "evidence_kind": "diagnostic_non_confirmatory", "run_id": run_id,
        "repeats": repeats, "segment_id": "seg_04", "source_plan_sha256": plan_sha,
        "reference_prompt_version": "v0.4", "evaluator_version": None,
        "speech_speed": SPEED, "mapped": FEATURES.copy(), "expected_sampling_parameters": copy.deepcopy(SAMPLING),
        "speech_token_hash_encoding": TOKEN_HASH_ENCODING,
        "feature_plan_hash_encoding": "SHA-256 of json.dumps(plan, ensure_ascii=False).encode('utf-8'); existing executor serialization",
        "seed_policy": "Runtime unchanged; this tool never sets or changes a random seed",
        "diagnostic_script_sha256": sha256(Path(__file__).read_bytes()),
        "renderer_source_sha256": sha256((PROJECT_ROOT / "src/teachintent/renderers/batonvoice.py").read_bytes()),
        "runtime": {**{k: str(getattr(config, k)) if getattr(config, k) is not None else None
                       for k in ("model_path", "cosyvoice_model_dir", "batonvoice_source_dir", "wetext_fst_dir", "prompt_audio_path")},
                    "tensor_parallel_size": config.tensor_parallel_size,
                    "gpu_memory_utilization": config.gpu_memory_utilization, "fp16": config.fp16},
        **provenance, "status": "running", "setup_error_type": None, "cleanup_error_type": None,
        "content_fidelity_assessment": "human_listening_required", "samples": records,
    }
    template = "# seg_04 固定条件重复实验：人工听评\n\n所有条目留空，由人工听评；执行成功不代表内容正确。\n\n"
    template += "\n".join(
        f"## {r['repeat_id']}\n\n- 音频：{r['audio_filename']}\n- 内容完整：是/否（待填写）\n"
        "- “所以”是否清楚：\n- 末尾“变化”是否完整：\n- 其他错字/漏字/重复：\n"
        for r in records
    )
    with (run_dir / "LISTENING_TEMPLATE.md").open("x", encoding="utf-8") as handle:
        handle.write(template)
    renderer = None
    try:
        renderer = BatonVoiceRenderer(config, backend_factory=backend_factory or RepeatabilityBackend)
        for record in records:
            try:
                result = renderer.render(text=sample["text"], plan=copy.deepcopy(sample["plan"]),
                                         output_path=run_dir / record["audio_filename"])
                _capture(record, result.executor_diagnostics)
                for key in WAV_FIELDS:
                    value = getattr(result, key)
                    record[key] = None if isinstance(value, float) and not math.isfinite(value) else value
                record["status"] = "success"
                if (record["is_truncated"] is not False or record["speech_token_roundtrip_match"] is not True
                        or any(record[k] is None for k in (*HASH_FIELDS, *WAV_FIELDS, "generation_finish_reason",
                                                          "generation_token_count", "raw_speech_token_count",
                                                          "extracted_speech_token_count"))
                        or record["raw_speech_token_sha256"] != record["extracted_speech_token_sha256"]
                        or not result.output_path.is_file() or record["nan"] or record["inf"]):
                    record["status"] = "diagnostic_failure"
            except KeyboardInterrupt:
                record["status"] = "interrupted"
                raise
            except Exception as exc:
                record["status"] = "error"
                record["error_type"] = type(exc).__name__
                _capture(record, getattr(exc, "executor_diagnostics", None))
                if isinstance(exc, BatonVoiceUnavailable):
                    break  # Do not repeatedly attempt backend loading.
            if record["sampling_matches_expected"] is False or record["executor_input_matches_expected"] is False:
                report["status"] = "condition_mismatch"
                break  # Never continue knowingly changed conditions or silently repair them.
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
    parser.add_argument("--execute", action="store_true", help="Run synthesis; default previews only")
    args = parser.parse_args(argv)
    try:
        root = project_output_root(args.output_root)
        if args.repeats < 1:
            raise ValueError("repeats must be positive")
        if not args.execute:
            sample, _ = fixed_sample(args.plan)
            print(json.dumps({"mode": "preview", "repeats": args.repeats, "output_root": str(root),
                              "speech_speed": SPEED, "sampling_parameters": SAMPLING,
                              "speech_token_hash_encoding": TOKEN_HASH_ENCODING, **sample}, ensure_ascii=False, indent=2))
            return 0
        run_dir, report = run_repeatability(BatonVoiceConfig.from_env(), repeats=args.repeats,
                                            plan_path=args.plan, output_root=root)
        print(f"{report['status']}: {run_dir}")
        return 0 if report["status"] == "completed" else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Repeatability setup failed ({type(exc).__name__}); check the fixed plan and BATONVOICE_* settings.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
