import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { QualityCheck } from "./QualityCheck";
import { recorded } from "../../test/fixtures";
import type { EvaluationArtifact, ExampleId } from "../../types/teachintent";

function evaluation(source: string, text: string): EvaluationArtifact {
  return {
    available: true,
    evaluator_version: "v0.1",
    judge_prompt_version: "v0.1",
    source_run_id: "test-only",
    scores: {
      pedagogical_intent_fidelity: {
        score: 4,
        brief_justification: `English reason referencing ${source}.`,
        evidence: [{ source, text }],
      },
    },
    critical_flags: [],
  };
}

it.each<ExampleId>(["corrective-feedback", "scaffolding", "supportive-feedback"])(
  "shows six concise evidence summaries without exposing raw data for %s",
  (id) => {
    const data = recorded(id).evaluation;
    const original = JSON.stringify(data);
    const { container } = render(<QualityCheck evaluation={data} />);
    const grid = container.querySelector(".quality-grid")!;
    expect(grid.querySelectorAll("dt")).toHaveLength(6);
    expect(grid.querySelectorAll(".evidence-excerpt")).toHaveLength(6);
    expect(grid.querySelector("mark")).not.toBeNull();
    expect(grid.textContent).not.toMatch(/(?:input|plan|speech_plan)\./);
    for (const mark of grid.querySelectorAll("mark"))
      expect(Array.from(mark.textContent ?? "").length).toBeLessThanOrEqual(24);
    expect(screen.getByText("查看详细评价").closest("details")).not.toHaveAttribute("open");
    for (const raw of container.querySelectorAll("pre")) expect(raw).not.toBeVisible();
    expect(JSON.stringify(data)).toBe(original);
  },
);

it.each([
  ["plan.verbal_plan.segments[0].text", "教学步骤 · 第 1 段"],
  ["speech_plan.verbal_plan.segments[2].text", "教学步骤 · 第 3 段"],
  ["input.instructional_content.content_anchor", "教学内容"],
  ["input.learner.affective_state", "学生状态"],
  ["input.pedagogical_context.scenario", "教学情境"],
  ["input.pedagogical_context.learner_utterance", "学生回答"],
  ["plan.delivery_plan", "表达计划"],
  ["plan.delivery_plan.segment_overrides[2].emotion", "表达计划"],
  ["unknown.field", "评价证据（来源未识别）"],
])("labels %s without inventing a resolved target", (source, label) => {
  const { container } = render(<QualityCheck evaluation={evaluation(source, "证据原文")} />);
  expect(container.querySelector(".quality-grid cite")).toHaveTextContent(`来源：${label}`);
  expect(container.querySelector(".quality-grid")).not.toHaveTextContent(source);
});

it("shortens only the preview and preserves exact evidence and reason behind explicit disclosure", async () => {
  const source = "plan.verbal_plan.segments[0].text";
  const text = "保留证据原文，不推断或改写。".repeat(15);
  const data = evaluation(source, text);
  const { container } = render(<QualityCheck evaluation={data} />);
  const preview = container.querySelector(".quality-grid .evidence-excerpt p")!;
  expect(preview).toHaveTextContent(`“${Array.from(text).slice(0, 72).join("")}…”`);
  const user = userEvent.setup();
  await user.click(screen.getByText("查看详细评价"));
  const article = container.querySelector(".evaluation-detail")! as HTMLElement;
  expect(article.querySelector(".evidence-excerpt p")).toHaveTextContent(`“${Array.from(text).slice(0, 72).join("")}…”`);
  expect(article.querySelectorAll(".evidence-excerpt")).toHaveLength(1);
  const pre = article.querySelector("pre")!;
  expect(pre).not.toBeVisible();
  await user.click(within(article).getByText("查看原始评价"));
  expect(pre).toBeVisible();
  expect(JSON.parse(pre.textContent!)).toEqual({
    brief_justification: data.scores.pedagogical_intent_fidelity!.brief_justification,
    evidence: [{ source, text }],
  });
});

