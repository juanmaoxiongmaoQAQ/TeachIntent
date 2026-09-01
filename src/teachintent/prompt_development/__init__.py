"""Prompt v0.2-rc.1 development package.

Two read-only stages over the SAME frozen 30-case Pilot population:

* :mod:`teachintent.prompt_development.development_runner` — regenerates the
  population with a selected candidate Prompt (``v0.2-rc.1`` or ``v0.2-rc.2``)
  passed as an explicit ``prompt_version``; v0.2-rc.1 remains the default and
  each version writes to its own results directory;
* :mod:`teachintent.prompt_development.development_evaluation` — paired
  comparison of the finished Generator v0.1 baseline against a finished
  candidate generation run, both measured with the frozen Evaluator v0.1.
  The candidate side is selected by ``prompt_version`` (``v0.2-rc.1`` default,
  ``v0.2-rc.2`` explicit) through the SAME framework — the protocol, the retry
  taxonomy, the reducer and every aggregation formula are shared, and only the
  artifact key label (``rc_1`` / ``rc_2``) and the source run differ.

Neither stage regenerates the v0.1 side and neither re-evaluates the frozen
v0.1 baseline evaluation run.
"""

from .development_evaluation import (  # noqa: E402  (order is intentional)
    BASELINE_EVALUATION_ROOT,
    BASELINE_EVALUATION_RUN_ID,
    BASELINE_PROMPT_VERSION,
    CANDIDATE_DIR_SLUGS,
    CANDIDATE_GENERATION_ROOT,
    CANDIDATE_GENERATION_ROOT_RC2,
    CANDIDATE_GENERATION_RUN_ID,
    CANDIDATE_GENERATION_RUN_ID_RC2,
    CANDIDATE_LABELS,
    CANDIDATE_PROMPT_VERSION,
    CASE_COUNT,
    PRIMARY_DIMENSION,
    PROTECTED_DIMENSIONS,
    RESULTS_ROOT,
    RESULTS_ROOT_RC2,
    SECONDARY_DIMENSION,
    SUPPORTED_PROMPT_VERSIONS,
    BaselineSide,
    CandidateIntegrity,
    DevelopmentEvaluationError,
    DevelopmentEvaluationRun,
    build_development_manifest,
    build_development_summary,
    build_paired_comparison,
    candidate_generation_root_for_prompt_version,
    candidate_generation_run_id_for_prompt_version,
    candidate_dir_slug_for_prompt_version,
    candidate_label_for_prompt_version,
    case_pair_rows,
    critical_flag_comparison,
    delta_stats,
    dimension_paired_stats,
    evaluation_results_root_for_prompt_version,
    execute_candidate_evaluation,
    group_breakdown,
    load_baseline_evaluation,
    load_candidate_cases,
    prepare_candidate_run,
    prepare_development_evaluation,
    summarize_candidate_delivery_behavior,
    write_development_artifacts,
)
from .development_runner import (
    CANONICAL_PILOT_RUNS,
    DEVELOPMENT_RESULTS_ROOT,
    DEVELOPMENT_RESULTS_ROOT_RC2,
    GENERATOR_MODEL,
    GENERATOR_VERSION,
    PEDAGOGICAL_INTENTS,
    # CANDIDATE_PROMPT_VERSION is shared with development_evaluation and is
    # imported once, above — do not re-import it here.
    PROMPT_VERSION_RC2,
    SUPPORTED_PROMPT_VERSIONS,
    TEMPERATURE,
    DevelopmentCase,
    DevelopmentValidationError,
    canonical_population_case_ids,
    discover_canonical_inputs,
    results_root_for_prompt_version,
    run_development_batch,
    summarize_delivery_distribution,
    validate_development_inputs,
)

__all__ = [
    # ---- development_evaluation ----
    "BASELINE_EVALUATION_ROOT",
    "BASELINE_EVALUATION_RUN_ID",
    "BASELINE_PROMPT_VERSION",
    "CANDIDATE_GENERATION_ROOT",
    "CANDIDATE_GENERATION_ROOT_RC2",
    "CANDIDATE_GENERATION_RUN_ID",
    "CANDIDATE_GENERATION_RUN_ID_RC2",
    "CANDIDATE_LABELS",
    "CANDIDATE_DIR_SLUGS",
    "CANDIDATE_PROMPT_VERSION",
    "CASE_COUNT",
    "PRIMARY_DIMENSION",
    "PROTECTED_DIMENSIONS",
    "RESULTS_ROOT",
    "RESULTS_ROOT_RC2",
    "SECONDARY_DIMENSION",
    "SUPPORTED_PROMPT_VERSIONS",
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
    # ---- candidate-version routing (shared by both stages) ----
    "candidate_label_for_prompt_version",
    "candidate_dir_slug_for_prompt_version",
    "candidate_generation_run_id_for_prompt_version",
    "candidate_generation_root_for_prompt_version",
    "evaluation_results_root_for_prompt_version",
    "summarize_candidate_delivery_behavior",
    # ---- development_runner ----
    # CANDIDATE_PROMPT_VERSION is shared: the runner writes it, the evaluation
    # asserts it. It is imported once above.
    "GENERATOR_VERSION",
    "GENERATOR_MODEL",
    "TEMPERATURE",
    "CANONICAL_PILOT_RUNS",
    "PROMPT_VERSION_RC2",
    "SUPPORTED_PROMPT_VERSIONS",
    "PEDAGOGICAL_INTENTS",
    "DEVELOPMENT_RESULTS_ROOT",
    "DEVELOPMENT_RESULTS_ROOT_RC2",
    "DevelopmentCase",
    "DevelopmentValidationError",
    "canonical_population_case_ids",
    "discover_canonical_inputs",
    "validate_development_inputs",
    "results_root_for_prompt_version",
    "summarize_delivery_distribution",
    "run_development_batch",
]
