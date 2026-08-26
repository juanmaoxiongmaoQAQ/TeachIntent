"""Structural JSON Schema tests for the Speech Plan contract.

Covers schemas/speech_plan.schema.json (docs/speech_plan_schema.md).
Structural rules only — the cross-field semantic rules (1/2/3/5/8/11/12)
are covered in test_speech_plan_models.py and test_layer_parity.py.
"""

from __future__ import annotations

import pytest

from teachintent.validators import iter_speech_plan_errors

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def assert_valid(doc: dict) -> None:
    errors = iter_speech_plan_errors(doc)
    assert not errors, f"expected valid, got: {[e.message for e in errors]}"


def assert_invalid(doc: dict, validator: str | None = None) -> None:
    errors = iter_speech_plan_errors(doc)
    assert errors, "expected document to be rejected"
    if validator is not None:
        assert any(
            error.validator == validator for error in errors
        ), f"expected a '{validator}' error among: {[(e.validator, e.message) for e in errors]}"


def set_override(doc: dict, index: int, **changes) -> None:
    """Replace an existing canonical override with mutated fields."""
    override = doc["delivery_plan"]["segment_overrides"][index]
    override.update(changes)


# ---------------------------------------------------------------------------
# Canonical validity and sparse-control baseline.
# ---------------------------------------------------------------------------


def test_canonical_example_is_valid(canonical_speech_plan_doc) -> None:
    assert_valid(canonical_speech_plan_doc)


def test_empty_delivery_plan_is_valid(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"] = {}
    assert_valid(canonical_speech_plan_doc)


def test_delivery_plan_with_only_global_is_valid(
    canonical_speech_plan_doc,
) -> None:
    del canonical_speech_plan_doc["delivery_plan"]["segment_overrides"]
    assert_valid(canonical_speech_plan_doc)


def test_delivery_plan_with_only_segment_overrides_is_valid(
    canonical_speech_plan_doc,
) -> None:
    del canonical_speech_plan_doc["delivery_plan"]["global"]
    assert_valid(canonical_speech_plan_doc)


def test_segment_prosody_default_is_structurally_valid(
    canonical_speech_plan_doc,
) -> None:
    set_override(canonical_speech_plan_doc, 0, prosody={"speaking_rate": "default"})
    assert_valid(canonical_speech_plan_doc)


def test_minimal_one_segment_no_controls_is_valid() -> None:
    assert_valid(
        {
            "schema_version": "1.0.0-rc.3",
            "verbal_plan": {
                "segments": [{"segment_id": "seg_01", "text": "你好。"}]
            },
            "delivery_plan": {},
        }
    )


# ---------------------------------------------------------------------------
# Required fields (section 4).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["schema_version", "verbal_plan", "delivery_plan"]
)
def test_missing_required_top_level_field_is_rejected(
    canonical_speech_plan_doc, field
) -> None:
    del canonical_speech_plan_doc[field]
    assert_invalid(canonical_speech_plan_doc, validator="required")


def test_empty_segments_array_is_rejected(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"] = []
    assert_invalid(canonical_speech_plan_doc, validator="minItems")


def test_missing_segment_fields_are_rejected(
    canonical_speech_plan_doc,
) -> None:
    del canonical_speech_plan_doc["verbal_plan"]["segments"][0]["segment_id"]
    assert_invalid(canonical_speech_plan_doc, validator="required")


# ---------------------------------------------------------------------------
# Rule 7 — empty-object policy (structural: minProperties).
# ---------------------------------------------------------------------------


def test_empty_global_is_rejected(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"] = {}
    assert_invalid(canonical_speech_plan_doc, validator="minProperties")


def test_empty_prosody_is_rejected(canonical_speech_plan_doc) -> None:
    set_override(canonical_speech_plan_doc, 0, prosody={})
    assert_invalid(canonical_speech_plan_doc, validator="minProperties")


def test_non_empty_delivery_plan_without_global_or_overrides_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    # The only way to be non-empty but carry neither key is impossible with
    # additionalProperties:false, so build it explicitly as an empty object
    # plus a null field instead: {"global": null} fails type validation and
    # the anyOf passes only via required(global).
    canonical_speech_plan_doc["delivery_plan"] = {"global": None}
    assert_invalid(canonical_speech_plan_doc, validator="type")


def test_empty_segment_overrides_array_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"] = []
    assert_invalid(canonical_speech_plan_doc, validator="minItems")


# ---------------------------------------------------------------------------
# segment_id pattern (section 5.2) including the line-break guard.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "segment_id",
    [
        "seg_1",  # fewer than two digits
        "seg_",  # no digits
        "seg_001a",  # trailing non-digit
        "SEG_01",  # case
        "seg_01",  # control (valid)
    ],
)
def test_segment_id_pattern(canonical_speech_plan_doc, segment_id) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"][0]["segment_id"] = (
        segment_id
    )
    if segment_id == "seg_01":
        assert_valid(canonical_speech_plan_doc)
    else:
        assert_invalid(canonical_speech_plan_doc, validator="pattern")


