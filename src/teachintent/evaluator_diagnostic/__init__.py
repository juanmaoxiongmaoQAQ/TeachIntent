"""TeachIntent Evaluator v0.1 — controlled diagnostic perturbation validation.

This package validates the **Evaluator itself**, not the Generator. It provides:

* ``dataset`` — the frozen diagnostic pairs loader + mechanical validator;
* ``metrics`` — the frozen diagnostic metrics (directional accuracy, targeted
  drop, off-target MAE, repeatability, critical-flag diagnostics);
* ``runner`` — an offline, judge-injected batch runner (no API calls on its own).

None of these modules modify any frozen component (Generator v0.1, Prompt v0.1,
Evaluator v0.1, the two Schemas, or the 30 pilot cases).
"""

from .dataset import (
    DIAGNOSTIC_DATASET_PATH,
    DIAGNOSTIC_FAMILIES,
    EXPECTED_PAIR_COUNT,
    PAIRS_PER_FAMILY,
    EXPECTED_PAIR_FIELDS,
    PAIR_ID_RE,
    DiagnosticCaseError,
    DiagnosticValidationReport,
    load_diagnostic_pairs,
    validate_diagnostic_dataset,
)
from .metrics import (
    DirectionalAccuracy,
    MeanTargetedDrop,
    OffTargetMAE,
    Repeatability,
    FlagDiagnostics,
    EvaluationRecord,
    directional_accuracy,
    mean_targeted_drop,
    off_target_mae,
    repeatability,
    critical_flag_diagnostics,
)
from .runner import (
    DiagnosticRunResult,
    build_judge_config,
    build_run_context,
    run_diagnostic,
    run_diagnostic_dry,
)
from .holdout import (
    HOLDOUT_DATASET_PATH,
    PROTOCOL_METADATA_PATH,
    DEVELOPMENT_DATASET_SHA256,
    HOLDOUT_PAIR_FIELDS,
    HOLDOUT_PAIR_ID_RE,
    HoldoutMetadataReport,
    validate_protocol_metadata,
    validate_holdout_dataset,
)

__all__ = [
    "DIAGNOSTIC_DATASET_PATH",
    "DIAGNOSTIC_FAMILIES",
    "EXPECTED_PAIR_COUNT",
    "PAIRS_PER_FAMILY",
    "EXPECTED_PAIR_FIELDS",
    "PAIR_ID_RE",
    "DiagnosticCaseError",
    "DiagnosticValidationReport",
    "load_diagnostic_pairs",
    "validate_diagnostic_dataset",
    "DirectionalAccuracy",
    "MeanTargetedDrop",
    "OffTargetMAE",
    "Repeatability",
    "FlagDiagnostics",
    "EvaluationRecord",
    "directional_accuracy",
    "mean_targeted_drop",
    "off_target_mae",
    "repeatability",
    "critical_flag_diagnostics",
    "DiagnosticRunResult",
    "build_judge_config",
    "build_run_context",
    "run_diagnostic",
    "run_diagnostic_dry",
    "HOLDOUT_DATASET_PATH",
    "PROTOCOL_METADATA_PATH",
    "DEVELOPMENT_DATASET_SHA256",
    "HOLDOUT_PAIR_FIELDS",
    "HOLDOUT_PAIR_ID_RE",
    "HoldoutMetadataReport",
    "validate_protocol_metadata",
    "validate_holdout_dataset",
]
