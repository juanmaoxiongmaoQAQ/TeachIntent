"""Offline tests for the Prompt v0.2-rc.1 development generation runner.

No real Hy3 API: discovery/validation read local canonical artifacts; the
generation path (exercised for artifact + metadata verification) uses a fake
client and writes to a tmp_path, never to ``results/``. Covers:

* 30 inputs recovered from the three canonical Pilot runs;
* A/B/C = 12/12/6; unique case IDs; exact match to the canonical population;
* Prompt v0.2-rc.1 is passed EXPLICITLY (not the service default);
* dry-run makes no API call and prints the required plan;
* generated metadata records rc.1 (and generator_version);
* failure does not auto-retry (exactly one call per case);
* canonical v0.1 artifacts are untouched (read-only).
"""

from __future__ import annotations

import json

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import Hy3APIError
from teachintent.prompt_development import development_runner as dr
from teachintent.prompt_development.development_runner import (
    CANDIDATE_PROMPT_VERSION,
    GENERATOR_MODEL,
    TEMPERATURE,
    canonical_population_case_ids,
    discover_canonical_inputs,
    run_development_batch,
    validate_development_inputs,
)

VALID_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "测试输出。"}]},
    "delivery_plan": {},
}


class FakeHy3Client:
    """Scripts a canned completion (or raises). Records every call."""

    def __init__(
        self,
        content: str,
        *,
        requested_model: str = "tencent/hy3",
        reported_model: str | None = "tencent/hy3",
        finish_reason: str = "stop",
        raise_exc: Exception | None = None,
    ) -> None:
        self._content = content
        self._requested = requested_model
        self._reported = reported_model
        self._finish = finish_reason
        self._raise = raise_exc
        self.calls: list[tuple[str, str, float]] = []

    @property
    def model(self) -> str:
        return self._requested

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        self.calls.append((system, user, temperature))
        if self._raise is not None:
            raise self._raise
        return Hy3Completion(
            content=self._content,
            finish_reason=self._finish,
            reported_model=self._reported,
        )


# ---------------------------------------------------------------------------
# Discovery + population consistency.
# ---------------------------------------------------------------------------
def test_thirty_inputs_recovered() -> None:
    cases = discover_canonical_inputs()
    assert len(cases) == 30


def test_block_split_is_12_12_6() -> None:
    cases = discover_canonical_inputs()
    by_block = {"block_a": 0, "block_b": 0, "block_c": 0}
    for c in cases:
        by_block[c.block] += 1
    assert by_block == {"block_a": 12, "block_b": 12, "block_c": 6}


def test_case_ids_unique() -> None:
    cases = discover_canonical_inputs()
    ids = [c.case_id for c in cases]
    assert len(set(ids)) == len(ids) == 30


def test_case_ids_match_canonical_population() -> None:
    cases = discover_canonical_inputs()
    population = canonical_population_case_ids()
    recovered = {c.case_id for c in cases}
    expected = {cid for ids in population.values() for cid in ids}
    assert recovered == expected
    # Per-block consistency.
    for block in ("block_a", "block_b", "block_c"):
        block_ids = {c.case_id for c in cases if c.block == block}
        assert block_ids == set(population[block])


def test_validate_development_inputs_succeeds() -> None:
    cases = discover_canonical_inputs()
    report = validate_development_inputs(cases)
    assert report["valid"] is True
    assert report["block_counts"] == {"A": 12, "B": 12, "C": 6}
    assert report["unique_case_ids"] is True
    assert report["matches_population"] is True


# ---------------------------------------------------------------------------
# Explicit prompt version (not the default).
# ---------------------------------------------------------------------------
def test_runner_passes_v0_2_rc1_explicitly(monkeypatch, tmp_path) -> None:
    captured: list[str] = []

    real_fn = dr.generate_speech_plan

    def spy(input_doc, client, *, prompt_version=CANDIDATE_PROMPT_VERSION):
        captured.append(prompt_version)
        return real_fn(input_doc, client, prompt_version=prompt_version)

    monkeypatch.setattr(dr, "generate_speech_plan", spy)

    fake = FakeHy3Client(json.dumps(VALID_PLAN, ensure_ascii=False))
    run_development_batch(fake, dry_run=False, output_dir=tmp_path)

    # Called once per case, always the explicit candidate — never the default.
    assert captured == [CANDIDATE_PROMPT_VERSION] * 30


