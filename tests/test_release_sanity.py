from __future__ import annotations

import json
from pathlib import Path

from teachintent.evaluator import JudgeCompletion
from teachintent.generator import Hy3Completion
from teachintent.generator_evaluation.baseline_v0_1 import CanonicalCase
from teachintent.release_sanity import (
    DATASET_PATH,
    DIMENSION_IDS,
    EVIDENCE_LABEL,
    GENERATOR_MODEL,
    acquire_one_semantic_artifact,
    generation_schedule,
    load_jsonl,
    run_release_sanity,
    summarize_delivery_behavior,
    validate_release_sanity_dataset,
)


VALID_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [{"segment_id": "seg_01", "text": "请继续说明你的想法。"}]
    },
    "delivery_plan": {},
}


def judge_output(score: int = 4) -> str:
    return json.dumps(
        {
            "scores": {
                dimension: {
                    "score": score,
                    "evidence": [{"source": "plan.delivery_plan", "text": "{}"}],
                    "brief_justification": "evidence is grounded",
                }
                for dimension in DIMENSION_IDS
            },
            "critical_flags": [],
        },
        ensure_ascii=False,
    )


class FakeGenerator:
    model = GENERATOR_MODEL

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        self.calls.append((system, user, temperature))
        return Hy3Completion(
            content=json.dumps(VALID_PLAN, ensure_ascii=False),
            finish_reason="stop",
            reported_model=self.model,
        )


class FakeJudge:
    provider = "openrouter"
    model = "qwen/qwen3.5-plus-20260420"
    structured_output_enabled = False

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or [judge_output()])
        self.calls = 0

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        self.calls += 1
        content = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return JudgeCompletion(
            content=content,
            reported_model=self.model,
            structured_object=None,
            finish_reason="stop",
        )


def canonical_case() -> CanonicalCase:
    row = load_jsonl(DATASET_PATH)[0]
    return CanonicalCase(
        case_id=row["case_id"],
        block=row["block"],
        block_name=row["block"],
        intent=row["input"]["pedagogical_intent"]["primary"],
        source_run_id="test",
        source_path="test",
        input_doc=row["input"],
        raw_response=json.dumps(VALID_PLAN, ensure_ascii=False),
        prompt_version="v0.2",
        generator_version="v0.1",
        requested_model=GENERATOR_MODEL,
        reported_model=GENERATOR_MODEL,
        generation_outcome="success",
    )


def test_release_sanity_dataset_contract_and_manifest_hashes() -> None:
    report = validate_release_sanity_dataset()
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["case_count"] == 12
    assert report["intent_counts"] == {
        "corrective_feedback": 2,
        "elicitation": 2,
        "explanation": 2,
        "extension": 2,
        "scaffolding": 2,
        "supportive_feedback": 2,
    }
    assert report["role_counts"] == {"challenging": 6, "standard": 6}
    assert report["challenging_type_counts"] == {
        "cross_domain": 3,
        "hard_adversarial": 3,
    }
    assert report["output_language_counts"] == {"zh-CN": 12}
    assert report["duplicate_screen"]["passed"] is True


def test_generation_schedule_is_24_calls_and_balances_first_position() -> None:
    schedule = generation_schedule(load_jsonl(DATASET_PATH))
    assert len(schedule) == 24
    assert {(item["case_id"], item["prompt_version"]) for item in schedule} == {
        (row["case_id"], version)
        for row in load_jsonl(DATASET_PATH)
        for version in ("v0.1", "v0.2")
    }
    first = [item["prompt_version"] for item in schedule if item["within_case_position"] == 1]
    assert first.count("v0.1") == 6
    assert first.count("v0.2") == 6


def test_valid_low_score_never_retries() -> None:
    judge = FakeJudge([judge_output(score=0)])
    outcome = acquire_one_semantic_artifact(
        canonical_case(), judge, sleep_fn=lambda _: None
    )
    assert outcome["semantic_repeat_success"] is True
    assert outcome["attempt_count"] == 1
    assert outcome["successful_attempt_index"] == 1
    assert judge.calls == 1


def test_operational_failure_retries_and_preserves_failed_attempt() -> None:
    judge = FakeJudge(["not-json", judge_output()])
    sleeps: list[float] = []
    outcome = acquire_one_semantic_artifact(
        canonical_case(), judge, sleep_fn=sleeps.append
    )
    assert outcome["semantic_repeat_success"] is True
    assert outcome["attempt_count"] == 2
    assert outcome["successful_attempt_index"] == 2
    assert outcome["attempt_failure_types"] == ["judge_response_parse_error"]
    assert outcome["attempts"][0]["judge_raw_response"] == "not-json"
    assert sleeps == [2.0]


def test_delivery_summary_counts_atomic_controls() -> None:
    generations = [
        {
            "case_id": "empty",
            "prompt_version": "v0.2",
            "valid_plan": True,
            "parsed_plan": VALID_PLAN,
        },
        {
            "case_id": "controlled",
            "prompt_version": "v0.2",
            "valid_plan": True,
            "parsed_plan": {
                **VALID_PLAN,
                "delivery_plan": {
                    "global": {
                        "attitudinal_tone": "reassuring",
                        "prosody": {"speaking_rate": "slow"},
                    },
                    "segment_overrides": [
                        {
                            "segment_id": "seg_01",
                            "prominence_targets": [
                                {"text": "想法", "level": "moderate"}
                            ],
                        }
                    ],
                },
            },
        },
    ]
    summary = summarize_delivery_behavior(generations, "v0.2")
    assert summary["empty_count"] == 1
    assert summary["non_empty_count"] == 1
    assert summary["controls_per_non_empty_plan"] == {"controlled": 3}
    assert summary["obvious_all_empty_collapse"] is False
    assert summary["obvious_all_non_empty_over_control"] is False


def test_fake_end_to_end_run_writes_descriptive_artifacts(tmp_path: Path) -> None:
    generator = FakeGenerator()
    judge = FakeJudge()
    output = tmp_path / "release-sanity"
    run_dir, summary = run_release_sanity(
        generator,
        judge,
        output_dir=output,
        sleep_fn=lambda _: None,
    )
    assert len(generator.calls) == 24
    assert judge.calls == 24
    assert summary["evidence_label"] == EVIDENCE_LABEL
    assert summary["is_formal_confirmatory_evidence"] is False
    assert summary["formal_pass_fail"] is None
    assert summary["generation"]["v0.1"]["valid_plan_count"] == 12
    assert summary["generation"]["v0.2"]["valid_plan_count"] == 12
    assert summary["evaluation"]["v0.1"]["successful_artifacts"] == 12
    assert summary["evaluation"]["v0.2"]["successful_artifacts"] == 12
    assert summary["paired_comparison"]["pair_eligible_count"] == 12
    assert (run_dir / "run_manifest.json").is_file()
    assert (run_dir / "evaluations.jsonl").is_file()
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "paired_scores.csv").is_file()
    assert (run_dir / "REPORT.md").is_file()
    report_text = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "NOT FORMAL CONFIRMATORY EVIDENCE" in report_text
    assert "confidence interval" in summary["interpretation_note"]
