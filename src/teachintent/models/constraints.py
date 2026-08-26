"""Shared constants and string-validation helpers for the TeachIntent contracts.

This module is the single source of truth for pattern strings and character
sets that must stay byte-identical between the JSON Schema files
(``schemas/*.schema.json``) and the Pydantic model layer.

Layer parity discipline
-----------------------
``jsonschema`` evaluates ``pattern`` with Python ``re.search``.  Wherever the
Pydantic layer applies a regex, it must call ``re.search`` with the *identical
pattern-string constant* defined here, so that both layers are evaluated by
the same engine and the same API and therefore agree by construction.

Regex engine note
-----------------
Python ``re`` anchors ``$`` before a trailing newline (ECMA-262 does not).
Anchored patterns (``segment_id``, ``output_language``) therefore carry a
sibling ``NO_LINE_BREAK_PATTERN`` guard, mirroring the ``allOf`` pattern pairs
in the JSON Schema files, so that e.g. ``"seg_01\\n"`` is rejected exactly as
the declared ECMA-262 semantics of the specification require.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Schema versions (must match docs/problem_definition.md and
# docs/speech_plan_schema.md; the two versions evolve independently by design).
# ---------------------------------------------------------------------------
INPUT_SCHEMA_VERSION = "1.0.0-rc.2"
SPEECH_PLAN_SCHEMA_VERSION = "1.0.0-rc.3"

# ---------------------------------------------------------------------------
# Pattern constants (kept identical to the pattern strings in the JSON Schema
# files; see the module docstring for the parity discipline).
# ---------------------------------------------------------------------------
SEGMENT_ID_PATTERN = r"^seg_[0-9]{2,}$"

# Lightweight/common BCP-47 syntax subset for supported TeachIntent languages
# (zh-CN, en-US, yue-Hant-HK, ...).  This is NOT a full BCP-47 validator.
BCP47_PATTERN = r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$"

NON_WHITESPACE_PATTERN = r"\S"

# Line-break guard neutralizing the Python re '$' trailing-newline quirk.
NO_LINE_BREAK_PATTERN = r"^(?!.*[\n\r\u2028\u2029])"

# Explicit whitespace class shared with the JSON Schema styleDescriptor
# patterns (22 code points; engine-neutral between Python re and ECMA-262).
WS_CHARS = (
    " \t\n\r\f\v"
    "\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)

# ECMAScript line terminators (engineering interpretation: deliberately
# narrower than Python str.splitlines()).
LINE_BREAK_CHARS = "\n\r\u2028\u2029"

STYLE_DESCRIPTOR_MAX_LENGTH = 64


# ---------------------------------------------------------------------------
# Primitive checks (plain string operations; no regex anchor quirks).
# ---------------------------------------------------------------------------
def contains_non_whitespace(value: str) -> bool:
    """Return True if *value* contains at least one non-whitespace character."""
    return any(ch not in WS_CHARS for ch in value)


def is_trimmed(value: str) -> bool:
    """Return True if *value* carries no leading/trailing WS_CHARS whitespace."""
    return value.strip(WS_CHARS) == value


def has_line_breaks(value: str) -> bool:
    """Return True if *value* contains any LINE_BREAK_CHARS character."""
    return any(ch in LINE_BREAK_CHARS for ch in value)


# ---------------------------------------------------------------------------
# Field validators (raise ValueError with rule-tagged messages).
# ---------------------------------------------------------------------------
def validate_non_empty_string(value: str) -> str:
    """Non-empty string containing at least one non-whitespace character."""
    if not isinstance(value, str) or not contains_non_whitespace(value):
        raise ValueError(
            "must be a non-empty string containing at least one "
            f"non-whitespace character (got {value!r})"
        )
    return value


def validate_style_descriptor(value: str) -> str:
    """Rule 13 (style descriptor normalization), strict-trim interpretation.

    ``attitudinal_tone`` / ``emotion`` must arrive trimmed: leading/trailing
    whitespace is rejected rather than silently stripped, because JSON Schema
    patterns cannot normalize and strict rejection is the only behaviour
    consistent across both validation layers.
    """
    if has_line_breaks(value):
        raise ValueError(
            "Rule 13 (style descriptor normalization): must not contain line "
            f"breaks (got {value!r})"
        )
    if not is_trimmed(value):
        raise ValueError(
            "Rule 13 (style descriptor normalization): must be trimmed "
            f"(got {value!r})"
        )
    if not 1 <= len(value) <= STYLE_DESCRIPTOR_MAX_LENGTH:
        raise ValueError(
            "Rule 13 (style descriptor normalization): must be 1-"
            f"{STYLE_DESCRIPTOR_MAX_LENGTH} Unicode characters after trimming "
            f"(got length {len(value)})"
        )
    if not contains_non_whitespace(value):
        raise ValueError(
            "Rule 13 (style descriptor normalization): must contain "
            f"non-whitespace content (got {value!r})"
        )
    return value


def validate_segment_id(value: str) -> str:
    """Segment id pattern ``^seg_[0-9]{2,}$`` plus the line-break guard."""
    if (
        not isinstance(value, str)
        or re.search(SEGMENT_ID_PATTERN, value) is None
        or re.search(NO_LINE_BREAK_PATTERN, value) is None
    ):
        raise ValueError(
            "segment_id must match ^seg_[0-9]{2,}$ "
            f"(docs/speech_plan_schema.md section 5.2; got {value!r})"
        )
    return value


def validate_bcp47(value: str) -> str:
    """Lightweight/common BCP-47 syntax subset (not a full BCP-47 validator)."""
    if (
        not isinstance(value, str)
        or re.search(BCP47_PATTERN, value) is None
        or re.search(NO_LINE_BREAK_PATTERN, value) is None
    ):
        raise ValueError(
            "output_language must be a well-formed language tag from the "
            "lightweight/common BCP-47 syntax subset supported by TeachIntent "
            f"(e.g. zh-CN, en-US, yue-Hant-HK; got {value!r})"
        )
    return value
