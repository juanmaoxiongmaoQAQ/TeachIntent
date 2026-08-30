"""Offline CLI tests for scripts/run_prompt_v0_2_rc1_development.py.

No real Hy3 API. Covers the two explicit modes and all fail-fast guards:

* ``--dry-run`` makes no API call and prints the plan;
* ``--execute`` with no API key fails fast (exit 2), before any API call / result dir;
* no flag (and both flags) fails fast with usage (exit 2);
* ``--execute`` with an injected fake client performs exactly 30 first-call
  generations, all with the explicit ``prompt_version="v0.2-rc.1"`` (no retry).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.generator import Hy3Completion
from teachintent.generator.errors import Hy3APIError
from teachintent.prompt_development import development_runner as dr
from teachintent.prompt_development.development_runner import (
    API_GATEWAY,
    CANDIDATE_PROMPT_VERSION,
)

# Import the CLI entry point (runs as __main__ only when executed directly).
import importlib.util
import os

_CLI_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_prompt_v0_2_rc1_development.py"
)
_spec = importlib.util.spec_from_file_location("dev_runner_cli", _CLI_PATH)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


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
# --dry-run
# ---------------------------------------------------------------------------
def test_cli_dry_run_makes_no_api_call_and_prints_plan(capsys, monkeypatch) -> None:
    # Redirect any accidental result dir to tmp so the assertion is airtight.
    sentinel = FakeHy3Client("{}")
    result = cli.main(["--dry-run"], client=sentinel)
    assert result == 0
    assert sentinel.calls == []  # no Hy3 contact

    out = capsys.readouterr().out
    assert "Development set = existing 30 Pilot cases" in out
    assert "A = 12" in out and "B = 12" in out and "C = 6" in out
    assert "total = 30" in out
    assert "candidate prompt = v0.2-rc.1" in out
    assert "planned Generator calls = 30" in out
    assert "No API call was made." in out


# ---------------------------------------------------------------------------
# --execute with no API key: fail-fast, before any API call / result dir.
# ---------------------------------------------------------------------------
def test_cli_execute_missing_key_fails_fast(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HY3_API_KEY", raising=False)
    # Neutralize .env loading so the absent key is not re-injected.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    # Redirect result root so we can prove nothing was created there.
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)

    sentinel = FakeHy3Client("{}")
    result = cli.main(["--execute"], client=sentinel)
    assert result == 2
    # The key check aborts before the client is ever used / any dir is made.
    assert sentinel.calls == []
    assert list(tmp_path.glob("*")) == []  # no result directory created


# ---------------------------------------------------------------------------
# No flag -> fail-fast with usage (exit 2).
# ---------------------------------------------------------------------------
def test_cli_no_mode_fails_fast_with_usage(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "usage" in err.lower()
    assert "--dry-run" in err


# ---------------------------------------------------------------------------
# Both flags -> fail-fast (mutually exclusive), exit 2.
# ---------------------------------------------------------------------------
def test_cli_both_modes_fails_fast(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--dry-run", "--execute"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "usage" in err.lower()


# ---------------------------------------------------------------------------
# --execute with fake client: exactly 30 first-call generations.
# ---------------------------------------------------------------------------
def test_cli_execute_runs_exactly_30_calls(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)

    fake = FakeHy3Client(json.dumps(VALID_PLAN, ensure_ascii=False))
    result = cli.main(["--execute"], client=fake)
    assert result == 0
    # Exactly one first-call attempt per case — never more.
    assert len(fake.calls) == 30

    run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    case_dirs = list((run_dirs[0] / "cases").iterdir())
    assert len(case_dirs) == 30


# ---------------------------------------------------------------------------
# --execute with fake client: every call uses explicit v0.2-rc.1.
# ---------------------------------------------------------------------------
def test_cli_execute_uses_explicit_v0_2_rc1(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)

    captured: list[str] = []
    real_fn = dr.generate_speech_plan

    def spy(input_doc, client, *, prompt_version=CANDIDATE_PROMPT_VERSION):
        captured.append(prompt_version)
        return real_fn(input_doc, client, prompt_version=prompt_version)

    monkeypatch.setattr(dr, "generate_speech_plan", spy)
    fake = FakeHy3Client(json.dumps(VALID_PLAN, ensure_ascii=False))
    cli.main(["--execute"], client=fake)

    # All 30 calls passed the explicit candidate — never the service default.
    assert captured == [CANDIDATE_PROMPT_VERSION] * 30

    # And the written artifacts record it.
    run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
    manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["prompt_version"] == CANDIDATE_PROMPT_VERSION
    assert manifest["generator_version"] == "v0.1"


# ---------------------------------------------------------------------------
# --execute failure path: no automatic retry.
# ---------------------------------------------------------------------------
def test_cli_execute_failure_does_not_retry(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)

    fake = FakeHy3Client(
        "{}", raise_exc=Hy3APIError("Hy3 API returned HTTP 503", status_code=503)
    )
    result = cli.main(["--execute"], client=fake)
    # The run completes (records failures); it does not crash.
    assert result == 0
    assert len(fake.calls) == 30  # one attempt per case, no retry
    run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
    manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["fail_count"] == 30
    assert manifest["structural_report"]["first_call_validity"] == 0


# ---------------------------------------------------------------------------
# --execute with ONLY HY3_API_KEY (no OPENROUTER_API_KEY) -> fail-fast, no fallback.
# ---------------------------------------------------------------------------
def test_cli_execute_only_hy3_key_fails_fast(tmp_path, monkeypatch) -> None:
    # OPENROUTER_API_KEY absent, but HY3_API_KEY present — must NOT be accepted.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("HY3_API_KEY", "some-hy3-key")
    # Neutralize .env loading so the absent key is not re-injected.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)

    sentinel = FakeHy3Client("{}")
    result = cli.main(["--execute"], client=sentinel)
    assert result == 2  # no fallback to HY3_API_KEY
    assert sentinel.calls == []
    assert list(tmp_path.glob("*")) == []  # nothing written


# ---------------------------------------------------------------------------
# --execute ignores wrong HY3_* env and fixes base_url / model explicitly.
# ---------------------------------------------------------------------------
class _RecorderClient:
    """Records the exact constructor args the CLI passes to the real client."""

    instances: list = []

    def __init__(
        self,
        api_key,
        base_url,
        model,
        timeout=120.0,
        response_format=None,
        transport=None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.calls: list = []
        _RecorderClient.instances.append(self)

    def complete(self, system: str, user: str, *, temperature: float = 0.0):
        self.calls.append((system, user, temperature))
        return Hy3Completion(
            content=json.dumps(VALID_PLAN, ensure_ascii=False),
            finish_reason="stop",
            reported_model=self.model,
        )


def test_cli_execute_fixes_base_url_model_regardless_of_hy3_env(
    tmp_path, monkeypatch
) -> None:
    # Polluting ambient HY3_* variables that must NOT leak into the real config.
    monkeypatch.setenv("HY3_BASE_URL", "https://evil.example.com/v1")
    monkeypatch.setenv("HY3_MODEL", "gpt-4o")
    monkeypatch.setenv("HY3_API_KEY", "should-be-ignored")
    monkeypatch.setenv("OPENROUTER_API_KEY", "real-openrouter-key")
    monkeypatch.setattr(dr, "DEVELOPMENT_RESULTS_ROOT", tmp_path)
    monkeypatch.setattr(cli, "Hy3Client", _RecorderClient)
    _RecorderClient.instances = []

    result = cli.main(["--execute"])
    assert result == 0

    # Exactly one client built, with the STRICTLY FIXED base_url / model.
    assert len(_RecorderClient.instances) == 1
    built = _RecorderClient.instances[0]
    assert built.base_url == "https://openrouter.ai/api/v1"
    assert built.model == "tencent/hy3"
    assert built.api_key == "real-openrouter-key"
    # The 30 generations ran through the recorder with the fixed model.
    assert len(built.calls) == 30

    # The manifest records the fixed condition, not the polluting env values.
    run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["actual_conditions"]["api_gateway"] == API_GATEWAY  # "openrouter"
    assert manifest["actual_conditions"]["model"] == "tencent/hy3"
    assert manifest["prompt_version"] == CANDIDATE_PROMPT_VERSION
    assert manifest["actual_conditions"]["temperature"] == 0
    assert manifest["actual_conditions"]["retry"] is False
    assert manifest["actual_conditions"]["self_repair"] is False

    # Per-case metadata likewise records the fixed condition.
    sample = next(p for p in (run_dir / "cases").iterdir())
    meta = json.loads((sample / "metadata.json").read_text(encoding="utf-8"))
    assert meta["requested_model"] == "tencent/hy3"
    assert meta["api_gateway"] == "openrouter"
    assert meta["prompt_version"] == CANDIDATE_PROMPT_VERSION
    assert meta["temperature"] == 0
