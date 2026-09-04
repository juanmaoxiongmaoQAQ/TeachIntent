import { describe, expect, it } from "vitest";

import {
  classifyEvidenceSource,
  evidenceTextsForContextField,
  evidenceTextsForDeliveryField,
  evidenceTextsForVerbalSegment,
  resolveEvidenceTarget,
  resolveJudgmentEvidence,
} from "./evidence";
import type { DimensionJudgment } from "../types/teachintent";

describe("evidence routing", () => {
  it("classifies known source areas conservatively", () => {
    expect(
      classifyEvidenceSource("input.instructional_content.content_anchor"),
    ).toBe("context");
    expect(
      classifyEvidenceSource("plan.delivery_plan.global.attitudinal_tone"),
    ).toBe("speech");
    expect(classifyEvidenceSource("other.value")).toBe("unknown");
  });

  it("routes D2 content anchor evidence to context", () => {
    const target = resolveEvidenceTarget({
      source: "input.instructional_content.content_anchor",
      text: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
    });

    expect(target.resolved).toBe(true);
    expect(target.contextField).toBe("instructional_content.content_anchor");
    expect(target.label).toBe("Teaching Context · Content anchor");
  });

  it("routes D6 tone evidence to speech delivery", () => {
    const target = resolveEvidenceTarget({
      source: "plan.delivery_plan.global.attitudinal_tone",
      text: "安抚但纠正",
    });

    expect(target.resolved).toBe(true);
    expect(target.deliveryField).toBe("delivery_plan.global.attitudinal_tone");
    expect(target.label).toBe("Speech Plan · Attitudinal tone");
  });

  it("preserves multi evidence across context, speech, and unknown sources", () => {
    const judgment: DimensionJudgment = {
      score: 4,
      evidence: [
        {
          source: "input.pedagogical_context.scenario",
          text: "slightly frustrated",
        },
        {
          source: "plan.verbal_plan.segments[1].text",
          text: "second segment",
        },
        {
          source: "unmapped.source",
          text: "must not be dropped",
        },
      ],
      brief_justification: "Grounded.",
    };

    const targets = resolveJudgmentEvidence(judgment);

    expect(targets).toHaveLength(3);
    expect(
      evidenceTextsForContextField(targets, "pedagogical_context.scenario"),
    ).toEqual(["slightly frustrated"]);
    expect(evidenceTextsForVerbalSegment(targets, 1)).toEqual([
      "second segment",
    ]);
    expect(targets[2]).toMatchObject({
      resolved: false,
      label: "Unresolved grounded excerpt",
      text: "must not be dropped",
    });
  });

  it("finds delivery field evidence without guessing", () => {
    const target = resolveEvidenceTarget({
      source: "speech_plan.delivery_plan.global.prosody.speaking_rate",
      text: "slow",
    });

    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.global.prosody.speaking_rate",
      ),
    ).toEqual(["slow"]);
    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.global.prosody.volume",
      ),
    ).toEqual([]);
  });

  it("routes segment-level scalar delivery evidence", () => {
    const target = resolveEvidenceTarget({
      source: "plan.delivery_plan.segment_overrides[0].emotion",
      text: "calm",
    });

    expect(target.resolved).toBe(true);
    expect(target.deliveryField).toBe(
      "delivery_plan.segment_overrides[0].emotion",
    );
    expect(target.label).toBe("Speech Plan · Segment control 1 · Emotion");
  });

  it("routes segment-level prosody evidence", () => {
    const target = resolveEvidenceTarget({
      source: "plan.delivery_plan.segment_overrides[2].prosody.pitch_range",
      text: "narrow",
    });

    expect(target.resolved).toBe(true);
    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.segment_overrides[2].prosody.pitch_range",
      ),
    ).toEqual(["narrow"]);
  });

  it("routes canonical JSON prominence evidence to exact child fields", () => {
    const target = resolveEvidenceTarget({
      source: "plan.delivery_plan.segment_overrides[0].prominence_targets[0]",
      text: '{"level":"moderate","text":"方向在变化"}',
    });

    expect(target.resolved).toBe(true);
    expect(target.deliveryField).toBe(
      "delivery_plan.segment_overrides[0].prominence_targets[0]",
    );
    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.segment_overrides[0].prominence_targets[0].text",
      ),
    ).toEqual(["方向在变化"]);
    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.segment_overrides[0].prominence_targets[0].level",
      ),
    ).toEqual(["moderate"]);
  });

  it("routes direct prominence child evidence", () => {
    const target = resolveEvidenceTarget({
      source: "plan.delivery_plan.segment_overrides[0].prominence_targets[1].text",
      text: "方向在变化",
    });

    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.segment_overrides[0].prominence_targets[1].text",
      ),
    ).toEqual(["方向在变化"]);
  });

  it("routes boundary object evidence to strength", () => {
    const target = resolveEvidenceTarget({
      source: "plan.delivery_plan.segment_overrides[0].boundary_after",
      text: '{"strength":"medium"}',
    });

    expect(target.resolved).toBe(true);
    expect(
      evidenceTextsForDeliveryField(
        [target],
        "delivery_plan.segment_overrides[0].boundary_after.strength",
      ),
    ).toEqual(["medium"]);
  });
});
