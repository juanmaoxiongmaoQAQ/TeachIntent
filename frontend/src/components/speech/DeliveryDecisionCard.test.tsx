import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeliveryDecisionCard } from "./DeliveryDecisionCard";

describe("DeliveryDecisionCard", () => {
  it("renders empty delivery as an explicit default decision", () => {
    render(<DeliveryDecisionCard deliveryPlan={{}} evidenceTargets={[]} />);

    expect(screen.getByText("Default rendering selected")).toBeInTheDocument();
    expect(
      screen.getByText(
        "TeachIntent selected no additional delivery control for this case.",
      ),
    ).toBeInTheDocument();
  });

  it("highlights selected D6 tone evidence", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{ global: { attitudinal_tone: "安抚但纠正" } }}
        evidenceTargets={[
          {
            area: "speech",
            source: "plan.delivery_plan.global.attitudinal_tone",
            text: "安抚但纠正",
            deliveryField: "delivery_plan.global.attitudinal_tone",
            label: "Speech Plan · Attitudinal tone",
            resolved: true,
          },
        ]}
      />,
    );

    expect(screen.getByText("Selective delivery control added")).toBeInTheDocument();
    expect(screen.getByText("安抚但纠正").tagName).toBe("MARK");
  });

  it("renders global only as selective delivery control", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{
          global: {
            prosody: {
              speaking_rate: "slow",
              pitch_level: "medium",
              pitch_range: "narrow",
              volume: "soft",
            },
          },
        }}
        evidenceTargets={[]}
      />,
    );

    expect(screen.getByText("Selective delivery control added")).toBeInTheDocument();
    expect(screen.queryByText("Default rendering selected")).not.toBeInTheDocument();
    expect(screen.getByText("Global control")).toBeInTheDocument();
    expect(screen.getByText("slow")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(screen.getByText("narrow")).toBeInTheDocument();
    expect(screen.getByText("soft")).toBeInTheDocument();
  });

  it("renders segment overrides only as selective delivery control", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{
          segment_overrides: [
            {
              segment_id: "seg_02",
              prominence_targets: [{ text: "方向在变化", level: "moderate" }],
            },
          ],
        }}
        evidenceTargets={[]}
      />,
    );

    expect(screen.getByText("Selective delivery control added")).toBeInTheDocument();
    expect(screen.queryByText("Default rendering selected")).not.toBeInTheDocument();
    expect(screen.getByText("Segment controls")).toBeInTheDocument();
    expect(screen.getByText("seg_02")).toBeInTheDocument();
    expect(screen.getByText("Prominence target")).toBeInTheDocument();
    expect(screen.getByText("方向在变化")).toBeInTheDocument();
    expect(screen.getByText("moderate")).toBeInTheDocument();
  });

  it("renders boundary_after strength", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{
          segment_overrides: [
            {
              segment_id: "seg_01",
              boundary_after: { strength: "medium" },
            },
          ],
        }}
        evidenceTargets={[]}
      />,
    );

    expect(screen.getByText("Boundary after")).toBeInTheDocument();
    expect(screen.getByText("Strength")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("renders segment prosody and contour fields", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{
          segment_overrides: [
            {
              segment_id: "seg_01",
              attitudinal_tone: "encouraging",
              emotion: "calm",
              contour_shape: "rising",
              prosody: {
                speaking_rate: "slow",
                pitch_level: "medium",
                pitch_range: "narrow",
                volume: "soft",
              },
            },
          ],
        }}
        evidenceTargets={[]}
      />,
    );

    expect(screen.getByText("encouraging")).toBeInTheDocument();
    expect(screen.getByText("calm")).toBeInTheDocument();
    expect(screen.getByText("rising")).toBeInTheDocument();
    expect(screen.getByText("slow")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(screen.getByText("narrow")).toBeInTheDocument();
    expect(screen.getByText("soft")).toBeInTheDocument();
  });

  it("renders global and segment controls together", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{
          global: { attitudinal_tone: "supportive" },
          segment_overrides: [
            {
              segment_id: "seg_02",
              prominence_targets: [{ text: "关键变化", level: "strong" }],
            },
          ],
        }}
        evidenceTargets={[]}
      />,
    );

    expect(screen.getByText("Global control")).toBeInTheDocument();
    expect(screen.getByText("Segment controls")).toBeInTheDocument();
    expect(screen.getByText("supportive")).toBeInTheDocument();
    expect(screen.getByText("关键变化")).toBeInTheDocument();
  });

  it("focuses canonical JSON prominence evidence on target fields", () => {
    render(
      <DeliveryDecisionCard
        deliveryPlan={{
          segment_overrides: [
            {
              segment_id: "seg_02",
              prominence_targets: [{ text: "方向在变化", level: "moderate" }],
            },
          ],
        }}
        evidenceTargets={[
          {
            area: "speech",
            source: "plan.delivery_plan.segment_overrides[0].prominence_targets[0]",
            text: '{"level":"moderate","text":"方向在变化"}',
            deliveryField:
              "delivery_plan.segment_overrides[0].prominence_targets[0]",
            evidenceValues: {
              "delivery_plan.segment_overrides[0].prominence_targets[0].text":
                "方向在变化",
              "delivery_plan.segment_overrides[0].prominence_targets[0].level":
                "moderate",
            },
            label: "Speech Plan · Segment control 1 · Prominence target 1",
            resolved: true,
          },
        ]}
      />,
    );

    expect(screen.getByText("方向在变化").tagName).toBe("MARK");
    expect(screen.getByText("moderate").tagName).toBe("MARK");
  });
});
