"""Tests for the Hy3 response parser.

Parsing is strictly separated from validation. The only tolerated deviation from
strict JSON is a single Markdown fence wrapping the whole response. No field/enum/
text/prosody fixing is performed; prose + unfenced JSON is a hard parse failure.
"""

from __future__ import annotations

import json

import pytest

from teachintent.generator.errors import ResponseParsingError
from teachintent.generator.parser import parse_speech_plan_json

CANONICAL = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
    },
    "delivery_plan": {},
}


def test_pure_json_object_is_parsed() -> None:
    raw = json.dumps(CANONICAL, ensure_ascii=False)
    assert parse_speech_plan_json(raw) == CANONICAL


def test_json_with_surrounding_whitespace_is_parsed() -> None:
    raw = "\n\n  " + json.dumps(CANONICAL, ensure_ascii=False) + "  \n\n"
    assert parse_speech_plan_json(raw) == CANONICAL


@pytest.mark.parametrize("info", ["json", "JSON", ""])
def test_markdown_fenced_json_is_parsed(info) -> None:
    body = json.dumps(CANONICAL, ensure_ascii=False)
    raw = f"```{info}\n{body}\n```"
    assert parse_speech_plan_json(raw) == CANONICAL


def test_empty_input_raises() -> None:
    for raw in ["", "   ", "\n\t"]:
        with pytest.raises(ResponseParsingError) as exc:
            parse_speech_plan_json(raw)
        assert exc.value.raw_text == raw


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '"a string"',
        "42",
        "true",
        "null",
    ],
)
def test_non_object_json_raises(raw) -> None:
    with pytest.raises(ResponseParsingError) as exc:
        parse_speech_plan_json(raw)
    assert "not an object" in str(exc.value)
    assert exc.value.raw_text == raw


def test_fenced_non_object_raises() -> None:
    with pytest.raises(ResponseParsingError) as exc:
        parse_speech_plan_json("```json\n[1, 2, 3]\n```")
    assert "not an object" in str(exc.value)


def test_prose_around_unfenced_json_raises() -> None:
    raw = "Here is the plan:\n" + json.dumps(CANONICAL) + "\nHope this helps!"
    with pytest.raises(ResponseParsingError) as exc:
        parse_speech_plan_json(raw)
    assert exc.value.raw_text == raw


def test_prose_around_fenced_json_raises() -> None:
    # The fence must wrap the WHOLE trimmed text; surrounding prose defeats it.
    raw = "Here is the plan:\n```json\n" + json.dumps(CANONICAL) + "\n```\nThanks!"
    with pytest.raises(ResponseParsingError) as exc:
        parse_speech_plan_json(raw)
    assert exc.value.raw_text == raw


def test_malformed_json_raises_with_head_snippet() -> None:
    raw = '{"schema_version": "1.0.0-rc.3", broken'
    with pytest.raises(ResponseParsingError) as exc:
        parse_speech_plan_json(raw)
    assert exc.value.raw_text == raw
    assert "head" in str(exc.value)


def test_parser_does_not_mutate_field_values() -> None:
    # The parser returns the dict verbatim from json.loads; it must not coerce
    # enums, fix names, or edit content.
    doc = {"weird_field_name": "very-slow", "text": "  spaced  "}
    raw = json.dumps(doc)
    assert parse_speech_plan_json(raw) == doc
