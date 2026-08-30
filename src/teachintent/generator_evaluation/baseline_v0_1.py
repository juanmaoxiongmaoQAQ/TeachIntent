"""Generator v0.1 Baseline Evaluation — canonical-run loading, execution, aggregation.

Implements ``docs/generator_v0.1_evaluation_protocol_v0.1.md`` (Status: **Frozen**).

Scope and boundaries:

* the 30 canonical Generator v0.1 Pilot outputs are **reused as-is** — nothing
  is regenerated, replaced, cherry-picked, dropped, or repaired;
* the frozen Evaluator v0.1 is **called**, never re-implemented, copied, or
  modified. All Evaluator logic (Layer-0 gate, Layer-1 judge, evidence
  validation, deterministic ``overall_score``) stays in
  :mod:`teachintent.evaluator`;
* the Judge condition constants are **imported** from the frozen diagnostic
  protocol module so this baseline can never silently declare a different
  condition than the validated confirmatory run;
* an operational failure is **never** converted into a semantic score;
* this module defines **no** Generator PASS/FAIL threshold. It produces a
  descriptive baseline only.

All metric functions are pure and deterministic. None of them call the Judge.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from pydantic import ValidationError

from ..evaluator import (
    CRITICAL_FLAGS,
    DIMENSION_IDS,
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    EvaluationRunContext,
    JudgeClient,
    JudgeCompleter,
    JudgeConfig,
    compute_judge_prompt_sha256,
    evaluate_speech_plan,
)
# The frozen Judge condition is a single source of truth. Importing it (rather
# than re-declaring it here) guarantees the baseline cannot drift from the
# condition under which the Evaluator's validity was established.
from ..evaluator_diagnostic.protocol_v0_2 import (
    FROZEN_JUDGE_BASE_URL,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    FROZEN_RETRY_ENABLED,
    FROZEN_SELF_REPAIR_ENABLED,
    FROZEN_STRUCTURED_OUTPUT_ENABLED,
    FROZEN_TEMPERATURE,
)
from ..generator.errors import ResponseParsingError
from ..generator.parser import parse_speech_plan_json
from ..models import SpeechPlan, TeachIntentInput
from ..validators import iter_input_errors, iter_speech_plan_errors

__all__ = [
    # Protocol / shape constants
    "PROTOCOL_VERSION",
    "PROTOCOL_STATUS",
    "PROTOCOL_DOC_PATH",
    "GENERATOR_VERSION",
    "GENERATOR_VERSION_PROVENANCE",
    "PROMPT_VERSION",
    "PROMPT_VERSION_PROVENANCE",
    "SOURCE_POPULATION_SHA256",
    "POPULATION_HASH_ARTIFACTS",
    "REPEATS",
    "MIN_SUCCESSFUL_REPEATS",
    "CASE_COUNT",
    "EXPECTED_CALLS",
    "INTENTS",
    "WEAKNESS_THRESHOLD",
    "SEVERE_WEAKNESS_THRESHOLD",
    "BLOCK_NAMES",
    # Frozen judge condition (re-exported)
    "FROZEN_JUDGE_PROVIDER",
    "FROZEN_JUDGE_MODEL_REQUESTED",
    "FROZEN_JUDGE_BASE_URL",
    "FROZEN_TEMPERATURE",
    "FROZEN_STRUCTURED_OUTPUT_ENABLED",
    "FROZEN_RETRY_ENABLED",
    "FROZEN_SELF_REPAIR_ENABLED",
    # Data types
    "CanonicalRunSpec",
    "CanonicalCase",
    "PopulationIntegrity",
    "BaselineRecord",
    "BaselineRun",
    # Loading / integrity
    "CANONICAL_RUNS",
    "CanonicalRunError",
    "load_canonical_cases",
    "verify_population",
    # Population fingerprint
    "case_population_record",
    "build_population_records",
    "compute_population_sha256",
    "verify_population_fingerprint",
    # Planning / execution
    "plan_baseline_calls",
    "build_frozen_judge_config",
    "build_baseline_judge",
    "prepare_baseline_run",
    "evaluate_one",
    "reduce_result",
    "execute_baseline_run",
    # Metrics
    "successful_records",
    "successful_repeat_count",
    "case_eligible",
    "case_dimension_means",
    "case_overall_mean",
    "case_critical_flags",
    "case_failure_types",
    "failure_taxonomy_counts",
    "critical_flag_counts",
    "case_diagnostics",
    "global_metrics",
    "intent_metrics",
    "block_metrics",
    "aggregate",
    # Artifacts
    "build_manifest",
    "build_summary",
    "write_artifacts",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PILOT_ROOT = _REPO_ROOT / "results" / "pilot"

# ---------------------------------------------------------------------------
# Protocol constants.
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "v0.1"
PROTOCOL_STATUS = "Frozen"
PROTOCOL_DOC_PATH = (
    _REPO_ROOT / "docs" / "generator_v0.1_evaluation_protocol_v0.1.md"
)

# Generator v0.1 is frozen. The Pilot artifacts record ``prompt_version``
# directly; ``generator_version`` is determined from the frozen Generator stack
# (src/teachintent/generator/, the single-pass v0.1 pipeline) that produced the
# three canonical runs. The artifacts themselves contain no
# ``generator_version`` field, so the provenance is stated explicitly rather
# than being presented as artifact-confirmed.
GENERATOR_VERSION = "v0.1"
GENERATOR_VERSION_PROVENANCE = (
    "inferred_from_frozen_generator_stack_and_prompt_v0.1; source Pilot "
    "artifacts do not directly record generator_version"
)
PROMPT_VERSION = "v0.1"
PROMPT_VERSION_PROVENANCE = (
    "artifact_directly_recorded; cases/<case_id>/prompt.json and metadata.json "
    "both record prompt_version = v0.1 and are asserted per case"
)

REPEATS = 3
MIN_SUCCESSFUL_REPEATS = 2
CASE_COUNT = 30
EXPECTED_CALLS = 90

INTENTS: tuple[str, ...] = (
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
)

BLOCK_NAMES: dict[str, str] = {
    "A": "controlled_contrast",
    "B": "cross_domain_generalization",
    "C": "hard_adversarial",
}

# Diagnostic-only thresholds (NOT acceptance criteria).
WEAKNESS_THRESHOLD = 3.0
SEVERE_WEAKNESS_THRESHOLD = 2.0

# Short labels D1..D6 in frozen dimension order.
DIMENSION_LABELS: tuple[str, ...] = tuple(f"D{i + 1}" for i in range(len(DIMENSION_IDS)))
_LABEL_TO_DIM: dict[str, str] = dict(zip(DIMENSION_LABELS, DIMENSION_IDS))

_REQUIRED_ARTIFACTS = (
    "input.json",
    "metadata.json",
    "parsed.json",
    "prompt.json",
    "raw_response.txt",
    "validation.json",
)

# ---------------------------------------------------------------------------
# Population fingerprint.
#
# Pinning the source run IDs alone does not pin the *content*: an edit to any
# canonical artifact would leave the IDs unchanged. The population fingerprint
# hashes every raw source artifact of all 30 cases into a single digest, so any
# modification of the canonical population changes the fingerprint and the run
# fails fast.
# ---------------------------------------------------------------------------
POPULATION_HASH_ARTIFACTS: dict[str, str] = {
    "input": "input.json",
    "metadata": "metadata.json",
    "parsed": "parsed.json",
    "prompt": "prompt.json",
    "raw_response": "raw_response.txt",
    "validation": "validation.json",
}

#: SHA256 of the canonical serialization of the 30 population records below.
#: Recomputed offline from the untouched canonical Pilot runs; any change to any
#: source artifact invalidates it (Protocol Section 3.4).
SOURCE_POPULATION_SHA256 = (
    "a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b"
)


# ---------------------------------------------------------------------------
# Canonical run registry.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CanonicalRunSpec:
    """One frozen canonical Generator v0.1 Pilot run (reused, never rerun)."""

    block: str
    block_name: str
    run_id: str
    path: Path
    expected_cases: int


CANONICAL_RUNS: tuple[CanonicalRunSpec, ...] = (
    CanonicalRunSpec(
        block="A",
        block_name="controlled_contrast",
        run_id="20260827-002543",
        path=_PILOT_ROOT / "block_a" / "20260827-002543",
        expected_cases=12,
    ),
    CanonicalRunSpec(
        block="B",
        block_name="cross_domain_generalization",
        run_id="20260827-051547",
        path=_PILOT_ROOT / "block_b" / "20260827-051547",
        expected_cases=12,
    ),
    CanonicalRunSpec(
        block="C",
        block_name="hard_adversarial",
        run_id="20260827-074602",
        path=_PILOT_ROOT / "block_c" / "20260827-074602",
        expected_cases=6,
    ),
)


class CanonicalRunError(RuntimeError):
    """Raised when the canonical Generator v0.1 population fails a pre-flight check."""


# ---------------------------------------------------------------------------
# Data types.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CanonicalCase:
    """One restored canonical Generator v0.1 output (reused as-is)."""

    case_id: str
    block: str
    block_name: str
    intent: str
    source_run_id: str
    source_path: str
    input_doc: dict
    raw_response: str
    prompt_version: str
    generator_version: str
    requested_model: str | None
    reported_model: str | None
    generation_outcome: str


@dataclass
class PopulationIntegrity:
    """Offline pre-flight report for the 30-case canonical population."""

    ok: bool
    messages: list[str] = field(default_factory=list)
    per_block_counts: dict[str, int] = field(default_factory=dict)
    total_cases: int = 0
    unique_case_ids: bool = False
    duplicate_case_ids: list[str] = field(default_factory=list)
    prompt_versions: list[str] = field(default_factory=list)
    generation_outcomes: list[str] = field(default_factory=list)
    restorable_cases: int = 0
    per_block_expected: dict[str, int] = field(default_factory=dict)
    # ---- Population fingerprint (Section 3.4) ----
    population_sha256: str = ""
    population_sha256_expected: str = SOURCE_POPULATION_SHA256
    population_sha256_match: bool = False
    population_records: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class BaselineRecord:
    """One (case, repeat) evaluation outcome.

    ``scores is None`` means the repeat did not succeed semantically (Layer-0
    gate failure or an Evaluator-owned failure). A failure is NEVER represented
    as a semantic zero — ``failure_type`` carries the reason instead.
    """

    case_id: str
    block: str
    intent: str
    repeat_index: int
    scores: dict[str, int] | None
    overall_score: float | None
    critical_flags: tuple[str, ...]
    failure_type: str | None


@dataclass
class BaselineRun:
    """State for one baseline evaluation run."""

    run_id: str
    started_at: str
    completed_at: str | None = None
    dry_run: bool = True
    protocol_version: str = PROTOCOL_VERSION
    protocol_status: str = PROTOCOL_STATUS
    protocol_document_sha256: str = ""
    source_runs: list[dict] = field(default_factory=list)
    integrity: PopulationIntegrity | None = None
    cases: list[CanonicalCase] = field(default_factory=list)
    repeats: int = REPEATS
    planned_calls: int = 0
    generator_version: str = GENERATOR_VERSION
    generator_version_provenance: str = GENERATOR_VERSION_PROVENANCE
    prompt_version: str = PROMPT_VERSION
    prompt_version_provenance: str = PROMPT_VERSION_PROVENANCE
    source_population_sha256: str = ""
    source_population_sha256_expected: str = SOURCE_POPULATION_SHA256
    source_population_sha256_match: bool = False
    judge_provider: str | None = None
    judge_model_requested: str | None = None
    judge_model_reported: tuple[str, ...] = ()
    records: tuple[BaselineRecord, ...] = ()
    raw_evaluations: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------
def _canonical_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _round(value: float | int | None) -> float | None:
    """Round to 4 decimal places (protocol Section 6.5)."""
    if value is None:
        return None
    return round(float(value), 4)


# ---------------------------------------------------------------------------
# Population fingerprint (deterministic; reads only, never writes).
# ---------------------------------------------------------------------------
def case_population_record(case: CanonicalCase) -> dict[str, str]:
    """Fingerprint record for one canonical case (Section 3.4).

    Hashes the six raw source artifacts exactly as stored on disk.
    """
    base = Path(case.source_path)
    record: dict[str, str] = {
        "block": case.block,
        "source_run_id": case.source_run_id,
        "case_id": case.case_id,
    }
    for key, filename in POPULATION_HASH_ARTIFACTS.items():
        record[f"{key}_sha256"] = _sha256_file(base / filename)
    return record


def build_population_records(
    cases: Sequence[CanonicalCase],
) -> list[dict[str, str]]:
    """Population records sorted by ``case_id`` — fully deterministic order."""
    return [case_population_record(c) for c in sorted(cases, key=lambda c: c.case_id)]


def compute_population_sha256(records: Sequence[dict]) -> str:
    """SHA256 (lowercase hex) of the canonical JSON serialization."""
    canonical = json.dumps(
        list(records),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_population_fingerprint(
    cases: Sequence[CanonicalCase],
    expected: str = SOURCE_POPULATION_SHA256,
) -> tuple[str, bool]:
    """Return ``(sha256, matches_expected)`` for the given population."""
    digest = compute_population_sha256(build_population_records(cases))
    return digest, digest == expected


# ---------------------------------------------------------------------------
# Loading + restorability verification (offline, no API).
# ---------------------------------------------------------------------------
def _verify_restorable(case: CanonicalCase) -> list[str]:
    """Verify one case can be fully restored through the frozen contracts.

    Reuses the canonical input validators and the Generator's own parser /
    Speech-Plan validators (the same Layer-0 contract the Evaluator uses).
    Returns a list of problem strings (empty == restorable).
    """
    problems: list[str] = []

    # Validated input.
    input_errors = iter_input_errors(case.input_doc)
    if input_errors:
        problems.append(
            "input JSON Schema: "
            + "; ".join(f"{e.json_path}: {e.message}" for e in input_errors)
        )
    try:
        TeachIntentInput.model_validate(case.input_doc)
    except ValidationError as exc:
        problems.append(f"input Pydantic: {exc}")

    # Raw Generator response -> generated Speech Plan.
    try:
        parsed = parse_speech_plan_json(case.raw_response)
        plan_errors = iter_speech_plan_errors(parsed)
        if plan_errors:
            problems.append(
                "speech plan JSON Schema: "
                + "; ".join(f"{e.json_path}: {e.message}" for e in plan_errors)
            )
        try:
            SpeechPlan.model_validate(parsed)
        except ValidationError as exc:
            problems.append(f"speech plan Pydantic: {exc}")
    except ResponseParsingError as exc:
        problems.append(f"response parsing: {exc}")

    return problems


def load_canonical_cases(
    runs: Sequence[CanonicalRunSpec] = CANONICAL_RUNS,
) -> tuple[list[CanonicalCase], PopulationIntegrity]:
    """Load and verify the 30 canonical Generator v0.1 Pilot outputs.

    Reads the three frozen run directories in a fixed order (A, B, C; within a
    block sorted by ``case_id``) so the population and the call plan are fully
    deterministic. Raises :class:`CanonicalRunError` on any pre-flight failure.

    Never regenerates, replaces, or repairs anything — it only reads.
    """
    cases: list[CanonicalCase] = []
    integrity = PopulationIntegrity(
        ok=True,
        per_block_expected={spec.block: spec.expected_cases for spec in runs},
    )
    problems: list[str] = []

    for spec in runs:
        run_dir = Path(spec.path)
        manifest_path = run_dir / "manifest.json"
        if not run_dir.is_dir():
            problems.append(f"run directory missing: {run_dir}")
            continue
        if not manifest_path.is_file():
            problems.append(f"manifest missing: {manifest_path}")
            continue

        manifest = _read_json(manifest_path)
        if manifest.get("run_id") != spec.run_id:
            problems.append(
                f"{run_dir}: manifest run_id={manifest.get('run_id')!r} != "
                f"expected {spec.run_id!r}"
            )

        cases_dir = run_dir / "cases"
        if not cases_dir.is_dir():
            problems.append(f"cases directory missing: {cases_dir}")
            continue

        case_dirs = sorted(
            (p for p in cases_dir.iterdir() if p.is_dir()), key=lambda p: p.name
        )
        integrity.per_block_counts[spec.block] = len(case_dirs)
        if len(case_dirs) != spec.expected_cases:
            problems.append(
                f"block {spec.block}: expected {spec.expected_cases} cases, "
                f"found {len(case_dirs)}"
            )

        for case_dir in case_dirs:
            missing = [
                name
                for name in _REQUIRED_ARTIFACTS
                if not (case_dir / name).is_file()
            ]
            if missing:
                problems.append(f"{case_dir}: missing artifact(s) {missing}")
                continue

            metadata = _read_json(case_dir / "metadata.json")
            validation = _read_json(case_dir / "validation.json")
            prompt = _read_json(case_dir / "prompt.json")
            input_doc = _read_json(case_dir / "input.json")
            raw_response = (case_dir / "raw_response.txt").read_text(encoding="utf-8")

            case_id = metadata.get("case_id") or case_dir.name
            if case_id != case_dir.name:
                problems.append(
                    f"{case_dir}: metadata case_id={case_id!r} != dir name"
                )

            # Generator version provenance: the artifacts record prompt_version
            # only; generator_version comes from the frozen Generator stack.
            prompt_version = prompt.get("prompt_version")
            if metadata.get("prompt_version") != prompt_version:
                problems.append(
                    f"{case_id}: prompt_version mismatch "
                    f"(metadata={metadata.get('prompt_version')!r}, "
                    f"prompt.json={prompt_version!r})"
                )
            if prompt_version != PROMPT_VERSION:
                problems.append(
                    f"{case_id}: prompt_version={prompt_version!r} != {PROMPT_VERSION!r}"
                )

            outcome = validation.get("outcome")
            if outcome != "success":
                problems.append(
                    f"{case_id}: canonical generation outcome={outcome!r} != 'success'"
                )

            intent = (input_doc.get("pedagogical_intent") or {}).get("primary")
            if intent not in INTENTS:
                problems.append(f"{case_id}: unknown intent {intent!r}")

            case = CanonicalCase(
                case_id=case_id,
                block=spec.block,
                block_name=spec.block_name,
                intent=intent if intent in INTENTS else "",
                source_run_id=spec.run_id,
                source_path=str(case_dir),
                input_doc=input_doc,
                raw_response=raw_response,
                prompt_version=prompt_version or "",
                generator_version=GENERATOR_VERSION,
                requested_model=metadata.get("requested_model"),
                reported_model=metadata.get("reported_model"),
                generation_outcome=outcome or "",
            )

            restore_problems = _verify_restorable(case)
            if restore_problems:
                problems.append(f"{case_id}: not restorable: {restore_problems}")
            else:
                integrity.restorable_cases += 1

            cases.append(case)

    # ---- Population-level checks ----
    ids = [c.case_id for c in cases]
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    integrity.total_cases = len(ids)
    integrity.duplicate_case_ids = duplicates
    integrity.unique_case_ids = not duplicates
    integrity.prompt_versions = sorted({c.prompt_version for c in cases})
    integrity.generation_outcomes = sorted({c.generation_outcome for c in cases})

    if duplicates:
        problems.append(f"duplicate case_id(s): {duplicates}")
    if len(cases) != CASE_COUNT:
        problems.append(f"expected {CASE_COUNT} cases total, found {len(cases)}")
    if integrity.prompt_versions not in ([], [PROMPT_VERSION]):
        problems.append(
            f"unexpected prompt_version set: {integrity.prompt_versions}"
        )
    if integrity.generation_outcomes not in ([], ["success"]):
        problems.append(
            f"unexpected generation outcome set: {integrity.generation_outcomes}"
        )

    # ---- Population fingerprint (Section 3.4) ----
    # Computed from the six raw artifacts of every case, so any edit to any
    # canonical source artifact changes it. Runs on the canonical population
    # must reproduce the frozen digest exactly.
    integrity.population_records = build_population_records(cases)
    integrity.population_sha256 = compute_population_sha256(
        integrity.population_records
    )
    integrity.population_sha256_match = (
        integrity.population_sha256 == integrity.population_sha256_expected
    )
    if not integrity.population_sha256_match:
        problems.append(
            "source population SHA256 mismatch: "
            f"computed={integrity.population_sha256}, "
            f"expected={integrity.population_sha256_expected} "
            "(a canonical Pilot artifact was modified or replaced)"
        )

    integrity.messages = problems
    integrity.ok = not problems
    if not integrity.ok:
        raise CanonicalRunError("; ".join(problems))

    return cases, integrity


def verify_population(
    cases: Sequence[CanonicalCase],
    runs: Sequence[CanonicalRunSpec] = CANONICAL_RUNS,
) -> PopulationIntegrity:
    """Re-verify an already-loaded population (pure, offline)."""
    ids = [c.case_id for c in cases]
    per_block: dict[str, int] = {}
    for c in cases:
        per_block[c.block] = per_block.get(c.block, 0) + 1
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    problems: list[str] = []
    if len(cases) != CASE_COUNT:
        problems.append(f"expected {CASE_COUNT} cases, got {len(cases)}")
    if duplicates:
        problems.append(f"duplicate case_id(s): {duplicates}")
    for spec in runs:
        found = per_block.get(spec.block, 0)
        if found != spec.expected_cases:
            problems.append(
                f"block {spec.block}: expected {spec.expected_cases}, got {found}"
            )
    return PopulationIntegrity(
        ok=not problems,
        messages=problems,
        per_block_counts=per_block,
        total_cases=len(cases),
        unique_case_ids=not duplicates,
        duplicate_case_ids=duplicates,
        prompt_versions=sorted({c.prompt_version for c in cases}),
        generation_outcomes=sorted({c.generation_outcome for c in cases}),
        restorable_cases=len(cases),
        per_block_expected={spec.block: spec.expected_cases for spec in runs},
    )


# ---------------------------------------------------------------------------
# Planning.
# ---------------------------------------------------------------------------
def plan_baseline_calls(
    cases: Sequence[CanonicalCase],
    repeats: int = REPEATS,
) -> list[dict]:
    """Return the call plan: 30 cases x ``repeats`` = 90 calls (repeat 1..3)."""
    if repeats < 1:
        raise ValueError(f"repeats must be >= 1, got {repeats}")
    calls: list[dict] = []
    for case in cases:
        for repeat_index in range(1, repeats + 1):
            calls.append(
                {
                    "case_id": case.case_id,
                    "block": case.block,
                    "intent": case.intent,
                    "repeat_index": repeat_index,
                }
            )
    return calls


# ---------------------------------------------------------------------------
# Frozen judge config / backend.
# ---------------------------------------------------------------------------
def build_frozen_judge_config(judge: JudgeCompleter) -> JudgeConfig:
    """Build the frozen JudgeConfig, binding the actual backend to the frozen
    condition. Raises ``ValueError`` on any mismatch."""
    if judge.provider != FROZEN_JUDGE_PROVIDER:
        raise ValueError(
            f"judge provider mismatch: backend={judge.provider!r}, "
            f"frozen={FROZEN_JUDGE_PROVIDER!r}"
        )
    if judge.model != FROZEN_JUDGE_MODEL_REQUESTED:
        raise ValueError(
            f"judge model mismatch: backend={judge.model!r}, "
            f"frozen={FROZEN_JUDGE_MODEL_REQUESTED!r}"
        )
    if judge.structured_output_enabled:
        raise ValueError(
            "structured_output_enabled must be False for the frozen baseline condition"
        )
    return JudgeConfig(
        judge_provider=judge.provider,
        judge_model_requested=judge.model,
        temperature=FROZEN_TEMPERATURE,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        judge_prompt_sha256=compute_judge_prompt_sha256(),
        structured_output_enabled=FROZEN_STRUCTURED_OUTPUT_ENABLED,
        retry_enabled=FROZEN_RETRY_ENABLED,
        self_repair_enabled=FROZEN_SELF_REPAIR_ENABLED,
    )


def build_baseline_judge(env: dict[str, str] | None = None) -> JudgeClient | None:
    """Build a JudgeClient from the frozen condition + ``OPENROUTER_API_KEY``.

    Provider/model/base-url are FROZEN (never read from env); only the API key
    comes from the environment. Returns ``None`` when no key is present (the
    caller treats that as dry-run). The key is never printed or stored.
    """
    env = env if env is not None else os.environ
    api_key = (env.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None
    return JudgeClient(
        api_key=api_key,
        base_url=FROZEN_JUDGE_BASE_URL,
        model=FROZEN_JUDGE_MODEL_REQUESTED,
        provider=FROZEN_JUDGE_PROVIDER,
    )


# ---------------------------------------------------------------------------
# Prepare (offline; no API).
# ---------------------------------------------------------------------------
def prepare_baseline_run(
    runs: Sequence[CanonicalRunSpec] = CANONICAL_RUNS,
    *,
    repeats: int = REPEATS,
) -> BaselineRun:
    """Load + verify the canonical population and plan the run. Never calls the Judge."""
    if repeats != REPEATS:
        raise ValueError(
            f"repeats must be exactly {REPEATS}: the baseline design is fixed at "
            f"{CASE_COUNT} cases x {REPEATS} repeats = {EXPECTED_CALLS} calls "
            f"(got {repeats})"
        )

    cases, integrity = load_canonical_cases(runs)
    calls = plan_baseline_calls(cases, repeats)

    source_runs = []
    for spec in runs:
        manifest = _read_json(Path(spec.path) / "manifest.json")
        source_runs.append(
            {
                "block": spec.block,
                "block_name": spec.block_name,
                "run_id": spec.run_id,
                "path": str(spec.path),
                "dataset_path": manifest.get("dataset_path"),
                "expected_cases": spec.expected_cases,
                "actual_cases": integrity.per_block_counts.get(spec.block, 0),
                "pass_count": manifest.get("pass_count"),
                "fail_count": manifest.get("fail_count"),
                "started_at": manifest.get("started_at"),
                "finished_at": manifest.get("finished_at"),
                "requested_model": (manifest.get("actual_conditions") or {}).get("model"),
                "temperature": (manifest.get("actual_conditions") or {}).get("temperature"),
            }
        )

    return BaselineRun(
        run_id=_utc_run_id(),
        started_at=_canonical_utc_now(),
        dry_run=True,
        protocol_version=PROTOCOL_VERSION,
        protocol_status=PROTOCOL_STATUS,
        protocol_document_sha256=(
            _sha256_file(PROTOCOL_DOC_PATH) if PROTOCOL_DOC_PATH.is_file() else ""
        ),
        source_runs=source_runs,
        integrity=integrity,
        cases=cases,
        repeats=repeats,
        planned_calls=len(calls),
        generator_version=GENERATOR_VERSION,
        generator_version_provenance=GENERATOR_VERSION_PROVENANCE,
        prompt_version=PROMPT_VERSION,
        prompt_version_provenance=PROMPT_VERSION_PROVENANCE,
        source_population_sha256=integrity.population_sha256,
        source_population_sha256_expected=integrity.population_sha256_expected,
        source_population_sha256_match=integrity.population_sha256_match,
    )


# ---------------------------------------------------------------------------
# Execution (real mode only; never called in dry-run).
# ---------------------------------------------------------------------------
def evaluate_one(
    case: CanonicalCase,
    repeat_index: int,
    judge: JudgeCompleter,
    judge_config: JudgeConfig,
):
    """Run one (case, repeat) through the frozen Evaluator.

    Only the restored input document and the restored raw Generator response
    reach the Evaluator; block/intent/ordering metadata never does.
    """
    eval_id = f"{case.case_id}__r{repeat_index}"
    ctx = EvaluationRunContext(
        input_case_id=eval_id,
        generator_version=case.generator_version,
        prompt_version=case.prompt_version,
    )
    return evaluate_speech_plan(
        case.input_doc, case.raw_response, ctx, judge_config, judge
    )


def reduce_result(
    case: CanonicalCase,
    repeat_index: int,
    result,
) -> BaselineRecord:
    """Reduce one EvaluatorResult to a BaselineRecord. Never converts a failure
    into a semantic zero."""
    artifact = result.artifact
    if artifact is not None and artifact.structural_valid:
        return BaselineRecord(
            case_id=case.case_id,
            block=case.block,
            intent=case.intent,
            repeat_index=repeat_index,
            scores={d: artifact.scores[d].score for d in DIMENSION_IDS},
            overall_score=artifact.overall_score,
            critical_flags=tuple(cf.flag for cf in artifact.critical_flags),
            failure_type=None,
        )
    if artifact is not None and not artifact.structural_valid:
        return BaselineRecord(
            case_id=case.case_id,
            block=case.block,
            intent=case.intent,
            repeat_index=repeat_index,
            scores=None,
            overall_score=None,
            critical_flags=(),
            failure_type=f"gate_{artifact.gate_failure.stage}",
        )
    failure_type = result.failure.failure_type if result.failure is not None else "unknown"
    return BaselineRecord(
        case_id=case.case_id,
        block=case.block,
        intent=case.intent,
        repeat_index=repeat_index,
        scores=None,
        overall_score=None,
        critical_flags=(),
        failure_type=failure_type,
    )


def execute_baseline_run(run: BaselineRun, judge: JudgeCompleter) -> None:
    """Execute the 90-call baseline run (real mode) and fill ``run``.

    One independent attempt per (case, repeat). No retry, no self-repair, no
    selective top-up. Every raw Evaluator artifact is captured verbatim.
    """
    judge_config = build_frozen_judge_config(judge)

    run.dry_run = False
    run.judge_provider = judge.provider
    run.judge_model_requested = judge.model

    records: list[BaselineRecord] = []
    raw_evaluations: list[dict] = []
    reported: set[str] = set()

    for case in run.cases:
        for repeat_index in range(1, run.repeats + 1):
            result = evaluate_one(case, repeat_index, judge, judge_config)

            artifact_dump = None
            failure_dump = None
            outcome: str
            if result.artifact is not None:
                outcome = "artifact"
                artifact_dump = result.artifact.model_dump(mode="json")
                rm = result.artifact.run_metadata.judge_model_reported
                if rm:
                    reported.add(rm)
            elif result.failure is not None:
                outcome = "failure"
                failure_dump = result.failure.model_dump(mode="json")
            else:  # pragma: no cover — defensive
                outcome = "unknown"

            raw_evaluations.append(
                {
                    "evaluation_id": f"{case.case_id}__r{repeat_index}",
                    "case_id": case.case_id,
                    "block": case.block,
                    "intent": case.intent,
                    "repeat_index": repeat_index,
                    "outcome": outcome,
                    "artifact": artifact_dump,
                    "failure": failure_dump,
                }
            )
            records.append(reduce_result(case, repeat_index, result))

    run.records = tuple(records)
    run.raw_evaluations = raw_evaluations
    run.judge_model_reported = tuple(sorted(reported))
    run.completed_at = _canonical_utc_now()


# ---------------------------------------------------------------------------
# Metrics (pure, deterministic).
# ---------------------------------------------------------------------------
def successful_records(
    records: Iterable[BaselineRecord], case_id: str
) -> list[BaselineRecord]:
    """Successful repeats of one case, ordered by ``repeat_index``."""
    return sorted(
        (
            r
            for r in records
            if r.case_id == case_id and r.scores is not None
        ),
        key=lambda r: r.repeat_index,
    )


def successful_repeat_count(records: Iterable[BaselineRecord], case_id: str) -> int:
    return len(successful_records(records, case_id))


def case_eligible(
    records: Iterable[BaselineRecord],
    case_id: str,
    min_successful: int = MIN_SUCCESSFUL_REPEATS,
) -> bool:
    """A case is semantic-eligible iff >= min_successful repeats succeeded."""
    return successful_repeat_count(records, case_id) >= min_successful


def case_dimension_means(
    records: Iterable[BaselineRecord], case_id: str
) -> dict[str, float] | None:
    """Per-dimension arithmetic mean over the case's successful repeats."""
    ok = successful_records(records, case_id)
    if not ok:
        return None
    return {
        dim: _round(sum(r.scores[dim] for r in ok) / len(ok))
        for dim in DIMENSION_IDS
    }


