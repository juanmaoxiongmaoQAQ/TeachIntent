import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { PlanView } from "./PlanView";
import { deliveryFor } from "../../lib/product";
it("attaches Chinese delivery to its own step and keeps absent controls absent", () => {
  const plan = {
    schema_version: "1.0.0-rc.3",
    verbal_plan: {
      segments: [
        { segment_id: "seg_01", text: "先理解分母。" },
        { segment_id: "seg_02", text: "再比较大小。" },
      ],
    },
    delivery_plan: {
      segment_overrides: [
        {
          segment_id: "seg_01",
          prosody: { volume: "soft" as const, pitch_level: "high" as const },
        },
      ],
    },
  };
  render(<PlanView plan={plan} />);
  expect(screen.getByText(/柔和/)).toBeVisible();
  expect(screen.getByText(/适度提高语调/)).toBeVisible();
  expect(screen.getByText("本段无需额外表达控制")).toBeVisible();
  expect(screen.queryByText("{}")).not.toBeInTheDocument();
  expect(screen.queryByText(/pitch_level/)).not.toBeInTheDocument();
});
it("inherits global fields, overrides matching local fields and never mutates the plan", () => {
  const delivery = {
    global: {
      prosody: { volume: "soft" as const, pitch_level: "low" as const },
    },
    segment_overrides: [
      { segment_id: "seg_02", prosody: { volume: "loud" as const } },
    ],
  };
  const original = JSON.stringify(delivery);
  expect(deliveryFor(delivery, "seg_01")).toEqual(["柔和", "适度降低语调"]);
  expect(deliveryFor(delivery, "seg_02")).toEqual([
    "增强表达力度",
    "适度降低语调",
  ]);
  expect(JSON.stringify(delivery)).toBe(original);
  expect(deliveryFor({}, "seg_01")).toEqual([]);
});
