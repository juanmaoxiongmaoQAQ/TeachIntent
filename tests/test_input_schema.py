"""Structural JSON Schema tests for the TeachIntent input contract.

Covers schemas/teachintent_input.schema.json (docs/problem_definition.md
section 4).  Assertions check correct rejection plus, where useful, the
``validator`` / ``absolute_path`` of the error; error message text is not
asserted beyond that (rule traceability lives in ``$comment`` annotations).
"""

from __future__ import annotations

import pytest

from teachintent.validators import iter_input_errors, validate_input_document

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def assert_valid(doc: dict) -> None:
    errors = iter_input_errors(doc)
    assert not errors, f"expected valid, got: {[e.message for e in errors]}"


def assert_invalid(doc: dict, validator: str | None = None) -> None:
    errors = iter_input_errors(doc)
    assert errors, "expected document to be rejected"
    if validator is not None:
        assert any(
            error.validator == validator for error in errors
        ), f"expected a '{validator}' error among: {[(e.validator, e.message) for e in errors]}"


# ---------------------------------------------------------------------------
# Canonical validity.
# ---------------------------------------------------------------------------


def test_canonical_example_is_valid(canonical_input_doc) -> None:
    assert_valid(canonical_input_doc)


@pytest.mark.parametrize(
    "primary",
    [
        "elicitation",
        "scaffolding",
        "explanation",
        "corrective_feedback",
        "supportive_feedback",
        "extension",
    ],
)
def test_all_six_intents_are_valid(canonical_input_doc, primary) -> None:
    canonical_input_doc["pedagogical_intent"]["primary"] = primary
    assert_valid(canonical_input_doc)


@pytest.mark.parametrize(
    "language",
    ["zh-CN", "en-US", "yue-Hant-HK", "zh", "ZH-cn"],
)
def test_common_bcp47_tags_are_valid(canonical_input_doc, language) -> None:
    canonical_input_doc["output_language"] = language
    assert_valid(canonical_input_doc)


def test_optional_fields_may_be_omitted(canonical_input_doc) -> None:
    del canonical_input_doc["instructional_content"]["subject"]
    del canonical_input_doc["instructional_content"]["topic"]
    del canonical_input_doc["pedagogical_context"]["learner_utterance"]
    del canonical_input_doc["learner"]["affective_state"]
    assert_valid(canonical_input_doc)


# ---------------------------------------------------------------------------
# Required fields (problem_definition.md section 4).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "output_language",
        "instructional_content",
        "pedagogical_context",
        "learner",
        "pedagogical_intent",
    ],
)
def test_missing_required_top_level_field_is_rejected(
    canonical_input_doc, field
) -> None:
    del canonical_input_doc[field]
    assert_invalid(canonical_input_doc, validator="required")


def test_missing_content_anchor_is_rejected(canonical_input_doc) -> None:
    del canonical_input_doc["instructional_content"]["content_anchor"]
    assert_invalid(canonical_input_doc, validator="required")


def test_missing_scenario_is_rejected(canonical_input_doc) -> None:
    del canonical_input_doc["pedagogical_context"]["scenario"]
    assert_invalid(canonical_input_doc, validator="required")


@pytest.mark.parametrize("field", ["level", "knowledge_state"])
def test_missing_required_learner_fields_are_rejected(
    canonical_input_doc, field
) -> None:
    del canonical_input_doc["learner"][field]
    assert_invalid(canonical_input_doc, validator="required")


def test_missing_primary_intent_is_rejected(canonical_input_doc) -> None:
    del canonical_input_doc["pedagogical_intent"]["primary"]
    assert_invalid(canonical_input_doc, validator="required")


# ---------------------------------------------------------------------------
# schema_version (problem_definition.md section 4.1).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version", ["1.0.0-rc.3", "1.0.0", "1.0.0-rc.1", "", "1.0.0-rc.2\n"]
)
def test_wrong_schema_version_is_rejected(canonical_input_doc, version) -> None:
    canonical_input_doc["schema_version"] = version
    assert_invalid(canonical_input_doc, validator="const")


