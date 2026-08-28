"""Tests for the frozen Judge Prompt v0.1.

Covers: SHA-256 determinism, dynamic case data not entering the hash,
prompt structure, LF normalization.
"""

from __future__ import annotations

import hashlib
import json

from teachintent.evaluator import (
    JUDGE_OUTPUT_CONTRACT,
    JUDGE_PROMPT_VERSION,
    RUBRIC_TEXT,
    SYSTEM_TEMPLATE,
    USER_TEMPLATE,
    build_judge_prompt,
    compute_judge_prompt_sha256,
)


def _normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _manual_sha256():
    """Manually compute the expected SHA-256 per Section 5.2."""
    pkg = {
        "system_template": _normalize_lf(SYSTEM_TEMPLATE),
        "user_template": _normalize_lf(USER_TEMPLATE),
        "rubric_text": _normalize_lf(RUBRIC_TEXT),
        "judge_output_contract": _normalize_lf(JUDGE_OUTPUT_CONTRACT),
    }
    canonical = json.dumps(
        pkg, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# Prompt version.
# ---------------------------------------------------------------------------


def test_judge_prompt_version_is_v0_1():
    assert JUDGE_PROMPT_VERSION == "v0.1"


# ---------------------------------------------------------------------------
# SHA-256 determinism.
# ---------------------------------------------------------------------------


def test_sha256_is_deterministic():
    assert compute_judge_prompt_sha256() == compute_judge_prompt_sha256()


def test_sha256_matches_manual_computation():
    assert compute_judge_prompt_sha256() == _manual_sha256()


def test_sha256_is_64_lowercase_hex():
    sha = compute_judge_prompt_sha256()
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)


# ---------------------------------------------------------------------------
# Dynamic case data does not enter the hash.
# ---------------------------------------------------------------------------


def test_dynamic_case_data_not_in_hash():
    """The hash is over the static package only; different case data does
    not change the hash."""
    sha_before = compute_judge_prompt_sha256()
    # Build a rendered prompt with different case data.
    payload_a = {"input": {"output_language": "zh-CN", "instructional_content": {"content_anchor": "AAA"}, "pedagogical_context": {"scenario": "x"}, "learner": {"level": "middle_school", "knowledge_state": "misconception"}, "pedagogical_intent": {"primary": "explanation"}}, "plan": {"verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "a"}]}, "delivery_plan": {}}}
    payload_b = {"input": {"output_language": "en-US", "instructional_content": {"content_anchor": "BBB"}, "pedagogical_context": {"scenario": "y"}, "learner": {"level": "high_school", "knowledge_state": "correct_understanding"}, "pedagogical_intent": {"primary": "elicitation"}}, "plan": {"verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "b"}]}, "delivery_plan": {}}}
    build_judge_prompt(payload_a)
    build_judge_prompt(payload_b)
    sha_after = compute_judge_prompt_sha256()
    assert sha_before == sha_after


# ---------------------------------------------------------------------------
# Prompt structure.
# ---------------------------------------------------------------------------


def test_system_template_contains_rubric_placeholder():
    assert "{rubric_text}" in SYSTEM_TEMPLATE
    assert "{judge_output_contract}" in SYSTEM_TEMPLATE


def test_user_template_contains_data_delimiters():
    assert "BEGIN TEACHINTENT INPUT DATA" in USER_TEMPLATE
    assert "END TEACHINTENT INPUT DATA" in USER_TEMPLATE
    assert "BEGIN GENERATED SPEECH PLAN DATA" in USER_TEMPLATE
    assert "END GENERATED SPEECH PLAN DATA" in USER_TEMPLATE


def test_rubric_text_contains_all_six_dimensions():
    for dim in (
        "D1", "D2", "D3", "D4", "D5", "D6",
        "Pedagogical Intent Fidelity",
        "Content Faithfulness and Boundary Control",
        "Learner-State Compatibility",
        "Intent-Specific Instructional Adequacy",
        "Delivery Necessity and Sparsity",
        "Delivery-Pedagogy Alignment",
    ):
        assert dim in RUBRIC_TEXT


def test_rubric_text_contains_d1_d4_distinction():
    assert "D1/D4" in RUBRIC_TEXT or "D1 asks" in RUBRIC_TEXT
    assert "D4 asks" in RUBRIC_TEXT or "D4 evaluates" in RUBRIC_TEXT


def test_rubric_text_contains_d5_d6_distinction():
    assert "D5" in RUBRIC_TEXT
    assert "D6" in RUBRIC_TEXT


def test_judge_output_contract_contains_evidence_grammar():
    assert "path" in JUDGE_OUTPUT_CONTRACT
    assert "root" in JUDGE_OUTPUT_CONTRACT
    assert "input" in JUDGE_OUTPUT_CONTRACT
    assert "plan" in JUDGE_OUTPUT_CONTRACT


def test_judge_output_contract_contains_all_critical_flags():
    for flag in (
        "prompt_injection_compliance",
        "false_content_affirmation",
        "content_anchor_contradiction",
        "material_off_anchor_content",
        "learner_humiliation",
        "negative_self_label_reinforcement",
        "coercive_or_hostile_delivery",
    ):
        assert flag in JUDGE_OUTPUT_CONTRACT


def test_system_template_includes_anti_injection():
    assert "UNTRUSTED EVALUATION DATA" in SYSTEM_TEMPLATE
    assert "Anti-injection" in SYSTEM_TEMPLATE or "anti-injection" in SYSTEM_TEMPLATE.lower()


def test_system_template_forbids_overall_score():
    assert "overall_score" in SYSTEM_TEMPLATE
    assert "MUST NOT produce" in SYSTEM_TEMPLATE or "MUST NOT" in SYSTEM_TEMPLATE


def test_system_template_json_only():
    assert "JSON" in SYSTEM_TEMPLATE
    assert "No Markdown" in SYSTEM_TEMPLATE or "No text before or after" in SYSTEM_TEMPLATE


def test_system_template_no_chain_of_thought():
    assert "chain-of-thought" in SYSTEM_TEMPLATE.lower()


# ---------------------------------------------------------------------------
# build_judge_prompt renders correctly.
# ---------------------------------------------------------------------------


def test_build_judge_prompt_renders_system_and_user():
    payload = {"input": {"output_language": "zh-CN", "instructional_content": {"content_anchor": "x"}, "pedagogical_context": {"scenario": "y"}, "learner": {"level": "middle_school", "knowledge_state": "misconception"}, "pedagogical_intent": {"primary": "explanation"}}, "plan": {"verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "a"}]}, "delivery_plan": {}}}
    prompt = build_judge_prompt(payload)
    assert prompt.system
    assert prompt.user
    assert "zh-CN" in prompt.user
    assert "BEGIN TEACHINTENT INPUT DATA" in prompt.user
    assert "BEGIN GENERATED SPEECH PLAN DATA" in prompt.user
