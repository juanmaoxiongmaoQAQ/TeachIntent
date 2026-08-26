"""Pydantic cross-field semantic validator tests for the Speech Plan.

Covers the rules that the JSON Schema layer deliberately does not carry
(Rule 15 division of labor in docs/speech_plan_schema.md):

* Rule 1 — segment ID uniqueness;
* Rule 2 — segment override reference integrity;
* Rule 3 — one override per segment;
* Rule 4 — override must contain a control besides segment_id;
* Rule 5 — prominence span integrity (exact substring, exactly once,
  overlapping occurrences counted);
* Rule 7 — empty-object policy (Pydantic mirror of minProperties);
* Rule 8 — contour_shape vs segment-level pitch_level / pitch_range;
* Rule 10 — non-empty verbal plan (Pydantic mirror);
* Rule 11 — meaningful ``default`` resets;
* Rule 12 — prominence non-overlap (duplicates and overlapping spans);
* Rule 14 — schema version exactness (Literal mirror).

Error messages carry rule tags; tests assert them.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teachintent.models import SpeechPlan
from teachintent.models.speech_plan import (
    count_occurrences,
    resolve_span,
    spans_overlap,
)


def make_plan(
    segments: list[dict] | None = None,
    overrides: list[dict] | None = None,
    global_delivery: dict | None = None,
    schema_version: str = "1.0.0-rc.3",
) -> dict:
    """Build a small speech plan document for semantic rule tests."""
    if segments is None:
        segments = [{"segment_id": "seg_01", "text": "速度大，并不代表加速度一定大。"}]
    delivery: dict = {}
    if global_delivery is not None:
        delivery["global"] = global_delivery
    if overrides is not None:
        delivery["segment_overrides"] = overrides
    return {
        "schema_version": schema_version,
        "verbal_plan": {"segments": segments},
        "delivery_plan": delivery,
    }


def assert_rejected(doc: dict, message_contains: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        SpeechPlan.model_validate(doc)
    assert message_contains in str(exc_info.value), (
        f"expected error containing {message_contains!r}, "
        f"got: {exc_info.value}"
    )


def assert_accepted(doc: dict) -> SpeechPlan:
    return SpeechPlan.model_validate(doc)


# ---------------------------------------------------------------------------
# Canonical document.
# ---------------------------------------------------------------------------


def test_canonical_example_parses(canonical_speech_plan_doc) -> None:
    model = assert_accepted(canonical_speech_plan_doc)
    assert model.schema_version == "1.0.0-rc.3"
    assert len(model.verbal_plan.segments) == 4


def test_empty_delivery_plan_parses(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"] = {}
    assert_accepted(canonical_speech_plan_doc)


# ---------------------------------------------------------------------------
# Rule 1 — segment ID uniqueness.
# ---------------------------------------------------------------------------


def test_rule_1_duplicate_segment_ids_are_rejected() -> None:
    doc = make_plan(
        segments=[
            {"segment_id": "seg_01", "text": "第一句。"},
            {"segment_id": "seg_01", "text": "第二句。"},
        ]
    )
    assert_rejected(doc, "Rule 1 (segment ID uniqueness)")


def test_rule_1_distinct_segment_ids_are_accepted() -> None:
    doc = make_plan(
        segments=[
            {"segment_id": "seg_01", "text": "第一句。"},
            {"segment_id": "seg_02", "text": "第二句。"},
        ]
    )
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 2 — segment override reference integrity.
# ---------------------------------------------------------------------------


def test_rule_2_override_for_unknown_segment_is_rejected() -> None:
    doc = make_plan(
        overrides=[{"segment_id": "seg_99", "emotion": "calm"}]
    )
    assert_rejected(doc, "Rule 2 (segment reference integrity)")


def test_rule_2_override_for_existing_segment_is_accepted() -> None:
    doc = make_plan(overrides=[{"segment_id": "seg_01", "emotion": "calm"}])
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 3 — one override per segment.
# ---------------------------------------------------------------------------


def test_rule_3_two_overrides_for_same_segment_are_rejected() -> None:
    doc = make_plan(
        overrides=[
            {"segment_id": "seg_01", "emotion": "calm"},
            {"segment_id": "seg_01", "prosody": {"speaking_rate": "slow"}},
        ]
    )
    assert_rejected(doc, "Rule 3 (one override per segment)")


def test_rule_3_overrides_for_distinct_segments_are_accepted() -> None:
    doc = make_plan(
        segments=[
            {"segment_id": "seg_01", "text": "第一句。"},
            {"segment_id": "seg_02", "text": "第二句。"},
        ],
        overrides=[
            {"segment_id": "seg_01", "emotion": "calm"},
            {"segment_id": "seg_02", "prosody": {"speaking_rate": "slow"}},
        ],
    )
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 4 — non-empty override (Pydantic mirror of minProperties: 2).
# ---------------------------------------------------------------------------


def test_rule_4_override_with_only_segment_id_is_rejected() -> None:
    doc = make_plan(overrides=[{"segment_id": "seg_01"}])
    assert_rejected(doc, "Rule 4 (non-empty override)")


def test_rule_4_override_with_any_control_is_accepted() -> None:
    doc = make_plan(
        overrides=[{"segment_id": "seg_01", "boundary_after": {"strength": "weak"}}]
    )
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 5 — prominence span integrity.
# ---------------------------------------------------------------------------


def test_rule_5_non_substring_target_is_rejected() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "位移", "level": "strong"}],
            }
        ]
    )
    assert_rejected(doc, "Rule 5 (prominence span integrity)")


def test_rule_5_target_occurring_twice_is_rejected() -> None:
    doc = make_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大速度小。"}],
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "速度", "level": "strong"}],
            }
        ],
    )
    assert_rejected(doc, "Rule 5 (prominence span integrity)")


def test_rule_5_overlapping_occurrences_are_counted() -> None:
    # "哈哈" occurs twice in "哈哈哈" under overlapping-inclusive counting;
    # a non-overlapping counter would report one and wrongly accept.
    assert count_occurrences("哈哈哈", "哈哈") == 2
    doc = make_plan(
        segments=[{"segment_id": "seg_01", "text": "哈哈哈"}],
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "哈哈", "level": "strong"}],
            }
        ],
    )
    assert_rejected(doc, "Rule 5 (prominence span integrity)")


@pytest.mark.parametrize("text", ["", "   ", "\t", "\n"])
def test_rule_5_whitespace_target_text_is_rejected(text: str) -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": text, "level": "strong"}],
            }
        ]
    )
    with pytest.raises(ValidationError):
        SpeechPlan.model_validate(doc)


def test_rule_5_unique_target_is_accepted() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "速度大", "level": "strong"}],
            }
        ]
    )
    assert_accepted(doc)


def test_rule_5_target_must_be_exact_substring() -> None:
    # Partial/normalized matches are not exact substrings.
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "速度很大", "level": "strong"}],
            }
        ]
    )
    assert_rejected(doc, "Rule 5 (prominence span integrity)")


# ---------------------------------------------------------------------------
# Rule 7 — empty-object policy (Pydantic mirror).
# ---------------------------------------------------------------------------


def test_rule_7_empty_global_is_rejected() -> None:
    doc = make_plan(global_delivery={})
    assert_rejected(doc, "Rule 7 (empty-object policy)")


def test_rule_7_empty_prosody_is_rejected() -> None:
    doc = make_plan(
        overrides=[{"segment_id": "seg_01", "prosody": {}}]
    )
    assert_rejected(doc, "Rule 7 (empty-object policy)")


def test_rule_7_empty_global_prosody_is_rejected() -> None:
    doc = make_plan(global_delivery={"prosody": {}})
    assert_rejected(doc, "Rule 7 (empty-object policy)")


# ---------------------------------------------------------------------------
# Rule 8 — contour conflict.
# ---------------------------------------------------------------------------


def test_rule_8_contour_with_segment_pitch_level_is_rejected() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "contour_shape": "falling",
                "prosody": {"pitch_level": "high"},
            }
        ]
    )
    assert_rejected(doc, "Rule 8 (contour conflict)")


def test_rule_8_contour_with_segment_pitch_range_is_rejected() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "contour_shape": "rising",
                "prosody": {"pitch_range": "low"},
            }
        ]
    )
    assert_rejected(doc, "Rule 8 (contour conflict)")


def test_rule_8_contour_with_speaking_rate_is_accepted() -> None:
    # Section 9.1 forbids only pitch_level / pitch_range coexistence.
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "contour_shape": "falling",
                "prosody": {"speaking_rate": "slow"},
            }
        ]
    )
    assert_accepted(doc)


def test_rule_8_contour_with_volume_is_accepted() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "contour_shape": "rise-fall",
                "prosody": {"volume": "soft"},
            }
        ]
    )
    assert_accepted(doc)


def test_rule_8_contour_with_global_pitch_baseline_is_accepted() -> None:
    # Section 9.1: "A global pitch baseline may still exist."
    doc = make_plan(
        global_delivery={"prosody": {"pitch_level": "medium"}},
        overrides=[
            {
                "segment_id": "seg_01",
                "contour_shape": "falling",
                "prominence_targets": [{"text": "速度大", "level": "strong"}],
            }
        ],
    )
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 10 — non-empty verbal plan (Pydantic mirror).
# ---------------------------------------------------------------------------


def test_rule_10_empty_segments_array_is_rejected() -> None:
    doc = make_plan(segments=[])
    with pytest.raises(ValidationError):
        SpeechPlan.model_validate(doc)


# ---------------------------------------------------------------------------
# Rule 11 — meaningful default resets.
# ---------------------------------------------------------------------------


def test_rule_11_default_without_global_field_is_rejected() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prosody": {"speaking_rate": "default"},
            }
        ]
    )
    assert_rejected(doc, "Rule 11 (meaningful default reset)")


def test_rule_11_default_with_unrelated_global_field_is_rejected() -> None:
    doc = make_plan(
        global_delivery={"prosody": {"volume": "soft"}},
        overrides=[
            {
                "segment_id": "seg_01",
                "prosody": {"speaking_rate": "default"},
            }
        ],
    )
    assert_rejected(doc, "Rule 11 (meaningful default reset)")


def test_rule_11_default_with_matching_global_field_is_accepted() -> None:
    doc = make_plan(
        global_delivery={"prosody": {"speaking_rate": "slow"}},
        overrides=[
            {
                "segment_id": "seg_01",
                "prosody": {"speaking_rate": "default"},
            }
        ],
    )
    assert_accepted(doc)


def test_rule_11_non_default_value_without_global_field_is_accepted() -> None:
    # Rule 11 constrains only the literal "default" reset value.
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prosody": {"speaking_rate": "slow"},
            }
        ]
    )
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 12 — prominence non-overlap.
# ---------------------------------------------------------------------------


def test_rule_12_duplicate_targets_are_rejected() -> None:
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [
                    {"text": "速度大", "level": "strong"},
                    {"text": "速度大", "level": "moderate"},
                ],
            }
        ]
    )
    assert_rejected(doc, "Rule 12 (prominence non-overlap)")


def test_rule_12_overlapping_targets_are_rejected() -> None:
    # "度大" spans [1,3) and "大，" spans [2,4) in "速度大，并不代表…".
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [
                    {"text": "度大", "level": "strong"},
                    {"text": "大，", "level": "strong"},
                ],
            }
        ]
    )
    assert_rejected(doc, "Rule 12 (prominence non-overlap)")


def test_rule_12_adjacent_targets_are_accepted() -> None:
    # "并不代表" spans [4,8) and "加速度" spans [8,11) in
    # "速度大，并不代表加速度一定大。" — touching but not overlapping.
    doc = make_plan(
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [
                    {"text": "并不代表", "level": "strong"},
                    {"text": "加速度", "level": "moderate"},
                ],
            }
        ]
    )
    assert_accepted(doc)


def test_rule_12_multiple_targets_in_different_segments_are_accepted() -> None:
    doc = make_plan(
        segments=[
            {"segment_id": "seg_01", "text": "速度大，并不代表加速度一定大。"},
            {"segment_id": "seg_02", "text": "速度描述运动的快慢。"},
        ],
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "速度大", "level": "strong"}],
            },
            {
                "segment_id": "seg_02",
                "prominence_targets": [{"text": "速度", "level": "moderate"}],
            },
        ],
    )
    assert_accepted(doc)


# ---------------------------------------------------------------------------
# Rule 13 — style descriptors (Pydantic mirror, strict trim).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tone", [" calm", "calm ", "\tcalm", "ca\nlm", "calm\n", "calm\u2028", "   ", ""]
)
def test_rule_13_malformed_style_descriptors_are_rejected(tone: str) -> None:
    doc = make_plan(global_delivery={"attitudinal_tone": tone})
    assert_rejected(doc, "Rule 13 (style descriptor normalization)")


def test_rule_13_64_char_descriptor_is_accepted() -> None:
    doc = make_plan(global_delivery={"attitudinal_tone": "a" * 64})
    assert_accepted(doc)


def test_rule_13_65_char_descriptor_is_rejected() -> None:
    doc = make_plan(global_delivery={"attitudinal_tone": "a" * 65})
    assert_rejected(doc, "Rule 13 (style descriptor normalization)")


# ---------------------------------------------------------------------------
# Rule 14 — schema version exactness (Literal mirror).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["1.0.0-rc.2", "1.0.0", "1.0.0-rc.4", ""])
def test_rule_14_wrong_schema_version_is_rejected(version: str) -> None:
    doc = make_plan(schema_version=version)
    with pytest.raises(ValidationError):
        SpeechPlan.model_validate(doc)


# ---------------------------------------------------------------------------
# Structural mirrors (defense in depth).
# ---------------------------------------------------------------------------


def test_unknown_override_field_is_rejected() -> None:
    doc = make_plan(
        overrides=[{"segment_id": "seg_01", "teacher_authority": 0.8}]
    )
    with pytest.raises(ValidationError):
        SpeechPlan.model_validate(doc)


def test_explicit_null_override_field_is_rejected() -> None:
    doc = make_plan(
        overrides=[{"segment_id": "seg_01", "emotion": None}]
    )
    assert_rejected(doc, "explicit null is not allowed")


def test_segment_id_pattern_is_enforced() -> None:
    doc = make_plan(
        segments=[{"segment_id": "seg_1", "text": "内容。"}]
    )
    with pytest.raises(ValidationError):
        SpeechPlan.model_validate(doc)


# ---------------------------------------------------------------------------
# Span helpers (unit-level).
# ---------------------------------------------------------------------------


def test_span_helpers() -> None:
    assert count_occurrences("abcabc", "abc") == 2
    assert count_occurrences("abc", "xyz") == 0
    assert count_occurrences("aaa", "aa") == 2  # overlapping
    assert resolve_span("速度大，", "速度大") == (0, 3)
    assert resolve_span("速度大，", "大，") == (2, 4)
    assert spans_overlap((0, 3), (2, 4)) is True
    assert spans_overlap((0, 2), (2, 4)) is False  # adjacent
    assert spans_overlap((0, 3), (0, 3)) is True  # duplicate
