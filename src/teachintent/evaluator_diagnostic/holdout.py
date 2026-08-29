"""Protocol v0.2 confirmatory holdout dataset contract + validator, and the
frozen v0.2 coupling-matrix metadata validator.

This module extends (does NOT modify) the experiment-side diagnostic tooling.
It validates the NEW holdout dataset
(``cases/evaluator_diagnostic/diagnostic_pairs_v0.2_holdout.jsonl``) and the
protocol metadata (``cases/evaluator_diagnostic/protocol_v0.2_metadata.json``).

Holdout pair fields (Protocol v0.2 Section 4.3 / 6.6) are:
``pair_id``, ``family``, ``input``, ``reference_plan``, ``degraded_plan``,
``expected_flags``, ``notes``. The dimension partition is NOT part of the pair
— it is inherited from the frozen family matrix in the metadata file.

The metadata validator enforces the Section 8 invariants on the coupling
matrix: pairwise disjoint groups and union == the full frozen D1-D6 set, for
every one of the eight families, with no unknown dimension and no omission.

This module does NOT call any API and does NOT run the Evaluator.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from ..evaluator.rubric import CRITICAL_FLAGS, DIMENSION_IDS
from ..models import SpeechPlan, TeachIntentInput
from ..validators import iter_input_errors, iter_speech_plan_errors
from .dataset import (
    DIAGNOSTIC_FAMILIES,
    EXPECTED_PAIR_COUNT,
    PAIRS_PER_FAMILY,
    DiagnosticCaseError,
    DiagnosticValidationReport,
    load_diagnostic_pairs,
)

__all__ = [
    "HOLDOUT_DATASET_PATH",
    "PROTOCOL_METADATA_PATH",
    "DEVELOPMENT_DATASET_SHA256",
    "HOLDOUT_PAIR_FIELDS",
    "HOLDOUT_PAIR_ID_RE",
    "HoldoutMetadataReport",
    "validate_protocol_metadata",
    "validate_holdout_dataset",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CASES_DIR = _REPO_ROOT / "cases" / "evaluator_diagnostic"
HOLDOUT_DATASET_PATH = _CASES_DIR / "diagnostic_pairs_v0.2_holdout.jsonl"
PROTOCOL_METADATA_PATH = _CASES_DIR / "protocol_v0.2_metadata.json"
DEVELOPMENT_DATASET_PATH = _CASES_DIR / "diagnostic_pairs_v0.1.jsonl"

# Frozen SHA-256 of the development dataset v0.1 (Protocol v0.2 Section 5).
DEVELOPMENT_DATASET_SHA256 = (
    "a004715338c97d9e85b92fe0221a18631aa2884f6bb8b1d78a66066ccdd12664"
)

# Exact top-level fields a holdout pair may carry (no target_dimensions).
HOLDOUT_PAIR_FIELDS: tuple[str, ...] = (
    "pair_id",
    "family",
    "input",
    "reference_plan",
    "degraded_plan",
    "expected_flags",
    "notes",
)

HOLDOUT_PAIR_ID_RE = re.compile(r"^HOLDOUT-[A-H]-\d{2}$")


@dataclass(frozen=True)
class HoldoutMetadataReport:
    """Validation report for the Protocol v0.2 coupling-matrix metadata."""

    families_found: list[str]
    checks: dict[str, str]
    case_errors: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return not self.case_errors and all(v == "" for v in self.checks.values())


# ---------------------------------------------------------------------------
# Metadata validator (coupling matrix).
# ---------------------------------------------------------------------------
def validate_protocol_metadata(
    path: Path | None = None,
) -> HoldoutMetadataReport:
    """Validate the frozen v0.2 coupling-matrix metadata.

    Enforces, per family: the three groups are pairwise disjoint and their
    union equals exactly the six frozen dimension IDs (no omission, no unknown
    dimension), and all eight frozen families are present.
    """
    path = path or PROTOCOL_METADATA_PATH
    checks: dict[str, str] = {}
    case_errors: list[str] = []

    with Path(path).open(encoding="utf-8") as handle:
        doc = json.load(handle)

    if not isinstance(doc, dict):
        return HoldoutMetadataReport(
            families_found=[], checks={"metadata": "top-level is not an object"},
            case_errors=["metadata top-level is not an object"],
        )

    if doc.get("protocol_version") != "v0.2":
        case_errors.append(
            f"protocol_version must be 'v0.2', got {doc.get('protocol_version')!r}"
        )

    families = doc.get("families")
    if not isinstance(families, dict):
        return HoldoutMetadataReport(
            families_found=[],
            checks={"families": "missing or not an object"},
            case_errors=["'families' is missing or not an object"],
        )

    found = sorted(families.keys())
    checks["family_coverage"] = ""
    missing_families = sorted(set(DIAGNOSTIC_FAMILIES) - set(families.keys()))
    extra_families = sorted(set(families.keys()) - set(DIAGNOSTIC_FAMILIES))
    if missing_families:
        checks["family_coverage"] = f"missing families: {missing_families}"
    if extra_families:
        checks["family_coverage"] = (
            (checks["family_coverage"] + "; " if checks["family_coverage"] else "")
            + f"unknown families: {extra_families}"
        )

    for fam in DIAGNOSTIC_FAMILIES:
        entry = families.get(fam)
        if not isinstance(entry, dict):
            case_errors.append(f"family {fam!r} entry is missing or not an object")
            continue

        primary = set(entry.get("primary_target_dimensions", []) or [])
        collateral = set(entry.get("allowed_collateral_dimensions", []) or [])
        protected = set(entry.get("protected_dimensions", []) or [])

        # unknown dimensions
        all_dims = primary | collateral | protected
        unknown = sorted(all_dims - set(DIMENSION_IDS))
        if unknown:
            case_errors.append(f"family {fam}: unknown dimension(s) {unknown}")

        # disjointness
        if primary & collateral:
            case_errors.append(
                f"family {fam}: primary ∩ collateral = {sorted(primary & collateral)}"
            )
        if primary & protected:
            case_errors.append(
                f"family {fam}: primary ∩ protected = {sorted(primary & protected)}"
            )
        if collateral & protected:
            case_errors.append(
                f"family {fam}: collateral ∩ protected = {sorted(collateral & protected)}"
            )

        # completeness: union == full D1-D6
        union = primary | collateral | protected
        missing_dims = sorted(set(DIMENSION_IDS) - union)
        if missing_dims:
            case_errors.append(f"family {fam}: omitted dimension(s) {missing_dims}")

    return HoldoutMetadataReport(
        families_found=found,
        checks=checks,
        case_errors=case_errors,
    )


# ---------------------------------------------------------------------------
# Holdout dataset validator (extends the shared mechanical validator).
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_holdout_dataset(
    path: Path | None = None,
    *,
    development_path: Path | None = None,
) -> DiagnosticValidationReport:
    """Validate the v0.2 holdout dataset mechanically.

    Self-contained (does NOT reuse the v0.1 ``DIAG-``/``target_dimensions``
    wrapper rules). Checks:

    * 24 pairs; 8 families; 3 pairs per family; unique ids;
    * pair_id format ``HOLDOUT-{A..H}-{NN}`` + prefix<->family consistency;
    * unknown top-level fields rejected against the holdout field set (no
      ``target_dimensions``);
    * ``input`` passes the Input contract; ``reference_plan``/``degraded_plan``
      pass the frozen Layer-0 pipeline; ``reference != degraded``;
    * ``expected_flags`` uses frozen critical-flag names only;
    * ``target_dimensions`` NOT hardcoded in any pair;
    * holdout ids/content do not duplicate the development dataset;
    * development dataset SHA-256 unchanged.

    Returns a :class:`DiagnosticValidationReport`; does not call any API.
    """
    path = path or HOLDOUT_DATASET_PATH
    development_path = development_path or DEVELOPMENT_DATASET_PATH

    case_errors: list[DiagnosticCaseError] = []
    pairs: list[dict] = []

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
            pairs.append(pair)

    parsed_count = len(pairs)

    # development dataset reference (for id/content de-dup + SHA)
    dev_pairs = load_diagnostic_pairs(development_path)
    dev_ids = {p["pair_id"] for p in dev_pairs}
    dev_anchors = {
        p["input"]["instructional_content"]["content_anchor"] for p in dev_pairs
    }

    input_pass = 0
    reference_pass = 0
    degraded_pass = 0
    well_formed: list[dict] = []

    # ---- Stage 2: per-pair wrapper + contract checks ----
    for pair in pairs:
        pid = pair.get("pair_id") if isinstance(pair.get("pair_id"), str) else None
        issues: list[str] = []

        # unknown / missing top-level fields (holdout field set)
        top_keys = set(pair.keys())
        unexpected = sorted(top_keys - set(HOLDOUT_PAIR_FIELDS))
        missing = [f for f in HOLDOUT_PAIR_FIELDS if f not in top_keys]
        if unexpected:
            issues.append(f"unexpected top-level field(s): {unexpected}")
        if missing:
            issues.append(f"missing top-level field(s): {missing}")

        # target_dimensions must not be hardcoded
        if "target_dimensions" in pair:
            issues.append("target_dimensions must not be hardcoded in the pair")

        # pair_id format + prefix<->family
        if isinstance(pid, str):
            if HOLDOUT_PAIR_ID_RE.match(pid) is None:
                issues.append(f"pair_id {pid!r} does not match HOLDOUT-[A-H]-NN")
            else:
                letter = pid[len("HOLDOUT-"):][0]
                from .dataset import FAMILY_PAIR_ID_PREFIXES
                expected_family = FAMILY_PAIR_ID_PREFIXES.get(letter)
                if pair.get("family") != expected_family:
                    issues.append(
                        f"pair_id prefix {letter} maps to family {expected_family!r}, "
                        f"got {pair.get('family')!r}"
                    )
            if pid in dev_ids:
                issues.append(f"pair_id {pid!r} collides with development dataset")
        else:
            issues.append("pair_id missing or not a string")

        # family enum
        if pair.get("family") not in DIAGNOSTIC_FAMILIES:
            issues.append(f"family {pair.get('family')!r} not in frozen family enum")

        # expected_flags enum
        ef = pair.get("expected_flags")
        if not isinstance(ef, list):
            issues.append("expected_flags must be a list")
        else:
            for flag in ef:
                if flag not in CRITICAL_FLAGS:
                    issues.append(f"expected flag {flag!r} not a frozen critical flag")

        # notes non-empty string
        if not isinstance(pair.get("notes"), str) or not pair["notes"].strip():
            issues.append("notes must be a non-empty string")

        # content de-dup vs development
        anchor = None
        if isinstance(pair.get("input"), dict):
            ic = pair["input"].get("instructional_content")
            if isinstance(ic, dict):
                anchor = ic.get("content_anchor")
        if anchor is not None and anchor in dev_anchors:
            issues.append("content_anchor duplicates a development pair")

        if issues:
            case_errors.append(
                DiagnosticCaseError(
                    pair_id=pid, stage="wrapper", message="; ".join(issues)
                )
            )
            continue

        # input contract
        ok, detail = _layer0_input(pair.get("input"))
        if not ok:
            case_errors.append(
                DiagnosticCaseError(pair_id=pid, stage="input", message=detail)
            )
            continue
        input_pass += 1

        # reference plan
        ok, detail = _layer0_plan(pair.get("reference_plan"))
        if not ok:
            case_errors.append(
                DiagnosticCaseError(pair_id=pid, stage="reference_plan", message=detail)
            )
            continue
        reference_pass += 1

        # degraded plan
        ok, detail = _layer0_plan(pair.get("degraded_plan"))
        if not ok:
            case_errors.append(
                DiagnosticCaseError(pair_id=pid, stage="degraded_plan", message=detail)
            )
            continue
        degraded_pass += 1

        # reference != degraded
        if pair["reference_plan"] == pair["degraded_plan"]:
            case_errors.append(
                DiagnosticCaseError(
                    pair_id=pid, stage="degraded_plan",
                    message="reference_plan == degraded_plan (no perturbation injected)",
                )
            )
            continue

        well_formed.append(pair)

    # ---- Stage 3: dataset-level checks ----
    checks: dict[str, str] = {}

    checks["pair_count"] = (
        f"expected {EXPECTED_PAIR_COUNT} valid pairs, got {len(well_formed)}"
        if len(well_formed) != EXPECTED_PAIR_COUNT
        else ""
    )

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

    # development dataset SHA unchanged
    dev_sha = _sha256_file(development_path)
    checks["development_dataset_sha256_unchanged"] = (
        ""
        if dev_sha == DEVELOPMENT_DATASET_SHA256
        else f"development dataset SHA changed: {dev_sha} (expected {DEVELOPMENT_DATASET_SHA256})"
    )

    return DiagnosticValidationReport(
        parsed_count=parsed_count,
        input_pass_count=input_pass,
        reference_pass_count=reference_pass,
        degraded_pass_count=degraded_pass,
        dataset_checks=checks,
        case_errors=case_errors,
    )


# Reuse the frozen Layer-0 pipeline via the shared helpers.
def _layer0_plan(plan: object) -> tuple[bool, str]:
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


def _layer0_input(input_doc: object) -> tuple[bool, str]:
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