# ---------------------------------------------------------------------------
# output_language (problem_definition.md section 4.2; lightweight BCP-47
# syntax subset — not a full BCP-47 validator).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "language",
    ["zh_CN", "zh-", "-zh", "", " zh-CN", "zh-CN ", "zh-CN\n", "中"],
)
def test_malformed_output_language_is_rejected(
    canonical_input_doc, language
) -> None:
    canonical_input_doc["output_language"] = language
    assert_invalid(canonical_input_doc)


def test_non_string_output_language_is_rejected(canonical_input_doc) -> None:
    canonical_input_doc["output_language"] = 7
    assert_invalid(canonical_input_doc, validator="type")


# ---------------------------------------------------------------------------
# Unknown fields (strict additionalProperties:false everywhere).
# ---------------------------------------------------------------------------


def test_unknown_top_level_field_is_rejected(canonical_input_doc) -> None:
    canonical_input_doc["teacher_authority"] = 0.8
    assert_invalid(canonical_input_doc, validator="additionalProperties")


@pytest.mark.parametrize(
    "section,field",
    [
        ("instructional_content", "difficulty"),
        ("pedagogical_context", "dialogue_history"),
        ("learner", "personality"),
        ("pedagogical_intent", "secondary"),
    ],
)
def test_unknown_subfield_is_rejected(canonical_input_doc, section, field) -> None:
    canonical_input_doc[section][field] = "value"
    assert_invalid(canonical_input_doc, validator="additionalProperties")


# ---------------------------------------------------------------------------
# Non-empty string constraints (all input string fields).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["subject", "topic", "content_anchor"])
def test_empty_or_whitespace_content_fields_are_rejected(
    canonical_input_doc, field
) -> None:
    for value in ("", "   ", "\t", "\n"):
        canonical_input_doc["instructional_content"][field] = value
        assert_invalid(canonical_input_doc)


@pytest.mark.parametrize("field", ["scenario", "learner_utterance"])
def test_empty_or_whitespace_context_fields_are_rejected(
    canonical_input_doc, field
) -> None:
    for value in ("", "   ", "\t"):
        canonical_input_doc["pedagogical_context"][field] = value
        assert_invalid(canonical_input_doc)


@pytest.mark.parametrize(
    "field", ["level", "knowledge_state", "affective_state"]
)
def test_empty_or_whitespace_learner_fields_are_rejected(
    canonical_input_doc, field
) -> None:
    for value in ("", "   ", "\t"):
        canonical_input_doc["learner"][field] = value
        assert_invalid(canonical_input_doc)


# ---------------------------------------------------------------------------
# Explicit nulls are rejected (JSON Schema type errors).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ("instructional_content", "subject"),
        ("instructional_content", "content_anchor"),
        ("pedagogical_context", "scenario"),
        ("learner", "affective_state"),
        ("pedagogical_intent", "primary"),
        ("output_language",),
    ],
)
def test_explicit_null_is_rejected(canonical_input_doc, path) -> None:
    node = canonical_input_doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = None
    assert_invalid(canonical_input_doc, validator="type")


# ---------------------------------------------------------------------------
# pedagogical_intent.primary enum (docs/pedagogical_intents.md section 4).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "primary",
    [
        "out_of_scope",  # dataset QC only, not a generation-time intent
        "Explanation",  # case-sensitive
        "hint",  # strategy-level, not an intent
        "",
        "corrective feedback",
    ],
)
def test_intent_enum_violations_are_rejected(
    canonical_input_doc, primary
) -> None:
    canonical_input_doc["pedagogical_intent"]["primary"] = primary
    assert_invalid(canonical_input_doc, validator="enum")


def test_non_string_primary_intent_is_rejected(canonical_input_doc) -> None:
    canonical_input_doc["pedagogical_intent"]["primary"] = 4
    assert_invalid(canonical_input_doc, validator="type")


# ---------------------------------------------------------------------------
# Programmatic API sanity.
# ---------------------------------------------------------------------------


def test_validate_input_document_raises_on_invalid(canonical_input_doc) -> None:
    canonical_input_doc["schema_version"] = "1.0.0"
    with pytest.raises(Exception):
        validate_input_document(canonical_input_doc)


def test_validate_input_document_accepts_canonical(canonical_input_doc) -> None:
    validate_input_document(canonical_input_doc)
