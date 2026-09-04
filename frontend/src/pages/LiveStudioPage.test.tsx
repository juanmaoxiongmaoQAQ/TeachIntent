import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LiveStudioPage } from "./LiveStudioPage";
import type {
  LiveEvaluationResponse,
  LiveGenerationResponse,
  WorkbenchResponse,
} from "../types/teachintent";

const showcase: WorkbenchResponse = {
  example: {
    id: "corrective-feedback",
    title: "Corrective feedback",
    description: "Recorded case.",
    recommended: true,
  },
  prompt_version: "v0.2",
  input: {
    schema_version: "1.0.0-rc.2",
    output_language: "zh-CN",
    instructional_content: {
      content_anchor:
        "即使速度大小不变，只要方向发生变化，加速度也不为0。",
    },
    pedagogical_context: {
      scenario: "学生混淆速度大小不变和零加速度。",
      learner_utterance: "速度大小没变，所以加速度为0。",
    },
    learner: {
      level: "high_school",
      knowledge_state: "misconception",
      affective_state: "slightly_frustrated",
    },
    pedagogical_intent: {
      primary: "corrective_feedback",
    },
  },
  speech_plan: {
    schema_version: "1.0.0-rc.3",
    verbal_plan: { segments: [] },
    delivery_plan: {},
  },
  evaluation: {
    available: true,
    evaluator_version: "v0.1",
    judge_prompt_version: "v0.1",
    source_run_id: "20260901T043729Z",
    scores: {},
    critical_flags: [],
  },
};

