"""Evidence path grammar, resolution, and grounding validation.

Implements the frozen evidence contract from ``docs/evaluator_spec_v0.1.md``
Section 17. Evidence paths MUST explicitly name one of two roots (``input`` or
``plan``) and follow the frozen selector grammar. Grounding is deterministic:
strings use exact-substring matching; scalars use canonical JSON
representation; objects/arrays use canonical JSON serialization.

These are evaluator-owned validation functions. They MUST NOT delegate to the
LLM for repair; a grounding failure produces ``evidence_grounding_error`` and a
path syntax/resolution failure produces ``evidence_source_error``
(Section 17.5).
"""

from __future__ import annotations

import json
import re
from typing import Any

from .errors import EvidenceSourceError, EvidenceGroundingError

__all__ = [
    "EVIDENCE_PATH_RE",
    "validate_evidence_path",
    "resolve_evidence_source",
    "canonical_scalar_text",
    "canonical_json_text",
    "is_grounded",
    "validate_evidence",
]

# Frozen evidence path grammar (Section 17.2):
#   path       := root selector*
#   root       := "input" | "plan"
#   selector   := "." field | "[" index "]"
#   field      := [A-Za-z_][A-Za-z0-9_]*
#   index      := "0" | [1-9][0-9]*
EVIDENCE_PATH_RE = re.compile(
    r"^(input|plan)(?:\.[A-Za-z_][A-Za-z0-9_]*|\[(?:0|[1-9][0-9]*)\])*$"
)


def validate_evidence_path(path: str) -> None:
    """Validate that *path* satisfies the frozen evidence path grammar.

    Raises :class:`EvidenceSourceError` on syntax failure.
    """
    if not isinstance(path, str) or not path:
        raise EvidenceSourceError(f"evidence source path is empty or not a string: {path!r}")
    if EVIDENCE_PATH_RE.match(path) is None:
        raise EvidenceSourceError(f"evidence source path does not satisfy frozen grammar: {path!r}")


def resolve_evidence_source(path: str, input_doc: dict, plan_doc: dict) -> Any:
    """Resolve *path* against the validated input/plan documents.

    Roots:
        ``input`` -> the validated TeachIntent input document;
        ``plan``  -> the validated Speech Plan document.

    For ``.field``, the current value MUST be a JSON object containing that
    exact key. For ``[index]``, the current value MUST be a JSON array and the
    index MUST be within bounds.

    Raises :class:`EvidenceSourceError` on any resolution failure.
    """
    validate_evidence_path(path)
    # Determine the root and the remaining selector string (including the
    # leading '.' or '[' selector prefix).
    if path == "input":
        return input_doc
    if path == "plan":
        return plan_doc
    if path.startswith("input."):
        root_name = "input"
        rest = path[len("input"):]  # includes leading '.'
    elif path.startswith("plan."):
        root_name = "plan"
        rest = path[len("plan"):]
    elif path.startswith("input["):
        root_name = "input"
        rest = path[len("input"):]
    elif path.startswith("plan["):
        root_name = "plan"
        rest = path[len("plan"):]
    else:  # pragma: no cover — grammar already validated
        raise EvidenceSourceError(f"unreachable: invalid root for path {path!r}")

    roots = {"input": input_doc, "plan": plan_doc}
    current: Any = roots[root_name]

    # Parse the remaining selectors. ``rest`` starts with '.' or '['.
    pos = 0
    while pos < len(rest):
        if rest[pos] == ".":
            # field selector
            pos += 1
            end = pos
            while end < len(rest) and (rest[end].isalnum() or rest[end] == "_"):
                end += 1
            field = rest[pos:end]
            if not field:
                raise EvidenceSourceError(f"empty field name in path {path!r}")
            if not isinstance(current, dict) or field not in current:
                raise EvidenceSourceError(
                    f"evidence source path {path!r}: key {field!r} not found "
                    f"in current object"
                )
            current = current[field]
            pos = end
        elif rest[pos] == "[":
            # index selector
            end = rest.index("]", pos)
            index_str = rest[pos + 1:end]
            if not re.match(r"^(?:0|[1-9][0-9]*)$", index_str):
                raise EvidenceSourceError(
                    f"evidence source path {path!r}: invalid index {index_str!r}"
                )
            index = int(index_str)
            if not isinstance(current, list):
                raise EvidenceSourceError(
                    f"evidence source path {path!r}: indexed into a non-array value"
                )
            if index < 0 or index >= len(current):
                raise EvidenceSourceError(
                    f"evidence source path {path!r}: index {index} out of bounds "
                    f"(length {len(current)})"
                )
            current = current[index]
            pos = end + 1
        else:  # pragma: no cover — grammar already validated
            raise EvidenceSourceError(f"unreachable: invalid selector at pos {pos} in {path!r}")

    return current


def canonical_scalar_text(value: Any) -> str:
    """Canonical JSON scalar representation for number/bool/null (Section 17.4).

    For a string, this is NOT used -- strings use exact-substring matching.
    """
    return json.dumps(value, ensure_ascii=False)


def canonical_json_text(value: Any) -> str:
    """Canonical JSON serialization for object/array values (Section 17.4)."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def is_grounded(evidence_text: str, resolved_value: Any) -> bool:
    """Check whether *evidence_text* is grounded in *resolved_value*.

    String value: ``evidence_text`` MUST be an exact substring.
    Number/bool/null: ``evidence_text`` MUST exactly equal its canonical JSON
    scalar representation.
    Object/array: ``evidence_text`` MUST be an exact substring of the canonical
    JSON serialization of the resolved value.
    """
    if isinstance(resolved_value, str):
        return evidence_text in resolved_value
    if isinstance(resolved_value, bool) or isinstance(resolved_value, (int, float)) or resolved_value is None:
        return evidence_text == canonical_scalar_text(resolved_value)
    # object or array
    return evidence_text in canonical_json_text(resolved_value)


def validate_evidence(
    source: str,
    text: str,
    input_doc: dict,
    plan_doc: dict,
) -> None:
    """Validate one evidence item end-to-end.

    Raises :class:`EvidenceSourceError` on path syntax/resolution failure, or
    :class:`EvidenceGroundingError` on text mismatch.
    """
    resolved = resolve_evidence_source(source, input_doc, plan_doc)
    if not is_grounded(text, resolved):
        raise EvidenceGroundingError(
            f"evidence text not grounded in resolved source {source!r}: "
            f"text={text!r}"
        )
