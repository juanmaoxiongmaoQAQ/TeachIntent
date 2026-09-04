import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceRealizationPanel } from "./VoiceRealizationPanel";
import type { VoiceRealizationResponse } from "../../types/teachintent";

const availableVoice: VoiceRealizationResponse = {
  available: true,
  mode: "recorded",
  exact_verbal_text: "同样的话用于音频对比。",
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
    unsupported_controls: [
      {
        path: "delivery_plan.segment_overrides[0].prominence_targets",
        value: [{ text: "方向在变化", level: "moderate" }],
        reason: "Segment-local controls are not realized.",
      },
    ],
  },
  ab_invariants: {
    same_exact_verbal_text: true,
  },
  neutral: {
    instruct: "",
    audio_file: "neutral.wav",
    audio_url: "/api/audio/corrective-feedback/neutral",
    audio_sha256: "neutral-sha",
    duration_seconds: 2,
  },
  planned: {
    instruct: "整体采用“安抚但纠正”的态度语气。",
    audio_file: "planned.wav",
    audio_url: "/api/audio/corrective-feedback/planned",
    audio_sha256: "planned-sha",
    duration_seconds: 2,
  },
  limitations: ["No exact F0 control is claimed."],
};

describe("VoiceRealizationPanel", () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  });

  it("renders A/B comparison, exact text, instruction, invariants, and controls", () => {
    render(<VoiceRealizationPanel voice={availableVoice} />);

    expect(screen.getByText("Controlled comparison")).toBeInTheDocument();
    expect(screen.getByText("同样的话用于音频对比。")).toBeInTheDocument();
    expect(screen.getAllByText("整体采用“安抚但纠正”的态度语气。").length).toBeGreaterThan(0);
    expect(screen.getByText("delivery_plan.global.attitudinal_tone")).toBeInTheDocument();
    expect(
      screen.getByText("delivery_plan.segment_overrides[0].prominence_targets"),
    ).toBeInTheDocument();
    expect(screen.getByText("Preserved in Speech Plan; not realized by current adapter.")).toBeInTheDocument();
    expect(screen.getByText("Same exact words")).toBeInTheDocument();
    expect(screen.getByLabelText("Neutral audio")).toHaveAttribute(
      "src",
      "/api/audio/corrective-feedback/neutral",
    );
    expect(screen.getByLabelText("TeachIntent audio")).toHaveAttribute(
      "src",
      "/api/audio/corrective-feedback/planned",
    );
  });

  it("playing one condition pauses the other", async () => {
    const user = userEvent.setup();
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause");
    render(<VoiceRealizationPanel voice={availableVoice} />);

    await user.click(screen.getByLabelText("Play Neutral"));
    await waitFor(() => expect(screen.getByLabelText("Pause Neutral")).toBeInTheDocument());

    await user.click(screen.getByLabelText("Play TeachIntent"));

    expect(pause).toHaveBeenCalled();
    expect(await screen.findByLabelText("Pause TeachIntent")).toBeInTheDocument();
  });

  it("empty delivery no-op does not claim A/B delivery difference", () => {
    render(
      <VoiceRealizationPanel
        voice={{
          ...availableVoice,
          delivery_adapter: {
            instruct: "",
            supported_controls: [],
            unsupported_controls: [],
          },
          planned: {
            ...availableVoice.planned!,
            instruct: "",
          },
        }}
      />,
    );

    expect(screen.getAllByText("Default voice realization").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "TeachIntent selected no additional delivery control, so no A/B delivery difference is claimed for this case.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Controlled comparison")).not.toBeInTheDocument();
  });

  it("renders unavailable state", () => {
    render(
      <VoiceRealizationPanel
        voice={{
          available: false,
          mode: "recorded",
          reason: "Recorded voice artifact unavailable.",
          ab_invariants: {},
          limitations: [],
        }}
      />,
    );

    expect(screen.getByText("Recorded voice artifact unavailable.")).toBeInTheDocument();
  });
});
