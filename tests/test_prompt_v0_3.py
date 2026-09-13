from teachintent.prompts import (
    PROMPT_VERSION_V0_3,
    build_speech_plan_prompt_for_version,
)
from teachintent.prompts.speech_plan_v0_2 import build_speech_plan_prompt as build_v02


def doc():
    return {
        "schema_version": "1.0.0-rc.2", "output_language": "zh-CN",
        "instructional_content": {"subject": "physics", "content_anchor": "速度包含大小和方向。"},
        "pedagogical_context": {"scenario": "misconception", "learner_utterance": "速度不变就没有加速度"},
        "learner": {"level": "high_school", "knowledge_state": "misconception", "affective_state": "frustrated"},
        "pedagogical_intent": {"primary": "corrective_feedback"},
    }


def test_v03_is_explicit_and_v02_is_unchanged():
    assert PROMPT_VERSION_V0_3 == "v0.3"
    old = build_v02(doc())
    new = build_speech_plan_prompt_for_version(doc(), "v0.3")
    assert old.system != new.system
    assert "# v0.3 local delivery guidance" in new.system
    assert "segment-level control" in new.system


def test_v03_requires_sparse_conditional_controls_not_full_segmentation():
    prompt = build_speech_plan_prompt_for_version(doc(), "v0.3").system
    assert "not a request to control every segment" in prompt
    assert "ordinary explanation/transition MAY remain without an override" in prompt
    assert "Do not invent role" in prompt
    assert 'volume: "soft"' in prompt
    assert 'pitch_level: "high"' in prompt


def test_v03_contract_example_validates():
    from teachintent.models.speech_plan import SpeechPlan
    plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {"segments": [
            {"segment_id": "seg_01", "text": "你观察到这一点是对的。"},
            {"segment_id": "seg_02", "text": "但方向也很重要。"},
            {"segment_id": "seg_03", "text": "所以加速度不为零。"},
        ]},
        "delivery_plan": {"segment_overrides": [
            {"segment_id": "seg_01", "prosody": {"volume": "soft"}},
            {"segment_id": "seg_03", "prosody": {"pitch_level": "high"}},
        ]},
    }
    assert SpeechPlan.model_validate(plan).delivery_plan.segment_overrides
