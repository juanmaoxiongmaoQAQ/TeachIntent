"""Shared fixtures for the TeachIntent contract test suite.

The two canonical documents are transcribed verbatim from the research
specifications:

* input  — docs/problem_definition.md section 12 (Canonical Example);
* speech plan — docs/speech_plan_schema.md section 16 (Canonical Example).
"""

from __future__ import annotations

import copy

import pytest

CANONICAL_INPUT_DOC = {
    "schema_version": "1.0.0-rc.2",
    "output_language": "zh-CN",
    "instructional_content": {
        "subject": "physics",
        "topic": "speed_and_acceleration",
        "content_anchor": (
            "速度表示物体运动的快慢。加速度表示速度随时间变化的快慢。"
            "速度大不意味着加速度一定大。"
        ),
    },
    "pedagogical_context": {
        "scenario": "The learner has just answered a conceptual question.",
        "learner_utterance": "速度越大，加速度一定越大。",
    },
    "learner": {
        "level": "middle_school",
        "knowledge_state": "misconception",
        "affective_state": "slightly_frustrated",
    },
    "pedagogical_intent": {
        "primary": "corrective_feedback",
    },
}

CANONICAL_SPEECH_PLAN_DOC = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [
            {"segment_id": "seg_01", "text": "你的思路已经很接近了。"},
            {"segment_id": "seg_02", "text": "不过这里有一个关键点需要纠正。"},
            {"segment_id": "seg_03", "text": "速度大，并不代表加速度一定大。"},
            {
                "segment_id": "seg_04",
                "text": "速度描述运动的快慢，而加速度描述速度变化的快慢。",
            },
        ]
    },
    "delivery_plan": {
        "global": {
            "attitudinal_tone": "supportive",
            "emotion": "calm",
        },
        "segment_overrides": [
            {
                "segment_id": "seg_02",
                "attitudinal_tone": "firm but supportive",
                "prosody": {"speaking_rate": "slow"},
                "prominence_targets": [
                    {"text": "关键点", "level": "strong"}
                ],
                "boundary_after": {"strength": "strong"},
            },
            {
                "segment_id": "seg_03",
                "prosody": {"speaking_rate": "slow"},
                "prominence_targets": [
                    {"text": "速度大", "level": "strong"},
                    {"text": "并不代表", "level": "strong"},
                    {"text": "加速度一定大", "level": "strong"},
                ],
            },
            {
                "segment_id": "seg_04",
                "prosody": {"speaking_rate": "slow"},
                "prominence_targets": [
                    {"text": "运动的快慢", "level": "moderate"},
                    {"text": "速度变化的快慢", "level": "moderate"},
                ],
            },
        ],
    },
}


@pytest.fixture
def canonical_input_doc() -> dict:
    return copy.deepcopy(CANONICAL_INPUT_DOC)


@pytest.fixture
def canonical_speech_plan_doc() -> dict:
    return copy.deepcopy(CANONICAL_SPEECH_PLAN_DOC)
