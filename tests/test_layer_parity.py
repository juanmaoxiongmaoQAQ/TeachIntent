"""Layer parity tests: JSON Schema vs Pydantic.

The two layers have different responsibilities (Rule 15,
docs/speech_plan_schema.md), so parity is asserted per category:

* **valid cases** — both layers must accept;
* **structural-invalid cases** (types, enums, const/version, patterns,
  lengths, minItems, unknown fields, empty objects, minProperties) — both
  layers must reject;
* **cross-field semantic-invalid cases** (Rules 1/2/3/5/8/11/12) — the JSON
  Schema layer may accept (structure is fine); the Pydantic layer must
  reject.  These tests assert exactly that asymmetry.

Round-trip fidelity is also pinned here: Pydantic parse → dump must
reproduce the canonical documents and remain JSON-Schema-valid.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teachintent.models import SpeechPlan, TeachIntentInput
from teachintent.validators import (
    iter_input_errors,
    iter_speech_plan_errors,
)


def json_schema_ok(doc: dict, kind: str) -> bool:
    errors = (
        iter_input_errors(doc) if kind == "input" else iter_speech_plan_errors(doc)
    )
    return not errors


def pydantic_ok(doc: dict, kind: str) -> bool:
    model = TeachIntentInput if kind == "input" else SpeechPlan
    try:
        model.model_validate(doc)
        return True
    except ValidationError:
        return False


# ---------------------------------------------------------------------------
# Canonical documents: both layers must accept.
# ---------------------------------------------------------------------------


def test_canonical_input_accepted_by_both_layers(canonical_input_doc) -> None:
    assert json_schema_ok(canonical_input_doc, "input")
    assert pydantic_ok(canonical_input_doc, "input")


def test_canonical_speech_plan_accepted_by_both_layers(
    canonical_speech_plan_doc,
) -> None:
    assert json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert pydantic_ok(canonical_speech_plan_doc, "speech_plan")


# ---------------------------------------------------------------------------
# Round-trip fidelity.
# ---------------------------------------------------------------------------


def test_input_round_trip_still_passes_json_schema(canonical_input_doc) -> None:
    model = TeachIntentInput.model_validate(canonical_input_doc)
    dumped = model.model_dump(by_alias=True, exclude_none=True)
    assert dumped == canonical_input_doc
    assert not iter_input_errors(dumped)


def test_speech_plan_round_trip_still_passes_json_schema(
    canonical_speech_plan_doc,
) -> None:
    model = SpeechPlan.model_validate(canonical_speech_plan_doc)
    dumped = model.model_dump(by_alias=True, exclude_none=True)
    assert dumped == canonical_speech_plan_doc  # includes the "global" alias
    assert not iter_speech_plan_errors(dumped)


def test_minimal_plan_round_trip() -> None:
    doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "你好。"}]},
        "delivery_plan": {},
    }
    model = SpeechPlan.model_validate(doc)
    assert model.model_dump(by_alias=True, exclude_none=True) == doc


# ---------------------------------------------------------------------------
# Tricky strings: both layers must agree (reject).
# ---------------------------------------------------------------------------


def with_segment_id(doc: dict, segment_id: str) -> dict:
    doc["verbal_plan"]["segments"][0]["segment_id"] = segment_id
    return doc


@pytest.mark.parametrize(
    "segment_id",
    [
        "seg_1",
        "seg_",
        "seg_001a",
        "SEG_01",
        "seg_01 ",
        "seg_01\n",  # defeats naive ^...$ under Python re
        "seg_01\r",
        "seg_01\u2028",
        "seg_01\u2029",
    ],
)
def test_segment_id_tricky_strings_rejected_by_both(
    canonical_speech_plan_doc, segment_id
) -> None:
    doc = with_segment_id(canonical_speech_plan_doc, segment_id)
    assert not json_schema_ok(doc, "speech_plan")
    assert not pydantic_ok(doc, "speech_plan")


@pytest.mark.parametrize("segment_id", ["seg_01", "seg_99", "seg_000123"])
def test_segment_id_valid_strings_accepted_by_both(
    canonical_speech_plan_doc, segment_id
) -> None:
    # seg_99 / seg_000123 are structurally valid ids; overrides still point
    # at seg_02/03/04 which remain valid, and duplicate ids are avoided.
    doc = with_segment_id(canonical_speech_plan_doc, segment_id)
    assert json_schema_ok(doc, "speech_plan")
    assert pydantic_ok(doc, "speech_plan")


@pytest.mark.parametrize(
    "tone",
    [
        " calm",
        "calm ",
        "\tcalm",
        "calm\t",
        "ca\nlm",
        "calm\n",
        "calm\r",
        "calm\u2028",
        "calm\u2029",
        " calm ",
        "   ",
        "",
        "a" * 65,
    ],
)
def test_style_descriptor_tricky_strings_rejected_by_both(
    canonical_speech_plan_doc, tone
) -> None:
    doc = canonical_speech_plan_doc
    doc["delivery_plan"]["global"]["attitudinal_tone"] = tone
    assert not json_schema_ok(doc, "speech_plan")
    assert not pydantic_ok(doc, "speech_plan")


@pytest.mark.parametrize("tone", ["calm", "a" * 64, "firm but supportive", "支持的"])
def test_style_descriptor_valid_strings_accepted_by_both(
    canonical_speech_plan_doc, tone
) -> None:
    doc = canonical_speech_plan_doc
    doc["delivery_plan"]["global"]["attitudinal_tone"] = tone
    assert json_schema_ok(doc, "speech_plan")
    assert pydantic_ok(doc, "speech_plan")


@pytest.mark.parametrize(
    "language",
    ["zh_CN", "zh-", "-zh", "", " zh-CN", "zh-CN ", "zh-CN\n", "中"],
)
def test_output_language_tricky_strings_rejected_by_both(
    canonical_input_doc, language
) -> None:
    canonical_input_doc["output_language"] = language
    assert not json_schema_ok(canonical_input_doc, "input")
    assert not pydantic_ok(canonical_input_doc, "input")


@pytest.mark.parametrize(
    "language", ["zh-CN", "en-US", "yue-Hant-HK", "zh", "ZH-cn", "chinese"]
)
def test_output_language_valid_strings_accepted_by_both(
    canonical_input_doc, language
) -> None:
    # "chinese" is syntactically valid within the lightweight/common subset
    # (the subset is not a full BCP-47 validator and does no registry check).
    canonical_input_doc["output_language"] = language
    assert json_schema_ok(canonical_input_doc, "input")
    assert pydantic_ok(canonical_input_doc, "input")


# ---------------------------------------------------------------------------
# Structural-invalid documents: both layers must reject.
# ---------------------------------------------------------------------------


def test_wrong_version_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["schema_version"] = "1.0.0-rc.2"
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_unknown_root_field_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["teacher_authority"] = 0.8
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_enum_violation_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0][
        "prosody"
    ] = {"speaking_rate": "very-slow"}
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_numeric_precision_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0][
        "prosody"
    ] = {"speaking_rate": 0.8}
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_empty_global_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["global"] = {}
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_alias_global_accepted_by_both(canonical_speech_plan_doc) -> None:
    # The canonical document already spells the key "global"; make the
    # assertion explicit: the alias is the single accepted spelling.
    assert canonical_speech_plan_doc["delivery_plan"]["global"] is not None
    assert json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_field_name_global_delivery_rejected_by_both(
    canonical_speech_plan_doc,
) -> None:
    # "global_delivery" is the internal Python field name behind the
    # "global" alias; Pydantic must reject it exactly like the JSON Schema
    # does (validation is alias-only).
    delivery = canonical_speech_plan_doc["delivery_plan"]
    delivery["global_delivery"] = delivery.pop("global")
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_override_only_segment_id_rejected_by_both(
    canonical_speech_plan_doc,
) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0] = {
        "segment_id": "seg_02"
    }
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_explicit_null_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["delivery_plan"]["segment_overrides"][0][
        "emotion"
    ] = None
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


def test_empty_segments_rejected_by_both(canonical_speech_plan_doc) -> None:
    canonical_speech_plan_doc["verbal_plan"]["segments"] = []
    assert not json_schema_ok(canonical_speech_plan_doc, "speech_plan")
    assert not pydantic_ok(canonical_speech_plan_doc, "speech_plan")


# ---------------------------------------------------------------------------
# Cross-field semantic-invalid documents: JSON Schema may pass, Pydantic
# must reject (the Rule 15 division of labor, verified end to end).
# ---------------------------------------------------------------------------


def semantic_plan(
    segments: list[dict],
    overrides: list[dict] | None = None,
    global_delivery: dict | None = None,
) -> dict:
    delivery: dict = {}
    if global_delivery is not None:
        delivery["global"] = global_delivery
    if overrides is not None:
        delivery["segment_overrides"] = overrides
    return {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {"segments": segments},
        "delivery_plan": delivery,
    }


def assert_semantic_rule_only(
    doc: dict, message_contains: str
) -> None:
    """JSON Schema accepts the structure; Pydantic rejects the semantics."""
    assert not iter_speech_plan_errors(doc), (
        "document should be structurally valid "
        f"(semantic rule violated): {iter_speech_plan_errors(doc)}"
    )
    with pytest.raises(ValidationError) as exc_info:
        SpeechPlan.model_validate(doc)
    assert message_contains in str(exc_info.value)


def test_rule_1_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[
            {"segment_id": "seg_01", "text": "第一句。"},
            {"segment_id": "seg_01", "text": "第二句。"},
        ],
    )
    assert_semantic_rule_only(doc, "Rule 1 (segment ID uniqueness)")


def test_rule_2_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大。"}],
        overrides=[{"segment_id": "seg_99", "emotion": "calm"}],
    )
    assert_semantic_rule_only(doc, "Rule 2 (segment reference integrity)")


def test_rule_3_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大。"}],
        overrides=[
            {"segment_id": "seg_01", "emotion": "calm"},
            {"segment_id": "seg_01", "prosody": {"speaking_rate": "slow"}},
        ],
    )
    assert_semantic_rule_only(doc, "Rule 3 (one override per segment)")


def test_rule_5_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大，并不代表加速度一定大。"}],
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [{"text": "位移", "level": "strong"}],
            }
        ],
    )
    assert_semantic_rule_only(doc, "Rule 5 (prominence span integrity)")


def test_rule_8_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大。"}],
        overrides=[
            {
                "segment_id": "seg_01",
                "contour_shape": "falling",
                "prosody": {"pitch_level": "high"},
            }
        ],
    )
    assert_semantic_rule_only(doc, "Rule 8 (contour conflict)")


def test_rule_11_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大。"}],
        overrides=[
            {"segment_id": "seg_01", "prosody": {"speaking_rate": "default"}}
        ],
    )
    assert_semantic_rule_only(doc, "Rule 11 (meaningful default reset)")


def test_rule_12_is_semantic_only() -> None:
    doc = semantic_plan(
        segments=[{"segment_id": "seg_01", "text": "速度大，并不代表加速度一定大。"}],
        overrides=[
            {
                "segment_id": "seg_01",
                "prominence_targets": [
                    {"text": "度大", "level": "strong"},
                    {"text": "大，", "level": "strong"},
                ],
            }
        ],
    )
    assert_semantic_rule_only(doc, "Rule 12 (prominence non-overlap)")
