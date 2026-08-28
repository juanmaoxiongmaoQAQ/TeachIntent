"""Tests for the evidence path grammar, resolution, and grounding.

Covers: valid/invalid path syntax, nonexistent key, out-of-bounds index,
string grounding, scalar grounding, object/array canonical grounding,
empty delivery_plan evidence, evidence text mismatch.
"""

from __future__ import annotations

import pytest

from teachintent.evaluator import (
    EVIDENCE_PATH_RE,
    is_grounded,
    resolve_evidence_source,
    validate_evidence,
    validate_evidence_path,
)
from teachintent.evaluator.errors import EvidenceGroundingError, EvidenceSourceError

# Canonical documents for evidence resolution.
INPUT_DOC = {
    "output_language": "zh-CN",
    "instructional_content": {
        "subject": "physics",
        "topic": "speed_and_acceleration",
        "content_anchor": "速度表示物体运动的快慢。加速度表示速度随时间变化的快慢。速度大不意味着加速度一定大。",
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
    "pedagogical_intent": {"primary": "corrective_feedback"},
}

PLAN_DOC = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [
            {"segment_id": "seg_01", "text": "你的思路已经很接近了。"},
            {"segment_id": "seg_02", "text": "不过这里有一个关键点需要纠正。"},
        ]
    },
    "delivery_plan": {
        "global": {"attitudinal_tone": "supportive", "emotion": "calm"},
        "segment_overrides": [
            {
                "segment_id": "seg_02",
                "prosody": {"speaking_rate": "slow"},
                "prominence_targets": [
                    {"text": "关键点", "level": "strong"}
                ],
            }
        ],
    },
}


# ---------------------------------------------------------------------------
# Valid path syntax.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "input",
        "plan",
        "input.instructional_content.content_anchor",
        "input.learner.knowledge_state",
        "plan.verbal_plan.segments[0].text",
        "plan.delivery_plan",
        "plan.delivery_plan.segment_overrides[0].prominence_targets",
        "plan.verbal_plan.segments[1].text",
    ],
)
def test_valid_evidence_path_syntax(path):
    validate_evidence_path(path)
    assert EVIDENCE_PATH_RE.match(path) is not None


# ---------------------------------------------------------------------------
# Invalid path syntax.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "verbal_plan.segments[0].text",           # missing root
        "plan.verbal_plan.segments.0.text",       # dot-index not allowed
        'plan["verbal_plan"].segments[0].text',   # bracket-key not allowed
        "plan.verbal_plan.segments[*].text",      # wildcard not allowed
        "plan.verbal_plan.segments[-1].text",     # negative index not allowed
        "",                                        # empty
        "input..content_anchor",                  # double dot
        "plan.verbal_plan.segments[01].text",     # leading zero (not "0")
        "root.something",                         # invalid root
    ],
)
def test_invalid_evidence_path_syntax(path):
    with pytest.raises(EvidenceSourceError):
        validate_evidence_path(path)


# ---------------------------------------------------------------------------
# Path resolution: nonexistent key.
# ---------------------------------------------------------------------------


def test_resolve_nonexistent_key():
    with pytest.raises(EvidenceSourceError, match="not found"):
        resolve_evidence_source("input.instructional_content.nonexistent", INPUT_DOC, PLAN_DOC)


def test_resolve_nonexistent_top_key():
    with pytest.raises(EvidenceSourceError):
        resolve_evidence_source("input.nonexistent_field", INPUT_DOC, PLAN_DOC)


# ---------------------------------------------------------------------------
# Path resolution: out-of-bounds index.
# ---------------------------------------------------------------------------


def test_resolve_out_of_bounds_index():
    with pytest.raises(EvidenceSourceError, match="out of bounds"):
        resolve_evidence_source("plan.verbal_plan.segments[5].text", INPUT_DOC, PLAN_DOC)


def test_resolve_index_into_non_array():
    # Indexing into a dict (verbal_plan is a dict, not an array).
    with pytest.raises(EvidenceSourceError, match="non-array"):
        resolve_evidence_source("plan.verbal_plan[0]", INPUT_DOC, PLAN_DOC)


