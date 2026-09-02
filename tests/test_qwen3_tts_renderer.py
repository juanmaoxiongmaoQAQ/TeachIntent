from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from teachintent.demo import load_recorded_example
from teachintent.renderers.qwen3_tts import (
    AB_STATEMENT,
    TTSRenderError,
    build_qwen3_tts_instruction,
    qwen_language_from_bcp47,
    render_ab_comparison,
    verbal_text_from_plan,
)


class FakeBackend:
    model_id = "fake/local-custom-voice"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_custom_voice(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs.copy())
        output_path = Path(kwargs["output_path"])
        output_path.write_bytes(b"RIFF-fake-test-wave")
        return {"sample_rate": 24000, "sample_count": 24000}


def test_maps_only_supported_global_controls() -> None:
    mapping = build_qwen3_tts_instruction(
        {
            "global": {
                "attitudinal_tone": "温和而坚定",
                "emotion": "平静",
                "prosody": {
                    "speaking_rate": "slow",
                    "volume": "soft",
                    "pitch_level": "low",
                    "pitch_range": "narrow",
                },
            },
            "segment_overrides": [
                {"segment_id": "seg_01", "contour_shape": "rising"}
            ],
        }
    )

    assert mapping.instruct == (
        "整体采用“温和而坚定”的态度语气。 整体表达“平静”的情绪。 "
        "整体使用较慢的语速。 整体使用较轻柔的音量。"
    )
    assert [item["path"] for item in mapping.supported_controls] == [
        "delivery_plan.global.attitudinal_tone",
        "delivery_plan.global.emotion",
        "delivery_plan.global.prosody.speaking_rate",
        "delivery_plan.global.prosody.volume",
    ]
    assert [item["path"] for item in mapping.unsupported_controls] == [
        "delivery_plan.global.prosody.pitch_level",
        "delivery_plan.global.prosody.pitch_range",
        "delivery_plan.segment_overrides[0].contour_shape",
    ]


def test_empty_and_unknown_controls_are_not_invented() -> None:
    assert build_qwen3_tts_instruction({}).to_dict() == {
        "instruct": "",
        "supported_controls": (),
        "unsupported_controls": (),
    }
    mapping = build_qwen3_tts_instruction(
        {"global": {"prosody": {"speaking_rate": "warp"}}}
    )
    assert mapping.instruct == ""
    assert mapping.supported_controls == ()
    assert mapping.unsupported_controls[0]["value"] == "warp"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("zh-CN", "Chinese"), ("en-US", "English"), ("xx-Test", "Auto")],
)
def test_language_mapping(tag: str, expected: str) -> None:
    assert qwen_language_from_bcp47(tag) == expected


def test_ab_render_varies_only_instruction(tmp_path: Path) -> None:
    example = load_recorded_example("corrective-feedback", "v0.2")
    backend = FakeBackend()

    manifest = render_ab_comparison(
        example=example,
        backend=backend,
        speaker="Vivian",
        output_dir=tmp_path,
        seed=7,
    )

    assert len(backend.calls) == 2
    neutral, planned = backend.calls
    for invariant in ("text", "language", "speaker", "seed"):
        assert neutral[invariant] == planned[invariant]
    assert neutral["instruct"] == ""
    assert planned["instruct"] == "整体采用“安抚但纠正”的态度语气。"
    assert neutral["output_path"] == tmp_path / "neutral.wav"
    assert planned["output_path"] == tmp_path / "planned.wav"
    assert manifest["comparison_statement"] == AB_STATEMENT
    assert manifest["ab_invariants"]["only_condition_difference"] == "instruct"
    assert manifest["exact_verbal_text"] == verbal_text_from_plan(
        example["speech_plan"]
    )
    on_disk = json.loads((tmp_path / "render_manifest.json").read_text())
    assert on_disk["conditions"]["neutral"]["instruct"] == ""
    assert on_disk["conditions"]["planned"]["instruct"] == planned["instruct"]


def test_ab_render_refuses_to_overwrite(tmp_path: Path) -> None:
    (tmp_path / "neutral.wav").write_bytes(b"existing")
    with pytest.raises(TTSRenderError, match="Refusing to overwrite"):
        render_ab_comparison(
            example=load_recorded_example("corrective-feedback", "v0.2"),
            backend=FakeBackend(),
            speaker="Vivian",
            output_dir=tmp_path,
        )


def test_import_does_not_load_optional_runtime() -> None:
    assert "qwen_tts" not in sys.modules
    assert "gradio" not in sys.modules
