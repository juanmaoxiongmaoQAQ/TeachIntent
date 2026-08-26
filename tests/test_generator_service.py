"""Tests for the speech plan generation service.

Uses duck-typed fake clients (no network). Covers the canonical happy path with
round-trip, parser-tolerance integration, and every failure-taxonomy stage:
input contract, API error passthrough, response parsing, structural validation,
semantic validation. The input dict must not be mutated.
"""

from __future__ import annotations

import copy
import json

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import (
    Hy3APIError,
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from teachintent.generator.service import generate_speech_plan
from teachintent.prompts import PROMPT_VERSION


class FakeHy3Client:
    """Scripts a canned completion; records call args."""

    def __init__(
        self,
        content: str,
        *,
        requested_model: str = "fake-hy3",
        reported_model: str | None = "fake-hy3-reported",
        finish_reason: str = "stop",
    ) -> None:
        self._content = content
        self._requested = requested_model
        self._reported = reported_model
        self._finish = finish_reason
        self.calls: list[tuple[str, str, float]] = []

    @property
    def model(self) -> str:
        return self._requested

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        self.calls.append((system, user, temperature))
        return Hy3Completion(
            content=self._content,
            finish_reason=self._finish,
            reported_model=self._reported,
        )


class RaisingHy3Client:
    """Raises a preset exception on complete()."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self._requested = "fake-hy3"

    @property
    def model(self) -> str:
        return self._requested

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        raise self._exc


# ---------------------------------------------------------------------------
# Canonical success.
# ---------------------------------------------------------------------------


def test_canonical_input_yields_validated_speech_plan(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    result = generate_speech_plan(canonical_input_doc, fake)

    assert result.prompt_version == PROMPT_VERSION == "v0.1"
    assert result.requested_model == "fake-hy3"
    assert result.reported_model == "fake-hy3-reported"
    assert result.plan_doc == canonical_speech_plan_doc
    assert result.raw_response == json.dumps(
        canonical_speech_plan_doc, ensure_ascii=False
    )
    assert result.duration_seconds >= 0.0
    assert result.started_at  # ISO timestamp present

    # Pydantic round-trip (mode="json" so str-enums serialize to their values).
    dumped = result.speech_plan.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    assert dumped == canonical_speech_plan_doc


def test_canonical_success_sends_temperature_zero_and_built_prompt(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    generate_speech_plan(canonical_input_doc, fake)

    assert len(fake.calls) == 1
    system, user, temperature = fake.calls[0]
    assert temperature == 0.0
    # Prompt is built from the canonical input.
    assert canonical_input_doc["output_language"] in user
    assert "BEGIN CASE DATA" in user and "END CASE DATA" in user
    assert canonical_input_doc["instructional_content"]["content_anchor"] in user
    # R9 tonal-language safety rule present.
    assert "Tonal-language safety" in system


def test_markdown_fenced_canonical_response_succeeds(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    body = json.dumps(canonical_speech_plan_doc, ensure_ascii=False)
    fake = FakeHy3Client(f"```json\n{body}\n```")
    result = generate_speech_plan(canonical_input_doc, fake)
    assert result.plan_doc == canonical_speech_plan_doc


def test_reported_model_none_is_recorded(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(
        json.dumps(canonical_speech_plan_doc, ensure_ascii=False),
        reported_model=None,
    )
    result = generate_speech_plan(canonical_input_doc, fake)
    assert result.reported_model is None
    assert result.requested_model == "fake-hy3"


# ---------------------------------------------------------------------------
# Response parsing failure (stage 5).
# ---------------------------------------------------------------------------


def test_malformed_json_response_raises_parsing_error(canonical_input_doc) -> None:
    fake = FakeHy3Client("{not valid json")
    with pytest.raises(ResponseParsingError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert exc.value.raw_text == "{not valid json"


# ---------------------------------------------------------------------------
# Output structural validation failure (stage 6, JSON Schema layer).
# ---------------------------------------------------------------------------


def _minimal_valid_plan_doc() -> dict:
    return {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
        },
        "delivery_plan": {},
    }


def test_unknown_root_field_is_structural_failure(canonical_input_doc) -> None:
    doc = _minimal_valid_plan_doc()
    doc["teacher_authority"] = 0.8  # Rule 6/9
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanStructuralError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert exc.value.plan_doc == doc
    assert exc.value.raw_text  # raw_response preserved
    assert "teacher_authority" in str(exc.value) or "additional" in str(
        exc.value
    ).lower()


def test_bad_enum_is_structural_failure(canonical_input_doc) -> None:
    doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
        },
        "delivery_plan": {
            "segment_overrides": [
                {"segment_id": "seg_01", "prosody": {"speaking_rate": "very-slow"}}
            ]
        },
    }
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanStructuralError):
        generate_speech_plan(canonical_input_doc, fake)


def test_wrong_schema_version_is_structural_failure(canonical_input_doc) -> None:
    doc = _minimal_valid_plan_doc()
    doc["schema_version"] = "1.0.0-rc.2"
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanStructuralError):
        generate_speech_plan(canonical_input_doc, fake)


# ---------------------------------------------------------------------------
# Output semantic validation failure (stage 7, Pydantic layer).
# ---------------------------------------------------------------------------


def test_rule_2_unknown_override_reference_is_semantic_failure(
    canonical_input_doc,
) -> None:
    doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
        },
        "delivery_plan": {
            "segment_overrides": [{"segment_id": "seg_99", "emotion": "calm"}]
        },
    }
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanSemanticError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert "Rule 2 (segment reference integrity)" in exc.value.error_text
    assert exc.value.raw_text


def test_rule_5_prominence_not_substring_is_semantic_failure(
    canonical_input_doc,
) -> None:
    doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
        },
        "delivery_plan": {
            "segment_overrides": [
                {
                    "segment_id": "seg_01",
                    "prominence_targets": [
                        {"text": "位移", "level": "strong"}
                    ],
                }
            ]
        },
    }
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanSemanticError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert "Rule 5 (prominence span integrity)" in exc.value.error_text


def test_rule_3_duplicate_override_is_semantic_failure(canonical_input_doc) -> None:
    doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
        },
        "delivery_plan": {
            "segment_overrides": [
                {"segment_id": "seg_01", "emotion": "calm"},
                {"segment_id": "seg_01", "prosody": {"speaking_rate": "slow"}},
            ]
        },
    }
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanSemanticError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert "Rule 3 (one override per segment)" in exc.value.error_text


def test_rule_11_default_without_global_is_semantic_failure(
    canonical_input_doc,
) -> None:
    doc = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "速度大。"}]
        },
        "delivery_plan": {
            "segment_overrides": [
                {"segment_id": "seg_01", "prosody": {"speaking_rate": "default"}}
            ]
        },
    }
    fake = FakeHy3Client(json.dumps(doc))
    with pytest.raises(SpeechPlanSemanticError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert "Rule 11 (meaningful default reset)" in exc.value.error_text


# ---------------------------------------------------------------------------
# Input contract failure (stages 1-2).
# ---------------------------------------------------------------------------


def test_input_bad_intent_enum_is_input_contract_failure(
    canonical_speech_plan_doc,
) -> None:
    bad_input = {
        "schema_version": "1.0.0-rc.2",
        "output_language": "zh-CN",
        "instructional_content": {"content_anchor": "速度表示运动快慢。"},
        "pedagogical_context": {"scenario": "Learner answered."},
        "learner": {"level": "middle_school", "knowledge_state": "misconception"},
        "pedagogical_intent": {"primary": "out_of_scope"},
    }
    # The fake should never be called on invalid input.
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc))
    with pytest.raises(InputContractError) as exc:
        generate_speech_plan(bad_input, fake)
    assert exc.value.layer == "jsonschema"
    assert fake.calls == []


def test_input_missing_content_anchor_is_input_contract_failure(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    del canonical_input_doc["instructional_content"]["content_anchor"]
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc))
    with pytest.raises(InputContractError):
        generate_speech_plan(canonical_input_doc, fake)
    assert fake.calls == []


def test_input_explicit_null_is_input_contract_failure(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    canonical_input_doc["learner"]["affective_state"] = None
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc))
    with pytest.raises(InputContractError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    # JSON Schema rejects {"field": null} (type error) before Pydantic runs; the
    # Pydantic explicit-null guard is defense-in-depth that never fires here
    # because the jsonschema layer always catches null first.
    assert exc.value.layer == "jsonschema"


# ---------------------------------------------------------------------------
# API error passthrough (stage 4).
# ---------------------------------------------------------------------------


def test_hy3_api_error_propagates_unchanged(canonical_input_doc) -> None:
    api_error = Hy3APIError("Hy3 API returned HTTP 503", status_code=503)
    fake = RaisingHy3Client(api_error)
    with pytest.raises(Hy3APIError) as exc:
        generate_speech_plan(canonical_input_doc, fake)
    assert exc.value is api_error  # no wrapping, no retry


# ---------------------------------------------------------------------------
# Input non-mutation.
# ---------------------------------------------------------------------------


def test_input_doc_is_not_mutated(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    snapshot = copy.deepcopy(canonical_input_doc)
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    generate_speech_plan(canonical_input_doc, fake)
    assert canonical_input_doc == snapshot