# ---------------------------------------------------------------------------
# String evidence grounding.
# ---------------------------------------------------------------------------


def test_string_grounding_exact_substring():
    resolved = resolve_evidence_source("input.instructional_content.content_anchor", INPUT_DOC, PLAN_DOC)
    assert is_grounded("速度表示物体运动的快慢", resolved)
    assert is_grounded(resolved, resolved)


def test_string_grounding_mismatch():
    resolved = resolve_evidence_source("input.learner.knowledge_state", INPUT_DOC, PLAN_DOC)
    assert not is_grounded("correct_understanding", resolved)


def test_plan_segment_text_grounding():
    resolved = resolve_evidence_source("plan.verbal_plan.segments[0].text", INPUT_DOC, PLAN_DOC)
    assert is_grounded("你的思路", resolved)


# ---------------------------------------------------------------------------
# Scalar grounding (number/bool/null).
# ---------------------------------------------------------------------------


def test_scalar_grounding_number():
    assert is_grounded("3", 3)
    assert not is_grounded("3.0", 3)


def test_scalar_grounding_bool():
    assert is_grounded("true", True)
    assert is_grounded("false", False)
    assert not is_grounded("True", True)


def test_scalar_grounding_null():
    assert is_grounded("null", None)
    assert not is_grounded("None", None)


# ---------------------------------------------------------------------------
# Object/array canonical grounding.
# ---------------------------------------------------------------------------


def test_object_canonical_grounding():
    obj = {"a": 1, "b": [2, 3]}
    # canonical: {"a":1,"b":[2,3]}
    assert is_grounded('{"a":1,"b":[2,3]}', obj)
    assert is_grounded('"a":1', obj)  # substring of canonical


def test_array_canonical_grounding():
    arr = [{"x": 1}, {"y": 2}]
    # canonical: [{"x":1},{"y":2}]
    assert is_grounded('[{"x":1},{"y":2}]', arr)


def test_canonical_json_sorts_keys():
    obj = {"b": 1, "a": 2}
    # canonical: {"a":2,"b":1}
    assert is_grounded('{"a":2,"b":1}', obj)
    assert not is_grounded('{"b":1,"a":2}', obj)


# ---------------------------------------------------------------------------
# Empty delivery_plan evidence.
# ---------------------------------------------------------------------------


def test_empty_delivery_plan_grounding():
    plan = {"schema_version": "1.0.0-rc.3", "verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "x"}]}, "delivery_plan": {}}
    resolved = resolve_evidence_source("plan.delivery_plan", INPUT_DOC, plan)
    assert resolved == {}
    assert is_grounded("{}", resolved)
    assert not is_grounded("null", resolved)


# ---------------------------------------------------------------------------
# Evidence text mismatch -> evidence_grounding_error.
# ---------------------------------------------------------------------------


def test_validate_evidence_text_mismatch_raises_grounding_error():
    with pytest.raises(EvidenceGroundingError):
        validate_evidence(
            "input.learner.knowledge_state",
            "correct_understanding",  # actual is "misconception"
            INPUT_DOC,
            PLAN_DOC,
        )


def test_validate_evidence_full_success():
    validate_evidence(
        "input.instructional_content.content_anchor",
        "速度表示物体运动的快慢",
        INPUT_DOC,
        PLAN_DOC,
    )
    # Canonical JSON with sort_keys=True: keys are sorted at every level.
    validate_evidence("plan.delivery_plan", '{"global":{"attitudinal_tone":"supportive","emotion":"calm"},"segment_overrides":[{"prominence_targets":[{"level":"strong","text":"关键点"}],"prosody":{"speaking_rate":"slow"},"segment_id":"seg_02"}]}', INPUT_DOC, PLAN_DOC)


# ---------------------------------------------------------------------------
# Root-only paths.
# ---------------------------------------------------------------------------


def test_root_input_resolves_to_full_input():
    resolved = resolve_evidence_source("input", INPUT_DOC, PLAN_DOC)
    assert resolved is INPUT_DOC


def test_root_plan_resolves_to_full_plan():
    resolved = resolve_evidence_source("plan", INPUT_DOC, PLAN_DOC)
    assert resolved is PLAN_DOC
