"""Tests for the judge response parser.

Covers: raw JSON parsing, single Markdown fence parsing, malformed JSON,
non-object JSON, empty output, no field repair.
"""

from __future__ import annotations

import json

import pytest

from teachintent.evaluator import parse_judge_response
from teachintent.evaluator.errors import JudgeResponseParseError

VALID_OUTPUT = {
    "scores": {
        "pedagogical_intent_fidelity": {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": "{}"}], "brief_justification": "ok"},
        "content_faithfulness_boundary": {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": "{}"}], "brief_justification": "ok"},
        "learner_state_compatibility": {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": "{}"}], "brief_justification": "ok"},
        "intent_specific_instructional_adequacy": {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": "{}"}], "brief_justification": "ok"},
        "delivery_necessity_sparsity": {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": "{}"}], "brief_justification": "ok"},
        "delivery_pedagogy_alignment": {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": "{}"}], "brief_justification": "ok"},
    },
    "critical_flags": [],
}


# ---------------------------------------------------------------------------
# Raw JSON parsing.
# ---------------------------------------------------------------------------


def test_parse_raw_json():
    raw = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    parsed = parse_judge_response(raw)
    assert parsed == VALID_OUTPUT
    assert isinstance(parsed, dict)


def test_parse_raw_json_with_surrounding_whitespace():
    raw = "  \n  " + json.dumps(VALID_OUTPUT, ensure_ascii=False) + "  \n  "
    parsed = parse_judge_response(raw)
    assert parsed == VALID_OUTPUT


# ---------------------------------------------------------------------------
# Single Markdown fence parsing.
# ---------------------------------------------------------------------------


def test_parse_single_markdown_fence_json():
    body = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    raw = f"```json\n{body}\n```"
    parsed = parse_judge_response(raw)
    assert parsed == VALID_OUTPUT


def test_parse_single_markdown_fence_no_lang():
    body = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    raw = f"```\n{body}\n```"
    parsed = parse_judge_response(raw)
    assert parsed == VALID_OUTPUT


def test_parse_single_markdown_fence_uppercase():
    body = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    raw = f"```JSON\n{body}\n```"
    parsed = parse_judge_response(raw)
    assert parsed == VALID_OUTPUT


# ---------------------------------------------------------------------------
# Malformed JSON.
# ---------------------------------------------------------------------------


def test_malformed_json_raises_parse_error():
    raw = '{"scores": {"bad'
    with pytest.raises(JudgeResponseParseError) as exc_info:
        parse_judge_response(raw)
    assert exc_info.value.raw_text == raw


def test_empty_output_raises_parse_error():
    with pytest.raises(JudgeResponseParseError, match="empty"):
        parse_judge_response("   \n  ")


def test_non_object_json_raises_parse_error():
    raw = "[1, 2, 3]"
    with pytest.raises(JudgeResponseParseError, match="not an object"):
        parse_judge_response(raw)


def test_string_json_raises_parse_error():
    raw = '"just a string"'
    with pytest.raises(JudgeResponseParseError, match="not an object"):
        parse_judge_response(raw)


def test_number_json_raises_parse_error():
    raw = "42"
    with pytest.raises(JudgeResponseParseError):
        parse_judge_response(raw)


def test_markdown_fence_with_malformed_body():
    raw = "```json\n{bad json}\n```"
    with pytest.raises(JudgeResponseParseError):
        parse_judge_response(raw)


def test_text_before_fence_rejected():
    body = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    raw = f"Here is the output:\n```json\n{body}\n```"
    with pytest.raises(JudgeResponseParseError):
        parse_judge_response(raw)


def test_text_after_fence_rejected():
    body = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    raw = f"```json\n{body}\n```\nDone."
    with pytest.raises(JudgeResponseParseError):
        parse_judge_response(raw)


# ---------------------------------------------------------------------------
# No field repair: parser returns exact parsed object.
# ---------------------------------------------------------------------------


def test_parser_does_not_repair_fields():
    # Missing a dimension -- parser returns the object as-is; validation is
    # the service's job, not the parser's.
    raw = json.dumps({"scores": {}, "critical_flags": []})
    parsed = parse_judge_response(raw)
    assert parsed == {"scores": {}, "critical_flags": []}
