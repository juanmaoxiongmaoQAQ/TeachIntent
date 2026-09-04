import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Workbench } from "./Workbench";
import type {
  EvaluationArtifact,
  SpeechPlan,
  TeachIntentInput,
} from "../../types/teachintent";

const input: TeachIntentInput = {
  schema_version: "1.0.0-rc.2",
  output_language: "zh-CN",
  instructional_content: {
    content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
  },
  pedagogical_context: {
    scenario: "学生混淆速度大小不变和零加速度。",
  },
  learner: {
    level: "high_school",
    knowledge_state: "misconception",
  },
  pedagogical_intent: {
    primary: "corrective_feedback",
  },
};

const speechPlan: SpeechPlan = {
  schema_version: "1.0.0-rc.3",
  verbal_plan: {
    segments: [
      {
        segment_id: "seg_02",
        text: "汽车转弯时速度大小没变，但方向在变化，所以加速度不为0。",
      },
    ],
  },
  delivery_plan: {
    segment_overrides: [
      {
        segment_id: "seg_02",
        prominence_targets: [{ text: "方向在变化", level: "moderate" }],
      },
    ],
  },
};

const evaluation: EvaluationArtifact = {
  available: true,
  evaluator_version: "v0.1",
  judge_prompt_version: "v0.1",
  source_run_id: null,
  critical_flags: [],
  scores: {
    pedagogical_intent_fidelity: {
      score: 4,
      evidence: [
        {
          source: "plan.verbal_plan.segments[0].text",
          text: "汽车转弯时速度大小没变，但方向在变化，所以加速度不为0。",
        },
      ],
      brief_justification: "D1 grounded.",
    },
    content_faithfulness_boundary: {
      score: 4,
      evidence: [
        {
          source: "input.instructional_content.content_anchor",
          text: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
        },
      ],
      brief_justification: "D2 grounded.",
    },
    delivery_pedagogy_alignment: {
      score: 4,
      evidence: [
        {
          source: "plan.delivery_plan.segment_overrides[0].prominence_targets[0]",
          text: '{"level":"moderate","text":"方向在变化"}',
        },
      ],
      brief_justification: "D6 grounded.",
    },
  },
};

describe("Workbench segment delivery evidence focus", () => {
  it("highlights segment prominence for D6 and clears it when switching to D2", async () => {
    const user = userEvent.setup();
    render(
      <Workbench
        mode="live"
        input={input}
        speechPlan={speechPlan}
        evaluation={evaluation}
      />,
    );

    await user.click(screen.getByText("Delivery Alignment"));

    expect(screen.getByText("方向在变化").tagName).toBe("MARK");
    expect(screen.getByText("moderate").tagName).toBe("MARK");

    await user.click(screen.getByText("Content Faithfulness"));

    expect(
      screen
        .getAllByText("方向在变化")
        .some((node) => node.tagName === "MARK"),
    ).toBe(false);
    expect(
      screen
        .getAllByText("moderate")
        .some((node) => node.tagName === "MARK"),
    ).toBe(false);
    expect(
      screen
        .getAllByText("即使速度大小不变，只要方向发生变化，加速度也不为0。")
        .some((node) => node.tagName === "MARK"),
    ).toBe(true);
  });
});
