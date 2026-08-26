"""Pydantic models for the TeachIntent Input Contract.

Source of truth: ``docs/problem_definition.md`` (Document Version 0.3,
Input Schema Version ``1.0.0-rc.2``).  The models mirror the structural
constraints of ``schemas/teachintent_input.schema.json``; cross-field
semantic constraints (there are none in the input contract beyond the
structural ones) would live in model validators.

Field semantics follow the specification exactly:

* ``schema_version`` — identifies the TeachIntent input schema; independent
  of the Speech Plan output schema version.
* ``output_language`` — BCP 47 language tag validated against a
  lightweight/common syntax subset for supported TeachIntent languages.
* ``instructional_content`` — case-level instructional knowledge;
  ``content_anchor`` is the authoritative knowledge reference, not the final
  spoken transcript.
* ``pedagogical_context`` — minimal single-turn teaching situation.
* ``learner`` — explicitly supplied, pedagogically relevant learner info.
* ``pedagogical_intent`` — exactly one primary intent from the six-way
  TeachIntent v1 control set (docs/pedagogical_intents.md section 4).
  Secondary/compositional intents are not part of the v1 standard-case input
  schema; ``out_of_scope`` is not a generation-time intent.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator

from .base import StrictModel
from .constraints import (
    validate_bcp47,
    validate_non_empty_string,
)

NonEmptyStr = Annotated[str, AfterValidator(validate_non_empty_string)]
Bcp47LanguageTag = Annotated[str, AfterValidator(validate_bcp47)]


class PedagogicalPrimary(str, Enum):
    """The six pedagogical intents (docs/pedagogical_intents.md section 4).

    TeachIntent does not ask the planner to choose the intent: the intent is
    supplied, not inferred (problem_definition.md section 9.1).
    """

    ELICITATION = "elicitation"
    SCAFFOLDING = "scaffolding"
    EXPLANATION = "explanation"
    CORRECTIVE_FEEDBACK = "corrective_feedback"
    SUPPORTIVE_FEEDBACK = "supportive_feedback"
    EXTENSION = "extension"


class InstructionalContent(StrictModel):
    """problem_definition.md section 4.3."""

    subject: Optional[NonEmptyStr] = None
    topic: Optional[NonEmptyStr] = None
    content_anchor: NonEmptyStr


class PedagogicalContext(StrictModel):
    """problem_definition.md section 4.4 (minimal single-turn context)."""

    scenario: NonEmptyStr
    learner_utterance: Optional[NonEmptyStr] = None


class Learner(StrictModel):
    """problem_definition.md section 4.5.

    Safety: only explicitly supplied and pedagogically relevant learner
    information.  The contract layer never infers sensitive attributes.
    """

    level: NonEmptyStr
    knowledge_state: NonEmptyStr
    affective_state: Optional[NonEmptyStr] = None


class PedagogicalIntent(StrictModel):
    """problem_definition.md section 4.6 / docs/pedagogical_intents.md."""

    primary: PedagogicalPrimary


class TeachIntentInput(StrictModel):
    """Root model of the TeachIntent Input Contract."""

    schema_version: Literal["1.0.0-rc.2"]
    output_language: Bcp47LanguageTag
    instructional_content: InstructionalContent
    pedagogical_context: PedagogicalContext
    learner: Learner
    pedagogical_intent: PedagogicalIntent
