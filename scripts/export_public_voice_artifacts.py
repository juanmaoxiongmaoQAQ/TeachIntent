#!/usr/bin/env python3
"""Export curated public TeachIntent voice artifacts from existing WAV renders.

This script copies already-rendered Qwen3-TTS A/B WAV files byte-for-byte into
``public_demo/voice`` and writes a safe, minimal manifest for the web app. It
does not invoke any model or renderer backend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import wave
from pathlib import Path
from typing import Any

from teachintent import demo
from teachintent.renderers.qwen3_tts import (
    DEFAULT_QWEN3_TTS_MODEL,
    build_qwen3_tts_instruction,
    qwen_language_from_bcp47,
    verbal_text_from_plan,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_EXAMPLES = (
    "corrective-feedback",
    "scaffolding",
    "supportive-feedback",
)
PROMPT_VERSION = "v0.2"
PROMPT_DIR = "v0_2"
PUBLIC_ARTIFACT_VERSION = "1.0"
MAX_WAV_BYTES = 20 * 1024 * 1024
FORBIDDEN_PUBLIC_TEXT = (
    "/Users/",
    "/mnt/",
    "chengtengteng",
    "Authorization:",
    "Bearer",
    "sk-",
    "HY3_API_KEY",
    "OPENROUTER_API_KEY",
    "raw_response",
    "judge_raw_response",
)


class VoiceExportError(RuntimeError):
    """Raised when public voice artifacts cannot be exported safely."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
    if rate <= 0:
        raise VoiceExportError(f"Invalid WAV sample rate: {path.name}")
    return round(frames / rate, 4)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VoiceExportError(f"Cannot read JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise VoiceExportError(f"JSON artifact must be an object: {path}")
    return payload


def _assert_plain_child(parent: Path, child: Path) -> None:
    parent_resolved = parent.resolve()
    child_resolved = child.resolve(strict=False)
    try:
        child_resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise VoiceExportError(f"Path escapes artifact root: {child}") from exc


def _validate_wav(path: Path, expected_sha256: str) -> str:
    if path.is_symlink():
        raise VoiceExportError(f"Refusing symlink WAV: {path}")
    if not path.is_file():
        raise VoiceExportError(f"Missing source WAV: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise VoiceExportError(f"Empty WAV file: {path}")
    if size > MAX_WAV_BYTES:
        raise VoiceExportError(f"WAV exceeds 20 MB public limit: {path}")
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha256:
        raise VoiceExportError(
            f"WAV SHA-256 mismatch for {path.name}: "
            f"manifest={expected_sha256} actual={actual_sha}"
        )
    wav_duration_seconds(path)
    return actual_sha


def _condition(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    conditions = manifest.get("conditions")
    if not isinstance(conditions, dict):
        raise VoiceExportError("Source render manifest has no conditions object")
    condition = conditions.get(name)
    if not isinstance(condition, dict):
        raise VoiceExportError(f"Source render manifest has no {name} condition")
    return condition


def _source_prompt_version(manifest: dict[str, Any]) -> str | None:
    source = manifest.get("source")
    if isinstance(source, dict):
        value = source.get("prompt_version")
        if value is not None:
            return str(value)
    value = manifest.get("prompt_version")
    return str(value) if value is not None else None


def _seed(manifest: dict[str, Any]) -> int:
    if "seed" in manifest:
        return int(manifest["seed"])
    if "seed_reset_before_each_condition" in manifest:
        return int(manifest["seed_reset_before_each_condition"])
    raise VoiceExportError("Source render manifest has no seed")


def _condition_output_file(condition: dict[str, Any], expected: str) -> None:
    value = condition.get("output_file") or condition.get("audio_file") or expected
    if value != expected:
        raise VoiceExportError(f"Unexpected condition output file: {value!r}")


def _condition_duration(condition: dict[str, Any], wav_path: Path) -> float:
    backend_meta = condition.get("backend_metadata")
    if isinstance(backend_meta, dict) and backend_meta.get("duration_seconds") is not None:
        return round(float(backend_meta["duration_seconds"]), 4)
    if condition.get("duration_seconds") is not None:
        return round(float(condition["duration_seconds"]), 4)
    return wav_duration_seconds(wav_path)


def _safe_manifest_scan(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_PUBLIC_TEXT:
        if forbidden in text:
            raise VoiceExportError(
                f"Unsafe public voice manifest contains forbidden pattern: {forbidden}"
            )


def scan_public_voice_text(output_root: Path) -> None:
    """Fail if public voice JSON contains local paths or credential-like text."""
    if not output_root.exists():
        return
    for path in sorted(output_root.rglob("*.json")):
        _safe_manifest_scan(path)


def _load_recorded_example(
    example_name: str,
    example_files: dict[str, Path] | None,
) -> dict[str, Any]:
    if example_files is None:
        return demo.load_recorded_example(example_name, PROMPT_VERSION)
    path = example_files[example_name]
    doc = _read_json(path)

    return {
        "title": doc["title"],
        "description": doc["description"],
        "source": doc.get("source", {}),
        "input": doc["input"],
        "speech_plan": doc["recorded_outputs"][PROMPT_VERSION],
        "prompt_version": PROMPT_VERSION,
    }


def build_public_voice_manifest(
    *,
    example_name: str,
    example: dict[str, Any],
    source_dir: Path,
) -> dict[str, Any]:
    source_manifest_path = source_dir / "render_manifest.json"
    source_manifest = _read_json(source_manifest_path)
    speech_plan = example["speech_plan"]
    exact_text = verbal_text_from_plan(speech_plan)
    exact_text_sha = sha256_text(exact_text)
    mapping = build_qwen3_tts_instruction(speech_plan["delivery_plan"])
    neutral = _condition(source_manifest, "neutral")
    planned = _condition(source_manifest, "planned")

    if source_manifest.get("exact_verbal_text") != exact_text:
        raise VoiceExportError(f"Exact verbal text mismatch for {example_name}")
    if source_manifest.get("exact_verbal_text_sha256") != exact_text_sha:
        raise VoiceExportError(f"Exact verbal text SHA mismatch for {example_name}")
    if _source_prompt_version(source_manifest) != PROMPT_VERSION:
        raise VoiceExportError(f"Prompt version mismatch for {example_name}")

    language = str(source_manifest.get("language") or qwen_language_from_bcp47(example["input"]["output_language"]))
    speaker = str(source_manifest.get("speaker") or "")
    model = str(source_manifest.get("model") or "")
    seed = _seed(source_manifest)
    if model != DEFAULT_QWEN3_TTS_MODEL:
        raise VoiceExportError(f"Unexpected Qwen3-TTS model for {example_name}: {model}")
    if not speaker:
        raise VoiceExportError(f"Missing speaker in source manifest for {example_name}")

    for condition_name, condition in (("neutral", neutral), ("planned", planned)):
        if condition.get("text") not in (None, exact_text):
            raise VoiceExportError(f"{condition_name} text mismatch for {example_name}")
        if condition.get("text_sha256") not in (None, exact_text_sha):
            raise VoiceExportError(f"{condition_name} text SHA mismatch for {example_name}")
        if condition.get("speaker") not in (None, speaker):
            raise VoiceExportError(f"{condition_name} speaker mismatch for {example_name}")
        if condition.get("model") not in (None, model):
            raise VoiceExportError(f"{condition_name} model mismatch for {example_name}")
        if condition.get("language") not in (None, language):
            raise VoiceExportError(f"{condition_name} language mismatch for {example_name}")

    if neutral.get("instruct") != "":
        raise VoiceExportError(f"Neutral instruct must be empty for {example_name}")
    if planned.get("instruct") != mapping.instruct:
        raise VoiceExportError(f"Planned instruct mismatch for {example_name}")

    _condition_output_file(neutral, "neutral.wav")
    _condition_output_file(planned, "planned.wav")
    neutral_path = source_dir / "neutral.wav"
    planned_path = source_dir / "planned.wav"
    neutral_sha = _validate_wav(neutral_path, str(neutral.get("audio_sha256", "")))
    planned_sha = _validate_wav(planned_path, str(planned.get("audio_sha256", "")))

    ab_invariants = {
        "same_exact_verbal_text": True,
        "same_text_sha256": exact_text_sha,
        "same_speaker": True,
        "same_model": True,
        "same_language": True,
        "same_seed_and_generation_path": True,
        "only_condition_difference": "instruct",
        "neutral_instruct_is_empty": True,
        "planned_instruct_comes_only_from_delivery_plan": True,
    }
    adapter = mapping.to_dict()
    adapter["supported_controls"] = list(adapter["supported_controls"])
    adapter["unsupported_controls"] = list(adapter["unsupported_controls"])

    return {
        "artifact_version": PUBLIC_ARTIFACT_VERSION,
        "example_name": example_name,
        "prompt_version": PROMPT_VERSION,
        "exact_verbal_text": exact_text,
        "exact_verbal_text_sha256": exact_text_sha,
        "language": language,
        "speaker": speaker,
        "model": model,
        "seed": seed,
        "delivery_adapter": adapter,
        "ab_invariants": ab_invariants,
        "conditions": {
            "neutral": {
                "instruct": "",
                "audio_file": "neutral.wav",
                "audio_sha256": neutral_sha,
                "duration_seconds": _condition_duration(neutral, neutral_path),
            },
            "planned": {
                "instruct": mapping.instruct,
                "audio_file": "planned.wav",
                "audio_sha256": planned_sha,
                "duration_seconds": _condition_duration(planned, planned_path),
            },
        },
        "limitations": [
            "Qwen3-TTS instruction realization is best-effort, not deterministic acoustic control.",
            "No exact F0, timing, loudness, prominence-strength, or contour realization is claimed.",
            "Unsupported controls remain preserved in the source Speech Plan and are listed by the adapter.",
        ],
    }


def copy_public_voice_artifact(
    *,
    example_name: str,
    source_root: Path,
    output_root: Path,
    example_files: dict[str, Path] | None = None,
) -> dict[str, Any]:
    if example_name not in CURATED_EXAMPLES:
        raise VoiceExportError(f"Unknown curated voice example: {example_name}")
    source_root = Path(source_root)
    output_root = Path(output_root)
    source_dir = source_root / example_name / PROMPT_DIR
    if not source_dir.is_dir():
        raise VoiceExportError(f"Missing source voice directory: {source_dir}")
    for source_file in ("neutral.wav", "planned.wav"):
        if (source_dir / source_file).is_symlink():
            raise VoiceExportError(f"Refusing symlink source WAV: {source_file}")

    example = _load_recorded_example(example_name, example_files)
    manifest = build_public_voice_manifest(
        example_name=example_name,
        example=example,
        source_dir=source_dir,
    )

    destination_dir = output_root / example_name / PROMPT_DIR
    _assert_plain_child(output_root, destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    for file_name in ("neutral.wav", "planned.wav"):
        destination = destination_dir / file_name
        _assert_plain_child(output_root, destination)
        if destination.exists() and destination.is_symlink():
            raise VoiceExportError(f"Refusing symlink output target: {destination}")
        shutil.copyfile(source_dir / file_name, destination)
        if sha256_file(destination) != manifest["conditions"][file_name.removesuffix(".wav")]["audio_sha256"]:
            raise VoiceExportError(f"Copied WAV hash mismatch: {destination}")

    manifest_path = destination_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _safe_manifest_scan(manifest_path)
    return manifest


def export_public_voice_artifacts(
    *,
    source_root: Path,
    output_root: Path,
    example_files: dict[str, Path] | None = None,
) -> dict[str, dict[str, Any]]:
    exported: dict[str, dict[str, Any]] = {}
    for example_name in CURATED_EXAMPLES:
        exported[example_name] = copy_public_voice_artifact(
            example_name=example_name,
            source_root=source_root,
            output_root=output_root,
            example_files=example_files,
        )
    scan_public_voice_text(output_root)
    return exported


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy and verify existing curated Qwen3-TTS WAV artifacts for the "
            "public TeachIntent web demo. This does not invoke Qwen3-TTS."
        )
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=REPO_ROOT / "results" / "tts_demo",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "public_demo" / "voice",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifests = export_public_voice_artifacts(
            source_root=args.source_root,
            output_root=args.output_root,
        )
    except VoiceExportError as exc:
        print(f"Public voice export failed: {exc}", file=sys.stderr)
        return 1

    for example_name, manifest in manifests.items():
        neutral = manifest["conditions"]["neutral"]
        planned = manifest["conditions"]["planned"]
        print(f"{example_name}:")
        print(f"  neutral.wav {neutral['audio_sha256']}")
        print(f"  planned.wav {planned['audio_sha256']}")
        print(f"  planned instruct: {planned['instruct'] or '<empty>'}")
        print(
            "  controls: "
            f"{len(manifest['delivery_adapter']['supported_controls'])} supported / "
            f"{len(manifest['delivery_adapter']['unsupported_controls'])} unsupported"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
