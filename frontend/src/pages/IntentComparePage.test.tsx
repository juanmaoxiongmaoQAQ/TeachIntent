import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { IntentComparePage } from "./IntentComparePage";
import { comparisonResponse, json } from "../test/fixtures";
beforeEach(() =>
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(() => Promise.resolve(json(comparisonResponse()))),
  ),
);
it("compares only on an explicit request, preserving both intent fields", async () => {
  render(<IntentComparePage />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("使用示例"), "fractions");
  expect(fetch).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "生成对比计划" }));
  expect(await screen.findByText("纠正这个判断。")).toBeVisible();
  expect(screen.getByText("先拆成一个小问题。")).toBeVisible();
  const [url, init] = vi.mocked(fetch).mock.calls[0];
  expect(url).toBe("/api/compare-intents");
  const body = JSON.parse(init!.body as string);
  expect(body).toMatchObject({
    left_intent: "corrective_feedback",
    right_intent: "scaffolding",
  });
  expect(body).not.toHaveProperty("prompt_version");
  expect(body).not.toHaveProperty("pedagogical_intent");
  expect(screen.getByText("技术详情").closest("details")).not.toHaveAttribute(
    "open",
  );
});
it("swaps intents and prevents identical-intent comparisons", async () => {
  render(<IntentComparePage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "交换意图" }));
  expect(screen.getByLabelText("教学意图 A")).toHaveValue("scaffolding");
  await user.selectOptions(screen.getByLabelText("教学意图 B"), "scaffolding");
  expect(screen.getByRole("button", { name: "生成对比计划" })).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
});
it("hides raw failures while giving an actionable Chinese message", async () => {
  vi.mocked(fetch).mockRejectedValueOnce(new Error("private upstream failure"));
  render(<IntentComparePage />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("使用示例"), "fractions");
  await user.click(screen.getByRole("button", { name: "生成对比计划" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "对比生成失败，请检查服务配置后重试。",
  );
  expect(screen.getByText(/private upstream failure/)).not.toBeVisible();
});