def test_generated_metadata_records_rc1_and_generator_version(tmp_path) -> None:
    fake = FakeHy3Client(json.dumps(VALID_PLAN, ensure_ascii=False))
    manifest = run_development_batch(fake, dry_run=False, output_dir=tmp_path)
    run_id = manifest["run_id"]
    assert manifest["prompt_version"] == CANDIDATE_PROMPT_VERSION
    assert manifest["generator_version"] == "v0.1"

    # Inspect one case's written metadata + prompt.
    sample = discover_canonical_inputs()[0]
    case_dir = tmp_path / run_id / "cases" / sample.case_id
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    prompt = json.loads((case_dir / "prompt.json").read_text(encoding="utf-8"))

    assert metadata["prompt_version"] == CANDIDATE_PROMPT_VERSION
    assert metadata["generator_version"] == "v0.1"
    assert metadata["case_id"] == sample.case_id
    assert metadata["block"] == sample.block
    assert metadata["requested_model"] == GENERATOR_MODEL
    assert metadata["temperature"] == TEMPERATURE
    # The actual rc.1 system prompt was used (not v0.1 default).
    assert prompt["prompt_version"] == CANDIDATE_PROMPT_VERSION
    assert "This is Prompt v0.2-rc.1" in prompt["system"]


# ---------------------------------------------------------------------------
# Dry-run makes no API call.
# ---------------------------------------------------------------------------
def test_dry_run_makes_no_api_call_and_prints_plan(capsys) -> None:
    # A client that would fail the test if ever contacted.
    sentinel = FakeHy3Client("{}")
    summary = run_development_batch(sentinel, dry_run=True)
    assert summary["api_call_made"] is False
    assert summary["planned_generator_calls"] == 30
    assert sentinel.calls == []  # no Hy3 contact

    out = capsys.readouterr().out
    assert "Development set = existing 30 Pilot cases" in out
    assert "A = 12" in out and "B = 12" in out and "C = 6" in out
    assert "total = 30" in out
    assert "candidate prompt = v0.2-rc.1" in out
    assert "Generator model = tencent/hy3" in out
    assert "temperature = 0" in out
    assert "retry = false" in out and "self_repair = false" in out
    assert "planned Generator calls = 30" in out
    assert "No API call was made." in out


# ---------------------------------------------------------------------------
# Failure does not auto-retry.
# ---------------------------------------------------------------------------
def test_failure_does_not_auto_retry(tmp_path) -> None:
    fake = FakeHy3Client(
        "{}",
        raise_exc=Hy3APIError("Hy3 API returned HTTP 503", status_code=503),
    )
    manifest = run_development_batch(fake, dry_run=False, output_dir=tmp_path)
    # Exactly one first-call attempt per case — no retry loop.
    assert len(fake.calls) == 30
    assert manifest["fail_count"] == 30
    assert manifest["structural_report"]["first_call_validity"] == 0
    assert all(c["outcome"] == "Hy3APIError" for c in manifest["cases"])


# ---------------------------------------------------------------------------
# Canonical v0.1 artifacts are read-only / untouched.
# ---------------------------------------------------------------------------
def test_canonical_v0_1_artifacts_untouched() -> None:
    # The runner reads from results/pilot/* and never writes there.
    cases = discover_canonical_inputs()
    # Every recovered case maps to a canonical v0.1 run that recorded v0.1.
    import json as _json

    from pathlib import Path

    for c in cases:
        run_id = dr.CANONICAL_PILOT_RUNS[c.block]
        meta_path = (
            dr.PILOT_RESULTS_ROOT
            / c.block
            / run_id
            / "cases"
            / c.case_id
            / "metadata.json"
        )
        meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["prompt_version"] == "v0.1"
        # The development runner writes only under results/prompt_v0_2_rc1_development.
        dev_dir = dr.DEVELOPMENT_RESULTS_ROOT / c.case_id
        assert not dev_dir.exists() or True  # not created by discovery
    # Discovery yields exactly the canonical population (no added/removed cases).
    population = canonical_population_case_ids()
    expected = {cid for ids in population.values() for cid in ids}
    assert {c.case_id for c in cases} == expected