@pytest.mark.parametrize(
    "segment_id", ["seg_01\n", "seg_01\r", "seg_01\u2028", "seg_01\u2029"]
)
def test_segment_id_with_line_break_is_rejected(
    canonical_speech_plan_doc, segment_id
) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"][0]["segment_id"] = (
        segment_id
    )
    assert_invalid(canonical_speech_plan_doc, validator="pattern")


# ---------------------------------------------------------------------------
# Segment text (section 5.3).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\t", "\n"])
def test_empty_or_whitespace_segment_text_is_rejected(
    canonical_speech_plan_doc, text
) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"][0]["text"] = text
    assert_invalid(canonical_speech_plan_doc)


# ---------------------------------------------------------------------------
# Rule 4 — override must contain a control besides segment_id (minProperties).
# ---------------------------------------------------------------------------


def test_override_with_only_segment_id_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0] = {
        "segment_id": "seg_02"
    }
    assert_invalid(canonical_speech_plan_doc, validator="minProperties")


# ---------------------------------------------------------------------------
# Rule 6 / Rule 9 — unknown fields and fabricated precision are rejected.
# ---------------------------------------------------------------------------


def test_unknown_root_field_is_rejected(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["teacher_authority"] = 0.8
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_verbal_plan_field_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["verbal_plan"]["spoken_text"] = "..."
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_segment_field_is_rejected(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"][0]["emphasis"] = 1
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_global_field_is_rejected(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["vocal_warmness"] = 0.7
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_prosody_field_is_rejected(canonical_speech_plan_doc) -> None:
    set_override(
        canonical_speech_plan_doc, 0, prosody={"speaking_rate": "slow", "f0_hz": 220}
    )
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_override_field_is_rejected(canonical_speech_plan_doc) -> None:
    set_override(canonical_speech_plan_doc, 0, pause_ms=500)
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_prominence_field_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0][
        "prominence_targets"
    ][0]["pitch_shift"] = "+3st"
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


def test_unknown_boundary_field_is_rejected(canonical_speech_plan_doc) -> None:
    set_override(
        canonical_speech_plan_doc, 0, boundary_after={"strength": "strong", "ms": 300}
    )
    assert_invalid(canonical_speech_plan_doc, validator="additionalProperties")


@pytest.mark.parametrize("value", [0.8, 220, True])
def test_numeric_prosody_value_is_rejected(
    canonical_speech_plan_doc, value
) -> None:
    # Rule 9: no fabricated precision — categorical enums only.
    set_override(canonical_speech_plan_doc, 0, prosody={"speaking_rate": value})
    assert_invalid(canonical_speech_plan_doc, validator="type")


# ---------------------------------------------------------------------------
# Global prosody must not contain "default" (section 8.1).
# ---------------------------------------------------------------------------


def test_default_in_global_prosody_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["prosody"] = {
        "speaking_rate": "default"
    }
    assert_invalid(canonical_speech_plan_doc, validator="enum")


# ---------------------------------------------------------------------------
# Enum constraints (sections 7, 8, 9, 10.2, 11.1).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("speaking_rate", "slow-ish"),
        ("pitch_level", "very-high"),
        ("pitch_range", "wide"),
        ("volume", "silent"),  # intentionally omitted from v1
    ],
)
def test_global_prosody_enum_violations_are_rejected(
    canonical_speech_plan_doc, field, value
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["prosody"] = {
        field: value
    }
    assert_invalid(canonical_speech_plan_doc, validator="enum")


def test_contour_shape_enum_violation_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    set_override(canonical_speech_plan_doc, 0, contour_shape="bouncy")
    assert_invalid(canonical_speech_plan_doc, validator="enum")


def test_prominence_level_enum_violation_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    targets = canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0][
        "prominence_targets"
    ]
    targets[0]["level"] = "reduced"
    assert_invalid(canonical_speech_plan_doc, validator="enum")


