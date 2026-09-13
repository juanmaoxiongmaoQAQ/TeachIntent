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
  voice_realization: {
    available: false,
    mode: "recorded",
    reason: "Recorded voice artifact unavailable.",
    ab_invariants: {},
    limitations: [],
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

    expect(screen.getByRole("combobox", { name: "Speech Plan prompt" })).toHaveValue("v0.2");

    await user.click(screen.getByText("Load showcase scenario"));

    expect(await screen.findByDisplayValue("high_school")).toBeInTheDocument();
    expect(screen.queryByText("Speech Plan")).not.toBeInTheDocument();
    expect(screen.queryByText("Recorded Evaluator v0.1")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Speech Plan prompt" })).toHaveValue("v0.2");
  });

  it.each(["v0.3", "v0.4"])("uses explicit %s and keeps evaluation/render on the generated session", async (version) => {
    const fetchMock = vi.fn((url: string) => {
      if (url === "/api/examples/corrective-feedback") return Promise.resolve(jsonResponse(showcase));
      if (url === "/api/generate") return Promise.resolve(jsonResponse({
        ...generated, generation: { ...generated.generation, prompt_version: version },
      }));
      if (url === "/api/evaluate") return Promise.resolve(jsonResponse(evaluated));
      if (url === "/api/render/batonvoice") return Promise.resolve(jsonResponse({
        session_id: generated.session_id, status: "success", renderer: "batonvoice",
        audio_url: `/api/live/${generated.session_id}/batonvoice.wav`,
        render_metadata: { sample_rate: 24000, duration_seconds: 1, channels: 1 },
      }));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<LiveStudioPage />);
    const selector = screen.getByRole("combobox", { name: "Speech Plan prompt" });
    expect(selector).toHaveValue("v0.2");
    expect(screen.getByRole("option", { name: "v0.4 (expressive sparse delivery)" })).toBeInTheDocument();
    await user.selectOptions(selector, version);
    await user.click(screen.getByText("Load showcase scenario"));
    await screen.findByDisplayValue("high_school");
    expect(selector).toHaveValue(version);
    await user.click(screen.getByText("Generate with Hy3"));
    expect(await screen.findByText(`Live Hy3 · Prompt ${version}`)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/generate", expect.objectContaining({
      body: expect.stringContaining(`"prompt_version":"${version}"`),
    }));
    // Editing the next request must not change the already-generated session.
    await user.selectOptions(selector, "v0.2");
    await user.click(screen.getByText("Evaluate this plan"));
    await screen.findByText("Live Evaluator v0.1 · Independent Judge");
    await user.click(screen.getByText("Render with BatonVoice"));
    await screen.findByText("Render again");
    for (const url of ["/api/evaluate", "/api/render/batonvoice"]) {
      expect(fetchMock).toHaveBeenCalledWith(url, expect.objectContaining({
        body: JSON.stringify({ session_id: generated.session_id }),
      }));
    }
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/generate")).toHaveLength(1);
    expect(screen.getByText(`Live Hy3 · Prompt ${version}`)).toBeInTheDocument();
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

  it("reports a showcase load failure without an unhandled rejection or generation", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("network unavailable"));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<LiveStudioPage />);
    await user.click(screen.getByText("Load showcase scenario"));
    expect(await screen.findByText(/Could not load the showcase scenario/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/examples/corrective-feedback");
    expect(screen.getByText("Generate with Hy3")).toBeEnabled();
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

  it("keeps single-pass and segmented controls independent on the saved session", async () => {
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    const fetchMock = vi.fn((url: string) => {
      if (url === "/api/examples/corrective-feedback") return Promise.resolve(jsonResponse(showcase));
      if (url === "/api/generate") return Promise.resolve(jsonResponse(generated));
      if (url === "/api/render/batonvoice") return Promise.resolve(jsonResponse({
        session_id: generated.session_id, status: "success", renderer: "batonvoice", audio_url: "/single.wav",
      }));
      if (url === "/api/render/batonvoice-segmented") return Promise.resolve(jsonResponse({
        session_id: generated.session_id, status: "success", renderer: "batonvoice_segmented", run_id: "run-1",
        speech_speed: 0.85, manifest_metadata: {}, segments: [{
          segment_id: "seg_01", order: 1, status: "success", audio_url: "/seg_01.wav", duration_seconds: 5,
          text_sha256: "hash", text_char_count: 10, mapped: {}, mapping_diagnostics: {},
          executor_diagnostics: {}, failure_reasons: [],
        }],
      }));
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { container, unmount } = render(<LiveStudioPage />);
    await user.click(screen.getByText("Load showcase scenario"));
    await user.click(screen.getByText("Generate with Hy3"));
    await screen.findByText("Render with BatonVoice");
    expect(screen.getByText("Render segmented candidate")).toBeEnabled();
    await user.click(screen.getByText("Render with BatonVoice"));
    await screen.findByText("Render again");
    const single = container.querySelector('audio[src="/single.wav"]');
    expect(single).toHaveAttribute("controls");
    await user.click(screen.getByText("Render segmented candidate"));
    await screen.findByText("Play full segmented response");
    expect(container.querySelector('audio[src="/single.wav"]')).toBe(single);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/generate")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/evaluate")).toHaveLength(0);
    expect(fetchMock).toHaveBeenCalledWith("/api/render/batonvoice-segmented", expect.objectContaining({
      body: JSON.stringify({ session_id: generated.session_id }),
    }));
    unmount();
    pause.mockRestore();
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
