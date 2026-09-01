"""Offline tests for the Generator Prompt **v0.2-rc.1**.

v0.2-rc.1 is a narrow, prompt-level behavioral revision of v0.1. These tests
assert:

* v0.1 remains independently loadable and BYTE-IDENTICAL (regression lock);
* v0.2-rc.1 is loadable and clearly distinct from v0.1;
* the v0.2-rc.1 system prompt actually contains every behavioral addition the
  revision specifies (delivery necessity gate, empty-delivery validity, verbal
  first / delivery second, per-intent minimum adequacy, hard/adversarial intent
  discipline, internal self-check that must not appear in the output);
* explicit version selection works through the registry.

No model API is ever called. Every prompt is built locally from a dict.
"""

from __future__ import annotations

import hashlib

import pytest

from teachintent.prompts import (
    DEFAULT_PROMPT_VERSION,
    PROMPT_VERSION,
    PROMPT_VERSION_V0_2_RC1,
    SpeechPlanPrompt,
    UnknownPromptVersionError,
    build_speech_plan_prompt,
    build_speech_plan_prompt_for_version,
    build_speech_plan_prompt_v0_2_rc1,
    get_speech_plan_prompt_version,
    list_speech_plan_prompt_versions,
)
from teachintent.prompts.speech_plan_v0_2_rc1 import PROMPT_VERSION as RC1_VERSION

# Frozen anchors so an accidental edit to either prompt is caught.
V0_1_SYSTEM_SHA256 = (
    "7f438b2eb8b652a576d95f1cfae38607b888a634b1fbe33a6869d80e1392aed2"
)
V0_2_RC1_SYSTEM_SHA256 = (
    "9c49c0b5ad0651c6792e7b1bdf23288fad62d870144a4894ae40e65e2846f4a4"
)


def _doc() -> dict:
    return {
        "schema_version": "1.0.0-rc.2",
        "output_language": "zh-CN",
        "instructional_content": {
            "subject": "physics",
            "content_anchor": "速度表示物体运动的快慢。",
        },
        "pedagogical_context": {
            "scenario": "Learner answered.",
            "learner_utterance": "速度越大加速度一定越大。",
        },
        "learner": {
            "level": "middle_school",
            "knowledge_state": "misconception",
            "affective_state": "slightly_frustrated",
        },
        "pedagogical_intent": {"primary": "corrective_feedback"},
    }


# ---------------------------------------------------------------------------
# 1. v0.1 still loads; 2. v0.2-rc.1 loads; 3. clearly distinct.
# ---------------------------------------------------------------------------
def test_v0_1_still_loadable_and_is_the_package_default() -> None:
    assert PROMPT_VERSION == "v0.1"
    assert DEFAULT_PROMPT_VERSION == "v0.1"
    prompt = build_speech_plan_prompt(_doc())
    assert isinstance(prompt, SpeechPlanPrompt)
    assert prompt.system and prompt.user


def test_v0_2_rc1_loadable_and_version_constant() -> None:
    assert RC1_VERSION == "v0.2-rc.1"
    assert PROMPT_VERSION_V0_2_RC1 == "v0.2-rc.1"
    prompt = build_speech_plan_prompt_v0_2_rc1(_doc())
    assert isinstance(prompt, SpeechPlanPrompt)
    assert prompt.system and prompt.user


def test_two_versions_are_clearly_distinct() -> None:
    v1 = build_speech_plan_prompt(_doc())
    v2 = build_speech_plan_prompt_v0_2_rc1(_doc())
    assert v1.system != v2.system
    # The user message (input serialization) is intentionally shared/identical.
    assert v1.user == v2.user


# ---------------------------------------------------------------------------
# 4. v0.1 content unchanged (regression lock).
# ---------------------------------------------------------------------------
def test_v0_1_prompt_text_is_byte_identical() -> None:
    prompt = build_speech_plan_prompt(_doc())
    assert (
        hashlib.sha256(prompt.system.encode("utf-8")).hexdigest()
        == V0_1_SYSTEM_SHA256
    )
    # And through the registry default path too.
    via_registry = build_speech_plan_prompt_for_version(_doc(), "v0.1")
    assert via_registry.system == prompt.system


# ---------------------------------------------------------------------------
# 5. delivery necessity rule present.
# ---------------------------------------------------------------------------
def test_v0_2_rc1_contains_delivery_necessity_gate() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "Delivery Necessity Gate" in system
    assert "Default to no delivery control" in system
    assert (
        "Add a delivery control only when a specific pedagogical need clearly "
        "requires vocal realization beyond what the verbal wording alone can "
        "achieve" in system
    )
    assert "What exact pedagogical need does this control serve?" in system