it("discloses the six original judgments independently without changing the approved summary", async () => {
  const data = recorded("supportive-feedback").evaluation;
  const original = JSON.stringify(data);
  const { container } = render(<QualityCheck evaluation={data} />);
  const grid = container.querySelector(".quality-grid")!;
  const summaryBefore = grid.innerHTML;
  const user = userEvent.setup();
  await user.click(screen.getByText("查看详细评价"));
  const articles = [...container.querySelectorAll<HTMLElement>(".evaluation-detail")];
  expect(articles).toHaveLength(6);
  for (const article of articles) {
    expect(article.querySelector("h3")).toBeVisible();
    expect(article.querySelectorAll(".evidence-excerpt")).toHaveLength(1);
    expect(article.querySelector(".evidence-excerpt cite")).toBeVisible();
    expect(article.querySelector("pre")).not.toBeVisible();
    expect(article.querySelector(":scope > p")).toBeNull();
  }
  await user.click(within(articles[0]).getByText("查看原始评价"));
  expect(articles[0].querySelector("pre")).toBeVisible();
  expect(JSON.parse(articles[0].querySelector("pre")!.textContent!)).toEqual({
    brief_justification: data.scores.pedagogical_intent_fidelity!.brief_justification,
    evidence: data.scores.pedagogical_intent_fidelity!.evidence,
  });
  for (const article of articles.slice(1)) expect(article.querySelector("pre")).not.toBeVisible();
  await user.click(within(articles[0]).getByText("查看原始评价"));
  expect(articles[0].querySelector("pre")).not.toBeVisible();
  expect(grid.innerHTML).toBe(summaryBefore);
  expect(JSON.stringify(data)).toBe(original);
});

it("keeps structured and missing evidence honest instead of inventing quotations", () => {
  const data = evaluation("plan.delivery_plan", "{}");
  data.scores.content_faithfulness_boundary = { score: 2, brief_justification: "No excerpt.", evidence: [] };
  const { container } = render(<QualityCheck evaluation={data} />);
  const grid = container.querySelector(".quality-grid")! as HTMLElement;
  expect(within(grid).getByText("未设置额外表达控制（空表达计划）。")).toBeVisible();
  expect(within(grid).getByText("未提供证据片段。")).toBeVisible();
  expect(grid.querySelector("mark")).toBeNull();
  expect(grid).not.toHaveTextContent("{}");
  expect(grid).toHaveTextContent("2/4");
  expect(grid).toHaveTextContent("未返回");
});

it("previews an existing structured tone and a known Chinese state label while retaining raw values", () => {
  const data = evaluation("plan.delivery_plan", '{"global":{"attitudinal_tone":"安抚但纠正"}}');
  data.scores.learner_state_compatibility = {
    score: 4, brief_justification: "Matches the learner state.",
    evidence: [{ source: "input.learner.affective_state", text: "slightly_frustrated" }],
  };
  const original = JSON.stringify(data);
  const { container } = render(<QualityCheck evaluation={data} />);
  const grid = container.querySelector(".quality-grid")! as HTMLElement;
  expect(within(grid).getByText("安抚但纠正").tagName).toBe("MARK");
  expect(within(grid).getByText("有些挫败").tagName).toBe("MARK");
  expect(grid).not.toHaveTextContent("slightly_frustrated");
  expect(container.querySelector("pre")).toHaveTextContent('attitudinal_tone');
  expect(JSON.stringify(data)).toBe(original);
});

it("retains flagged evidence safely, including HTML-looking text", async () => {
  const text = "<img src=x onerror=alert(1)>";
  const data = evaluation("input.instructional_content.content_anchor", text);
  data.critical_flags = [{ flag: "test_flag", brief_justification: "Check plan.delivery_plan.", evidence: [{ source: "plan.delivery_plan", text: "控制原文" }] }];
  const { container } = render(<QualityCheck evaluation={data} />);
  expect(screen.getByText(/检查发现需要关注的问题/)).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
  await userEvent.setup().click(screen.getByText("查看详细评价"));
  expect(screen.queryByText("Check 表达计划.")).not.toBeInTheDocument();
  expect(screen.getByText("需关注的问题")).toBeVisible();
  for (const raw of container.querySelectorAll("pre")) expect(raw).not.toBeVisible();
  await userEvent.setup().click(screen.getAllByText("查看原始评价").at(-1)!);
  const flaggedRaw = [...container.querySelectorAll("pre")].at(-1)!;
  expect(flaggedRaw).toBeVisible();
  expect(JSON.parse(flaggedRaw.textContent!).brief_justification).toBe("Check plan.delivery_plan.");
});
