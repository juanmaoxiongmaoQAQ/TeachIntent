"""Prompt v0.2-rc.1 development package.

Two read-only stages over the SAME frozen 30-case Pilot population:

* :mod:`teachintent.prompt_development.development_runner` — regenerates the
  population with the candidate Prompt v0.2-rc.1 (explicit ``prompt_version``);
* :mod:`teachintent.prompt_development.development_evaluation` — paired
  comparison of the finished Generator v0.1 baseline against the finished rc.1
  candidate, both measured with the frozen Evaluator v0.1.

Neither stage regenerates the v0.1 side and neither re-evaluates the frozen
v0.1 baseline evaluation run.
"""

from .development_evaluation import (  # noqa: E402  (order is intentional)
    BASELINE_EVALUATION_ROOT,
    BASELINE_EVALUATION_RUN_ID,
    BASELINE_PROMPT_VERSION,
    CANDIDATE_GENERATION_ROOT,
    CANDIDATE_GENERATION_RUN_ID,
    CANDIDATE_PROMPT_VERSION,
    CASE_COUNT,
    PRIMARY_DIMENSION,
    PROTECTED_DIMENSIONS,
    RESULTS_ROOT,
    SECONDARY_DIMENSION,
    BaselineSide,
    CandidateIntegrity,
    DevelopmentEvaluationError,
    DevelopmentEvaluationRun,
    build_development_manifest,
    build_development_summary,
    build_paired_comparison,
    case_pair_rows,
    critical_flag_comparison,
    delta_stats,
    dimension_paired_stats,
    execute_candidate_evaluation,
    group_breakdown,
    load_baseline_evaluation,
    load_candidate_cases,
    prepare_candidate_run,
    prepare_development_evaluation,
    write_development_artifacts,
)
from .development_runner import (
    CANONICAL_PILOT_RUNS,
    GENERATOR_MODEL,
    GENERATOR_VERSION,
    TEMPERATURE,
    DevelopmentCase,
    DevelopmentValidationError,
    canonical_population_case_ids,
    discover_canonical_inputs,
    run_development_batch,
    validate_development_inputs,
)

__all__ = [
    # ---- development_evaluation ----
    "BASELINE_EVALUATION_ROOT",
    "BASELINE_EVALUATION_RUN_ID",
    "BASELINE_PROMPT_VERSION",
    "CANDIDATE_GENERATION_ROOT",
    "CANDIDATE_GENERATION_RUN_ID",
    "CANDIDATE_PROMPT_VERSION",
    "CASE_COUNT",
    "PRIMARY_DIMENSION",
    "PROTECTED_DIMENSIONS",
    "RESULTS_ROOT",
    "SECONDARY_DIMENSION",
    "BaselineSide",
    "CandidateIntegrity",
    "DevelopmentEvaluationError",
    "DevelopmentEvaluationRun",
    "build_development_manifest",
    "build_development_summary",
    "build_paired_comparison",
    "case_pair_rows",
    "critical_flag_comparison",
    "delta_stats",
    "dimension_paired_stats",
    "execute_candidate_evaluation",
    "group_breakdown",
    "load_baseline_evaluation",
    "load_candidate_cases",
    "prepare_candidate_run",
    "prepare_development_evaluation",
    "write_development_artifacts",
    # ---- development_runner ----
    # CANDIDATE_PROMPT_VERSION is shared: the runner writes it, the evaluation
    # asserts it. It is imported once above.
    "GENERATOR_VERSION",
    "GENERATOR_MODEL",
    "TEMPERATURE",
    "CANONICAL_PILOT_RUNS",
    "DevelopmentCase",
    "DevelopmentValidationError",
    "canonical_population_case_ids",
    "discover_canonical_inputs",
    "validate_development_inputs",
    "run_development_batch",
]
