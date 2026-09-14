import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { LiveStudioPage } from "./LiveStudioPage";
import { generated, json, recorded } from "../test/fixtures";
import { INTENT_OPTIONS } from "../lib/product";
import type { ExampleId } from "../types/teachintent";
beforeEach(() => {
  window.history.replaceState(null, "", "/studio");
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith("/api/examples/")
          ? json(recorded(url.split("/").at(-1) as ExampleId))
          : url === "/api/generate"
            ? json(generated())
            : url === "/api/evaluate"
              ? json({ evaluation: recorded("corrective-feedback").evaluation })
              : json(
                  { detail: "Renderer unavailable; private exception" },
                  503,
                ),
      ),
    ),
  );
});
async function generate() {
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("使用示例"), "fractions");
  await user.click(screen.getByRole("button", { name: "生成教学计划" }));
  await screen.findByText("教学计划已生成");
  return user;
}
it("prioritizes three inputs and six Chinese intents; supplemental and technical fields start collapsed", () => {
  render(<LiveStudioPage />);
  expect(screen.getByLabelText(/教学内容/)).toBeVisible();
  expect(screen.getByLabelText("学生当前回答")).toBeVisible();
  for (const item of INTENT_OPTIONS)
    expect(
      screen.getByRole("radio", { name: new RegExp(item.label) }),
    ).toBeVisible();
  expect(screen.getAllByRole("radio")).toHaveLength(6);
  expect(
    screen.getByText("补充学生与教学信息").closest("details"),
  ).not.toHaveAttribute("open");
  expect(screen.getByText("技术详情").closest("details")).not.toHaveAttribute(
    "open",
  );
  expect(screen.getByLabelText("Prompt 版本")).not.toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
});
it.each([
  "fractions",
  "corrective-feedback",
  "scaffolding",
  "supportive-feedback",
])("example %s only fills the form", async (id) => {
  render(<LiveStudioPage />);
  await userEvent.setup().selectOptions(screen.getByLabelText("使用示例"), id);
  await screen.findByText("已填入示例。确认内容后，再生成教学计划。");
  expect(
    (screen.getByLabelText(/教学内容/) as HTMLTextAreaElement).value.length,
  ).toBeGreaterThan(0);
  expect(
    vi.mocked(fetch).mock.calls.every(([, init]) => init?.method !== "POST"),
  ).toBe(true);
});
it("manual generation preserves API fields and never evaluates or renders automatically", async () => {
  render(<LiveStudioPage />);
  await generate();
  const [url, init] = vi.mocked(fetch).mock.calls[0];
  expect(url).toBe("/api/generate");
  expect(JSON.parse(init!.body as string)).toMatchObject({
    pedagogical_intent: "corrective_feedback",
    prompt_version: "v0.2",
    learner_level: "小学",
  });
  expect(fetch).toHaveBeenCalledTimes(1);
  const plan = screen.getByRole("region", { name: "教学语音计划" });
  expect(
    within(plan).getByText(
      generated().speech_plan.verbal_plan.segments[0].text,
    ),
  ).toBeVisible();
  expect(screen.getAllByText("技术详情")).toHaveLength(1);
  expect(screen.getByLabelText("语音执行方式")).not.toBeVisible();
});
it("checks quality explicitly and discloses original evaluation only on request", async () => {
  render(<LiveStudioPage />);
  const user = await generate();
  await user.click(screen.getByRole("button", { name: "检查计划质量" }));
  await screen.findByText("教学意图一致性");
  expect(vi.mocked(fetch).mock.calls.at(-1)).toEqual([
    "/api/evaluate",
    expect.objectContaining({
      body: JSON.stringify({ session_id: "mock-session" }),
    }),
  ]);
  const details = screen.getByText("查看详细评价").closest("details");
  expect(details).not.toHaveAttribute("open");
  const quality = screen.getByRole("region", { name: "计划质量检查" });
  expect(quality.querySelector(".quality-grid mark")).not.toBeNull();
  expect(quality.querySelector(".quality-grid")).not.toHaveTextContent(/(?:input|plan)\./);
  await user.click(screen.getByText("查看详细评价"));
  expect(details).toHaveAttribute("open");
  for (const raw of quality.querySelectorAll(".evidence-locations pre"))
    expect(raw).not.toBeVisible();
});
it("handles unavailable speech quietly while retaining the plan", async () => {
  render(<LiveStudioPage />);
  const user = await generate();
  await user.click(screen.getByRole("button", { name: "生成语音" }));
  expect(await screen.findByText("当前未配置语音生成服务。")).toBeVisible();
  expect(screen.getByRole("region", { name: "教学语音计划" })).toBeVisible();
  expect(vi.mocked(fetch).mock.calls.at(-1)?.[0]).toBe(
    "/api/render/batonvoice-segmented",
  );
  expect(screen.getByText(/private exception/)).not.toBeVisible();
});
it("retains the plan if quality checking fails", async () => {
  render(<LiveStudioPage />);
  const user = await generate();
  vi.mocked(fetch).mockRejectedValueOnce(new Error("private judge failure"));
  await user.click(screen.getByRole("button", { name: "检查计划质量" }));
  expect(await screen.findByText(/暂时无法完成质量检查/)).toBeVisible();
  expect(screen.getByRole("region", { name: "教学语音计划" })).toBeVisible();
  expect(screen.getByText(/private judge failure/)).not.toBeVisible();
});
it("shows actionable Chinese generation errors and hides the raw exception", async () => {
  vi.mocked(fetch).mockRejectedValueOnce(new Error("private Python exception"));
  render(<LiveStudioPage />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("使用示例"), "fractions");
  await user.click(screen.getByRole("button", { name: "生成教学计划" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "生成失败，请检查服务配置后重试。",
  );
  expect(screen.getByText(/private Python exception/)).not.toBeVisible();
  expect(screen.getByRole("button", { name: "生成教学计划" })).toBeEnabled();
});
it("blocks duplicate requests while generating and ignores responses after unmount", async () => {
  let resolve!: (value: Response) => void;
  vi.mocked(fetch).mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const { unmount } = render(<LiveStudioPage />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("使用示例"), "fractions");
  await user.click(screen.getByRole("button", { name: "生成教学计划" }));
  expect(
    screen.getByRole("button", { name: "正在生成教学计划…" }),
  ).toBeDisabled();
  expect(fetch).toHaveBeenCalledTimes(1);
  unmount();
  await act(async () => resolve(json(generated())));
  expect(screen.queryByText("教学计划已生成")).not.toBeInTheDocument();
});
it("validates content locally and accepts an absent student utterance", async () => {
  render(<LiveStudioPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "生成教学计划" }));
  expect(fetch).not.toHaveBeenCalled();
  await user.type(
    screen.getByLabelText(/教学内容/),
    "分母表示平均分成的份数。",
  );
  await user.click(screen.getByRole("button", { name: "生成教学计划" }));
  await screen.findByText("教学计划已生成");
  expect(
    JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string)
      .learner_utterance,
  ).toBeNull();
});
