from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import wave
from pathlib import Path

import pytest

from teachintent.renderers.qwen3_tts import (
    DEFAULT_QWEN3_TTS_MODEL,
    build_qwen3_tts_instruction,
    qwen_language_from_bcp47,
    verbal_text_from_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "export_public_voice_artifacts.py"
SPEC = importlib.util.spec_from_file_location(
    "export_public_voice_artifacts", SCRIPT_PATH
)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_wav(path: Path, frames: int = 2400) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * frames)


def _example_plan(delivery_plan: dict) -> dict:
    return {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [
                {"segment_id": "seg_01", "text": "第一句教学反馈。"},
                {"segment_id": "seg_02", "text": "第二句继续引导。"},
            ]
        },
        "delivery_plan": delivery_plan,
    }


def _write_example(
    path: Path,
    *,
    delivery_plan: dict,
) -> dict:
    plan = _example_plan(delivery_plan)
    _write_json(
        path,
        {
            "title": path.stem,
            "description": "synthetic voice export fixture",
            "source": {"case_id": path.stem},
            "input": {
                "schema_version": "1.0.0-rc.2",
                "output_language": "zh-CN",
                "instructional_content": {"content_anchor": "content"},
                "pedagogical_context": {"scenario": "scenario"},
                "learner": {
                    "level": "high_school",
                    "knowledge_state": "misconception",
                },
                "pedagogical_intent": {"primary": "corrective_feedback"},
            },
            "recorded_outputs": {"v0.2": plan},
        },
    )
    return plan


def _write_render_source(
    source_root: Path,
    example_name: str,
    *,
    plan: dict,
    unsafe_extra: bool = True,
    planned_instruct: str | None = None,
) -> None:
    source_dir = source_root / example_name / "v0_2"
    neutral_wav = source_dir / "neutral.wav"
    planned_wav = source_dir / "planned.wav"
    _write_wav(neutral_wav)
    _write_wav(planned_wav, frames=3600)
    text = verbal_text_from_plan(plan)
    text_sha = exporter.sha256_text(text)
    mapping = build_qwen3_tts_instruction(plan["delivery_plan"])
    manifest = {
        "manifest_version": "1.0",
        "source": {
            "prompt_version": "v0.2",
            "local_path": "/Users/chengtengteng/private/results",
        },
        "exact_verbal_text": text,
        "exact_verbal_text_sha256": text_sha,
        "language": qwen_language_from_bcp47("zh-CN"),
        "speaker": "Vivian",
        "model": DEFAULT_QWEN3_TTS_MODEL,
        "seed_reset_before_each_condition": 20260901,
        "delivery_adapter": mapping.to_dict(),
        "conditions": {
            "neutral": {
                "text": text,
                "text_sha256": text_sha,
                "speaker": "Vivian",
                "model": DEFAULT_QWEN3_TTS_MODEL,
                "language": "Chinese",
                "instruct": "",
                "output_file": "neutral.wav",
                "audio_sha256": _sha256(neutral_wav),
                "backend_metadata": {"duration_seconds": 0.1},
            },
            "planned": {
                "text": text,
                "text_sha256": text_sha,
                "speaker": "Vivian",
                "model": DEFAULT_QWEN3_TTS_MODEL,
                "language": "Chinese",
                "instruct": mapping.instruct
                if planned_instruct is None
                else planned_instruct,
                "output_file": "planned.wav",
                "audio_sha256": _sha256(planned_wav),
                "backend_metadata": {"duration_seconds": 0.15},
            },
        },
    }
    if unsafe_extra:
        manifest["raw_response"] = "must be stripped"
    _write_json(source_dir / "render_manifest.json", manifest)


def _write_synthetic_sources(tmp_path: Path) -> tuple[Path, Path, dict[str, Path]]:
    source_root = tmp_path / "results" / "tts_demo"
    output_root = tmp_path / "public_demo" / "voice"
    examples_root = tmp_path / "examples"
    example_files = {
        "corrective-feedback": examples_root / "corrective_feedback.json",
        "scaffolding": examples_root / "scaffolding.json",
        "supportive-feedback": examples_root / "supportive_feedback.json",
    }
    plans = {
        "corrective-feedback": _write_example(
            example_files["corrective-feedback"],
            delivery_plan={"global": {"attitudinal_tone": "安抚但纠正"}},
        ),
        "scaffolding": _write_example(
            example_files["scaffolding"],
            delivery_plan={
                "global": {
                    "attitudinal_tone": "reassuring",
                    "prosody": {"speaking_rate": "slow", "pitch_level": "low"},
                },
                "segment_overrides": [
                    {
                        "segment_id": "seg_01",
                        "prominence_targets": [
                            {"text": "继续引导", "level": "moderate"}
                        ],
                    }
                ],
            },
        ),
        "supportive-feedback": _write_example(
            example_files["supportive-feedback"],
            delivery_plan={},
        ),
    }
    for example_name, plan in plans.items():
        _write_render_source(source_root, example_name, plan=plan)
    return source_root, output_root, example_files


