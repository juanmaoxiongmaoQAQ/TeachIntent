import math
import json

import pytest
from teachintent.generator.client import Hy3Completion
from teachintent.adapters.hy3_baton_conductor import Hy3BatonConductor

from teachintent.adapters.hy3_baton_conductor import (
    BatonPlanValidationError,
    decode_tool_plan,
    lexical_tokens,
    validate_baton_plan,
)

TEXT = "You are right."
VALID = [{
    "word": "You are right.",
    "pitch_mean": 226,
    "pitch_slope": 0,
    "energy_rms": 0.0081,
    "energy_slope": 0,
    "spectral_centroid": 1885,
}]


def test_valid_plan_canonicalizes_energy():
    assert validate_baton_plan(TEXT, VALID)[0]["energy_rms"] == 0.008


@pytest.mark.parametrize("field,value,expected", [
    ("pitch_mean", 226.0, 226),
    ("pitch_slope", -20.0, -20),
    ("energy_slope", 15.0, 15),
    ("spectral_centroid", 1885.0, 1885),
])
def test_integral_float_integer_fields_are_canonicalized(field, value, expected):
    plan = [{**VALID[0], field: value}]
    assert validate_baton_plan(TEXT, plan)[0][field] == expected


@pytest.mark.parametrize("mutator", [
    lambda p: p[0].pop("energy_slope"),
    lambda p: p[0].update(extra=1),
    lambda p: p[0].update(pitch_mean="226"),
    lambda p: p[0].update(energy_slope=12.5),
    lambda p: p[0].update(energy_slope="12"),
    lambda p: p[0].update(energy_slope=True),
    lambda p: p[0].update(energy_rms=math.nan),
    lambda p: p[0].update(energy_rms=math.inf),
    lambda p: p[0].update(word=""),
    lambda p: p[0].update(word="You are"),
    lambda p: p[0].update(word="You are right. now"),
    lambda p: p[0].update(word="right. are You"),
])
def test_invalid_plan_shapes_and_text(mutator):
    plan = [{**VALID[0]}]
    mutator(plan)
    with pytest.raises(BatonPlanValidationError):
        validate_baton_plan(TEXT, plan)


def test_empty_plan_rejected():
    with pytest.raises(BatonPlanValidationError):
        validate_baton_plan(TEXT, [])


@pytest.mark.parametrize("original,planned", [
    ("same,", "same"),
    ("direction.", "direction"),
    ("hello!", "hello"),
    ("don't", "don't"),
    ("state-of-the-art", "state-of-the-art"),
])
def test_lexical_coverage_allows_punctuation_only_changes(original, planned):
    assert lexical_tokens(original) == lexical_tokens(planned)


@pytest.mark.parametrize("original,planned", [
    ("hello world", "hello"),
    ("hello world", "hello brave world"),
    ("direction changes", "direction shifts"),
    ("speed remains constant", "constant speed remains"),
    ("don't", "dont"),
])
def test_lexical_coverage_rejects_content_changes(original, planned):
    assert lexical_tokens(original) != lexical_tokens(planned)


class FakeToolClient:
    model = "tencent/hy3"
    def __init__(self, calls):
        self.calls = calls
    def complete(self, *args, **kwargs):
        return Hy3Completion("", "tool_calls", self.model, tool_calls=self.calls)


def test_valid_tool_arguments_pass():
    tool_plan = [{**VALID[0], "energy_rms": None, "energy_rms_milli": 8}]
    tool_plan[0].pop("energy_rms")
    calls = [{"function": {"name": "emit_baton_plan", "arguments": json.dumps({"plan": tool_plan})}}]
    result = Hy3BatonConductor(FakeToolClient(calls)).conduct(
        content=TEXT, pedagogical_context="x", learner_information="y", pedagogical_intent="explanation", force_tool_call=True)
    assert result.plan[0]["word"] == TEXT


@pytest.mark.parametrize("calls", [
    [{"function": {"name": "emit_baton_plan", "arguments": json.dumps({"plan": [{**{k:v for k,v in VALID[0].items() if k != 'energy_rms'}, "energy_rms_milli": 17}]})}}],
    [{"function": {"name": "emit_baton_plan", "arguments": json.dumps({})}}],
    [{"function": {"name": "emit_baton_plan", "arguments": json.dumps({"plan": VALID})}}, {"function": {"name": "emit_baton_plan", "arguments": json.dumps({"plan": VALID})}}],
    [{"function": {"name": "other", "arguments": json.dumps({"plan": VALID})}}],
])
def test_invalid_tool_contracts_fail(calls):
    with pytest.raises(BatonPlanValidationError):
        Hy3BatonConductor(FakeToolClient(calls)).conduct(
            content=TEXT, pedagogical_context="x", learner_information="y", pedagogical_intent="explanation", force_tool_call=True)


@pytest.mark.parametrize("value,expected", [(4, 0.004), (8, 0.008), (16, 0.016)])
def test_energy_rms_milli_codec(value, expected):
    segment = {k: v for k, v in VALID[0].items() if k != "energy_rms"}
    segment["energy_rms_milli"] = value
    decoded = decode_tool_plan([segment])
    assert decoded[0]["energy_rms"] == expected
    assert validate_baton_plan(TEXT, decoded)


@pytest.mark.parametrize("value", [0, 17, 8.0, "8", True])
def test_energy_rms_milli_invalid(value):
    segment = {k: v for k, v in VALID[0].items() if k != "energy_rms"}
    segment["energy_rms_milli"] = value
    with pytest.raises(BatonPlanValidationError):
        decode_tool_plan([segment])
