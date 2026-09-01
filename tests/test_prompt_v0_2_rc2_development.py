"""Offline tests for Prompt v0.2-rc.2 support in the development generation runner.

No real Hy3 / OpenRouter API: the generation path uses a fake client and writes to
a ``tmp_path``, never to ``results/``. The finished rc.1 run (20260831-052126) is
read but never modified.

Covers the minimal version-parameterization of the shared development runner:

* ``v0.2-rc.2`` is passed EXPLICITLY to ``generate_speech_plan``;
* the rc.1 path still works (it remains the default);
* the same 30-case canonical population is used, with unchanged inputs;
* rc.2 artifacts land in their own results directory (rc.1 is never overwritten);
* metadata records ``prompt_version = v0.2-rc.2``;
* the delivery-plan distribution (empty vs. non-empty) is counted correctly,
  per intent, with the correct non-empty case IDs;
* no retry (exactly one first-call attempt per case);
* dry-run makes no API call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import Hy3APIError
from teachintent.prompt_development import development_runner as dr
from teachintent.prompt_development.development_runner import (
    CANDIDATE_PROMPT_VERSION,
    DEVELOPMENT_RESULTS_ROOT,
    DEVELOPMENT_RESULTS_ROOT_RC2,
    GENERATOR_MODEL,
    PEDAGOGICAL_INTENTS,
    PROMPT_VERSION_RC2,
    SUPPORTED_PROMPT_VERSIONS,
    TEMPERATURE,
    canonical_population_case_ids,
    discover_canonical_inputs,
    results_root_for_prompt_version,
    run_development_batch,
    summarize_delivery_distribution,
    validate_development_inputs,
)

# The finished, read-only rc.1 development generation run.
RC1_RUN_DIR = DEVELOPMENT_RESULTS_ROOT / "20260831-052126"


def _plan(delivery_plan: dict | None = None) -> str:
    """Build a schema-valid Speech Plan payload with the given delivery_plan."""
    return json.dumps(
        {
            "schema_version": "1.0.0-rc.3",
            "verbal_plan": {
                "segments": [{"segment_id": "seg_01", "text": "测试输出。"}]
            },
            "delivery_plan": {} if delivery_plan is None else delivery_plan,
        },
        ensure_ascii=False,
    )


class FakeHy3Client:
    """Scripts canned completions (or raises). Records every call.

    ``plans`` maps a 0-based case index to a raw response string; indices with no
    entry fall back to ``default``.
    """

    def __init__(
        self,
        default: str = "",
        *,
        plans: dict[int, str] | None = None,
        raise_exc: Exception | None = None,
        requested_model: str = "tencent/hy3",
    ) -> None:
        self._default = default or _plan()
        self._plans = plans or {}
        self._raise = raise_exc
        self._requested = requested_model
        self.calls: list[tuple[str, str, float]] = []

    @property
    def model(self) -> str:
        return self._requested

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        index = len(self.calls)
        self.calls.append((system, user, temperature))
        if self._raise is not None:
            raise self._raise
        return Hy3Completion(
            content=self._plans.get(index, self._default),
            finish_reason="stop",
            reported_model=self._requested,
        )


# ---------------------------------------------------------------------------
# 1. rc.2 is passed EXPLICITLY to generate_speech_plan.
# ---------------------------------------------------------------------------
def test_rc2_is_passed_explicitly_to_generate_speech_plan(
    monkeypatch, tmp_path
) -> None:
    captured: list[str] = []
    real_fn = dr.generate_speech_plan

    def spy(input_doc, client, *, prompt_version=CANDIDATE_PROMPT_VERSION):
        captured.append(prompt_version)
        return real_fn(input_doc, client, prompt_version=prompt_version)

    monkeypatch.setattr(dr, "generate_speech_plan", spy)

    run_development_batch(
        FakeHy3Client(),
        dry_run=False,
        output_dir=tmp_path,
        prompt_version=PROMPT_VERSION_RC2,
    )

    # All 30 calls received the explicit rc.2 — never the service default.
    assert captured == [PROMPT_VERSION_RC2] * 30


def test_supported_versions_are_exactly_rc1_and_rc2() -> None:
    assert SUPPORTED_PROMPT_VERSIONS == ("v0.2-rc.1", "v0.2-rc.2")


def test_unsupported_prompt_version_is_rejected_before_any_work() -> None:
    with pytest.raises(dr.DevelopmentValidationError) as exc:
        run_development_batch(None, dry_run=True, prompt_version="v0.2-rc.3")
    assert "v0.2-rc.3" in str(exc.value)

    with pytest.raises(dr.DevelopmentValidationError):
        results_root_for_prompt_version("v0.1")


# ---------------------------------------------------------------------------
# 2. The rc.1 path is still available (and remains the default).
# ---------------------------------------------------------------------------
def test_default_prompt_version_remains_rc1(monkeypatch, tmp_path) -> None:
    captured: list[str] = []
    real_fn = dr.generate_speech_plan

    def spy(input_doc, client, *, prompt_version=CANDIDATE_PROMPT_VERSION):
        captured.append(prompt_version)
        return real_fn(input_doc, client, prompt_version=prompt_version)

    monkeypatch.setattr(dr, "generate_speech_plan", spy)

    # No prompt_version argument at all -> the historical rc.1 default.
    manifest = run_development_batch(
        FakeHy3Client(), dry_run=False, output_dir=tmp_path
    )

    assert captured == [CANDIDATE_PROMPT_VERSION] * 30
    assert manifest["prompt_version"] == CANDIDATE_PROMPT_VERSION


def test_rc1_still_runs_when_selected_explicitly(monkeypatch, tmp_path) -> None:
    captured: list[str] = []
    real_fn = dr.generate_speech_plan

    def spy(input_doc, client, *, prompt_version=CANDIDATE_PROMPT_VERSION):
        captured.append(prompt_version)
        return real_fn(input_doc, client, prompt_version=prompt_version)

    monkeypatch.setattr(dr, "generate_speech_plan", spy)

    manifest = run_development_batch(
        FakeHy3Client(),
        dry_run=False,
        output_dir=tmp_path,
        prompt_version=CANDIDATE_PROMPT_VERSION,
    )

    assert captured == [CANDIDATE_PROMPT_VERSION] * 30
    assert manifest["prompt_version"] == "v0.2-rc.1"


# ---------------------------------------------------------------------------
# 3. Same 30-case population; inputs unchanged.
# ---------------------------------------------------------------------------
def test_thirty_cases_exact_match_canonical_population() -> None:
    cases = discover_canonical_inputs()
    report = validate_development_inputs(cases)
    assert report["valid"] is True
    assert report["block_counts"] == {"A": 12, "B": 12, "C": 6}
    assert report["matches_population"] is True

    population = canonical_population_case_ids()
    expected = {cid for ids in population.values() for cid in ids}
    assert {c.case_id for c in cases} == expected


def test_rc2_uses_inputs_identical_to_the_finished_rc1_run() -> None:
    """The rc.2 population is byte-identical to the inputs the rc.1 run used."""
    assert RC1_RUN_DIR.is_dir(), "the finished rc.1 run must remain on disk"

    for case in discover_canonical_inputs():
        rc1_input = RC1_RUN_DIR / "cases" / case.case_id / "input.json"
        assert rc1_input.is_file(), f"rc.1 input missing for {case.case_id}"
        stored = json.loads(rc1_input.read_text(encoding="utf-8"))
        assert stored == case.input_doc, f"input drift for {case.case_id}"


def test_rc1_run_artifacts_are_intact() -> None:
    """The rc.1 run is read-only: still 30 cases, still rc.1, still present."""
    manifest = json.loads(
        (RC1_RUN_DIR / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["prompt_version"] == "v0.2-rc.1"
    assert manifest["case_count"] == 30
    assert manifest["pass_count"] == 30


# ---------------------------------------------------------------------------
# 4. rc.2 artifacts land in their own directory.
# ---------------------------------------------------------------------------
def test_rc2_results_root_is_separate_from_rc1() -> None:
    assert (
        results_root_for_prompt_version(PROMPT_VERSION_RC2)
        == DEVELOPMENT_RESULTS_ROOT_RC2
    )
    assert (
        results_root_for_prompt_version(CANDIDATE_PROMPT_VERSION)
        == DEVELOPMENT_RESULTS_ROOT
    )
    assert DEVELOPMENT_RESULTS_ROOT_RC2 != DEVELOPMENT_RESULTS_ROOT
    assert DEVELOPMENT_RESULTS_ROOT_RC2.name == "prompt_v0_2_rc2_development"
    assert DEVELOPMENT_RESULTS_ROOT.name == "prompt_v0_2_rc1_development"


def test_rc2_run_writes_into_the_rc2_results_root(monkeypatch, tmp_path) -> None:
    # Point the rc.2 root at tmp_path so the real results/ tree is untouched.
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT_RC2", tmp_path)

    manifest = run_development_batch(
        FakeHy3Client(), dry_run=False, prompt_version=PROMPT_VERSION_RC2
    )

    run_dir = tmp_path / manifest["run_id"]
    assert run_dir.is_dir()
    assert len(list((run_dir / "cases").iterdir())) == 30


def test_rc1_run_still_writes_into_the_rc1_results_root(monkeypatch, tmp_path) -> None:
    """The rc.1 path keeps using the rc.1 root (its historical monkeypatch hook)."""
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)

    manifest = run_development_batch(
        FakeHy3Client(), dry_run=False, prompt_version=CANDIDATE_PROMPT_VERSION
    )

    assert (tmp_path / manifest["run_id"]).is_dir()
    assert len(list((tmp_path / manifest["run_id"] / "cases").iterdir())) == 30


def test_rc2_artifact_layout_is_complete(tmp_path) -> None:
    manifest = run_development_batch(
        FakeHy3Client(),
        dry_run=False,
        output_dir=tmp_path,
        prompt_version=PROMPT_VERSION_RC2,
    )
    sample = discover_canonical_inputs()[0]
    case_dir = tmp_path / manifest["run_id"] / "cases" / sample.case_id
    for name in (
        "input.json",
        "metadata.json",
        "prompt.json",
        "raw_response.txt",
        "parsed.json",
        "validation.json",
    ):
        assert (case_dir / name).is_file(), f"missing artifact {name}"


# ---------------------------------------------------------------------------
# 5. Metadata records rc.2 and the fixed experimental condition.
# ---------------------------------------------------------------------------
def test_metadata_records_rc2(tmp_path) -> None:
    manifest = run_development_batch(
        FakeHy3Client(),
        dry_run=False,
        output_dir=tmp_path,
        prompt_version=PROMPT_VERSION_RC2,
    )
    assert manifest["prompt_version"] == "v0.2-rc.2"
    assert manifest["generator_version"] == "v0.1"

    sample = discover_canonical_inputs()[0]
    case_dir = tmp_path / manifest["run_id"] / "cases" / sample.case_id
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["prompt_version"] == "v0.2-rc.2"
    assert metadata["generator_version"] == "v0.1"
    assert metadata["api_gateway"] == "openrouter"
    assert metadata["requested_model"] == GENERATOR_MODEL
    assert metadata["temperature"] == TEMPERATURE
    assert metadata["attempt_index"] == 1  # single first-call attempt, no retry
    # retry / self_repair are not per-case fields; they are fixed run conditions.
    assert manifest["actual_conditions"]["retry"] is False
    assert manifest["actual_conditions"]["self_repair"] is False


def test_prompt_artifact_is_the_real_rc2_prompt(tmp_path) -> None:
    manifest = run_development_batch(
        FakeHy3Client(),
        dry_run=False,
        output_dir=tmp_path,
        prompt_version=PROMPT_VERSION_RC2,
    )
    sample = discover_canonical_inputs()[0]
    case_dir = tmp_path / manifest["run_id"] / "cases" / sample.case_id
    prompt = json.loads((case_dir / "prompt.json").read_text(encoding="utf-8"))
    assert prompt["prompt_version"] == "v0.2-rc.2"
    assert "This is Prompt v0.2-rc.2" in prompt["system"]


# ---------------------------------------------------------------------------
# 6-8. Delivery-plan distribution.
# ---------------------------------------------------------------------------
def _mixed_client(count: int, delivery: dict) -> FakeHy3Client:
    """First *count* cases get a non-empty delivery_plan; the rest get ``{}``."""
    plans = {
        i: _plan(delivery if i < count else {}) for i in range(30)
    }
    return FakeHy3Client(plans=plans)


def test_delivery_distribution_counts_empty_and_non_empty(tmp_path) -> None:
    client = _mixed_client(7, {"attitudinal_tone": "reassuring but corrective"})
    manifest = run_development_batch(
        client, dry_run=False, output_dir=tmp_path, prompt_version=PROMPT_VERSION_RC2
    )

    dist = manifest["delivery_distribution"]
    assert dist["total_cases"] == 30
    assert dist["empty_count"] == 23
    assert dist["non_empty_count"] == 7
    assert dist["without_parsed_plan"] == 0
    assert len(dist["empty_case_ids"]) == 23
    assert len(dist["non_empty_case_ids"]) == 7


def test_delivery_distribution_non_empty_case_ids_are_correct(tmp_path) -> None:
    cases = discover_canonical_inputs()
    # Mark the first 7 cases (block order A, B, C) as non-empty.
    expected_ids = sorted(c.case_id for c in cases[:7])

    client = _mixed_client(7, {"attitudinal_tone": "reassuring but corrective"})
    manifest = run_development_batch(
        client, dry_run=False, output_dir=tmp_path, prompt_version=PROMPT_VERSION_RC2
    )

    dist = manifest["delivery_distribution"]
    assert dist["non_empty_case_ids"] == expected_ids
    # The two sets partition the population exactly.
    assert sorted(dist["empty_case_ids"] + dist["non_empty_case_ids"]) == sorted(
        c.case_id for c in cases
    )


def test_delivery_distribution_breakdown_by_intent(tmp_path) -> None:
    cases = discover_canonical_inputs()
    client = _mixed_client(7, {"attitudinal_tone": "reassuring but corrective"})
    manifest = run_development_batch(
        client, dry_run=False, output_dir=tmp_path, prompt_version=PROMPT_VERSION_RC2
    )
    dist = manifest["delivery_distribution"]

    # Every intent in the population is reported, with a full 5-case total.
    assert set(dist["by_intent"]) == set(PEDAGOGICAL_INTENTS)
    assert sum(b["total"] for b in dist["by_intent"].values()) == 30

    non_empty_ids = {c.case_id for c in cases[:7]}
    expected_per_intent: dict[str, int] = {}
    for c in cases:
        intent = c.input_doc["pedagogical_intent"]["primary"]
        if c.case_id in non_empty_ids:
            expected_per_intent[intent] = expected_per_intent.get(intent, 0) + 1

    for intent, bucket in dist["by_intent"].items():
        expected_non_empty = expected_per_intent.get(intent, 0)
        assert bucket["non_empty"] == expected_non_empty, intent
        assert bucket["empty"] == bucket["total"] - expected_non_empty, intent
        # empty + non-empty (+ unparsed) reconcile with the intent's total.
        assert (
            bucket["empty"] + bucket["non_empty"] + bucket["without_parsed_plan"]
            == bucket["total"]
        )


def test_all_empty_run_is_reported_as_full_collapse(tmp_path) -> None:
    """Reproduces the rc.1 failure mode: 30/30 empty, 0 non-empty."""
    manifest = run_development_batch(
        FakeHy3Client(),
        dry_run=False,
        output_dir=tmp_path,
        prompt_version=PROMPT_VERSION_RC2,
    )
    dist = manifest["delivery_distribution"]
    assert dist["empty_count"] == 30
    assert dist["non_empty_count"] == 0
    assert dist["non_empty_case_ids"] == []
    assert all(b["empty"] == b["total"] for b in dist["by_intent"].values())


def test_failed_generation_is_not_counted_as_empty(tmp_path) -> None:
    """A case with no parsed plan goes to without_parsed_plan, never to empty."""
    client = FakeHy3Client(
        raise_exc=Hy3APIError("Hy3 API returned HTTP 503", status_code=503)
    )
    manifest = run_development_batch(
        client, dry_run=False, output_dir=tmp_path, prompt_version=PROMPT_VERSION_RC2
    )
    dist = manifest["delivery_distribution"]
    assert dist["total_cases"] == 30
    assert dist["without_parsed_plan"] == 30
    assert dist["empty_count"] == 0
    assert dist["non_empty_count"] == 0
    assert len(dist["without_parsed_plan_case_ids"]) == 30


def test_summarize_delivery_distribution_is_pure_and_faithful() -> None:
    records = [
        {"case_id": "X-1", "intent": "explanation", "delivery_plan_empty": True},
        {"case_id": "X-2", "intent": "explanation", "delivery_plan_empty": False},
        {"case_id": "X-3", "intent": "scaffolding", "delivery_plan_empty": None},
    ]
    dist = summarize_delivery_distribution(records)
    assert dist["total_cases"] == 3
    assert dist["empty_count"] == 1
    assert dist["non_empty_count"] == 1
    assert dist["without_parsed_plan"] == 1
    assert dist["non_empty_case_ids"] == ["X-2"]
    assert dist["by_intent"]["explanation"] == {
        "total": 2,
        "empty": 1,
        "non_empty": 1,
        "without_parsed_plan": 0,
        "non_empty_case_ids": ["X-2"],
    }
    assert dist["by_intent"]["scaffolding"]["without_parsed_plan"] == 1


# ---------------------------------------------------------------------------
# 9. No retry.
# ---------------------------------------------------------------------------
def test_rc2_failure_does_not_retry(tmp_path) -> None:
    client = FakeHy3Client(
        raise_exc=Hy3APIError("Hy3 API returned HTTP 503", status_code=503)
    )
    manifest = run_development_batch(
        client, dry_run=False, output_dir=tmp_path, prompt_version=PROMPT_VERSION_RC2
    )
    # Exactly one first-call attempt per case — no retry loop, no self-repair.
    assert len(client.calls) == 30
    assert manifest["fail_count"] == 30
    assert manifest["structural_report"]["first_call_validity"] == 0
    assert all(c["outcome"] == "Hy3APIError" for c in manifest["cases"])


def test_rc2_success_makes_exactly_30_calls(tmp_path) -> None:
    client = FakeHy3Client()
    run_development_batch(
        client, dry_run=False, output_dir=tmp_path, prompt_version=PROMPT_VERSION_RC2
    )
    assert len(client.calls) == 30


# ---------------------------------------------------------------------------
# 10. Dry-run makes no API call.
# ---------------------------------------------------------------------------
def test_rc2_dry_run_makes_no_api_call_and_prints_plan(capsys) -> None:
    sentinel = FakeHy3Client("{}")
    summary = run_development_batch(
        sentinel, dry_run=True, prompt_version=PROMPT_VERSION_RC2
    )
    assert summary["api_call_made"] is False
    assert summary["planned_generator_calls"] == 30
    assert sentinel.calls == []  # no Hy3 contact

    out = capsys.readouterr().out
    assert "Development set = existing 30 Pilot cases" in out
    assert "A = 12" in out and "B = 12" in out and "C = 6" in out
    assert "total = 30" in out
    assert "candidate prompt = v0.2-rc.2" in out
    assert "Generator model = tencent/hy3" in out
    assert "temperature = 0" in out
    assert "retry = false" in out and "self_repair = false" in out
    assert "planned Generator calls = 30" in out
    assert "No API call was made." in out


def test_rc2_dry_run_writes_no_artifacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT_RC2", tmp_path)

    run_development_batch(None, dry_run=True, prompt_version=PROMPT_VERSION_RC2)
    assert list(tmp_path.iterdir()) == []  # nothing created
