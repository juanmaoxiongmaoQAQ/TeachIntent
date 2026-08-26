"""Pydantic model tests for the TeachIntent input contract.

Mirrors the structural constraints of schemas/teachintent_input.schema.json
(defense in depth) and checks round-trip fidelity.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teachintent.models import PedagogicalPrimary, TeachIntentInput


def parse(doc: dict) -> TeachIntentInput:
    return TeachIntentInput.model_validate(doc)


def assert_rejected(doc: dict, message_contains: str | None = None) -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse(doc)
    if message_contains is not None:
        assert message_contains in str(exc_info.value), (
            f"expected error containing {message_contains!r}, "
            f"got: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# Valid documents.
# ---------------------------------------------------------------------------


def test_canonical_example_parses(canonical_input_doc) -> None:
    model = parse(canonical_input_doc)
    assert model.pedagogical_intent.primary is (
        PedagogicalPrimary.CORRECTIVE_FEEDBACK
    )
    assert model.output_language == "zh-CN"


def test_round_trip_fidelity(canonical_input_doc) -> None:
    model = parse(canonical_input_doc)
    dumped = model.model_dump(by_alias=True, exclude_none=True)
    assert dumped == canonical_input_doc


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
def test_all_six_intents_parse(canonical_input_doc, primary) -> None:
    canonical_input_doc["pedagogical_intent"]["primary"] = primary
    assert parse(canonical_input_doc).pedagogical_intent.primary == primary


@pytest.mark.parametrize(
    "language", ["zh-CN", "en-US", "yue-Hant-HK", "zh", "ZH-cn"]
)
def test_common_bcp47_tags_parse_without_normalization(
    canonical_input_doc, language
) -> None:
    canonical_input_doc["output_language"] = language
    model = parse(canonical_input_doc)
    assert model.output_language == language  # case preserved, not normalized


def test_optional_fields_may_be_omitted(canonical_input_doc) -> None:
    del canonical_input_doc["instructional_content"]["subject"]
    del canonical_input_doc["pedagogical_context"]["learner_utterance"]
    del canonical_input_doc["learner"]["affective_state"]
    parse(canonical_input_doc)


# ---------------------------------------------------------------------------
# Structural rejections (mirroring the JSON Schema layer).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version", ["1.0.0-rc.3", "1.0.0", "1.0.0-rc.1", ""]
)
def test_wrong_schema_version_is_rejected(canonical_input_doc, version) -> None:
    canonical_input_doc["schema_version"] = version
    assert_rejected(canonical_input_doc)


@pytest.mark.parametrize(
    "language", ["zh_CN", "zh-", "-zh", "", " zh-CN", "zh-CN ", "zh-CN\n"]
)
def test_malformed_output_language_is_rejected(
    canonical_input_doc, language
) -> None:
    canonical_input_doc["output_language"] = language
    assert_rejected(canonical_input_doc, "output_language")


@pytest.mark.parametrize(
    "primary",
    ["out_of_scope", "Explanation", "hint", "", "corrective feedback"],
)
def test_intent_enum_violations_are_rejected(
    canonical_input_doc, primary
) -> None:
    canonical_input_doc["pedagogical_intent"]["primary"] = primary
    assert_rejected(canonical_input_doc)


@pytest.mark.parametrize(
    "path",
    [
        ("schema_version",),
        ("output_language",),
        ("instructional_content",),
        ("pedagogical_context",),
        ("learner",),
        ("pedagogical_intent",),
    ],
)
def test_missing_required_fields_are_rejected(canonical_input_doc, path) -> None:
    node = canonical_input_doc
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    assert_rejected(canonical_input_doc)


@pytest.mark.parametrize(
    "section,field",
    [
        (None, "teacher_authority"),
        ("instructional_content", "difficulty"),
        ("pedagogical_context", "dialogue_history"),
        ("learner", "personality"),
        ("pedagogical_intent", "secondary"),
    ],
)
def test_unknown_fields_are_rejected(canonical_input_doc, section, field) -> None:
    if section is None:
        canonical_input_doc[field] = "value"
    else:
        canonical_input_doc[section][field] = "value"
    assert_rejected(canonical_input_doc)


@pytest.mark.parametrize(
    "path,value",
    [
        (("instructional_content", "subject"), ""),
        (("instructional_content", "subject"), "   "),
        (("instructional_content", "content_anchor"), "\t"),
        (("pedagogical_context", "scenario"), " \n "),
        (("learner", "level"), ""),
        (("learner", "knowledge_state"), "  "),
        (("learner", "affective_state"), "\t"),
        (("pedagogical_context", "learner_utterance"), ""),
    ],
)
def test_empty_or_whitespace_strings_are_rejected(
    canonical_input_doc, path, value
) -> None:
    node = canonical_input_doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert_rejected(canonical_input_doc)


@pytest.mark.parametrize(
    "path",
    [
        ("instructional_content", "subject"),
        ("learner", "affective_state"),
        ("pedagogical_context", "learner_utterance"),
    ],
)
def test_explicit_nulls_on_optional_fields_are_rejected(
    canonical_input_doc, path
) -> None:
    """Optional fields accept omission but must reject explicit nulls
    (mirroring JSON Schema, where {"field": null} is a type error)."""
    node = canonical_input_doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = None
    assert_rejected(canonical_input_doc, "explicit null is not allowed")


@pytest.mark.parametrize(
    "path",
    [
        ("instructional_content", "content_anchor"),
        ("pedagogical_context", "scenario"),
        ("output_language",),
    ],
)
def test_explicit_nulls_on_required_fields_are_rejected(
    canonical_input_doc, path
) -> None:
    """Required (non-Optional) fields fail field validation on null before
    the explicit-null model validator runs; either way the document is
    rejected, matching the JSON Schema type error."""
    node = canonical_input_doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = None
    assert_rejected(canonical_input_doc)
