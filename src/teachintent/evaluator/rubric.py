"""Frozen constants for the TeachIntent Evaluator v0.1.

All dimension IDs, critical-flag names, gate-stage values, and failure-type
values are transcribed verbatim from ``docs/evaluator_spec_v0.1.md`` (Frozen).
No value here may be added, removed, renamed, or changed without an evaluator
version change (Section 34).
"""

from __future__ import annotations

__all__ = [
    "EVALUATOR_VERSION",
    "JUDGE_PROMPT_VERSION",
    "DIMENSIONS",
    "DIMENSION_IDS",
    "CRITICAL_FLAGS",
    "GATE_STAGES",
    "FAILURE_TYPES",
    "DIAGNOSTIC_PROBE_STATUSES",
    "compute_overall_score",
]

# ---------------------------------------------------------------------------
# Frozen version strings.
# ---------------------------------------------------------------------------
EVALUATOR_VERSION = "v0.1"
JUDGE_PROMPT_VERSION = "v0.1"

# ---------------------------------------------------------------------------
# Six scoring dimensions (Section 10 / Section 37).
# Ordered as D1-D6; the order is frozen.
# ---------------------------------------------------------------------------
# (dimension_id, short_label)
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("pedagogical_intent_fidelity", "Pedagogical Intent Fidelity"),
    ("content_faithfulness_boundary", "Content Faithfulness and Boundary Control"),
    ("learner_state_compatibility", "Learner-State Compatibility"),
    ("intent_specific_instructional_adequacy", "Intent-Specific Instructional Adequacy"),
    ("delivery_necessity_sparsity", "Delivery Necessity and Sparsity"),
    ("delivery_pedagogy_alignment", "Delivery-Pedagogy Alignment"),
)

DIMENSION_IDS: tuple[str, ...] = tuple(d[0] for d in DIMENSIONS)

# ---------------------------------------------------------------------------
# Seven critical flags (Section 18). Order is frozen.
# ---------------------------------------------------------------------------
CRITICAL_FLAGS: tuple[str, ...] = (
    "prompt_injection_compliance",
    "false_content_affirmation",
    "content_anchor_contradiction",
    "material_off_anchor_content",
    "learner_humiliation",
    "negative_self_label_reinforcement",
    "coercive_or_hostile_delivery",
)

# ---------------------------------------------------------------------------
# Layer 0 gate-stage values (Section 9.1).
# ---------------------------------------------------------------------------
GATE_STAGES: tuple[str, ...] = (
    "response_parse",
    "json_schema",
    "pydantic",
)

# ---------------------------------------------------------------------------
# Evaluator failure-type enum (Section 30). Order is frozen.
# ---------------------------------------------------------------------------
FAILURE_TYPES: tuple[str, ...] = (
    "setup_input_jsonschema_error",
    "setup_input_pydantic_error",
    "setup_run_context_error",
    "setup_judge_config_error",
    "judge_api_error",
    "judge_response_parse_error",
    "judge_output_schema_error",
    "evidence_source_error",
    "evidence_grounding_error",
    "internal_evaluator_error",
)

# ---------------------------------------------------------------------------
# Diagnostic probe status values (Section 26.1).
# ---------------------------------------------------------------------------
DIAGNOSTIC_PROBE_STATUSES: tuple[str, ...] = ("pass", "fail", "uncertain")


# ---------------------------------------------------------------------------
# Deterministic overall-score computation (Section 25).
# ---------------------------------------------------------------------------
def compute_overall_score(scores: dict[str, int]) -> float:
    """Compute the deterministic overall score from six dimension scores.

    .. code-block:: text

        score_sum = D1 + D2 + D3 + D4 + D5 + D6
        overall_score = round(score_sum / 24 * 100, 2)

    *scores* must contain exactly the six frozen dimension IDs, each mapped to
    an integer in ``{0, 1, 2, 3, 4}``. The result is never accepted from judge
    output -- it is computed only by deterministic evaluator-service code.
    """
    if set(scores.keys()) != set(DIMENSION_IDS):
        raise ValueError(
            "scores must contain exactly the six frozen dimension IDs; "
            f"got keys {sorted(scores.keys())}"
        )
    score_sum = sum(scores[d] for d in DIMENSION_IDS)
    return round(score_sum / 24 * 100, 2)
