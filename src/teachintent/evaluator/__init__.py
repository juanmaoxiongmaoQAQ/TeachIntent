"""TeachIntent Evaluator v0.1.

Diagnostic evaluation of generated pedagogical Speech Plans. Reuses the frozen
Generator-output contract validation (Layer 0) and adds a universal semantic
judge (Layer 1) plus experiment-specific diagnostic probes (Layer 2).

See ``docs/evaluator_spec_v0.1.md`` (Frozen) for the authoritative contract.
"""

from .errors import (
    EvaluatorError,
    SetupInputJsonSchemaError,
    SetupInputPydanticError,
    SetupRunContextError,
    SetupJudgeConfigError,
    JudgeAPIError,
    JudgeResponseParseError,
    JudgeOutputSchemaError,
    EvidenceSourceError,
    EvidenceGroundingError,
    InternalEvaluatorError,
)
from .rubric import (
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    DIMENSIONS,
    DIMENSION_IDS,
    CRITICAL_FLAGS,
    GATE_STAGES,
    FAILURE_TYPES,
    compute_overall_score,
)
from .evidence import (
    validate_evidence_path,
    resolve_evidence_source,
    is_grounded,
    validate_evidence,
    EVIDENCE_PATH_RE,
)
from .prompt import (
    SYSTEM_TEMPLATE,
    USER_TEMPLATE,
    RUBRIC_TEXT,
    JUDGE_OUTPUT_CONTRACT,
    compute_judge_prompt_sha256,
    build_judge_prompt,
)
from .models import (
    EvaluationRunContext,
    JudgeConfig,
    EvidenceItem,
    DimensionJudgment,
    CriticalFlagResult,
    JudgeOutput,
    GateFailure,
    RunMetadata,
    UniversalEvaluationArtifact,
    EvaluatorFailureArtifact,
    DiagnosticProbe,
    DiagnosticProbeArtifact,
)
from .parser import parse_judge_response
from .judge import (
    JudgeCompletion,
    JudgeCompleter,
    JudgeClient,
    sanitize_for_judge,
)
from .service import (
    EvaluatorResult,
    evaluate_speech_plan,
)

__all__ = [
    "EvaluatorError",
    "SetupInputJsonSchemaError",
    "SetupInputPydanticError",
    "SetupRunContextError",
    "SetupJudgeConfigError",
    "JudgeAPIError",
    "JudgeResponseParseError",
    "JudgeOutputSchemaError",
    "EvidenceSourceError",
    "EvidenceGroundingError",
    "InternalEvaluatorError",
    "EVALUATOR_VERSION",
    "JUDGE_PROMPT_VERSION",
    "DIMENSIONS",
    "DIMENSION_IDS",
    "CRITICAL_FLAGS",
    "GATE_STAGES",
    "FAILURE_TYPES",
    "compute_overall_score",
    "validate_evidence_path",
    "resolve_evidence_source",
    "is_grounded",
    "validate_evidence",
    "EVIDENCE_PATH_RE",
    "SYSTEM_TEMPLATE",
    "USER_TEMPLATE",
    "RUBRIC_TEXT",
    "JUDGE_OUTPUT_CONTRACT",
    "compute_judge_prompt_sha256",
    "build_judge_prompt",
    "EvaluationRunContext",
    "JudgeConfig",
    "EvidenceItem",
    "DimensionJudgment",
    "CriticalFlagResult",
    "JudgeOutput",
    "GateFailure",
    "RunMetadata",
    "UniversalEvaluationArtifact",
    "EvaluatorFailureArtifact",
    "DiagnosticProbe",
    "DiagnosticProbeArtifact",
    "parse_judge_response",
    "JudgeCompletion",
    "JudgeCompleter",
    "JudgeClient",
    "sanitize_for_judge",
    "EvaluatorResult",
    "evaluate_speech_plan",
]
