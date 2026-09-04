import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExplorePage } from "./ExplorePage";
import type { WorkbenchResponse } from "../types/teachintent";

const workbench: WorkbenchResponse = {
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
        "若速度的大小和方向都保持不变，则加速度为0；即使速度大小不变，只要方向发生变化，加速度也不为0。",
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
    pedagogical_intent: {
      primary: "corrective_feedback",
    },
  },
  speech_plan: {
    schema_version: "1.0.0-rc.3",
    verbal_plan: {
      segments: [
        {
          segment_id: "seg_01",
          text: "你提到速度大小没变，这观察本身没错。",
        },
      ],
    },
    delivery_plan: {
      global: {
        attitudinal_tone: "安抚但纠正",
      },
    },
  },
  evaluation: {
    available: true,
    evaluator_version: "v0.1",
    judge_prompt_version: "v0.1",
    source_run_id: "20260901T043729Z",
    critical_flags: [],
    scores: {
      pedagogical_intent_fidelity: {
        score: 4,
        evidence: [
          {
            source: "plan.verbal_plan.segments[0].text",
            text: "你提到速度大小没变，这观察本身没错。",
          },
        ],
        brief_justification: "D1 rationale.",
      },
      content_faithfulness_boundary: {
        score: 4,
        evidence: [
          {
            source: "input.instructional_content.content_anchor",
            text: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
          },
        ],
        brief_justification: "D2 rationale.",
      },
      delivery_pedagogy_alignment: {
        score: 4,
        evidence: [
          {
            source: "plan.delivery_plan.global.attitudinal_tone",
            text: "安抚但纠正",
          },
        ],
        brief_justification: "D6 rationale.",
      },
    },
  },
  voice_realization: {
    available: true,
    mode: "recorded",
    exact_verbal_text: "你提到速度大小没变，这观察本身没错。",
    exact_verbal_text_sha256: "text-sha",
    speaker: "Vivian",
    model: "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    language: "Chinese",
    seed: 20260901,
    delivery_adapter: {
      instruct: "整体采用“安抚但纠正”的态度语气。",
      supported_controls: [
        {
          path: "delivery_plan.global.attitudinal_tone",
          value: "安抚但纠正",
          instruction_fragment: "整体采用“安抚但纠正”的态度语气。",
          realization: "best_effort_natural_language_instruction",
        },
      ],
      unsupported_controls: [],
    },
    ab_invariants: {},
    neutral: {
      instruct: "",
      audio_file: "neutral.wav",
      audio_url: "/api/audio/corrective-feedback/neutral",
      audio_sha256: "neutral-sha",
      duration_seconds: 1,
    },
    planned: {
      instruct: "整体采用“安抚但纠正”的态度语气。",
      audio_file: "planned.wav",
      audio_url: "/api/audio/corrective-feedback/planned",
      audio_sha256: "planned-sha",
      duration_seconds: 1,
    },
    limitations: [],
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
                id: "corrective-feedback",
                title: "Corrective feedback",
                description: "Recorded case.",
                recommended: true,
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (url === "/api/examples/corrective-feedback") {
        return Promise.resolve(
          new Response(JSON.stringify(workbench), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    }),
  );
});

describe("ExplorePage", () => {
  it("changes selected dimension locally and updates highlights", async () => {
    const user = userEvent.setup();
    render(<ExplorePage />);

    await waitFor(() =>
      expect(screen.getByText("Recorded case.")).toBeInTheDocument(),
    );

    expect(
      screen
        .getAllByText("你提到速度大小没变，这观察本身没错。")
        .some((node) => node.tagName === "MARK"),
    ).toBe(true);

    await user.click(screen.getByText("Content Faithfulness"));

    expect(
      screen.getByText("即使速度大小不变，只要方向发生变化，加速度也不为0。").tagName,
    ).toBe("MARK");
    expect(
      screen
        .getAllByText("你提到速度大小没变，这观察本身没错。")
        .some((node) => node.tagName === "MARK"),
    ).toBe(false);

    await user.click(screen.getByText("Delivery Alignment"));

    expect(
      screen
        .getAllByText("安抚但纠正")
        .some((node) => node.tagName === "MARK"),
    ).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
