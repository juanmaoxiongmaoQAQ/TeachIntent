"""Focused mocked tests for the generalized Block B pilot baseline runner.

No real API calls. The frozen Block B dataset is loaded but only
case["input"] is passed to the Generator service; experiment metadata, tags,
and design_expectations must never reach the model prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import Hy3APIError
from teachintent.pilot_runner import (
    BLOCK_A_DATASET_PATH,
    BLOCK_B_DATASET_PATH,
    PILOT_BLOCKS,
    PreflightError,
    run_pilot_block,
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

    Records the system/user messages per call so tests can verify exactly
    what was sent to the model. Exposes endpoint/_response_format so the
    config preflight passes by default.
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
        self.systems: list[str] = []
        self.users: list[str] = []

    @property
    def model(self):
        return self._model

    @property
    def endpoint(self):
        return self._endpoint

    def complete(self, system, user, *, temperature=0.0):
        idx = self.call_count
        self.call_count += 1
        self.systems.append(system)
        self.users.append(user)
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


def _load_block_b_cases() -> list[dict]:
    cases: list[dict] = []
    with BLOCK_B_DATASET_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


# ---------------------------------------------------------------------------
# Block B runs 12/12 successfully.
# ---------------------------------------------------------------------------


def test_block_b_runs_12_12_successfully(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    assert manifest.case_count == 12
    assert manifest.pass_count == 12
    assert manifest.fail_count == 0
    assert manifest.block == "cross_domain_generalization"
    assert all(c["outcome"] == "success" for c in manifest.cases)
    run_dir = tmp_path / manifest.run_id
    assert (run_dir / "manifest.json").exists()
    assert len(list((run_dir / "cases").iterdir())) == 12


def test_block_b_metadata_includes_block(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["block"] == "cross_domain_generalization"
    assert metadata["case_id"] == "PILOT-B-ELI-01"
    assert metadata["attempt_index"] == 1
    assert metadata["prompt_version"] == "v0.1"
    assert metadata["api_gateway"] == "openrouter"
    assert metadata["requested_model"] == "tencent/hy3"
    assert metadata["reported_model"] == "tencent/hy3-reported"
    assert metadata["temperature"] == 0.0
    assert metadata["outcome"] == "success"
    assert metadata["finish_reason"] == "stop"


# ---------------------------------------------------------------------------
# Block B runs in dataset file order.
# ---------------------------------------------------------------------------


def test_block_b_runs_in_dataset_file_order(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    with BLOCK_B_DATASET_PATH.open(encoding="utf-8") as handle:
        expected_ids = [
            json.loads(line)["case_id"] for line in handle if line.strip()
        ]
    actual_ids = [c["case_id"] for c in manifest.cases]
    assert actual_ids == expected_ids
    assert actual_ids[0] == "PILOT-B-ELI-01"
    assert actual_ids[-1] == "PILOT-B-EXT-02"


# ---------------------------------------------------------------------------
# Only runtime input is passed to generation.
# ---------------------------------------------------------------------------


def test_only_runtime_input_passed_to_generation(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    assert fake.call_count == 12
    cases = _load_block_b_cases()
    for index, user in enumerate(fake.users):
        input_doc = cases[index]["input"]
        # The exact runtime input is serialized in the user message.
        case_json = json.dumps(input_doc, ensure_ascii=False, indent=2)
        assert case_json in user, f"case {index} input not fully serialized"
        # Experiment metadata must NEVER appear in the prompt.
        assert "design_expectations" not in user
        assert "delivery_need" not in user
        assert "cross_domain_generalization" not in user
        assert "PILOT-B-" not in user
        assert cases[index]["case_id"] not in user


def test_prompt_is_v0_1_for_block_b(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    case_dir = tmp_path / run_dir_name(tmp_path) / "cases" / "PILOT-B-ELI-01"
    prompt = json.loads((case_dir / "prompt.json").read_text(encoding="utf-8"))
    assert prompt["prompt_version"] == "v0.1"


def run_dir_name(output_dir: Path) -> str:
    dirs = [p.name for p in output_dir.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


# ---------------------------------------------------------------------------
# Preflight: structural failure -> zero model calls.
# ---------------------------------------------------------------------------


def test_structural_preflight_failure_zero_model_calls(tmp_path: Path) -> None:
    """A structurally invalid Block B dataset aborts before any model call."""
    cases = _load_block_b_cases()
    # Break the wrapper: add contrast_group to tags (Block A field in Block B).
    cases[0]["tags"]["contrast_group"] = "anchor_01"
    broken_path = tmp_path / "broken_block_b.jsonl"
    with broken_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    fake = FakePilotClient(_all_success_content)
    with pytest.raises(PreflightError, match="structural preflight failed"):
        run_pilot_block(fake, broken_path, tmp_path / "out")
    assert fake.call_count == 0


# ---------------------------------------------------------------------------
# Preflight: wrong configuration -> zero model calls.
# ---------------------------------------------------------------------------


def test_wrong_model_zero_model_calls(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content, model="wrong/model")
    with pytest.raises(PreflightError, match="model"):
        run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)
    assert fake.call_count == 0


def test_wrong_base_url_zero_model_calls(tmp_path: Path) -> None:
    fake = FakePilotClient(
        _all_success_content,
        endpoint="https://wrong.example.com/v1/chat/completions",
    )
    with pytest.raises(PreflightError, match="base URL"):
        run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)
    assert fake.call_count == 0


def test_structured_output_enabled_zero_model_calls(tmp_path: Path) -> None:
    fake = FakePilotClient(
        _all_success_content, response_format={"type": "json_object"}
    )
    with pytest.raises(PreflightError, match="structured_output"):
        run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)
    assert fake.call_count == 0


# ---------------------------------------------------------------------------
# One API failure preserved; remaining cases continue.
# ---------------------------------------------------------------------------


def test_one_api_failure_preserved_and_continues(tmp_path: Path) -> None:
    def content_fn(idx):
        if idx == 0:
            return Hy3APIError(
                "HTTP 503", status_code=503, response_text='{"error":"upstream"}'
            )
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    assert manifest.pass_count == 11
    assert manifest.fail_count == 1
    assert manifest.cases[0]["outcome"] == "Hy3APIError"
    assert manifest.cases[1]["outcome"] == "success"
    assert manifest.cases[11]["outcome"] == "success"  # batch ran to the end
    # Failure artifacts preserved.
    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[0]["case_id"]
    assert (case_dir / "http_response.txt").exists()
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["exception_class"] == "Hy3APIError"
    assert metadata["finish_reason"] is None


# ---------------------------------------------------------------------------
# One parsing/validation failure preserved; remaining cases continue.
# ---------------------------------------------------------------------------


def test_one_validation_failure_preserved_and_continues(tmp_path: Path) -> None:
    invalid_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "x"}]},
        "delivery_plan": {},
        "teacher_authority": 0.8,  # unknown field -> structural error
    }

    def content_fn(idx):
        if idx == 5:
            return json.dumps(invalid_plan)
        return json.dumps(CANONICAL_PLAN, ensure_ascii=False)

    fake = FakePilotClient(content_fn)
    manifest = run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    assert manifest.pass_count == 11
    assert manifest.fail_count == 1
    assert manifest.cases[5]["outcome"] == "SpeechPlanStructuralError"
    assert manifest.cases[6]["outcome"] == "success"
    # raw_response + parsed preserved for the failed case.
    case_dir = tmp_path / manifest.run_id / "cases" / manifest.cases[5]["case_id"]
    assert (case_dir / "raw_response.txt").exists()
    assert (case_dir / "parsed.json").exists()
    validation = json.loads((case_dir / "validation.json").read_text(encoding="utf-8"))
    assert validation["speech_plan_json_schema"]["status"] == "failed"
    assert validation["outcome"] == "SpeechPlanStructuralError"


# ---------------------------------------------------------------------------
# Artifacts go under the Block B results path (registry).
# ---------------------------------------------------------------------------


def test_block_b_registry_paths() -> None:
    entry = PILOT_BLOCKS["block_b"]
    assert entry["dataset_path"] == BLOCK_B_DATASET_PATH
    assert entry["results_dir"].name == "block_b"
    assert entry["results_dir"].parent.name == "pilot"
    assert entry["results_dir"].parent.parent.name == "results"
    # Block A registry is intact.
    assert PILOT_BLOCKS["block_a"]["dataset_path"] == BLOCK_A_DATASET_PATH
    assert PILOT_BLOCKS["block_a"]["results_dir"].name == "block_a"


# ---------------------------------------------------------------------------
# Block A existing behavior remains unchanged.
# ---------------------------------------------------------------------------


def test_block_a_alias_still_works(tmp_path: Path) -> None:
    """run_pilot_block_a (backward-compat alias) behaves identically."""
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block_a(fake, BLOCK_A_DATASET_PATH, tmp_path)
    assert manifest.case_count == 12
    assert manifest.pass_count == 12
    assert manifest.block == "controlled_contrast"


# ---------------------------------------------------------------------------
# No credentials appear in artifacts.
# ---------------------------------------------------------------------------


def test_no_credentials_in_block_b_artifacts(tmp_path: Path) -> None:
    fake = FakePilotClient(_all_success_content)
    manifest = run_pilot_block(fake, BLOCK_B_DATASET_PATH, tmp_path)

    run_dir = tmp_path / manifest.run_id
    for artifact in run_dir.rglob("*"):
        if artifact.is_file():
            content = artifact.read_text(encoding="utf-8")
            assert "sk-" not in content, f"key-like sentinel in {artifact}"
            assert "Bearer " not in content, f"auth header in {artifact}"
    for entry in manifest.cases:
        metadata = json.loads(
            (
                run_dir / "cases" / entry["case_id"] / "metadata.json"
            ).read_text(encoding="utf-8")
        )
        assert "api_key" not in metadata
        assert "authorization" not in metadata
