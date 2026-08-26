"""Pydantic data models for the TeachIntent contracts.

Public API:

* :class:`~teachintent.models.input.TeachIntentInput` — the input contract
  ``(C, P, L, G)`` (docs/problem_definition.md, schema version 1.0.0-rc.2);
* :class:`~teachintent.models.speech_plan.SpeechPlan` — the output contract
  ``(V, D)`` (docs/speech_plan_schema.md, schema version 1.0.0-rc.3).

All models are strict: unknown fields and explicit nulls are rejected,
mirroring the JSON Schema files in ``schemas/``.
"""

from .input import (
    InstructionalContent,
    Learner,
    PedagogicalContext,
    PedagogicalIntent,
    PedagogicalPrimary,
    TeachIntentInput,
)
from .speech_plan import (
    BoundaryAfter,
    BoundaryStrength,
    ContourShape,
    DeliveryPlan,
    GlobalDelivery,
    GlobalPitchLevel,
    GlobalPitchRange,
    GlobalProsody,
    GlobalSpeakingRate,
    GlobalVolume,
    ProminenceLevel,
    ProminenceTarget,
    Segment,
    SegmentOverride,
    SegmentPitchLevel,
    SegmentPitchRange,
    SegmentProsody,
    SegmentSpeakingRate,
    SegmentVolume,
    SpeechPlan,
    VerbalPlan,
)

__all__ = [
    "InstructionalContent",
    "Learner",
    "PedagogicalContext",
    "PedagogicalIntent",
    "PedagogicalPrimary",
    "TeachIntentInput",
    "BoundaryAfter",
    "BoundaryStrength",
    "ContourShape",
    "DeliveryPlan",
    "GlobalDelivery",
    "GlobalPitchLevel",
    "GlobalPitchRange",
    "GlobalProsody",
    "GlobalSpeakingRate",
    "GlobalVolume",
    "ProminenceLevel",
    "ProminenceTarget",
    "Segment",
    "SegmentOverride",
    "SegmentPitchLevel",
    "SegmentPitchRange",
    "SegmentProsody",
    "SegmentSpeakingRate",
    "SegmentVolume",
    "SpeechPlan",
    "VerbalPlan",
]
