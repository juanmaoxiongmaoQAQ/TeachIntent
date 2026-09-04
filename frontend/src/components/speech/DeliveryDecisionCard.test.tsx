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
});
