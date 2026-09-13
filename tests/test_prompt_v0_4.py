"""Offline prompt contract checks; these do not claim model compliance."""

import copy
import hashlib
from pathlib import Path

import pytest

from teachintent.models.speech_plan import SpeechPlan
from teachintent.prompts import (
    DEFAULT_PROMPT_VERSION,
    PROMPT_VERSION_V0_4,
    build_speech_plan_prompt_for_version,
    build_speech_plan_prompt_v0_4,
    list_speech_plan_prompt_versions,
)
from teachintent.renderers.batonvoice import quantitative_plan_from_speech_plan
from teachintent.validators import iter_speech_plan_errors


def test_v04_selection_preserves_prior_prompts_and_input(canonical_input_doc):
    original = copy.deepcopy(canonical_input_doc)
    old = build_speech_plan_prompt_for_version(original, "v0.2")
    v03_path = Path(__file__).resolve().parents[1] / "src/teachintent/prompts/speech_plan_v0_3.py"
    assert hashlib.sha256(v03_path.read_bytes()).hexdigest() == (
        "95253688027363cbe083147abbe5544232ddf333081ecd94cffcdae94d061bff"
    )
    assert PROMPT_VERSION_V0_4 == "v0.4"
    assert "v0.4" in list_speech_plan_prompt_versions()
    assert DEFAULT_PROMPT_VERSION == "v0.1"
    selected = build_speech_plan_prompt_for_version(canonical_input_doc, "v0.4")
    assert selected == build_speech_plan_prompt_v0_4(canonical_input_doc)
    assert selected.system.startswith(old.system + "\n\n")
    assert selected.user == old.user
    assert selected != build_speech_plan_prompt_for_version(original, "v0.3")
    assert canonical_input_doc == original


@pytest.mark.parametrize("guidance", [
    "sparse but meaningful local control",
    "present AND both need a vocal distinction",
    "at least two meaningful local controls on the relevant distinct segments",
    "not an unconditional numeric quota",
    'if wording alone suffices, `delivery_plan: {}` remains valid',
    'acknowledgement/validation MAY use `volume: "soft"`, without also changing pitch',
    "ordinary explanation/transition normally stays neutral, with no override",
    'using `pitch_level: "high"` when pedagogically justified',
    'do not combine `pitch_level: "high"` with `volume: "loud"` by default',
    "Do not require an override for every segment",
    "never by segment index or specific keywords",
    "Do not use free-form `attitudinal_tone` or `emotion` as acoustic control signals",
    "short but complete segments, each expressing one natural teaching meaning unit",
    "Explanation and evidence may span several natural short sentences",
    "Do not fragment speech into individual words or very short, incomplete phrases",
    "Do not add SSML, pause tokens, or renderer-specific markup",
    "Segment text must remain natural, directly speakable text",
    "BEFORE choosing delivery controls",
])
def test_v04_guidance_contract(canonical_input_doc, guidance):
    prompt = build_speech_plan_prompt_v0_4(canonical_input_doc)
    assert guidance in " ".join(prompt.system.split())


def test_sparse_example_validates_and_uses_unchanged_segment_mapping():
    # Illustrative authored plan, not a model output or a production text rule.
    # Non-consecutive IDs also ensure controls bind by reference, not position.
    plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {"segments": [
            {"segment_id": "seg_12", "text": "你找对了需要比较的量。"},
            {"segment_id": "seg_20", "text": "比较之前，我们需要统一单位。"},
            {"segment_id": "seg_35", "text": "所以要先换算，再比较数值。"},
        ]},
        "delivery_plan": {"segment_overrides": [
            {"segment_id": "seg_35", "prosody": {"pitch_level": "high"}},
            {"segment_id": "seg_12", "prosody": {"volume": "soft"}},
        ]},
    }
    original = copy.deepcopy(plan)
    assert iter_speech_plan_errors(plan) == []
    SpeechPlan.model_validate(plan)
    projection = quantitative_plan_from_speech_plan(plan)
    assert [(p["pitch_mean"], p["energy_rms"]) for p in projection] == [
        (226, 0.0076), (226, 0.0080), (232, 0.0080),
    ]
    assert all(
        (p["pitch_slope"], p["energy_slope"], p["spectral_centroid"]) == (0, 0, 1885)
        for p in projection
    )
    assert [p["word"] for p in projection] == [
        s["text"] for s in plan["verbal_plan"]["segments"]
    ]
    assert plan == original
