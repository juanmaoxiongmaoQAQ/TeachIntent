import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { DIMENSIONS } from "../lib/dimensions";
import type { ExampleId, WorkbenchResponse } from "../types/teachintent";
import { ShowcasePage } from "./ShowcasePage";

function recorded(id: ExampleId): WorkbenchResponse {
  const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), "..", path), "utf8"));
  const example = read(`examples/${id.replaceAll("-", "_")}.json`);
  const evaluation = read(`public_demo/evaluator_artifacts/${id}.v0_2.json`);
  const voice = read(`public_demo/voice/${id}/v0_2/manifest.json`);
  return {
    example: { id, title: example.title, description: example.description, recommended: false },
    prompt_version: "v0.2",
    input: example.input,
    speech_plan: example.recorded_outputs["v0.2"],
    evaluation: { ...evaluation, available: true },
    voice_realization: {
      ...voice, available: true, mode: "recorded",
      neutral: { ...voice.conditions.neutral, audio_url: `/api/audio/${id}/neutral` },
      planned: { ...voice.conditions.planned, audio_url: `/api/audio/${id}/planned` },
    },
  };
}

beforeEach(() => {
  window.history.replaceState(null, "", "/showcase");
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(
    JSON.stringify(recorded(url.split("/").at(-1) as ExampleId)),
    { status: 200, headers: { "Content-Type": "application/json" } },
  ))));
});

describe("Showcase", () => {
  it("renders the direct route with actual recorded plan and six evaluator dimensions", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "TeachIntent Showcase" })).toBeInTheDocument();
    expect(await screen.findByText("Recorded Hy3 · Prompt v0.2")).toBeInTheDocument();
    expect(screen.getByText("WHAT TO SAY")).toBeInTheDocument();
    expect(screen.getByText("HOW TO SAY")).toBeInTheDocument();
    const evaluation = screen.getByRole("region", { name: "Plan Evaluation" });
    for (const dimension of DIMENSIONS) expect(within(evaluation).getByText(dimension.label)).toBeInTheDocument();
    expect(within(evaluation).getAllByText("4/4")).toHaveLength(6);
    const user = userEvent.setup();
    await user.click(screen.getByText("View evaluator details"));
    expect(screen.getByText("View evaluator details").closest("details")).toHaveAttribute("open");
  });

  it("switches all three existing artifacts without navigation, POSTs or fabricated delivery", async () => {
    const user = userEvent.setup();
    render(<ShowcasePage onOpenLive={vi.fn()} />);
    for (const [id, label] of [["corrective-feedback", "Corrective Feedback"], ["scaffolding", "Scaffolding"], ["supportive-feedback", "Supportive Feedback"]] as const) {
      await user.click(screen.getByRole("button", { name: new RegExp(label) }));
      const text = recorded(id).speech_plan.verbal_plan.segments[0].text;
      const plan = await screen.findByRole("region", { name: "Pedagogical Speech Plan" });
      expect(await within(plan).findByText(text)).toBeInTheDocument();
      const audio = screen.getByLabelText("Neutral demo audio");
      expect(audio).toHaveAttribute("src", `/api/audio/${id}/neutral`);
      expect(screen.getByLabelText("Planned demo audio")).toHaveAttribute("src", `/api/audio/${id}/planned`);
      expect(audio).toHaveAttribute("controls");
      expect(audio).not.toHaveAttribute("autoplay");
      expect(window.location.pathname).toBe("/showcase");
    }
    expect(screen.getByText("No additional delivery control required.")).toBeInTheDocument();
    expect(screen.getByText(/Identical A\/B audio/)).toBeInTheDocument();
    for (const [url, options] of vi.mocked(fetch).mock.calls) {
      expect(url).toMatch(/^\/api\/examples\//);
      expect(options?.method ?? "GET").toBe("GET");
    }
  });

  it("opens the existing Live Studio route and responds to browser history", async () => {
    render(<App />);
    const user = userEvent.setup();
    const link = screen.getByRole("link", { name: "Open Live Studio" });
    expect(link).toHaveAttribute("href", "/live");
    await user.click(link);
    expect(window.location.pathname).toBe("/live");
    expect(screen.getByText("Generate with Hy3")).toBeInTheDocument();
    act(() => {
      window.history.replaceState(null, "", "/showcase");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(screen.getByRole("heading", { name: "TeachIntent Showcase" })).toBeInTheDocument();
    await screen.findByText("Recorded Hy3 · Prompt v0.2");
  });

  it("keeps the plan usable when optional audio or evaluation is absent", async () => {
    const data = recorded("corrective-feedback");
    data.voice_realization.available = false;
    data.evaluation.available = false;
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(data)));
    render(<ShowcasePage onOpenLive={vi.fn()} />);
    expect(await screen.findByText("Optional recorded audio unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Recorded evaluator artifact unavailable.")).toBeInTheDocument();
    expect(screen.getByText("WHAT TO SAY")).toBeInTheDocument();
  });

  it("offers a read-only reload after a connection failure", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("connection failed"));
    render(<ShowcasePage onOpenLive={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Recorded showcase could not load");
    await userEvent.setup().click(screen.getByRole("button", { name: "Reload recorded case" }));
    await waitFor(() => expect(screen.getByText("Recorded Hy3 · Prompt v0.2")).toBeInTheDocument());
  });
});
