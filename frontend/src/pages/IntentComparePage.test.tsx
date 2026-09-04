import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntentComparePage } from "./IntentComparePage";
import type { IntentCompareResponse } from "../types/teachintent";

function comparisonResponse(
  leftText = "纠正这个判断。",
  rightText = "先拆成一个小问题。",
): IntentCompareResponse {
  return {
    mode: "intent_compare",
    comparison: {
      changed_input_field: "input.pedagogical_intent.primary",
      left_intent: "corrective_feedback",
      right_intent: "scaffolding",
      all_other_input_fields_equal: true,
      prompt_version: "v0.2",
      same_prompt_version: true,
      same_requested_model: true,
    },
    base_context: {
      schema_version: "1.0.0-rc.2",
      output_language: "zh-CN",
      instructional_content: {
        content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
      },
      pedagogical_context: {
        scenario: "学生有些挫败。",
        learner_utterance: "汽车转弯的时候速度大小没变。",
      },
      learner: {
        level: "high_school",
        knowledge_state: "misconception",
        affective_state: "slightly_frustrated",
      },
    },
    left: {
      input: {
        schema_version: "1.0.0-rc.2",
        output_language: "zh-CN",
        instructional_content: {
          content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
        },
        pedagogical_context: {
          scenario: "学生有些挫败。",
          learner_utterance: "汽车转弯的时候速度大小没变。",
        },
        learner: {
          level: "high_school",
          knowledge_state: "misconception",
          affective_state: "slightly_frustrated",
        },
        pedagogical_intent: { primary: "corrective_feedback" },
      },
      speech_plan: {
        schema_version: "1.0.0-rc.3",
        verbal_plan: {
          segments: [{ segment_id: "seg_01", text: leftText }],
        },
        delivery_plan: {
          global: {
            attitudinal_tone: "安抚但纠正",
          },
        },
      },
      generation: {
        prompt_version: "v0.2",
        requested_model: "tencent/hy3",
        reported_model: "tencent/hy3",
        duration_seconds: 0.2,
      },
    },
    right: {
      input: {
        schema_version: "1.0.0-rc.2",
        output_language: "zh-CN",
        instructional_content: {
          content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
        },
        pedagogical_context: {
          scenario: "学生有些挫败。",
          learner_utterance: "汽车转弯的时候速度大小没变。",
        },
        learner: {
          level: "high_school",
          knowledge_state: "misconception",
          affective_state: "slightly_frustrated",
        },
        pedagogical_intent: { primary: "scaffolding" },
      },
      speech_plan: {
        schema_version: "1.0.0-rc.3",
        verbal_plan: {
          segments: [{ segment_id: "seg_01", text: rightText }],
        },
        delivery_plan: {
          segment_overrides: [
            {
              segment_id: "seg_01",
              prominence_targets: [{ text: "小问题", level: "moderate" }],
            },
          ],
        },
      },
      generation: {
        prompt_version: "v0.2",
        requested_model: "tencent/hy3",
        reported_model: "tencent/hy3",
        duration_seconds: 0.3,
      },
    },
    structural_contrast: {
      verbal_segments: { left: 1, right: 1 },
      delivery_decision: { left: "selective", right: "selective" },
      verbal_text_identical: false,
      delivery_plan_identical: false,
      left_control_paths: ["delivery_plan.global.attitudinal_tone"],
      right_control_paths: [
        "delivery_plan.segment_overrides[0].prominence_targets[0].text",
        "delivery_plan.segment_overrides[0].prominence_targets[0].level",
      ],
    },
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("IntentComparePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          return Promise.resolve(jsonResponse(comparisonResponse()));
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
  });

  it("renders form with defaults, loads showcase, swaps intents, and validates same intent", async () => {
    const user = userEvent.setup();
    render(<IntentComparePage />);

    expect(screen.getByText("Intent Compare")).toBeInTheDocument();
    expect(screen.getByDisplayValue("corrective_feedback")).toBeInTheDocument();
    expect(screen.getByDisplayValue("scaffolding")).toBeInTheDocument();

    await user.click(screen.getByText("Load showcase scenario"));
    expect(await screen.findByDisplayValue("high_school")).toBeInTheDocument();
    expect(screen.getByDisplayValue("misconception")).toBeInTheDocument();

    await user.click(screen.getByText("Swap"));
    expect(screen.getByDisplayValue("scaffolding")).toBeInTheDocument();
    expect(screen.getByDisplayValue("corrective_feedback")).toBeInTheDocument();

    const selectors = screen.getAllByLabelText(/Intent/);
    await user.selectOptions(selectors[1], "scaffolding");
    expect(screen.getByText("Choose two different pedagogical intents.")).toBeInTheDocument();
    expect(screen.getByText("Compare intents")).toBeDisabled();
  });

  it("shows loading and renders controlled comparison result without Judge or audio UI", async () => {
    const user = userEvent.setup();
    let resolveCompare: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          return new Promise<Response>((resolve) => {
            resolveCompare = resolve;
          });
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
    render(<IntentComparePage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Compare intents"));

    expect(screen.getByText("Generating both plans…")).toBeDisabled();
    resolveCompare?.(jsonResponse(comparisonResponse()));

    expect(await screen.findByText("Controlled input comparison")).toBeInTheDocument();
    expect(
      screen.getByText(/All non-intent input fields are exactly equal/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Teaching Context")).toHaveLength(1);
    expect(screen.getAllByText("Speech Plan")).toHaveLength(2);
    expect(screen.getByText("纠正这个判断。")).toBeInTheDocument();
    expect(screen.getByText("先拆成一个小问题。")).toBeInTheDocument();
    expect(screen.getByText("安抚但纠正")).toBeInTheDocument();
    expect(screen.getByText("小问题")).toBeInTheDocument();
    expect(screen.getByText("Structural Contrast")).toBeInTheDocument();
    expect(screen.getByText("delivery_plan.global.attitudinal_tone")).toBeInTheDocument();
    expect(screen.getByText("delivery_plan.segment_overrides[0].prominence_targets[0].text")).toBeInTheDocument();
    expect(screen.queryByText("Evaluate this plan")).not.toBeInTheDocument();
    expect(screen.queryByText("D1")).not.toBeInTheDocument();
    expect(screen.queryByText("Voice Realization")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/audio/i)).not.toBeInTheDocument();
  });

  it("shows API failure as incomplete comparison", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            { detail: { error: { message: "Right generation failed." } } },
            502,
          ),
        ),
      ),
    );
    render(<IntentComparePage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Compare intents"));

    expect(await screen.findByText("Comparison incomplete")).toBeInTheDocument();
    expect(screen.getByText("Right generation failed.")).toBeInTheDocument();
  });

  it("changing form after comparison does not mutate result, and compare again replaces it", async () => {
    const user = userEvent.setup();
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          calls += 1;
          return Promise.resolve(
            jsonResponse(
              comparisonResponse(
                calls === 1 ? "第一次左侧。" : "第二次左侧。",
                calls === 1 ? "第一次右侧。" : "第二次右侧。",
              ),
            ),
          );
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
    render(<IntentComparePage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Compare intents"));
    expect(await screen.findByText("第一次左侧。")).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/Content anchor/));
    await user.type(screen.getByLabelText(/Content anchor/), "changed content");
    expect(screen.getByText("第一次左侧。")).toBeInTheDocument();

    await user.click(screen.getByText("Compare intents"));
    expect(await screen.findByText("第二次左侧。")).toBeInTheDocument();
    expect(screen.queryByText("第一次左侧。")).not.toBeInTheDocument();
  });
});