# ---------------------------------------------------------------------------
# 6. empty delivery plan explicitly valid.
# ---------------------------------------------------------------------------
def test_v0_2_rc1_explicitly_allows_empty_delivery_plan() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "Empty delivery plan is valid" in system
    # `{}` is not incomplete / is preferred when wording suffices.
    assert "`{}` is not incomplete" in system
    # The schema contract still permits `{}`.
    assert "`delivery_plan`: object. `{}` is allowed." in system


# ---------------------------------------------------------------------------
# 7. verbal-first / delivery-second.
# ---------------------------------------------------------------------------
def test_v0_2_rc1_is_verbal_first_delivery_second() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "verbal first, delivery second" in system
    # Default to empty delivery until a need is named.
    assert "Default to `delivery_plan = {}`" in system
    # Wording over prosody preference.
    assert "Prefer wording over prosody" in system


# ---------------------------------------------------------------------------
# 8. six-intent minimum adequacy.
# ---------------------------------------------------------------------------
def test_v0_2_rc1_contains_six_intent_minimum_adequacy() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "Intent-specific Minimum Adequacy" in system
    for intent in (
        "elicitation",
        "scaffolding",
        "explanation",
        "corrective_feedback",
        "supportive_feedback",
        "extension",
    ):
        assert intent in system
    # Representative adequacy floors.
    assert "minimum sufficient hint" in system          # scaffolding
    assert "do more than restate the answer" in system  # explanation
    assert "specific successful behavior" in system     # supportive_feedback
    assert "unsupported external knowledge" in system   # extension boundary


# ---------------------------------------------------------------------------
# 9. hard / adversarial intent discipline.
# ---------------------------------------------------------------------------
def test_v0_2_rc1_contains_hard_adversarial_intent_discipline() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "Hard / Adversarial Intent Discipline" in system
    assert "PRESERVE the specified primary intent" in system
    # The drift examples.
    assert "scaffolding` != immediately handing over the full explanation" in system
    assert "`elicitation` != asking and then answering the question yourself" in system
    assert "supportive_feedback` != praise followed by unrelated new instruction" in system
    assert "`extension` != introducing unsupported external knowledge" in system


# ---------------------------------------------------------------------------
# 10. internal self-check present; 11. must not appear in output.
# ---------------------------------------------------------------------------
def test_v0_2_rc1_contains_internal_self_check() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "Internal pre-output self-check" in system
    for label in ("1. Intent", "2. Boundary", "3. Adequacy", "4. Delivery"):
        assert label in system


def test_v0_2_rc1_self_check_is_not_emitted_in_output() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert "do NOT emit" in system
    assert "NEVER part of the output" in system
    assert "Do NOT emit any of these checks" in system
    assert "chain-of-thought" in system
    # The existing output discipline must remain.
    assert "Output ONLY the final JSON object" in system
    assert "No Markdown fences" in system or "no Markdown code fences" in system


# ---------------------------------------------------------------------------
# Protected capabilities preserved (must not regress v0.1's strengths).
# ---------------------------------------------------------------------------
def test_v0_2_rc1_preserves_hard_rules_and_field_contract() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"):
        assert f"{rule}." in system
    # Schema contract unchanged.
    assert 'must be exactly "1.0.0-rc.3"' in system
    assert "seg_[0-9]{2,}" in system
    # Anti-injection preserved.
    assert "untrusted DATA" in system


def test_v0_2_rc1_system_prompt_is_locked() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert (
        hashlib.sha256(system.encode("utf-8")).hexdigest()
        == V0_2_RC1_SYSTEM_SHA256
    )


# ---------------------------------------------------------------------------
# Explicit version selection through the registry.
# ---------------------------------------------------------------------------
def test_registry_lists_all_versions_and_defaults_to_v0_1() -> None:
    versions = list_speech_plan_prompt_versions()
    assert versions == ["v0.1", "v0.2", "v0.2-rc.1", "v0.2-rc.2"]
    assert DEFAULT_PROMPT_VERSION == "v0.1"


def test_registry_selects_each_version() -> None:
    v1 = build_speech_plan_prompt_for_version(_doc(), "v0.1")
    v2 = build_speech_plan_prompt_for_version(_doc(), "v0.2-rc.1")
    assert v1.system == build_speech_plan_prompt(_doc()).system
    assert v2.system == build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert get_speech_plan_prompt_version("v0.2-rc.1") == "v0.2-rc.1"


def test_registry_rejects_unknown_version() -> None:
    with pytest.raises(UnknownPromptVersionError):
        build_speech_plan_prompt_for_version(_doc(), "v0.9")
    with pytest.raises(UnknownPromptVersionError):
        get_speech_plan_prompt_version("v0.9")


def test_v0_2_rc1_is_deterministic() -> None:
    a = build_speech_plan_prompt_v0_2_rc1(_doc())
    b = build_speech_plan_prompt_v0_2_rc1(_doc())
    assert a.system == b.system
    assert a.user == b.user
