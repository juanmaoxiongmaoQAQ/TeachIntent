"""Strict base model shared by all TeachIntent contract models.

Two guarantees mirror JSON Schema semantics exactly:

1. ``extra="forbid"`` — unknown fields are rejected (Rule 6 mirror in
   docs/speech_plan_schema.md; applied to every controlled object).
2. Explicit ``null`` rejection — JSON Schema rejects ``{"subject": null}``
   (type error) while allowing the field to be omitted.  A naive
   ``X | None = None`` Pydantic field would happily accept explicit nulls,
   which would make the two layers diverge.  No field in either contract is
   legitimately null-valued, so rejecting "explicitly provided and None"
   mirrors JSON Schema exactly: omit the field instead.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class StrictModel(BaseModel):
    """Base class for all TeachIntent contract models."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _reject_explicit_none(self) -> "StrictModel":
        for name in self.model_fields_set:
            if getattr(self, name, None) is None:
                raise ValueError(
                    f"{name}: explicit null is not allowed; omit the field "
                    "instead"
                )
        return self
