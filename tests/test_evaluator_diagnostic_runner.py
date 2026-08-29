"""Tests for the diagnostic runner (offline; fake judge injected).

Verifies: repeats are honored, experiment metadata never leaks into Layer 1,
deterministic record construction, dry-run makes no judge calls, and dataset
validation aborts before any judge call.
"""

from __future__ import annotations

import json

import pytest

from teachintent.evaluator import (
    DIMENSION_IDS,
    JudgeCompletion,
    compute_judge_prompt_sha256,
)
from teachintent.evaluator_diagnostic import (
    DIAGNOSTIC_DATASET_PATH,
    build_judge_config,
    build_run_context,
    load_diagnostic_pairs,
    run_diagnostic,
    run_diagnostic_dry,
)
from teachintent.evaluator_diagnostic.dataset import validate_diagnostic_dataset

SHA = compute_judge_prompt_sha256()


def _judge_output_json(scores=None):
    scores = scores or {d: 4 for d in DIMENSION_IDS}
    return json.dumps({
        "scores": {
            d: {
                "score": scores[d],
                "evidence": [{"source": "plan.schema_version", "text": "1.0.0-rc.3"}],
                "brief_justification": "ok",
            }
            for d in DIMENSION_IDS
        },
        "critical_flags": [],
    }, ensure_ascii=False)


class FakeJudge:
    """Deterministic fake judge; captures system/user messages per call."""

    def __init__(self, content_fn=None):
        self._content_fn = content_fn or (lambda idx: _judge_output_json())
        self.call_count = 0
        self.users: list[str] = []
        self.systems: list[str] = []

    @property
    def provider(self):
        return "openrouter"

    @property
    def model(self):
        return "tencent/hy3"

    @property
    def structured_output_enabled(self):
        return False

    def complete(self, system, user, *, temperature=0.0):
        self.call_count += 1
        self.systems.append(system)
        self.users.append(user)
        result = self._content_fn(self.call_count - 1)
        if isinstance(result, Exception):
            raise result
        return JudgeCompletion(
            content=result,
            reported_model="tencent/hy3-reported",
            structured_object=None,
            finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# Runner repeats.
# ---------------------------------------------------------------------------


def test_runner_repeats(tmp_path):
    judge = FakeJudge()
    result = run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge, repeats=3)
    # 24 pairs x 2 sides x 3 repeats
    assert len(result.records) == 24 * 2 * 3
    assert judge.call_count == 24 * 2 * 3
    assert result.repeats == 3


def test_runner_default_repeats_is_three():
    judge = FakeJudge()
    result = run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge)
    assert result.repeats == 3


def test_runner_rejects_zero_repeats(tmp_path):
    judge = FakeJudge()
    with pytest.raises(ValueError, match="repeats"):
        run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge, repeats=0)


# ---------------------------------------------------------------------------
# Experiment metadata never leaks into Layer 1.
# ---------------------------------------------------------------------------


def test_experiment_metadata_never_leaks_to_judge():
    judge = FakeJudge()
    run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge, repeats=1)

    pairs = load_diagnostic_pairs()
    forbidden = set()
    for p in pairs:
        forbidden.add(p["pair_id"])
        forbidden.add(p["family"])
        forbidden.update(p["target_dimensions"])
        forbidden.update(p["expected_flags"])

    for user in judge.users:
        # Structural metadata keys / values must not appear in the user payload.
        assert "pair_id" not in user
        assert '"family"' not in user
        assert "target_dimensions" not in user
        assert "expected_flags" not in user
        assert '"notes"' not in user
        for token in forbidden:
            assert token not in user, f"leaked metadata token {token!r}"


def test_judge_payload_contains_only_sanitized_input_and_plan():
    judge = FakeJudge()
    run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge, repeats=1)
    # Every user message must contain the Layer-1-visible input and plan
    # sections, and must NOT contain schema_version (dropped by the sanitizer).
    for user in judge.users:
        assert "BEGIN TEACHINTENT INPUT DATA" in user
        assert "BEGIN GENERATED SPEECH PLAN DATA" in user
        assert "1.0.0-rc.2" not in user
        assert "1.0.0-rc.3" not in user


