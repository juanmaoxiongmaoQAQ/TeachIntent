"""Frozen diagnostic-pairs dataset contract, loader, and mechanical validator.

The dataset lives at ``cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl``:
8 perturbation families x 3 reference/degraded pairs = 24 pairs.

The validator enforces the *mechanical* contract only:

* 24 total pairs; 8 families; 3 pairs per family;
* ``pair_id`` unique and matching ``DIAG-{A..H}-{01..03}``;
* ``input`` passes the TeachIntent Input contract (JSON Schema + Pydantic);
* ``reference_plan`` and ``degraded_plan`` both pass the Speech Plan contract
  (Layer 0: JSON Schema + Pydantic) — perturbations must be semantic, never
  structural;
* ``target_dimensions`` only uses frozen D1–D6 dimension IDs;
* ``expected_flags`` only uses frozen critical-flag names;
* ``family`` in the frozen family enum;
* unknown top-level pair fields rejected;
* ``reference_plan != degraded_plan``.

The validator does NOT call any API and does NOT judge pedagogical
reasonableness (that is a human review step).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from ..evaluator.rubric import CRITICAL_FLAGS, DIMENSION_IDS
from ..models import SpeechPlan, TeachIntentInput
from ..validators import iter_input_errors, iter_speech_plan_errors

__all__ = [
    "DIAGNOSTIC_DATASET_PATH",
    "DIAGNOSTIC_FAMILIES",
    "FAMILY_PAIR_ID_PREFIXES",
    "EXPECTED_PAIR_COUNT",
    "PAIRS_PER_FAMILY",
    "EXPECTED_PAIR_FIELDS",
    "PAIR_ID_RE",
    "DiagnosticCaseError",
    "DiagnosticValidationReport",
    "load_diagnostic_pairs",
    "validate_diagnostic_dataset",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIC_DATASET_PATH = (
    _REPO_ROOT / "cases" / "evaluator_diagnostic" / "diagnostic_pairs_v0.1.jsonl"
)

# ---------------------------------------------------------------------------
# Frozen family enum (8 families, ordered A..H).
# ---------------------------------------------------------------------------
DIAGNOSTIC_FAMILIES: tuple[str, ...] = (
    "intent_mismatch",
    "content_contradiction",
    "material_off_anchor_content",
    "learner_state_mismatch",
    "incomplete_corrective_feedback",
    "delivery_over_specification",
    "delivery_pedagogy_conflict",
    "prompt_injection_compliance",
)

# pair_id prefix letter -> family name (frozen A..H order).
FAMILY_PAIR_ID_PREFIXES: dict[str, str] = {
    letter: family
    for letter, family in zip("ABCDEFGH", DIAGNOSTIC_FAMILIES)
}

EXPECTED_PAIR_COUNT = 24
PAIRS_PER_FAMILY = 3

# Exact top-level fields a pair may carry (unknown fields rejected).
EXPECTED_PAIR_FIELDS: tuple[str, ...] = (
    "pair_id",
    "family",
    "input",
    "reference_plan",
    "degraded_plan",
    "target_dimensions",
    "expected_flags",
    "notes",
)

PAIR_ID_RE = re.compile(r"^DIAG-[A-H]-\d{2}$")


@dataclass(frozen=True)
class DiagnosticCaseError:
    """A single pair-specific validation error."""

    pair_id: str | None
    stage: str  # "json_parse" | "input" | "reference_plan" | "degraded_plan" | "wrapper"
    message: str


@dataclass(frozen=True)
class DiagnosticValidationReport:
    """Full validation report for a diagnostic pairs dataset."""

    parsed_count: int
    input_pass_count: int
    reference_pass_count: int
    degraded_pass_count: int
    dataset_checks: dict[str, str]
    case_errors: list[DiagnosticCaseError] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return (
            not self.case_errors
            and all(v == "" for v in self.dataset_checks.values())
        )


# ---------------------------------------------------------------------------
# Loader.
# ---------------------------------------------------------------------------
def load_diagnostic_pairs(path: Path | None = None) -> list[dict]:
    """Load diagnostic pairs from *path* in file order. Skips blank lines."""
    path = path or DIAGNOSTIC_DATASET_PATH
    pairs: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


# ---------------------------------------------------------------------------
# Validator.
# ---------------------------------------------------------------------------
def _layer0_valid_plan(plan: object) -> tuple[bool, str]:
    """Return (valid, detail) for a Speech Plan via the frozen Layer-0 pipeline."""
    if not isinstance(plan, dict):
        return False, "not an object"
    structural = list(iter_speech_plan_errors(plan))
    if structural:
        return False, "; ".join(f"{e.json_path}: {e.message}" for e in structural)
    try:
        SpeechPlan.model_validate(plan)
    except ValidationError as exc:
        return False, str(exc)
    return True, ""


def _valid_input(input_doc: object) -> tuple[bool, str]:
    if not isinstance(input_doc, dict):
        return False, "not an object"
    structural = list(iter_input_errors(input_doc))
    if structural:
        return False, "; ".join(f"{e.json_path}: {e.message}" for e in structural)
    try:
        TeachIntentInput.model_validate(input_doc)
    except ValidationError as exc:
        return False, str(exc)
    return True, ""


def validate_diagnostic_dataset(
    path: Path | None = None,
) -> DiagnosticValidationReport:
    """Validate the diagnostic pairs dataset mechanically.

    Returns a :class:`DiagnosticValidationReport`; does not raise on validation
    failures (only on I/O errors).
    """
    path = path or DIAGNOSTIC_DATASET_PATH
    case_errors: list[DiagnosticCaseError] = []
    pairs: list[tuple[int, dict]] = []  # (line_number, pair)

    # ---- Stage 1: JSONL parse ----
    with Path(path).open(encoding="utf-8") as handle:
        for index, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                pair = json.loads(line)
            except json.JSONDecodeError as exc:
                case_errors.append(
                    DiagnosticCaseError(
                        pair_id=None, stage="json_parse",
                        message=f"malformed JSON: {exc.msg} (col {exc.colno})",
                    )
                )
                continue
            if not isinstance(pair, dict):
                case_errors.append(
                    DiagnosticCaseError(
                        pair_id=None, stage="json_parse",
                        message="line parsed to a non-object value",
                    )
                )
                continue
            pairs.append((index, pair))

    parsed_count = len(pairs)
    input_pass = 0
    reference_pass = 0
    degraded_pass = 0
    well_formed: list[dict] = []

    # ---- Stage 2: per-pair wrapper + contract checks ----
    for _, pair in pairs:
        pair_id = pair.get("pair_id") if isinstance(pair.get("pair_id"), str) else None
        issues: list[str] = []

        # unknown top-level fields
        top_keys = set(pair.keys())
        unexpected = sorted(top_keys - set(EXPECTED_PAIR_FIELDS))
        missing = [f for f in EXPECTED_PAIR_FIELDS if f not in top_keys]
        if unexpected:
            issues.append(f"unexpected top-level field(s): {unexpected}")
        if missing:
            issues.append(f"missing top-level field(s): {missing}")

        # pair_id
        if isinstance(pair.get("pair_id"), str):
            if PAIR_ID_RE.match(pair["pair_id"]) is None:
                issues.append(f"pair_id {pair['pair_id']!r} does not match DIAG-[A-H]-NN")
        else:
            issues.append("pair_id missing or not a string")

        # family
        if pair.get("family") not in DIAGNOSTIC_FAMILIES:
            issues.append(
                f"family {pair.get('family')!r} not in frozen family enum"
            )

        # pair_id prefix <-> family consistency
        if isinstance(pair.get("pair_id"), str) and PAIR_ID_RE.match(pair["pair_id"]):
            letter = pair["pair_id"][5]
            expected_family = FAMILY_PAIR_ID_PREFIXES.get(letter)
            if expected_family is not None and pair.get("family") != expected_family:
                issues.append(
                    f"pair_id prefix {letter} maps to family {expected_family!r}, "
                    f"got {pair.get('family')!r}"
                )

        # target_dimensions
        td = pair.get("target_dimensions")
        if not isinstance(td, list) or not td:
            issues.append("target_dimensions must be a non-empty list")
        else:
            for dim in td:
                if dim not in DIMENSION_IDS:
                    issues.append(f"target dimension {dim!r} not a frozen D1-D6 id")

        # expected_flags
        ef = pair.get("expected_flags")
        if not isinstance(ef, list):
            issues.append("expected_flags must be a list")
        else:
            for flag in ef:
                if flag not in CRITICAL_FLAGS:
                    issues.append(f"expected flag {flag!r} not a frozen critical flag")

        # notes must be a non-empty string
        if not isinstance(pair.get("notes"), str) or not pair["notes"].strip():
            issues.append("notes must be a non-empty string")

        if issues:
            case_errors.append(
                DiagnosticCaseError(
                    pair_id=pair_id, stage="wrapper",
                    message="; ".join(issues),
                )
            )
            continue

        # input
        ok, detail = _valid_input(pair.get("input"))
        if not ok:
            case_errors.append(
                DiagnosticCaseError(pair_id=pair_id, stage="input", message=detail)
            )
            continue
        input_pass += 1

        # reference_plan
        ok, detail = _layer0_valid_plan(pair.get("reference_plan"))
        if not ok:
            case_errors.append(
                DiagnosticCaseError(
                    pair_id=pair_id, stage="reference_plan", message=detail
                )
            )
            continue
        reference_pass += 1

        # degraded_plan
        ok, detail = _layer0_valid_plan(pair.get("degraded_plan"))
        if not ok:
            case_errors.append(
                DiagnosticCaseError(
                    pair_id=pair_id, stage="degraded_plan", message=detail
                )
            )
            continue
        degraded_pass += 1

        # reference != degraded
        if pair["reference_plan"] == pair["degraded_plan"]:
            case_errors.append(
                DiagnosticCaseError(
                    pair_id=pair_id, stage="degraded_plan",
                    message="reference_plan == degraded_plan (no perturbation injected)",
                )
            )
            continue

        well_formed.append(pair)

    # ---- Stage 3: dataset-level checks ----
    checks: dict[str, str] = {}

    if len(well_formed) != EXPECTED_PAIR_COUNT:
        checks["pair_count"] = (
            f"expected {EXPECTED_PAIR_COUNT} valid pairs, got {len(well_formed)}"
        )
    else:
        checks["pair_count"] = ""

    family_counts = Counter(p["family"] for p in well_formed)
    missing_families = sorted(set(DIAGNOSTIC_FAMILIES) - set(family_counts))
    checks["family_coverage"] = (
        f"missing family/families: {missing_families}" if missing_families else ""
    )

    bad_family_counts = {
        fam: n for fam, n in family_counts.items() if n != PAIRS_PER_FAMILY
    }
    checks["pairs_per_family"] = (
        f"family counts not {PAIRS_PER_FAMILY}: {bad_family_counts}"
        if bad_family_counts
        else ""
    )

    pair_ids = [p["pair_id"] for p in well_formed]
    dup_ids = sorted({pid for pid in pair_ids if pair_ids.count(pid) > 1})
    checks["unique_pair_ids"] = f"duplicate pair_id(s): {dup_ids}" if dup_ids else ""

    return DiagnosticValidationReport(
        parsed_count=parsed_count,
        input_pass_count=input_pass,
        reference_pass_count=reference_pass,
        degraded_pass_count=degraded_pass,
        dataset_checks=checks,
        case_errors=case_errors,
    )
