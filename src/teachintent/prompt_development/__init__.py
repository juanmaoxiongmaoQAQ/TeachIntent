"""Prompt v0.2-rc.1 development generation runner package.

Regenerates the existing 30-case Pilot population with the candidate Prompt
v0.2-rc.1 (explicit ``prompt_version``), reusing the canonical v0.1 Pilot runs as
the fixed comparison baseline. See :mod:`teachintent.prompt_development.development_runner`.
"""

from .development_runner import (
    CANONICAL_PILOT_RUNS,
    CANDIDATE_PROMPT_VERSION,
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
    "GENERATOR_VERSION",
    "CANDIDATE_PROMPT_VERSION",
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
