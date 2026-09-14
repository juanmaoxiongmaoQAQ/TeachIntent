import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ExamplesPage } from "./ExamplesPage";
import { EXAMPLES } from "../lib/product";
import { json, recorded } from "../test/fixtures";
import type { ExampleId } from "../types/teachintent";
beforeEach(() => {
  window.history.replaceState(null, "", "/examples");
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(json(recorded(url.split("/").at(-1) as ExampleId))),
    ),
  );
});
it("shows three concise cases before loading any artifact", () => {
  render(<ExamplesPage />);
  for (const item of EXAMPLES)
    expect(
      screen.getByRole("button", { name: new RegExp(item.title) }),
    ).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
  expect(
    screen.getByRole("link", { name: /比较不同教学意图/ }),
  ).toHaveAttribute("href", "/compare");
});
it("switches the three frozen cases, preserving text, version and A/B audio without autoplay", async () => {
  window.history.replaceState(null, "", "/examples?case=corrective-feedback");
  const { container } = render(<ExamplesPage />);
  const user = userEvent.setup();
  for (const item of EXAMPLES) {
    await user.click(
      within(screen.getByRole("group", { name: "切换案例" })).getByRole(
        "button",
        { name: item.intent },
      ),
    );
    const plan = recorded(item.id).speech_plan;
    expect(
      await within(
        await screen.findByRole("region", { name: "教学语音计划" }),
      ).findByText(plan.verbal_plan.segments[0].text),
    ).toBeVisible();
    expect(screen.getByLabelText("基础语音")).toHaveAttribute(
      "src",
      `/api/audio/${item.id}/neutral`,
    );
    expect(screen.getByLabelText("规划后语音")).toHaveAttribute(
      "src",
      `/api/audio/${item.id}/planned`,
    );
    expect(
      [...container.querySelectorAll("audio")].every(
        (audio) => audio.controls && !audio.autoplay,
      ),
    ).toBe(true);
    expect(screen.getByText("技术详情").closest("details")).not.toHaveAttribute(
      "open",
    );
    const quality = screen.getByRole("region", { name: "计划质量检查" });
    expect(quality.querySelector(".quality-grid mark")).not.toBeNull();
    expect(quality.querySelector(".quality-grid")).not.toHaveTextContent(/(?:input|plan)\./);
    expect(screen.getByText("查看详细评价").closest("details")).not.toHaveAttribute("open");
    expect(screen.queryByText("想进一步比较教学策略？")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /比较不同教学意图/ })).toHaveAttribute("href", "/compare");
    for (const node of screen.getAllByText(/"prompt_version": "v0.2"/))
      expect(node).not.toBeVisible();
  }
  expect(screen.getByText("本段无需额外表达控制")).toBeVisible();
  expect(
    screen.getByText("此计划无需额外表达控制，两段音频相同。"),
  ).toBeVisible();
  expect(
    vi.mocked(fetch).mock.calls.every(([, init]) => init?.method !== "POST"),
  ).toBe(true);
});
it("keeps a recorded plan usable without optional audio or evaluation", async () => {
  const data = recorded("corrective-feedback");
  data.voice_realization.available = false;
  data.evaluation.available = false;
  vi.mocked(fetch).mockResolvedValue(json(data));
  window.history.replaceState(null, "", "/examples?case=corrective-feedback");
  render(<ExamplesPage />);
  expect(await screen.findByText(/此示例的可选音频暂不可用/)).toBeVisible();
  expect(screen.getByRole("region", { name: "教学语音计划" })).toBeVisible();
  expect(screen.queryByLabelText("基础语音")).not.toBeInTheDocument();
});
it("allows read-only reload on a Chinese connection error", async () => {
  vi.mocked(fetch).mockRejectedValueOnce(new Error("private network failure"));
  window.history.replaceState(null, "", "/examples?case=corrective-feedback");
  render(<ExamplesPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "示例暂时无法加载",
  );
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "重新加载" }));
  expect(
    await screen.findByRole("region", { name: "教学语音计划" }),
  ).toBeVisible();
});