def case_overall_mean(
    records: Iterable[BaselineRecord], case_id: str
) -> float | None:
    """Mean of the Evaluator's deterministic overall_score over successful repeats."""
    ok = successful_records(records, case_id)
    if not ok:
        return None
    return _round(sum(r.overall_score for r in ok) / len(ok))


def case_critical_flags(
    records: Iterable[BaselineRecord], case_id: str
) -> tuple[str, ...]:
    """Case-level flags via strict majority over successful repeats.

    A flag is raised iff ``count > successful / 2``. Failed repeats contribute
    neither evidence nor denominator.

    Case-level flags are defined only for semantic-eligible cases (at least
    ``MIN_SUCCESSFUL_REPEATS`` successful repeats, Protocol Section 11.2); an
    excluded case reports no case-level flag.
    """
    ok = successful_records(records, case_id)
    if len(ok) < MIN_SUCCESSFUL_REPEATS:
        return ()
    counts: dict[str, int] = {}
    for rec in ok:
        for flag in set(rec.critical_flags):
            counts[flag] = counts.get(flag, 0) + 1
    raised = sorted(f for f, n in counts.items() if n > len(ok) / 2)
    return tuple(raised)


def case_failure_types(
    records: Iterable[BaselineRecord], case_id: str
) -> list[str]:
    """Sorted unique failure types observed among one case's repeats."""
    return sorted(
        {
            r.failure_type
            for r in records
            if r.case_id == case_id and r.failure_type is not None
        }
    )


