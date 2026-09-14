import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import App from "./App";
beforeEach(() => {
  window.history.replaceState(null, "", "/");
  vi.stubGlobal("fetch", vi.fn());
});
it("explains the product and exposes exactly the four public navigation entries", () => {
  render(<App />);
  expect(
    screen.getByRole("heading", { name: "教学意图驱动的 AI 教学语音规划" }),
  ).toBeInTheDocument();
  const links = within(
    screen.getByRole("navigation", { name: "主导航" }),
  ).getAllByRole("link");
  expect(
    links.map((a) => [a.textContent?.trim(), a.getAttribute("href")]),
  ).toEqual([
    ["首页", "/"],
    ["在线体验", "/studio"],
    ["示例库", "/examples"],
    ["GitHub ↗", "https://github.com/juanmaoxiongmaoQAQ/TeachIntent"],
  ]);
  expect(screen.getByRole("link", { name: "开始体验" })).toHaveAttribute(
    "href",
    "/studio",
  );
  expect(fetch).not.toHaveBeenCalled();
});
it("navigates with the primary CTA and browser history without an API call", async () => {
  render(<App />);
  await userEvent.setup().click(screen.getByRole("link", { name: "开始体验" }));
  expect(window.location.pathname).toBe("/studio");
  expect(
    screen.getByRole("button", { name: "生成教学计划" }),
  ).toBeInTheDocument();
  act(() => {
    window.history.replaceState(null, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  expect(screen.getByRole("link", { name: "开始体验" })).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
it.each([
  ["/live", "/studio", "在线体验"],
  ["/explore", "/examples", "示例库"],
  ["/showcase", "/examples", "示例库"],
  ["/compare", "/compare", "教学意图对比"],
])("supports the direct route %s", (route, canonical, title) => {
  window.history.replaceState(null, "", route);
  render(<App />);
  expect(
    screen.getByRole("heading", { name: title, level: 1 }),
  ).toBeInTheDocument();
  expect(window.location.pathname).toBe(canonical);
  expect(
    within(screen.getByRole("navigation")).queryByRole("link", {
      name: /对比/,
    }),
  ).not.toBeInTheDocument();
});
it("keeps unknown URLs recoverable", () => {
  window.history.replaceState(null, "", "/missing");
  render(<App />);
  expect(screen.getByRole("link", { name: "返回首页" })).toHaveAttribute(
    "href",
    "/",
  );
});
