"""Offline freeze tests for formal Generator Prompt v0.2.

Formal v0.2 is provenance metadata around the exact v0.2-rc.2 model-facing
treatment. No network client or experiment is used in this module.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.service import generate_speech_plan
from teachintent.prompts import (
    DEFAULT_PROMPT_VERSION,
    PARENT_PROMPT_VERSION_V0_2,
    PROMPT_VERSION,
    PROMPT_VERSION_V0_2,
    UnknownPromptVersionError,
    build_speech_plan_prompt,
    build_speech_plan_prompt_for_version,
    build_speech_plan_prompt_v0_2,
    build_speech_plan_prompt_v0_2_rc1,
    build_speech_plan_prompt_v0_2_rc2,
    get_speech_plan_prompt_version,
    list_speech_plan_prompt_versions,
)
from teachintent.prompts import speech_plan as v0_1_module
from teachintent.prompts import speech_plan_v0_2 as v0_2_module
from teachintent.prompts import speech_plan_v0_2_rc2 as rc2_module

V0_1_SYSTEM_SHA256 = (
    "7f438b2eb8b652a576d95f1cfae38607b888a634b1fbe33a6869d80e1392aed2"
)
RC1_SYSTEM_SHA256 = (
    "9c49c0b5ad0651c6792e7b1bdf23288fad62d870144a4894ae40e65e2846f4a4"
)
RC2_SYSTEM_SHA256 = (
    "a3068124162649c10c6a13cba1b467be4357fef672258d666bba2119ecdcd2e0"
)
RC2_PROMPT_PACKAGE_SHA256 = (
    "77cfcd6afeff58cc6868aad9b64da1a5af04e615477223b877c5d12234a90234"
)


def _doc(*, output_language: str = "zh-CN") -> dict:
    return {
        "schema_version": "1.0.0-rc.2",
        "output_language": output_language,
        "instructional_content": {
            "subject": "physics",
            "content_anchor": "速度描述物体运动的快慢和方向。",
        },
        "pedagogical_context": {
            "scenario": "The learner repeated a misconception.",
            "learner_utterance": "速度大就一定加速度大。",
        },
        "learner": {
            "level": "high_school",
            "knowledge_state": "misconception",
            "affective_state": "slightly_frustrated",
        },
        "pedagogical_intent": {"primary": "corrective_feedback"},
    }


def _sha256_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _prompt_package_sha256(system_template: str, user_template: str) -> str:
    """Reproduce the audit's frozen canonical prompt-package hash."""

    package = {
        "system_template": system_template.replace("\r\n", "\n").replace(
            "\r", "\n"
        ),
        "user_template": user_template.replace("\r\n", "\n").replace(
            "\r", "\n"
        ),
    }
    canonical = json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class RecordingClient:
    """Return one canned valid plan while preserving the exact prompt call."""

    model = "offline-fake-hy3"

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str, float]] = []

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        self.calls.append((system, user, temperature))
        return Hy3Completion(
            content=self.content,
            finish_reason="stop",
            reported_model="offline-fake-hy3",
        )


def test_formal_v0_2_metadata_and_parent() -> None:
    assert v0_2_module.PROMPT_VERSION == "v0.2"
    assert PROMPT_VERSION_V0_2 == "v0.2"
    assert v0_2_module.PARENT_PROMPT_VERSION == "v0.2-rc.2"
    assert PARENT_PROMPT_VERSION_V0_2 == "v0.2-rc.2"


def test_formal_v0_2_is_explicitly_selectable_and_default_stays_v0_1() -> None:
    assert DEFAULT_PROMPT_VERSION == PROMPT_VERSION == "v0.1"
    assert get_speech_plan_prompt_version("v0.2") == "v0.2"
    assert list_speech_plan_prompt_versions() == [
        "v0.1",
        "v0.2",
        "v0.2-rc.1",
        "v0.2-rc.2",
    ]
    assert build_speech_plan_prompt_for_version(_doc()) == build_speech_plan_prompt(
        _doc()
    )


def test_existing_prompt_versions_are_untouched() -> None:
    assert _sha256_text(build_speech_plan_prompt(_doc()).system) == V0_1_SYSTEM_SHA256
    assert (
        _sha256_text(build_speech_plan_prompt_v0_2_rc1(_doc()).system)
        == RC1_SYSTEM_SHA256
    )
    assert (
        _sha256_text(build_speech_plan_prompt_v0_2_rc2(_doc()).system)
        == RC2_SYSTEM_SHA256
    )


def test_formal_builder_is_the_exact_rc2_builder_object() -> None:
    assert build_speech_plan_prompt_v0_2 is build_speech_plan_prompt_v0_2_rc2
    assert v0_2_module.build_speech_plan_prompt is rc2_module.build_speech_plan_prompt


@pytest.mark.parametrize("output_language", ["zh-CN", "en-US"])
def test_built_formal_prompt_is_byte_identical_to_rc2(
    output_language: str,
) -> None:
    doc = _doc(output_language=output_language)
    formal = build_speech_plan_prompt_for_version(doc, "v0.2")
    rc2 = build_speech_plan_prompt_for_version(doc, "v0.2-rc.2")
    assert formal.system == rc2.system
    assert formal.user == rc2.user
    assert formal == rc2


def test_formal_v0_2_adds_no_model_facing_version_text() -> None:
    formal = build_speech_plan_prompt_v0_2(_doc())
    rc2 = build_speech_plan_prompt_v0_2_rc2(_doc())
    assert formal.system == rc2.system
    assert "This is Prompt v0.2." not in formal.system
    assert formal.system.count("v0.2-rc.2") == rc2.system.count("v0.2-rc.2")


def test_formal_prompt_package_sha_matches_frozen_rc2_value() -> None:
    assert v0_2_module.build_speech_plan_prompt is rc2_module.build_speech_plan_prompt
    assert (
        _prompt_package_sha256(rc2_module._SYSTEM, v0_1_module._USER_TEMPLATE)
        == RC2_PROMPT_PACKAGE_SHA256
    )


def test_invalid_version_still_fails_fast() -> None:
    with pytest.raises(UnknownPromptVersionError):
        build_speech_plan_prompt_for_version(_doc(), "v0.2-rc.3")


def test_generator_records_formal_metadata_without_changing_prompt_bytes(
    canonical_input_doc: dict,
    canonical_speech_plan_doc: dict,
) -> None:
    content = json.dumps(canonical_speech_plan_doc, ensure_ascii=False)
    formal_client = RecordingClient(content)
    rc2_client = RecordingClient(content)

    formal_result = generate_speech_plan(
        canonical_input_doc,
        formal_client,
        prompt_version="v0.2",
    )
    rc2_result = generate_speech_plan(
        canonical_input_doc,
        rc2_client,
        prompt_version="v0.2-rc.2",
    )

    assert formal_result.prompt_version == "v0.2"
    assert rc2_result.prompt_version == "v0.2-rc.2"
    assert formal_client.calls == rc2_client.calls
    assert formal_result.prompt_system == rc2_result.prompt_system
    assert formal_result.prompt_user == rc2_result.prompt_user
