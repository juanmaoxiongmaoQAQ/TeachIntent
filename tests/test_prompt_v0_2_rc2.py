"""Offline tests for the Generator Prompt **v0.2-rc.2**.

v0.2-rc.2 is a minimal-scope correction of v0.2-rc.1 that fixes the observed
"always-empty delivery_plan" over-correction: sparsity must mean *minimum
justified control*, NOT *zero control*. These tests assert:

* v0.1 and v0.2-rc.1 remain independently loadable and BYTE-IDENTICAL;
* v0.2-rc.2 is loadable and selectable through the registry;
* v0.2-rc.2 no longer says "Assume you need NO delivery control";
* v0.2-rc.2 states the "minimum justified control, not zero control" principle;
* v0.2-rc.2 explicitly forbids the always-empty strategy;
* v0.2-rc.2 keeps the sparse-control prohibitions (no neutral defaults, no
  redundant controls, no importance-only prominence, etc.);
* v0.2-rc.2 keeps the six-intent minimum adequacy, content boundary, and
  hard/adversarial intent discipline.

No model API is ever called. Every prompt is built locally from a dict.
"""

from __future__ import annotations

import hashlib

from teachintent.prompts import (
    PROMPT_VERSION_V0_2_RC2,
    build_speech_plan_prompt,
    build_speech_plan_prompt_for_version,
    build_speech_plan_prompt_v0_2_rc1,
    build_speech_plan_prompt_v0_2_rc2,
    get_speech_plan_prompt_version,
    list_speech_plan_prompt_versions,
)
from teachintent.prompts.speech_plan_v0_2_rc2 import PROMPT_VERSION as RC2_VERSION

# Frozen anchors shared with the rc.1 test — they lock that v0.1 and v0.2-rc.1
# remain byte-identical after the rc.2 correction.
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


def _rc2_system() -> str:
    return build_speech_plan_prompt_v0_2_rc2(_doc()).system


# ---------------------------------------------------------------------------
# 1. version identity + loadable + selectable.
# ---------------------------------------------------------------------------
def test_rc2_version_constant() -> None:
    assert RC2_VERSION == "v0.2-rc.2"
    assert PROMPT_VERSION_V0_2_RC2 == "v0.2-rc.2"


def test_rc2_is_loadable_and_distinct_from_rc1() -> None:
    prompt = build_speech_plan_prompt_v0_2_rc2(_doc())
    assert prompt.system and prompt.user
    rc1 = build_speech_plan_prompt_v0_2_rc1(_doc())
    assert prompt.system != rc1.system
    # The user message (input serialization) is intentionally shared.
    assert prompt.user == rc1.user


def test_rc2_is_selectable_through_the_registry() -> None:
    via_registry = build_speech_plan_prompt_for_version(_doc(), "v0.2-rc.2")
    assert via_registry.system == _rc2_system()
    assert get_speech_plan_prompt_version("v0.2-rc.2") == "v0.2-rc.2"


# ---------------------------------------------------------------------------
# 2. v0.1 / rc.1 remain byte-identical (regression lock).
# ---------------------------------------------------------------------------
def test_v0_1_prompt_text_is_byte_identical() -> None:
    system = build_speech_plan_prompt(_doc()).system
    assert hashlib.sha256(system.encode("utf-8")).hexdigest() == V0_1_SYSTEM_SHA256


def test_rc1_prompt_text_is_byte_identical() -> None:
    system = build_speech_plan_prompt_v0_2_rc1(_doc()).system
    assert (
        hashlib.sha256(system.encode("utf-8")).hexdigest() == V0_2_RC1_SYSTEM_SHA256
    )


# ---------------------------------------------------------------------------
# 3. correction: no longer assumes zero delivery control.
# ---------------------------------------------------------------------------
def test_rc2_no_longer_assumes_no_delivery_control() -> None:
    system = _rc2_system()
    assert "Assume you need NO delivery control" not in system


