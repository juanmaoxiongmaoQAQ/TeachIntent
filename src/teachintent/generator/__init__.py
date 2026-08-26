"""Hy3 Speech Plan Generator v0.1.

Minimal single-pass generation chain: validated input -> versioned prompt -> Hy3
API -> raw response -> JSON parsing -> JSON Schema validation -> Pydantic semantic
validation -> validated Speech Plan. No retry/self-repair (first-call failures are
preserved facts). See ``service.py`` for the pipeline and ``errors.py`` for the
failure taxonomy.
"""

from .client import Hy3Client, Hy3Completion, Hy3Completer
from .errors import (
    GeneratorError,
    Hy3APIError,
    Hy3ConfigError,
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from .parser import parse_speech_plan_json
from .service import SpeechPlanGenerationResult, generate_speech_plan

__all__ = [
    "Hy3Client",
    "Hy3Completion",
    "Hy3Completer",
    "GeneratorError",
    "Hy3APIError",
    "Hy3ConfigError",
    "InputContractError",
    "ResponseParsingError",
    "SpeechPlanSemanticError",
    "SpeechPlanStructuralError",
    "parse_speech_plan_json",
    "SpeechPlanGenerationResult",
    "generate_speech_plan",
]
