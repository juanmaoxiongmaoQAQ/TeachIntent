import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { WorkbenchResponse } from "./types/teachintent";

const minimalWorkbench: WorkbenchResponse = {
  example: {
    id: "supportive-feedback",
    title: "Supportive feedback",
    description: "Recorded supportive case.",
    recommended: false,
  },
  prompt_version: "v0.2",
  input: {
    schema_version: "1.0.0-rc.2",
    output_language: "zh-CN",
    instructional_content: {
      content_anchor: "阅读图表时先确认横轴、纵轴、单位和图例。",
    },
    pedagogical_context: {
      scenario: "学生完成了正确迁移。",
    },
    learner: {
      level: "high_school",
      knowledge_state: "successful_cross_domain_transfer",
    },
    pedagogical_intent: {
      primary: "supportive_feedback",
    },
  },
  speech_plan: {
    schema_version: "1.0.0-rc.3",
    verbal_plan: {
      segments: [{ segment_id: "seg_01", text: "这个迁移做得很好。" }],
    },
    delivery_plan: {},
  },
  evaluation: {
    available: true,
    evaluator_version: "v0.1",
    judge_prompt_version: "v0.1",
    source_run_id: "20260901T093114Z",
    critical_flags: [],
    scores: {
      pedagogical_intent_fidelity: {
        score: 4,
        evidence: [
          {
            source: "plan.verbal_plan.segments[0].text",
            text: "这个迁移做得很好。",
          },
        ],
        brief_justification: "Grounded supportive feedback.",
      },
    },
  },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/examples") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: "supportive-feedback",
                title: "Supportive feedback",
                description: "Recorded supportive case.",
                recommended: false,
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (url === "/api/examples/corrective-feedback") {
        return Promise.resolve(
          new Response(JSON.stringify(minimalWorkbench), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    }),
  );
});

describe("App", () => {
  it("shows Explore technical details and Live Studio entry form", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() =>
      expect(screen.getByText("Technical details")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Live Studio" }));

    expect(screen.getByText("Build a teaching scenario")).toBeInTheDocument();
    expect(screen.getByText("Generate with Hy3")).toBeInTheDocument();
  });
});
