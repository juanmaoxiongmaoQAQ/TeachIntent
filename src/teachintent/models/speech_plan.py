"""Pydantic models for the TeachIntent Speech Plan.

Source of truth: ``docs/speech_plan_schema.md`` (Schema Version
``1.0.0-rc.3``).  Together with ``schemas/speech_plan.schema.json`` this
module implements the Rule 15 division of labor:

* JSON Schema — structural constraints (required fields, types, enums,
  ``const``, ``minItems``, ``minLength``/``maxLength``, object shape,
  ``additionalProperties: false``);
* Pydantic model validators — cross-field semantic constraints:
  Rule 1 (segment id uniqueness), Rule 2 (reference integrity),
  Rule 3 (one override per segment), Rule 5 (prominence span integrity),
  Rule 8 (contour conflict), Rule 11 (meaningful ``default`` reset),
  Rule 12 (prominence non-overlap).

Structural constraints are additionally mirrored here (``extra="forbid"``
via :class:`~teachintent.models.base.StrictModel`, enums, field validators,
``Literal`` schema_version, ``min_length`` on lists) as defense in depth.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from .base import StrictModel
from .constraints import (
    validate_non_empty_string,
    validate_segment_id,
    validate_style_descriptor,
)

NonEmptyStr = Annotated[str, AfterValidator(validate_non_empty_string)]
SegmentId = Annotated[str, AfterValidator(validate_segment_id)]
StyleDescriptor = Annotated[str, AfterValidator(validate_style_descriptor)]

#: Prosody field names shared by global and segment-level prosody objects.
PROSODY_FIELDS = ("speaking_rate", "pitch_level", "pitch_range", "volume")


# ---------------------------------------------------------------------------
# Enums (categorical SSML-style subset; no fabricated acoustic precision).
# ---------------------------------------------------------------------------
class GlobalSpeakingRate(str, Enum):
    """docs/speech_plan_schema.md section 7.1 (no ``default`` at global)."""

    X_SLOW = "x-slow"
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    X_FAST = "x-fast"


class SegmentSpeakingRate(str, Enum):
    """docs/speech_plan_schema.md section 8.2 (``default`` = reset)."""

    DEFAULT = "default"
    X_SLOW = "x-slow"
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    X_FAST = "x-fast"


class GlobalPitchLevel(str, Enum):
    """Section 7.2: relative pitch level, not absolute F0."""

    X_LOW = "x-low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    X_HIGH = "x-high"


class SegmentPitchLevel(str, Enum):
    """Section 8.2 (``default`` = reset)."""

    DEFAULT = "default"
    X_LOW = "x-low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    X_HIGH = "x-high"


class GlobalPitchRange(str, Enum):
    """Section 7.3: degree of pitch variability."""

    X_LOW = "x-low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    X_HIGH = "x-high"


class SegmentPitchRange(str, Enum):
    """Section 8.2 (``default`` = reset)."""

    DEFAULT = "default"
    X_LOW = "x-low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    X_HIGH = "x-high"


class GlobalVolume(str, Enum):
    """Section 7.4 (``silent`` intentionally omitted in v1)."""

    X_SOFT = "x-soft"
    SOFT = "soft"
    MEDIUM = "medium"
    LOUD = "loud"
    X_LOUD = "x-loud"


class SegmentVolume(str, Enum):
    """Section 8.2 (``default`` = reset)."""

    DEFAULT = "default"
    X_SOFT = "x-soft"
    SOFT = "soft"
    MEDIUM = "medium"
    LOUD = "loud"
    X_LOUD = "x-loud"


class ContourShape(str, Enum):
    """Section 9: coarse segment/phrase-level intonation movement."""

    LEVEL = "level"
    RISING = "rising"
    FALLING = "falling"
    RISE_FALL = "rise-fall"
    FALL_RISE = "fall-rise"


class ProminenceLevel(str, Enum):
    """Section 10.2: only spans intended to stand out."""

    MODERATE = "moderate"
    STRONG = "strong"


class BoundaryStrength(str, Enum):
    """Section 11.1: prosodic boundary strength after a segment."""

    NONE = "none"
    X_WEAK = "x-weak"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    X_STRONG = "x-strong"


# ---------------------------------------------------------------------------
# Prominence span helpers (Rules 5 and 12).
# ---------------------------------------------------------------------------
def count_occurrences(haystack: str, needle: str) -> int:
    """Count occurrences of *needle* in *haystack*, overlapping included.

    Overlapping occurrences are counted deliberately: ``"哈哈"`` occurs twice
    in ``"哈哈哈"`` under overlapping-inclusive counting, and such ambiguous
    targets must be rejected (Rule 5) because span resolution would be
    ambiguous.  ``str.count`` (non-overlapping) is intentionally not used.
    """
    count = 0
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index == -1:
            return count
        count += 1
        start = index + 1


def resolve_span(haystack: str, needle: str) -> tuple[int, int]:
    """Resolve the character span of the unique occurrence of *needle*.

    Only call after Rule 5 established exactly-once occurrence.
    """
    index = haystack.find(needle)
    return (index, index + len(needle))


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """True if half-open spans *a* and *b* intersect (adjacent is legal)."""
    return a[0] < b[1] and b[0] < a[1]


# ---------------------------------------------------------------------------
# Models.
# ---------------------------------------------------------------------------
class Segment(StrictModel):
    """Section 5: one verbal segment. Array order is canonical."""

    segment_id: SegmentId
    text: NonEmptyStr


class VerbalPlan(StrictModel):
    """Section 5.1: what the teacher should say."""

    segments: list[Segment] = Field(min_length=1)

    @model_validator(mode="after")
    def _rule_1_unique_segment_ids(self) -> "VerbalPlan":
        ids = [segment.segment_id for segment in self.segments]
        duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
        if duplicates:
            raise ValueError(
                "Rule 1 (segment ID uniqueness): duplicate segment_id "
                f"values {duplicates}"
            )
        return self


class GlobalProsody(StrictModel):
    """Section 6.3 / 7: global categorical prosody (no ``default``)."""

    speaking_rate: Optional[GlobalSpeakingRate] = None
    pitch_level: Optional[GlobalPitchLevel] = None
    pitch_range: Optional[GlobalPitchRange] = None
    volume: Optional[GlobalVolume] = None

    @model_validator(mode="after")
    def _rule_7_non_empty(self) -> "GlobalProsody":
        if all(getattr(self, name) is None for name in PROSODY_FIELDS):
            raise ValueError(
                "Rule 7 (empty-object policy): prosody must contain at "
                "least one control field"
            )
        return self


class SegmentProsody(StrictModel):
    """Section 8.2 / 8.5: segment-level prosody (``default`` = reset)."""

    speaking_rate: Optional[SegmentSpeakingRate] = None
    pitch_level: Optional[SegmentPitchLevel] = None
    pitch_range: Optional[SegmentPitchRange] = None
    volume: Optional[SegmentVolume] = None

    @model_validator(mode="after")
    def _rule_7_non_empty(self) -> "SegmentProsody":
        if all(getattr(self, name) is None for name in PROSODY_FIELDS):
            raise ValueError(
                "Rule 7 (empty-object policy): prosody must contain at "
                "least one control field"
            )
        return self


class GlobalDelivery(StrictModel):
    """Section 6: optional utterance-level delivery baseline."""

    attitudinal_tone: Optional[StyleDescriptor] = None
    emotion: Optional[StyleDescriptor] = None
    prosody: Optional[GlobalProsody] = None

    @model_validator(mode="after")
    def _rule_7_non_empty(self) -> "GlobalDelivery":
        if all(
            getattr(self, name) is None
            for name in ("attitudinal_tone", "emotion", "prosody")
        ):
            raise ValueError(
                "Rule 7 (empty-object policy): global must contain at least "
                "one control (attitudinal_tone, emotion, or prosody)"
            )
        return self


class ProminenceTarget(StrictModel):
    """Section 10: a local linguistic span that should stand out."""

    text: NonEmptyStr
    level: ProminenceLevel


class BoundaryAfter(StrictModel):
    """Section 11: prosodic boundary control after a segment."""

    strength: BoundaryStrength


class SegmentOverride(StrictModel):
    """Section 8: sparse segment-level override."""

    segment_id: SegmentId
    attitudinal_tone: Optional[StyleDescriptor] = None
    emotion: Optional[StyleDescriptor] = None
    prosody: Optional[SegmentProsody] = None
    contour_shape: Optional[ContourShape] = None
    prominence_targets: Optional[list[ProminenceTarget]] = Field(
        default=None, min_length=1
    )
    boundary_after: Optional[BoundaryAfter] = None

    @model_validator(mode="after")
    def _rules_4_and_8(self) -> "SegmentOverride":
        control_names = (
            "attitudinal_tone",
            "emotion",
            "prosody",
            "contour_shape",
            "prominence_targets",
            "boundary_after",
        )
        # Rule 4 — at least one actual control besides segment_id.
        if all(getattr(self, name) is None for name in control_names):
            raise ValueError(
                f"Rule 4 (non-empty override): the override for "
                f"{self.segment_id} must contain at least one control "
                "besides segment_id"
            )
        # Rule 8 — contour_shape vs segment-level pitch_level / pitch_range.
        # Coexistence with speaking_rate / volume is legal, and a global
        # pitch baseline may still exist (section 9.1).
        if self.contour_shape is not None and self.prosody is not None:
            conflicts = [
                name
                for name in ("pitch_level", "pitch_range")
                if getattr(self.prosody, name) is not None
            ]
            if conflicts:
                raise ValueError(
                    f"Rule 8 (contour conflict): contour_shape must not "
                    f"coexist with segment-level {conflicts} in segment "
                    f"{self.segment_id} (a global pitch baseline may still "
                    "exist)"
                )
        return self


class DeliveryPlan(StrictModel):
    """Sections 3.4 / 4.3: optional global baseline + sparse overrides.

    The top-level ``delivery_plan`` may be empty (``{}``), meaning no
    explicit TeachIntent control is motivated.  ``global`` uses a field
    alias because ``global`` is a Python keyword.  Validation accepts ONLY
    the alias ``"global"`` (the equivalent of validate_by_alias=True /
    validate_by_name=False, achieved by leaving populate_by_name off, which
    is Pydantic's default for aliased fields and stays compatible with the
    pydantic>=2.7 floor); the Python field name ``global_delivery`` is
    rejected as an unknown key, mirroring the JSON Schema, which knows no
    other spelling.  Serialization must use
    ``model_dump(by_alias=True, exclude_none=True)``.
    """

    model_config = ConfigDict(extra="forbid")

    global_delivery: Optional[GlobalDelivery] = Field(
        default=None, alias="global"
    )
    segment_overrides: Optional[list[SegmentOverride]] = Field(
        default=None, min_length=1
    )

    @model_validator(mode="after")
    def _rules_3_and_11(self) -> "DeliveryPlan":
        overrides = self.segment_overrides or []

        # Rule 3 — at most one override per segment.
        ids = [override.segment_id for override in overrides]
        duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
        if duplicates:
            raise ValueError(
                "Rule 3 (one override per segment): multiple overrides for "
                f"segment_id values {duplicates}"
            )

        # Rule 11 — a segment-level "default" is valid only when the same
        # field is defined in global prosody (otherwise it is a redundant
        # no-op that must be omitted).
        global_prosody_fields = set()
        if (
            self.global_delivery is not None
            and self.global_delivery.prosody is not None
        ):
            global_prosody_fields = {
                name
                for name in PROSODY_FIELDS
                if getattr(self.global_delivery.prosody, name) is not None
            }
        for override in overrides:
            if override.prosody is None:
                continue
            for name in PROSODY_FIELDS:
                value = getattr(override.prosody, name)
                if (
                    value is not None
                    and value == "default"
                    and name not in global_prosody_fields
                ):
                    raise ValueError(
                        f"Rule 11 (meaningful default reset): segment "
                        f"{override.segment_id} sets prosody.{name}="
                        f"'default' but the corresponding global prosody "
                        "field is not present; the reset would be a "
                        "redundant no-op and must be omitted"
                    )
        return self


class SpeechPlan(StrictModel):
    """Root model of the TeachIntent Speech Plan."""

    schema_version: Literal["1.0.0-rc.3"]
    verbal_plan: VerbalPlan
    delivery_plan: DeliveryPlan

    @model_validator(mode="after")
    def _rules_2_5_and_12(self) -> "SpeechPlan":
        segments_by_id = {
            segment.segment_id: segment for segment in self.verbal_plan.segments
        }
        overrides = self.delivery_plan.segment_overrides or []

        # Rule 2 — reference integrity (checked before prominence spans).
        for override in overrides:
            if override.segment_id not in segments_by_id:
                raise ValueError(
                    "Rule 2 (segment reference integrity): override "
                    f"references unknown segment_id {override.segment_id!r}"
                )

        # Rules 5 and 12 — prominence span integrity and non-overlap.
        for override in overrides:
            targets = override.prominence_targets or []
            if not targets:
                continue
            segment_text = segments_by_id[override.segment_id].text
            resolved: list[tuple[str, tuple[int, int]]] = []
            for target in targets:
                occurrences = count_occurrences(segment_text, target.text)
                if occurrences == 0:
                    raise ValueError(
                        f"Rule 5 (prominence span integrity): target "
                        f"{target.text!r} is not an exact substring of "
                        f"segment {override.segment_id}"
                    )
                if occurrences > 1:
                    raise ValueError(
                        f"Rule 5 (prominence span integrity): target "
                        f"{target.text!r} occurs {occurrences} times in "
                        f"segment {override.segment_id}; choose a longer "
                        "unique span"
                    )
                resolved.append((target.text, resolve_span(segment_text, target.text)))
            for i in range(len(resolved)):
                for j in range(i + 1, len(resolved)):
                    if spans_overlap(resolved[i][1], resolved[j][1]):
                        raise ValueError(
                            "Rule 12 (prominence non-overlap): targets "
                            f"{resolved[i][0]!r} and {resolved[j][0]!r} "
                            "resolve to duplicate or overlapping spans in "
                            f"segment {override.segment_id}"
                        )
        return self