const generated: LiveGenerationResponse = {
  session_id: "session-1",
  mode: "live",
  input: showcase.input,
  speech_plan: {
    schema_version: "1.0.0-rc.3",
    verbal_plan: {
      segments: [
        {
          segment_id: "seg_01",
          text: "先确认速度是否包含方向变化。",
        },
      ],
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
    duration_seconds: 0.25,
  },
  evaluation: null,
};

const evaluated: LiveEvaluationResponse = {
  session_id: "session-1",
  evaluation: {
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
            text: "先确认速度是否包含方向变化。",
          },
        ],
        brief_justification: "Intent is correct.",
      },
      content_faithfulness_boundary: {
        score: 4,
        evidence: [
          {
            source: "input.instructional_content.content_anchor",
            text: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
          },
        ],
        brief_justification: "Grounded in content.",
      },
      delivery_pedagogy_alignment: {
        score: 4,
        evidence: [
          {
            source: "plan.delivery_plan.global.attitudinal_tone",
            text: "安抚但纠正",
          },
        ],
        brief_justification: "Delivery aligns.",
      },
    },
  },
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("LiveStudioPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/examples/corrective-feedback") {
          return Promise.resolve(jsonResponse(showcase));
        }
        if (url === "/api/generate" && init?.method === "POST") {
          return Promise.resolve(jsonResponse(generated));
        }
        if (url === "/api/evaluate" && init?.method === "POST") {
          return Promise.resolve(jsonResponse(evaluated));
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
  });

  it("loads showcase input without rendering prerecorded output", async () => {
    const user = userEvent.setup();
    render(<LiveStudioPage />);

    await user.click(screen.getByText("Load showcase scenario"));

    expect(await screen.findByDisplayValue("high_school")).toBeInTheDocument();
    expect(screen.queryByText("Speech Plan")).not.toBeInTheDocument();
    expect(screen.queryByText("Recorded Evaluator v0.1")).not.toBeInTheDocument();
  });

  it("generates live workbench, evaluates, and highlights live evidence", async () => {
    const user = userEvent.setup();
    render(<LiveStudioPage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Generate with Hy3"));

    expect(await screen.findByText("Live Hy3 · Prompt v0.2")).toBeInTheDocument();
    expect(screen.getByText("Evaluation not run yet")).toBeInTheDocument();
    expect(screen.queryByText("Content Faithfulness")).not.toBeInTheDocument();

    await user.click(screen.getByText("Evaluate this plan"));

    expect(
      await screen.findByText("Live Evaluator v0.1 · Independent Judge"),
    ).toBeInTheDocument();
    expect(screen.getByText("先确认速度是否包含方向变化。").tagName).toBe("MARK");

    await user.click(screen.getByText("Content Faithfulness"));
    expect(
      screen
        .getAllByText("即使速度大小不变，只要方向发生变化，加速度也不为0。")
        .some((node) => node.tagName === "MARK"),
    ).toBe(true);

    await user.click(screen.getByText("Delivery Alignment"));
    expect(screen.getByText("安抚但纠正").tagName).toBe("MARK");
  });

  it("shows generation failure as unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url === "/api/generate") {
          return Promise.resolve(
            jsonResponse(
              { detail: { error: { message: "Hy3 provider unavailable." } } },
              502,
            ),
          );
        }
        return Promise.resolve(jsonResponse(showcase));
      }),
    );
    const user = userEvent.setup();
    render(<LiveStudioPage />);

    await user.type(screen.getByLabelText(/Content anchor/), "content");
    await user.type(screen.getByLabelText(/Teaching scenario/), "scenario");
    await user.type(screen.getByLabelText(/Learner level/), "high_school");
    await user.type(screen.getByLabelText(/Knowledge state/), "misconception");
    await user.click(screen.getByText("Generate with Hy3"));

    expect(await screen.findByText("Generation unavailable")).toBeInTheDocument();
    expect(screen.getByText("Hy3 provider unavailable.")).toBeInTheDocument();
  });

  it("shows Generate loading state", async () => {
    let resolveGenerate: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/examples/corrective-feedback") {
          return Promise.resolve(jsonResponse(showcase));
        }
        if (url === "/api/generate" && init?.method === "POST") {
          return new Promise<Response>((resolve) => {
            resolveGenerate = resolve;
          });
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
    const user = userEvent.setup();
    render(<LiveStudioPage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Generate with Hy3"));

    expect(screen.getByText("Generating…")).toBeDisabled();
    resolveGenerate?.(jsonResponse(generated));
    expect(await screen.findByText("Live Hy3 · Prompt v0.2")).toBeInTheDocument();
  });

  it("shows Evaluate loading state", async () => {
    let resolveEvaluate: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/examples/corrective-feedback") {
          return Promise.resolve(jsonResponse(showcase));
        }
        if (url === "/api/generate" && init?.method === "POST") {
          return Promise.resolve(jsonResponse(generated));
        }
        if (url === "/api/evaluate" && init?.method === "POST") {
          return new Promise<Response>((resolve) => {
            resolveEvaluate = resolve;
          });
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
    const user = userEvent.setup();
    render(<LiveStudioPage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Generate with Hy3"));
    await user.click(await screen.findByText("Evaluate this plan"));

    expect(screen.getByText("Evaluating…")).toBeDisabled();
    resolveEvaluate?.(jsonResponse(evaluated));
    expect(
      await screen.findByText("Live Evaluator v0.1 · Independent Judge"),
    ).toBeInTheDocument();
  });

  it("shows evaluation unavailable and clears it after generate again", async () => {
    let evaluateFailure = true;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/examples/corrective-feedback") {
          return Promise.resolve(jsonResponse(showcase));
        }
        if (url === "/api/generate" && init?.method === "POST") {
          return Promise.resolve(jsonResponse(generated));
        }
        if (url === "/api/evaluate" && init?.method === "POST") {
          if (evaluateFailure) {
            evaluateFailure = false;
            return Promise.resolve(
              jsonResponse({
                session_id: "session-1",
                evaluation: {
                  available: false,
                  evaluator_version: null,
                  judge_prompt_version: null,
                  source_run_id: null,
                  scores: {},
                  critical_flags: [],
                  failure_type: "judge_api_error",
                  failure_summary: "Judge unavailable.",
                },
              }),
            );
          }
          return Promise.resolve(jsonResponse(evaluated));
        }
        return Promise.resolve(jsonResponse({}, 404));
      }),
    );
    const user = userEvent.setup();
    render(<LiveStudioPage />);

    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Generate with Hy3"));
    await user.click(await screen.findByText("Evaluate this plan"));

    expect(await screen.findByText("Evaluation unavailable")).toBeInTheDocument();
    expect(screen.getByText("Judge unavailable.")).toBeInTheDocument();

    await user.click(screen.getByText("Generate with Hy3"));

    await waitFor(() =>
      expect(screen.getByText("Evaluation not run yet")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Judge unavailable.")).not.toBeInTheDocument();
  });
});