def test_boundary_strength_enum_violation_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    set_override(canonical_speech_plan_doc, 0, boundary_after={"strength": "huge"})
    assert_invalid(canonical_speech_plan_doc, validator="enum")


def test_boundary_after_without_strength_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    set_override(canonical_speech_plan_doc, 0, boundary_after={})
    assert_invalid(canonical_speech_plan_doc, validator="required")


# ---------------------------------------------------------------------------
# prominence_targets (section 10).
# ---------------------------------------------------------------------------


def test_empty_prominence_targets_array_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    set_override(canonical_speech_plan_doc, 0, prominence_targets=[])
    assert_invalid(canonical_speech_plan_doc, validator="minItems")


@pytest.mark.parametrize("text", ["", "   ", "\t", "\n"])
def test_whitespace_prominence_target_text_is_rejected(
    canonical_speech_plan_doc, text
) -> None:
    targets = canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0][
        "prominence_targets"
    ]
    targets[0]["text"] = text
    assert_invalid(canonical_speech_plan_doc)


# ---------------------------------------------------------------------------
# Rule 13 — style descriptor boundaries (strict trim, single line, 1-64).
# ---------------------------------------------------------------------------


def test_style_descriptor_of_64_chars_is_valid(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["attitudinal_tone"] = (
        "a" * 64
    )
    assert_valid(canonical_speech_plan_doc)


def test_style_descriptor_of_65_chars_is_rejected(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["attitudinal_tone"] = (
        "a" * 65
    )
    assert_invalid(canonical_speech_plan_doc, validator="maxLength")


@pytest.mark.parametrize(
    "tone",
    [
        " calm",  # leading whitespace
        "calm ",  # trailing whitespace
        "\tcalm",
        "ca\nlm",  # interior line break
        "calm\n",  # trailing line break (defeats naive $ anchors)
        "calm\u2028",
        "   ",  # whitespace only
        "",  # empty
    ],
)
def test_malformed_style_descriptors_are_rejected(
    canonical_speech_plan_doc, tone
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["attitudinal_tone"] = tone
    assert_invalid(canonical_speech_plan_doc)


def test_style_descriptor_with_interior_space_is_valid(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"]["attitudinal_tone"] = (
        "firm but supportive"
    )
    assert_valid(canonical_speech_plan_doc)


# ---------------------------------------------------------------------------
# Rule 14 — schema version exactness.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version", ["1.0.0-rc.2", "1.0.0", "1.0.0-rc.4", "", "1.0.0-rc.3\n"]
)
def test_wrong_schema_version_is_rejected(
    canonical_speech_plan_doc, version
) -> None:
    canonical_speech_plan_doc["schema_version"] = version
    assert_invalid(canonical_speech_plan_doc, validator="const")


# ---------------------------------------------------------------------------
# Error metadata sanity (validator / path / schema_path).
# ---------------------------------------------------------------------------


def test_error_reports_reasonable_path_and_schema_path(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"][0]["segment_id"] = "seg_1"
    errors = iter_speech_plan_errors(canonical_speech_plan_doc)
    assert errors
    error = errors[0]
    assert error.validator == "pattern"
    assert list(error.absolute_path) == [
        "verbal_plan",
        "segments",
        0,
        "segment_id",
    ]
    schema_path = "/".join(str(part) for part in error.absolute_schema_path)
    assert "segment_id" in schema_path
    assert schema_path.endswith("pattern")