# ---------------------------------------------------------------------------
# 4. minimum justified control, not zero control.
# ---------------------------------------------------------------------------
def test_rc2_states_minimum_justified_control_not_zero_control() -> None:
    system = _rc2_system()
    assert "minimum justified control, not zero control" in system
    assert "Sparsity does NOT mean always empty" in system
    assert "Start from the minimum necessary delivery plan" in system


# ---------------------------------------------------------------------------
# 5. forbids the always-empty strategy.
# ---------------------------------------------------------------------------
def test_rc2_forbids_always_empty_strategy() -> None:
    system = _rc2_system()
    assert "do NOT choose `{}` merely to avoid over-specification" in system
    assert "smallest justified control set" in system


# ---------------------------------------------------------------------------
# 6. sparse-control prohibitions preserved.
# ---------------------------------------------------------------------------
def test_rc2_preserves_sparse_control_prohibitions() -> None:
    system = _rc2_system()
    # No neutral/medium defaults.
    assert "Do NOT emit `speaking_rate = medium`" in system
    # Importance-only prominence still forbidden.
    assert "Importance alone does not justify emphasis" in system
    # Duplicated global/local controls still forbidden.
    assert "Avoid redundant global + local controls" in system
    # Redundant stacking still forbidden.
    assert "Do not stack redundant controls" in system
    # Wording over prosody still preferred.
    assert "Prefer wording over prosody" in system


# ---------------------------------------------------------------------------
# 7. protected capabilities preserved.
# ---------------------------------------------------------------------------
def test_rc2_preserves_six_intent_minimum_adequacy() -> None:
    system = _rc2_system()
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
    assert "minimum sufficient hint" in system          # scaffolding floor
    assert "do more than restate the answer" in system  # explanation floor


def test_rc2_preserves_hard_rules_and_content_boundary() -> None:
    system = _rc2_system()
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"):
        assert f"{rule}." in system
    # Schema contract unchanged.
    assert 'must be exactly "1.0.0-rc.3"' in system
    assert "seg_[0-9]{2,}" in system
    # Anti-injection and content boundary preserved.
    assert "untrusted DATA" in system
    assert "must NEVER contradict it" in system


def test_rc2_preserves_hard_adversarial_intent_discipline() -> None:
    system = _rc2_system()
    assert "Hard / Adversarial Intent Discipline" in system
    assert "PRESERVE the specified primary intent" in system


def test_rc2_is_still_verbal_first_delivery_second() -> None:
    system = _rc2_system()
    assert "verbal first, delivery second" in system


# ---------------------------------------------------------------------------
# 8. balanced delivery self-check (verify controls AND verify emptiness).
# ---------------------------------------------------------------------------
def test_rc2_self_check_has_balance_check() -> None:
    system = _rc2_system()
    assert "Internal pre-output self-check" in system
    # Present side: every control needs a specific pedagogical reason.
    assert (
        "For every delivery control, is there a specific pedagogical reason" in system
    )
    # Absent side: an empty plan must not silently omit a materially useful
    # vocal realization.
    assert "have I omitted a vocal realization" in system
    # Still no reasoning / chain-of-thought in the output.
    assert "Do NOT emit any of these checks" in system
    assert "chain-of-thought" in system


# ---------------------------------------------------------------------------
# 9. registry lists all four versions, default still v0.1.
# ---------------------------------------------------------------------------
def test_registry_lists_four_versions_and_defaults_to_v0_1() -> None:
    assert list_speech_plan_prompt_versions() == [
        "v0.1",
        "v0.2",
        "v0.2-rc.1",
        "v0.2-rc.2",
    ]


def test_rc2_is_deterministic() -> None:
    a = build_speech_plan_prompt_v0_2_rc2(_doc())
    b = build_speech_plan_prompt_v0_2_rc2(_doc())
    assert a.system == b.system
    assert a.user == b.user