def test_exports_three_public_voice_artifacts_byte_identical(tmp_path: Path) -> None:
    source_root, output_root, example_files = _write_synthetic_sources(tmp_path)
    before = {
        path: _sha256(path)
        for path in sorted(source_root.rglob("*"))
        if path.is_file()
    }

    manifests = exporter.export_public_voice_artifacts(
        source_root=source_root,
        output_root=output_root,
        example_files=example_files,
    )

    assert set(manifests) == set(exporter.CURATED_EXAMPLES)
    for example_name in exporter.CURATED_EXAMPLES:
        source_dir = source_root / example_name / "v0_2"
        public_dir = output_root / example_name / "v0_2"
        assert _sha256(public_dir / "neutral.wav") == _sha256(source_dir / "neutral.wav")
        assert _sha256(public_dir / "planned.wav") == _sha256(source_dir / "planned.wav")
        public_manifest = json.loads((public_dir / "manifest.json").read_text())
        assert public_manifest["artifact_version"] == "1.0"
        assert public_manifest["prompt_version"] == "v0.2"
        assert public_manifest["conditions"]["neutral"]["instruct"] == ""
        assert public_manifest["model"] == DEFAULT_QWEN3_TTS_MODEL
        assert "/Users/" not in json.dumps(public_manifest, ensure_ascii=False)
        assert "raw_response" not in public_manifest
    assert before == {
        path: _sha256(path)
        for path in sorted(source_root.rglob("*"))
        if path.is_file()
    }


def test_planned_instruct_is_validated_against_existing_adapter(tmp_path: Path) -> None:
    source_root, _output_root, example_files = _write_synthetic_sources(tmp_path)
    bad_plan = json.loads(
        example_files["corrective-feedback"].read_text(encoding="utf-8")
    )["recorded_outputs"]["v0.2"]
    _write_render_source(
        source_root,
        "corrective-feedback",
        plan=bad_plan,
        planned_instruct="fake instruction",
    )

    with pytest.raises(exporter.VoiceExportError, match="Planned instruct mismatch"):
        exporter.copy_public_voice_artifact(
            example_name="corrective-feedback",
            source_root=source_root,
            output_root=tmp_path / "public_demo" / "voice",
            example_files=example_files,
        )


def test_exact_verbal_text_and_wav_hash_are_validated(tmp_path: Path) -> None:
    source_root, _output_root, example_files = _write_synthetic_sources(tmp_path)
    manifest_path = (
        source_root
        / "corrective-feedback"
        / "v0_2"
        / "render_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["exact_verbal_text"] = "wrong text"
    _write_json(manifest_path, manifest)

    with pytest.raises(exporter.VoiceExportError, match="Exact verbal text mismatch"):
        exporter.copy_public_voice_artifact(
            example_name="corrective-feedback",
            source_root=source_root,
            output_root=tmp_path / "public_demo" / "voice",
            example_files=example_files,
        )

    _write_synthetic_sources(tmp_path)
    wav_path = source_root / "corrective-feedback" / "v0_2" / "neutral.wav"
    wav_path.write_bytes(wav_path.read_bytes() + b"tamper")
    with pytest.raises(exporter.VoiceExportError, match="WAV SHA-256 mismatch"):
        exporter.copy_public_voice_artifact(
            example_name="corrective-feedback",
            source_root=source_root,
            output_root=tmp_path / "public_demo" / "voice",
            example_files=example_files,
        )


def test_no_op_delivery_is_retained(tmp_path: Path) -> None:
    source_root, output_root, example_files = _write_synthetic_sources(tmp_path)

    manifest = exporter.copy_public_voice_artifact(
        example_name="supportive-feedback",
        source_root=source_root,
        output_root=output_root,
        example_files=example_files,
    )

    assert manifest["delivery_adapter"]["instruct"] == ""
    assert manifest["delivery_adapter"]["supported_controls"] == []
    assert manifest["conditions"]["planned"]["instruct"] == ""
    assert (output_root / "supportive-feedback" / "v0_2" / "neutral.wav").is_file()
    assert (output_root / "supportive-feedback" / "v0_2" / "planned.wav").is_file()


def test_secret_scanner_and_path_traversal_guards(tmp_path: Path) -> None:
    public_root = tmp_path / "public_demo" / "voice"
    _write_json(public_root / "bad" / "manifest.json", {"leak": "Bearer token"})

    with pytest.raises(exporter.VoiceExportError, match="forbidden pattern"):
        exporter.scan_public_voice_text(public_root)

    with pytest.raises(exporter.VoiceExportError, match="Unknown curated"):
        exporter.copy_public_voice_artifact(
            example_name="../bad",
            source_root=tmp_path / "results" / "tts_demo",
            output_root=public_root,
            example_files={},
        )