def failure_taxonomy_counts(records: Iterable[BaselineRecord]) -> dict[str, int]:
    """Counts per Evaluator failure type (frozen taxonomy; zeros omitted)."""
    counts: dict[str, int] = {}
    for rec in records:
        if rec.failure_type is not None:
            counts[rec.failure_type] = counts.get(rec.failure_type, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def critical_flag_counts(
    records: Iterable[BaselineRecord],
    cases: Sequence[CanonicalCase],
) -> dict[str, int]:
    """Case-level flag counts over eligible cases (all frozen flags present)."""
    counts = {flag: 0 for flag in CRITICAL_FLAGS}
    for case in cases:
        if not case_eligible(records, case.case_id):
            continue
        for flag in case_critical_flags(records, case.case_id):
            counts[flag] += 1
    return counts


def _stats(values: Sequence[float]) -> dict[str, Any]:
    """mean / median / sample stdev (n-1) / n, rounded to 4 dp."""
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0:
        return {"mean": None, "median": None, "stdev": None, "n": 0}
    stdev = statistics.stdev(vals) if n >= 2 else 0.0
    return {
        "mean": _round(statistics.fmean(vals)),
        "median": _round(statistics.median(vals)),
        "stdev": _round(stdev),
        "n": n,
    }


def case_diagnostics(
    records: Sequence[BaselineRecord],
    cases: Sequence[CanonicalCase],
) -> list[dict[str, Any]]:
    """Per-case diagnostics (Section 10) for EVERY case, eligible or excluded."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        cid = case.case_id
        ok = successful_records(records, cid)
        eligible = case_eligible(records, cid)
        means = case_dimension_means(records, cid)
        overall = case_overall_mean(records, cid)
        flags = case_critical_flags(records, cid)
        repeat_flags = sorted({f for r in ok for f in r.critical_flags})
        failure_types = case_failure_types(records, cid)

        weak: list[str] = []
        severe: list[str] = []
        if means is not None:
            for label, dim in _LABEL_TO_DIM.items():
                value = means[dim]
                if value < SEVERE_WEAKNESS_THRESHOLD:
                    severe.append(label)
                if value < WEAKNESS_THRESHOLD:
                    weak.append(label)

        rows.append(
            {
                "case_id": cid,
                "block": case.block,
                "block_name": case.block_name,
                "intent": case.intent,
                "source_run_id": case.source_run_id,
                "successful_repeats": len(ok),
                "expected_repeats": REPEATS,
                "eligible": eligible,
                "exclusion_reason": (
                    None if eligible else "excluded_due_to_operational_failure"
                ),
                "dimension_means": None if means is None else _labeled(means),
                "overall_mean": overall,
                "critical_flags": list(flags),
                "repeat_level_flags": repeat_flags,
                "failure_types": failure_types,
                "weak_dimensions": weak,
                "severe_dimensions": severe,
            }
        )
    return rows


def _labeled(means: dict[str, float]) -> dict[str, float]:
    """Map dimension ids to their short D1..D6 labels (frozen order)."""
    return {label: means[dim] for label, dim in zip(DIMENSION_LABELS, DIMENSION_IDS)}


def global_metrics(
    records: Sequence[BaselineRecord],
    cases: Sequence[CanonicalCase],
) -> dict[str, Any]:
    """Global metrics (Section 7) over eligible cases."""
    eligible_ids = [c.case_id for c in cases if case_eligible(records, c.case_id)]
    excluded_ids = [c.case_id for c in cases if not case_eligible(records, c.case_id)]

    means_by_case = {
        cid: case_dimension_means(records, cid) for cid in eligible_ids
    }
    overall_by_case = {
        cid: case_overall_mean(records, cid) for cid in eligible_ids
    }

    dimensions: dict[str, dict] = {}
    for label, dim in zip(DIMENSION_LABELS, DIMENSION_IDS):
        values = [means_by_case[cid][dim] for cid in eligible_ids]
        dimensions[label] = _stats(values)

    flag_counts = critical_flag_counts(records, cases)

    successful_calls = sum(1 for r in records if r.scores is not None)
    failed_calls = sum(1 for r in records if r.scores is None)
    expected = len(cases) * REPEATS

    return {
        "total_cases": len(cases),
        "eligible_case_count": len(eligible_ids),
        "excluded_case_count": len(excluded_ids),
        "excluded_case_ids": excluded_ids,
        "expected_calls": expected,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "operational_success_rate": (
            _round(successful_calls / expected) if expected else None
        ),
        "dimensions": dimensions,
        "overall_score": _stats(
            [overall_by_case[cid] for cid in eligible_ids]
        ),
        "critical_flag_counts": flag_counts,
        "critical_flag_total": sum(flag_counts.values()),
        "failure_taxonomy_counts": failure_taxonomy_counts(records),
    }


def intent_metrics(
    records: Sequence[BaselineRecord],
    cases: Sequence[CanonicalCase],
) -> dict[str, dict[str, Any]]:
    """Per-intent metrics (Section 8) over eligible cases.

    Reporting transparency: ``n_total`` / ``n_eligible`` / ``n_ex`` are always
    reported together so an operational exclusion can never be mistaken for a
    smaller population. Only eligible cases enter the statistics.
    """
    out: dict[str, dict[str, Any]] = {}
    for intent in INTENTS:
        intent_cases = [c for c in cases if c.intent == intent]
        eligible = [c for c in intent_cases if case_eligible(records, c.case_id)]
        excluded = [c for c in intent_cases if not case_eligible(records, c.case_id)]
        means_by_case = {
            c.case_id: case_dimension_means(records, c.case_id) for c in eligible
        }
        dimensions: dict[str, dict[str, Any]] = {}
        for label, dim in zip(DIMENSION_LABELS, DIMENSION_IDS):
            values = [means_by_case[c.case_id][dim] for c in eligible]
            dimensions[label] = _stats(values)
        flag_count = sum(
            len(case_critical_flags(records, c.case_id)) for c in eligible
        )
        out[intent] = {
            "n_total": len(intent_cases),
            "n_eligible": len(eligible),
            "n_excluded": len(excluded),
            "excluded_case_ids": [c.case_id for c in excluded],
            "dimensions": dimensions,
            "overall": _stats(
                [case_overall_mean(records, c.case_id) for c in eligible]
            ),
            "critical_flag_count": flag_count,
        }
    return out


def block_metrics(
    records: Sequence[BaselineRecord],
    cases: Sequence[CanonicalCase],
) -> dict[str, dict[str, Any]]:
    """Per-block metrics (Section 9) over eligible cases.

    ``n_total`` / ``n_eligible`` / ``n_excluded`` are always reported together
    (Section 9). Only eligible cases enter the statistics.
    """
    out: dict[str, dict[str, Any]] = {}
    for block in ("A", "B", "C"):
        block_cases = [c for c in cases if c.block == block]
        eligible = [c for c in block_cases if case_eligible(records, c.case_id)]
        excluded = [c for c in block_cases if not case_eligible(records, c.case_id)]
        means_by_case = {
            c.case_id: case_dimension_means(records, c.case_id) for c in eligible
        }
        dimensions: dict[str, dict[str, Any]] = {}
        for label, dim in zip(DIMENSION_LABELS, DIMENSION_IDS):
            values = [means_by_case[c.case_id][dim] for c in eligible]
            dimensions[label] = _stats(values)
        out[block] = {
            "block_name": BLOCK_NAMES[block],
            "n_total": len(block_cases),
            "n_eligible": len(eligible),
            "n_excluded": len(excluded),
            "excluded_case_ids": [c.case_id for c in excluded],
            "dimensions": dimensions,
            "overall": _stats(
                [case_overall_mean(records, c.case_id) for c in eligible]
            ),
        }
    return out


def aggregate(run: BaselineRun) -> dict[str, Any]:
    """Compute all baseline metrics over the run's records."""
    return {
        "global": global_metrics(run.records, run.cases),
        "intent": intent_metrics(run.records, run.cases),
        "block": block_metrics(run.records, run.cases),
        "cases": case_diagnostics(run.records, run.cases),
    }


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------
def _write_json(path: Path, obj: Any) -> None:
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_manifest(run: BaselineRun) -> dict[str, Any]:
    """Run manifest (Section 14). No secrets."""
    integrity = run.integrity
    return {
        "run_id": run.run_id,
        "protocol_version": run.protocol_version,
        "protocol_document_path": str(PROTOCOL_DOC_PATH),
        "protocol_document_sha256": run.protocol_document_sha256,
        "protocol_status": run.protocol_status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        # ---- Source: three canonical Generator v0.1 Pilot runs (reused) ----
        "source_runs": run.source_runs,
        "source_run_ids": [s["run_id"] for s in run.source_runs],
        "source_run_paths": [s["path"] for s in run.source_runs],
        # ---- Population fingerprint (Section 3.4) ----
        "source_population_sha256": run.source_population_sha256,
        "source_population_sha256_expected": run.source_population_sha256_expected,
        "source_population_sha256_match": run.source_population_sha256_match,
        "source_population_records": (
            run.integrity.population_records if run.integrity is not None else []
        ),
        # ---- Frozen Generator side ----
        "generator_version": run.generator_version,
        "generator_version_provenance": run.generator_version_provenance,
        "prompt_version": run.prompt_version,
        "prompt_version_provenance": run.prompt_version_provenance,
        "case_count": len(run.cases),
        "case_ids": [c.case_id for c in run.cases],
        "per_block_case_counts": (
            integrity.per_block_counts if integrity is not None else {}
        ),
        "unique_case_ids": integrity.unique_case_ids if integrity is not None else None,
        "population_integrity_ok": integrity.ok if integrity is not None else None,
        # ---- Frozen Evaluator side ----
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": run.judge_provider or FROZEN_JUDGE_PROVIDER,
        "judge_model_requested": (
            run.judge_model_requested or FROZEN_JUDGE_MODEL_REQUESTED
        ),
        "judge_model_reported": list(run.judge_model_reported),
        "temperature": FROZEN_TEMPERATURE,
        "structured_output_enabled": FROZEN_STRUCTURED_OUTPUT_ENABLED,
        "retry_enabled": FROZEN_RETRY_ENABLED,
        "self_repair_enabled": FROZEN_SELF_REPAIR_ENABLED,
        # ---- Design ----
        "repeats": run.repeats,
        "expected_calls": EXPECTED_CALLS,
        "planned_calls": run.planned_calls,
        "successful_evaluations": sum(1 for r in run.records if r.scores is not None),
        "failed_evaluations": sum(1 for r in run.records if r.scores is None),
    }


def build_summary(run: BaselineRun, agg: dict[str, Any]) -> dict[str, Any]:
    """summary.json: provenance + global / intent / block / case metrics."""
    return {
        "run_id": run.run_id,
        "protocol_version": run.protocol_version,
        "protocol_status": run.protocol_status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        "source_run_ids": [s["run_id"] for s in run.source_runs],
        "source_population_sha256": run.source_population_sha256,
        "source_population_sha256_expected": run.source_population_sha256_expected,
        "source_population_sha256_match": run.source_population_sha256_match,
        "generator_version": run.generator_version,
        "generator_version_provenance": run.generator_version_provenance,
        "prompt_version": run.prompt_version,
        "prompt_version_provenance": run.prompt_version_provenance,
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": run.judge_provider or FROZEN_JUDGE_PROVIDER,
        "judge_model_requested": (
            run.judge_model_requested or FROZEN_JUDGE_MODEL_REQUESTED
        ),
        "judge_model_reported": list(run.judge_model_reported),
        "temperature": FROZEN_TEMPERATURE,
        "structured_output_enabled": FROZEN_STRUCTURED_OUTPUT_ENABLED,
        "retry_enabled": FROZEN_RETRY_ENABLED,
        "self_repair_enabled": FROZEN_SELF_REPAIR_ENABLED,
        "case_count": len(run.cases),
        "repeats": run.repeats,
        "expected_calls": EXPECTED_CALLS,
        # Descriptive baseline — NO acceptance verdict.
        "verdict": None,
        "verdict_note": (
            "Generator v0.1 Baseline Evaluation (descriptive). No Generator "
            "PASS/FAIL threshold is defined by this protocol."
        ),
        "global_metrics": agg["global"],
        "intent_metrics": agg["intent"],
        "block_metrics": agg["block"],
        "case_diagnostics": agg["cases"],
        "diagnostic_thresholds": {
            "weakness_dimension_mean_lt": WEAKNESS_THRESHOLD,
            "severe_weakness_dimension_mean_lt": SEVERE_WEAKNESS_THRESHOLD,
            "note": (
                "Diagnostic thresholds only. Not a validated PASS/FAIL benchmark."
            ),
        },
    }


def _write_case_metrics_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    header = (
        ["case_id", "block", "block_name", "intent", "successful_repeats",
         "eligible", "exclusion_reason"]
        + list(DIMENSION_LABELS)
        + ["overall_mean", "critical_flags", "repeat_level_flags",
           "failure_types", "weak_dimensions", "severe_dimensions"]
    )
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            means = row["dimension_means"] or {}
            writer.writerow(
                [
                    row["case_id"],
                    row["block"],
                    row["block_name"],
                    row["intent"],
                    row["successful_repeats"],
                    row["eligible"],
                    row["exclusion_reason"] or "",
                ]
                + [means.get(label, "") for label in DIMENSION_LABELS]
                + [
                    "" if row["overall_mean"] is None else row["overall_mean"],
                    "|".join(row["critical_flags"]),
                    "|".join(row["repeat_level_flags"]),
                    "|".join(row["failure_types"]),
                    "|".join(row["weak_dimensions"]),
                    "|".join(row["severe_dimensions"]),
                ]
            )


def _write_group_metrics_csv(
    path: Path,
    groups: dict[str, dict[str, Any]],
    *,
    key_header: str,
    extra_columns: Sequence[str] = (),
    flag_column: bool = False,
) -> None:
    # Total / eligible / excluded are all reported explicitly so an operational
    # exclusion can never be read as a smaller population.
    header = (
        [key_header]
        + list(extra_columns)
        + ["n_total", "n_eligible", "n_excluded", "excluded_case_ids"]
        + [f"{label}_mean" for label in DIMENSION_LABELS]
        + ["overall_mean"]
    )
    if flag_column:
        header.append("critical_flag_count")

    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for key, metrics in groups.items():
            row: list[Any] = [key]
            for column in extra_columns:
                row.append(metrics.get(column, ""))
            row += [
                metrics["n_total"],
                metrics["n_eligible"],
                metrics["n_excluded"],
                "|".join(metrics["excluded_case_ids"]),
            ]
            row += [metrics["dimensions"][label]["mean"] for label in DIMENSION_LABELS]
            row.append(metrics["overall"]["mean"])
            if flag_column:
                row.append(metrics["critical_flag_count"])
            writer.writerow(row)


def write_artifacts(
    run: BaselineRun,
    out_dir: Path | str,
    *,
    agg: dict[str, Any] | None = None,
) -> None:
    """Write the baseline artifact set. ``agg`` is omitted in dry-run mode."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(out_dir / "run_manifest.json", build_manifest(run))

    if agg is not None:
        _write_json(out_dir / "summary.json", build_summary(run, agg))
        _write_case_metrics_csv(out_dir / "case_metrics.csv", agg["cases"])
        _write_group_metrics_csv(
            out_dir / "intent_metrics.csv", agg["intent"], key_header="intent"
        )
        _write_group_metrics_csv(
            out_dir / "block_metrics.csv",
            agg["block"],
            key_header="block",
            extra_columns=("block_name",),
        )
    else:
        # Dry-run still writes a summary stub documenting the plan.
        _write_json(
            out_dir / "summary.json",
            {
                "run_id": run.run_id,
                "dry_run": True,
                "protocol_version": run.protocol_version,
                "protocol_status": run.protocol_status,
                "started_at": run.started_at,
                "source_run_ids": [s["run_id"] for s in run.source_runs],
                "source_population_sha256": run.source_population_sha256,
                "source_population_sha256_match": run.source_population_sha256_match,
                "case_count": len(run.cases),
                "repeats": run.repeats,
                "expected_calls": EXPECTED_CALLS,
                "metrics": None,
            },
        )

    if run.raw_evaluations:
        with (out_dir / "evaluations.jsonl").open("w", encoding="utf-8") as handle:
            for rec in run.raw_evaluations:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

    (out_dir / "README.md").write_text(_readme_text(run, agg), encoding="utf-8")


def _readme_text(run: BaselineRun, agg: dict[str, Any] | None) -> str:
    lines = [
        "# Generator v0.1 Baseline Evaluation",
        "",
        f"- run_id: {run.run_id}",
        f"- protocol_version: {run.protocol_version} (status: {run.protocol_status})",
        f"- started_at: {run.started_at}",
        f"- completed_at: {run.completed_at}",
        f"- dry_run: {run.dry_run}",
        "",
        "## Source (canonical Generator v0.1 Pilot runs, reused as-is)",
        "",
    ]
    for src in run.source_runs:
        lines.append(
            f"- Block {src['block']} ({src['block_name']}): run `{src['run_id']}` "
            f"— {src['actual_cases']}/{src['expected_cases']} cases"
        )
    lines += [
        f"- total cases: {len(run.cases)}",
        f"- source_population_sha256: {run.source_population_sha256}",
        f"- source_population_sha256_match: {run.source_population_sha256_match}",
        "",
        "## Evaluator",
        "",
        f"- evaluator_version: {EVALUATOR_VERSION}",
        f"- judge_prompt_version: {JUDGE_PROMPT_VERSION}",
        f"- judge_provider: {run.judge_provider or FROZEN_JUDGE_PROVIDER}",
        f"- judge_model_requested: "
        f"{run.judge_model_requested or FROZEN_JUDGE_MODEL_REQUESTED}",
        f"- temperature: {FROZEN_TEMPERATURE}"
        f" / structured_output: {FROZEN_STRUCTURED_OUTPUT_ENABLED}"
        f" / retry: {FROZEN_RETRY_ENABLED} / self_repair: {FROZEN_SELF_REPAIR_ENABLED}",
        f"- generator_version: {run.generator_version} / prompt_version: {run.prompt_version}",
        f"- repeats: {run.repeats} — expected calls: {EXPECTED_CALLS}",
        "",
        "This is a descriptive baseline. No Generator PASS/FAIL threshold is defined.",
        "",
        "Artifacts: run_manifest.json / summary.json / evaluations.jsonl /",
        "case_metrics.csv / intent_metrics.csv / block_metrics.csv.",
        "",
        "This directory is git-ignored (results/). Do not commit.",
    ]
    if run.judge_model_reported:
        lines.append(f"- judge_model_reported: {sorted(run.judge_model_reported)}")
    if agg is not None:
        g = agg["global"]
        lines += [
            "",
            "## Headline results",
            "",
            f"- eligible cases: {g['eligible_case_count']}/{g['total_cases']}",
            f"- operational success rate: {g['operational_success_rate']}",
            f"- overall score mean: {g['overall_score']['mean']}",
            f"- overall score median: {g['overall_score']['median']}",
        ]
    return "\n".join(lines) + "\n"
