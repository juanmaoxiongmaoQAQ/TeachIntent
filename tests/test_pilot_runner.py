"""Focused mocked tests for the Block A pilot batch runner.

No real API calls. Uses a configurable fake client that scripts per-call-index
behavior. The frozen Block A dataset is loaded but only case["input"] is passed
to the Generator service.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import Hy3APIError
from teachintent.pilot_runner import (
    BLOCK_A_DATASET_PATH,
    FROZEN_CONDITIONS,
    PreflightError,
    run_pilot_block_a,
)

CANONICAL_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [
            {"segment_id": "seg_01", "text": "你的思路已经很接近了。"},
            {"segment_id": "seg_02", "text": "不过这里有一个关键点需要纠正。"},
        ]
    },
    "delivery_plan": {
        "global": {"attitudinal_tone": "supportive", "emotion": "calm"},
        "segment_overrides": [
            {
                "segment_id": "seg_02",
                "prosody": {"speaking_rate": "slow"},
                "prominence_targets": [
                    {"text": "关键点", "level": "strong"}
                ],
                "boundary_after": {"strength": "strong"},
            }
        ],
    },
}


class FakePilotClient:
    """Configurable fake: content_fn(call_index) -> str | Exception.

    Exposes ``endpoint`` and ``_response_format`` so the config preflight
    (which checks OpenRouter base URL and structured-output=disabled) passes
    by default, matching the frozen baseline.
    """

    def __init__(
        self,
        content_fn,
        *,
        model="tencent/hy3",
        reported_model="tencent/hy3-reported",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        response_format=None,
    ):
        self._content_fn = content_fn
        self._model = model
        self._reported = reported_model
        self._endpoint = endpoint
        self._response_format = response_format
        self.call_count = 0

    @property
    def model(self):
        return self._model

    @property
    def endpoint(self):
        return self._endpoint

    def complete(self, system, user, *, temperature=0.0):
        idx = self.call_count
        self.call_count += 1
        result = self._content_fn(idx)
        if isinstance(result, Exception):
            raise result
        return Hy3Completion(
            content=result,
            finish_reason="stop",
            reported_model=self._reported,
        )


def _all_success_content(idx):
    return json.dumps(CANONICAL_PLAN, ensure_ascii=False)


# ---------------------------------------------------------------------------
# All cases succeed.
# ---------------------------------------------------------------------------


def test_all_cases_succeed(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    assert manifest.case_count == 12
    assert manifest.pass_count == 12
    assert manifest.fail_count == 0
    assert all(c["outcome"] == "success" for c in manifest.cases)
    # Artifacts written.
    run_dir = tmp_path / manifest.run_id
    assert (run_dir / "manifest.json").exists()
    assert len(list((run_dir / "cases").iterdir())) == 12


def test_artifacts_structure_per_case(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    for filename in (
        "input.json",
        "prompt.json",
        "raw_response.txt",
        "parsed.json",
        "validation.json",
        "metadata.json",
    ):
        assert (case_dir / filename).exists(), f"missing {filename}"


def test_manifest_records_actual_conditions(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    # The manifest reflects the ACTUAL verified client config, not a hardcoded
    # copy of FROZEN_CONDITIONS.
    ac = manifest.actual_conditions
    assert ac["model"] == "tencent/hy3"
    assert ac["api_gateway"] == "openrouter"
    assert ac["base_url"] == "https://openrouter.ai/api/v1"
    assert ac["temperature"] == 0
    assert ac["structured_output"] is False
    assert ac["retry"] is False
    assert ac["self_repair"] is False


# ---------------------------------------------------------------------------
# finish_reason capture.
# ---------------------------------------------------------------------------


def test_finish_reason_captured_on_success(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["finish_reason"] == "stop"
    assert metadata["reported_model"] == "tencent/hy3-reported"
    assert metadata["requested_model"] == "tencent/hy3"
    assert metadata["temperature"] == 0.0
    assert metadata["attempt_index"] == 1
    assert metadata["outcome"] == "success"
    assert metadata["exception_class"] is None


# ---------------------------------------------------------------------------
# One case fails (API error), batch continues.
# ---------------------------------------------------------------------------


def test_one_api_failure_continues_batch(tmp_path: Path) -> None:
    def content_fn(idx):
        if idx == 0:
            return Hy3APIError("Hy3 API returned HTTP 503", status_code=503)
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    assert manifest.case_count == 12
    assert manifest.pass_count == 11
    assert manifest.fail_count == 1
    assert manifest.cases[0]["outcome"] == "Hy3APIError"
    assert manifest.cases[0]["exception_class"] == "Hy3APIError"
    assert manifest.cases[1]["outcome"] == "success"


def test_finish_reason_none_on_api_failure(tmp_path: Path) -> None:
    def content_fn(idx):
        if idx == 0:
            return Hy3APIError("Hy3 API returned HTTP 503", status_code=503)
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["finish_reason"] is None
    assert metadata["outcome"] == "Hy3APIError"


def test_api_failure_http_response_artifact_saved(tmp_path: Path) -> None:
    def content_fn(idx):
        if idx == 0:
            return Hy3APIError(
                "HTTP 500",
                status_code=500,
                response_text='{"error":"server"}',
            )
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    assert (case_dir / "http_response.txt").exists()
    assert "server" in (case_dir / "http_response.txt").read_text()


# ---------------------------------------------------------------------------
# One case produces structurally invalid output, batch continues.
# ---------------------------------------------------------------------------


def test_one_structural_failure_continues_batch(tmp_path: Path) -> None:
    invalid_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "x"}]
        },
        "delivery_plan": {},
        "teacher_authority": 0.8,  # unknown field -> structural error
    }

    def content_fn(idx):
        if idx == 3:
            return json.dumps(invalid_plan)
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    assert manifest.pass_count == 11
    assert manifest.fail_count == 1
    assert manifest.cases[3]["outcome"] == "SpeechPlanStructuralError"
    # raw_response + parsed preserved on structural failure.
    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[3]["case_id"]
    assert (case_dir / "raw_response.txt").exists()
    assert (case_dir / "parsed.json").exists()


def test_structural_failure_validation_json_stages(tmp_path: Path) -> None:
    invalid_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [{"segment_id": "seg_01", "text": "x"}]
        },
        "delivery_plan": {},
        "teacher_authority": 0.8,
    }

    def content_fn(idx):
        if idx == 0:
            return json.dumps(invalid_plan)
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    validation = json.loads((case_dir / "validation.json").read_text(encoding="utf-8"))
    assert validation["input_json_schema"] == "passed"
    assert validation["input_pydantic"] == "passed"
    assert validation["response_parsing"] == "passed"
    assert isinstance(validation["speech_plan_json_schema"], dict)
    assert validation["speech_plan_json_schema"]["status"] == "failed"
    assert validation["speech_plan_pydantic"] == "not_reached"
    assert validation["outcome"] == "SpeechPlanStructuralError"


# ---------------------------------------------------------------------------
# No API key / auth in artifacts.
# ---------------------------------------------------------------------------


def test_metadata_contains_no_api_key(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    for entry in manifest.cases:
        case_dir = tmp_path / manifest.run_id / "cases" / entry["case_id"]
        metadata_text = (case_dir / "metadata.json").read_text(encoding="utf-8")
        metadata = json.loads(metadata_text)
        assert "api_key" not in metadata
        assert "authorization" not in metadata
        assert "auth" not in str(metadata).lower()
        # No file in the case dir contains a key-like sentinel.
        for f in case_dir.iterdir():
            content = f.read_text(encoding="utf-8")
            assert "sk-" not in content
            assert "Bearer " not in content


# ---------------------------------------------------------------------------
# Cases run in file order.
# ---------------------------------------------------------------------------


def test_cases_run_in_file_order(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    # The manifest case order must match the dataset file order.
    import json as _json
    with BLOCK_A_DATASET_PATH.open(encoding="utf-8") as handle:
        expected_ids = [
            _json.loads(line)["case_id"]
            for line in handle
            if line.strip()
        ]
    actual_ids = [c["case_id"] for c in manifest.cases]
    assert actual_ids == expected_ids


# ---------------------------------------------------------------------------
# Prompt v0.1 is used.
# ---------------------------------------------------------------------------


def test_prompt_version_is_v0_1(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    prompt = json.loads((case_dir / "prompt.json").read_text(encoding="utf-8"))
    assert prompt["prompt_version"] == "v0.1"
    assert prompt["system"] and prompt["user"]


# ---------------------------------------------------------------------------
# Preflight safeguards.
# ---------------------------------------------------------------------------


def test_structural_preflight_failure_aborts_before_any_model_call(
    tmp_path: Path,
) -> None:
    """A structurally invalid dataset must abort before any complete() call."""
    # Write a broken dataset: one case with a missing required top-level field.
    broken_path = tmp_path / "broken.jsonl"
    with broken_path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "case_id": "BAD-01",
                    "block": "controlled_contrast",
                    "difficulty": "standard",
                    "tags": {"delivery_need": "low", "contrast_group": "anchor_01"},
                    # "input" missing -> wrapper_structure failure
                    "design_expectations": {"must": ["x"], "must_not": ["y"]},
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    fake = FakePilotClient(_all_success_content)
    with pytest.raises(PreflightError, match="structural preflight failed"):
        run_pilot_block_a(fake, broken_path, tmp_path)
    # No model calls were made.
    assert fake.call_count == 0
    # No run directory was created.
    assert not any(tmp_path.iterdir()) or all(
        not (p / "manifest.json").exists() for p in tmp_path.iterdir() if p.is_dir()
    )


def test_wrong_model_aborts_before_any_model_call(tmp_path: Path) -> None:
    """A client with the wrong model must abort before any complete() call."""
    fake = FakePilotClient(_all_success_content, model="wrong/model")
    with pytest.raises(PreflightError, match="model"):
        run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)
    assert fake.call_count == 0


def test_wrong_base_url_aborts_before_any_model_call(tmp_path: Path) -> None:
    """A client with the wrong base URL must abort before any complete() call."""
    fake = FakePilotClient(
        _all_success_content,
        endpoint="https://wrong.example.com/v1/chat/completions",
    )
    with pytest.raises(PreflightError, match="base URL"):
        run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)
    assert fake.call_count == 0


def test_structured_output_enabled_aborts_before_any_model_call(
    tmp_path: Path,
) -> None:
    """A client with structured output enabled must abort."""
    fake = FakePilotClient(
        _all_success_content,
        response_format={"type": "json_object"},
    )
    with pytest.raises(PreflightError, match="structured_output"):
        run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)
    assert fake.call_count == 0


def test_valid_frozen_configuration_proceeds_normally(tmp_path: Path) -> None:
    """A valid client + valid dataset proceeds normally (preflight passes)."""
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)
    assert manifest.case_count == 12
    assert manifest.pass_count == 12
    assert fake.call_count == 12