# ---------------------------------------------------------------------------
# Deterministic record construction.
# ---------------------------------------------------------------------------


def test_deterministic_record_construction():
    judge_a = FakeJudge()
    judge_b = FakeJudge()
    result_a = run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge_a, repeats=2)
    result_b = run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge_b, repeats=2)
    assert [r.pair_id for r in result_a.records] == [r.pair_id for r in result_b.records]
    assert [r.side for r in result_a.records] == [r.side for r in result_b.records]
    assert [r.scores for r in result_a.records] == [r.scores for r in result_b.records]
    assert [r.critical_flags for r in result_a.records] == [r.critical_flags for r in result_b.records]


def test_record_order_is_pair_then_side_then_repeat():
    judge = FakeJudge()
    result = run_diagnostic(DIAGNOSTIC_DATASET_PATH, judge, repeats=2)
    # First record is DIAG-A-01 reference repeat 0.
    assert result.records[0].pair_id == "DIAG-A-01"
    assert result.records[0].side == "reference"
    assert result.records[0].repeat_index == 0
    # Order: A-01 ref(0,1), A-01 deg(0,1), A-02 ref(0,1), ...
    assert result.records[1].side == "reference"
    assert result.records[1].repeat_index == 1
    assert result.records[2].side == "degraded"
    assert result.records[3].side == "degraded"
    assert result.records[4].pair_id == "DIAG-A-02"


# ---------------------------------------------------------------------------
# Judge config / run context.
# ---------------------------------------------------------------------------


def test_build_judge_config_binds_backend():
    judge = FakeJudge()
    cfg = build_judge_config(judge)
    assert cfg.judge_provider == "openrouter"
    assert cfg.judge_model_requested == "tencent/hy3"
    assert cfg.temperature == 0
    assert cfg.judge_prompt_version == "v0.1"
    assert cfg.judge_prompt_sha256 == SHA
    assert cfg.structured_output_enabled is False
    assert cfg.retry_enabled is False
    assert cfg.self_repair_enabled is False


def test_build_run_context_uses_pair_id():
    ctx = build_run_context("DIAG-A-01")
    assert ctx.input_case_id == "DIAG-A-01"
    assert ctx.generator_version == "v0.1"
    assert ctx.prompt_version == "v0.1"


# ---------------------------------------------------------------------------
# Dry run: no judge calls.
# ---------------------------------------------------------------------------


def test_dry_run_makes_no_judge_calls():
    result = run_diagnostic_dry(DIAGNOSTIC_DATASET_PATH, repeats=3)
    assert result.dry_run is True
    assert result.records == ()
    assert result.repeats == 3
    assert result.validator["all_passed"] is True


def test_dry_run_rejects_zero_repeats():
    with pytest.raises(ValueError, match="repeats"):
        run_diagnostic_dry(DIAGNOSTIC_DATASET_PATH, repeats=0)


# ---------------------------------------------------------------------------
# Dataset validation aborts before any judge call.
# ---------------------------------------------------------------------------


def test_invalid_dataset_aborts_before_judge_call(tmp_path):
    import copy
    pairs = load_diagnostic_pairs()
    broken = copy.deepcopy(pairs)
    broken[0]["pair_id"] = "DIAG-Z-99"  # invalid format
    path = tmp_path / "broken.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for p in broken:
            handle.write(json.dumps(p, ensure_ascii=False) + "\n")

    judge = FakeJudge()
    with pytest.raises(ValueError, match="structural validation"):
        run_diagnostic(path, judge, repeats=1)
    assert judge.call_count == 0


def test_frozen_dataset_validates():
    report = validate_diagnostic_dataset()
    assert report.all_passed
