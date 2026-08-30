"""Offline tests for explicit ``prompt_version`` selection in the generator service.

No network / no real Hy3 API: a duck-typed fake client scripts a canned
completion. Verifies:
* default (no arg) -> v0.1
* explicit "v0.1" -> v0.1
* explicit "v0.2-rc.1" -> rc.1 (and the actual system prompt differs)
* metadata records the resolved version for both
* an unknown version fails fast with no silent fallback to v0.1
"""

from __future__ import annotations

import json

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import (
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from teachintent.generator.service import generate_speech_plan
from teachintent.prompts import PROMPT_VERSION
from teachintent.prompts.registry import UnknownPromptVersionError

V0_1 = "v0.1"
V0_2_RC1 = "v0.2-rc.1"


class FakeHy3Client:
    """Scripts a canned completion; records the exact (system, user, temp) call."""

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


# ---------------------------------------------------------------------------
# 1 + 2 + 6: default and explicit v0.1 both yield v0.1; metadata records v0.1.
# ---------------------------------------------------------------------------


def test_default_no_prompt_version_is_v0_1(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    result = generate_speech_plan(canonical_input_doc, fake)
    assert result.prompt_version == V0_1 == PROMPT_VERSION
    # The default must be byte-identical to the original v0.1 behavior.
    assert len(fake.calls) == 1
    system, _, _ = fake.calls[0]
    assert "This is Prompt v0.2-rc.1" not in system  # v0.1 has no rc.1 intro


def test_explicit_v0_1_is_v0_1(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    result = generate_speech_plan(
        canonical_input_doc, fake, prompt_version=V0_1
    )
    assert result.prompt_version == V0_1
    # Same system prompt produced as the default path.
    assert len(fake.calls) == 1
    system, _, _ = fake.calls[0]
    assert "This is Prompt v0.2-rc.1" not in system


# ---------------------------------------------------------------------------
# 3 + 5 + 4: explicit v0.2-rc.1 routes to rc.1; metadata + system differ.
# ---------------------------------------------------------------------------


def test_explicit_v0_2_rc1_is_rc1(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    result = generate_speech_plan(
        canonical_input_doc, fake, prompt_version=V0_2_RC1
    )
    assert result.prompt_version == V0_2_RC1
    assert len(fake.calls) == 1
    system, _, _ = fake.calls[0]
    # rc.1 is actually wired: its distinctive intro/markers are present.
    assert "This is Prompt v0.2-rc.1" in system
    assert "Delivery Necessity Gate" in system


def test_two_versions_produce_different_system_prompts(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    out_v0_1 = FakeHy3Client(
        json.dumps(canonical_speech_plan_doc, ensure_ascii=False)
    )
    out_rc1 = FakeHy3Client(
        json.dumps(canonical_speech_plan_doc, ensure_ascii=False)
    )
    generate_speech_plan(canonical_input_doc, out_v0_1, prompt_version=V0_1)
    generate_speech_plan(canonical_input_doc, out_rc1, prompt_version=V0_2_RC1)
    sys_v0_1 = out_v0_1.calls[0][0]
    sys_rc1 = out_rc1.calls[0][0]
    assert sys_v0_1 != sys_rc1
    assert "This is Prompt v0.2-rc.1" not in sys_v0_1
    assert "This is Prompt v0.2-rc.1" in sys_rc1


def test_rc1_metadata_records_v0_2_rc1(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    result = generate_speech_plan(
        canonical_input_doc, fake, prompt_version=V0_2_RC1
    )
    # Not silently recorded as v0.1.
    assert result.prompt_version != V0_1
    assert result.prompt_version == V0_2_RC1
    assert V0_2_RC1 in result.prompt_system


def test_v0_1_metadata_records_v0_1(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    result = generate_speech_plan(canonical_input_doc, fake, prompt_version=V0_1)
    assert result.prompt_version == V0_1
    # The v0.1 system prompt is the original text (no rc.1 markers) and is not
    # silently swapped for the rc.1 prompt.
    assert "v0.2-rc.1" not in result.prompt_system


# ---------------------------------------------------------------------------
# 7: invalid version fails fast, before the Hy3 API call, no silent fallback.
# ---------------------------------------------------------------------------


def test_invalid_version_fails_fast_without_api_call(
    canonical_input_doc,
) -> None:
    fake = FakeHy3Client(json.dumps({"schema_version": "1.0.0-rc.3"}))
    with pytest.raises(UnknownPromptVersionError) as exc:
        generate_speech_plan(
            canonical_input_doc, fake, prompt_version="v9.9"
        )
    # Fail-fast: the client is never contacted.
    assert fake.calls == []
    assert "v9.9" in str(exc.value)
    assert V0_2_RC1 in str(exc.value) or V0_1 in str(exc.value)


def test_invalid_version_does_not_fall_back_to_v0_1(
    canonical_input_doc, canonical_speech_plan_doc
) -> None:
    fake = FakeHy3Client(json.dumps(canonical_speech_plan_doc, ensure_ascii=False))
    with pytest.raises(UnknownPromptVersionError):
        generate_speech_plan(
            canonical_input_doc, fake, prompt_version="v0.2"
        )
    # Confirmed: no generation happened (would have recorded a call otherwise).
    assert fake.calls == []
