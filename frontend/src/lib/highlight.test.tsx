import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { highlightExactText } from "./highlight";

function HighlightProbe({
  text,
  evidence,
}: {
  text: string;
  evidence: string[];
}) {
  return <p>{highlightExactText(text, evidence)}</p>;
}

describe("highlightExactText", () => {
  it("highlights an exact D2 content anchor substring", () => {
    render(
      <HighlightProbe
        text="若速度的大小和方向都保持不变，则加速度为0；即使速度大小不变，只要方向发生变化，加速度也不为0。"
        evidence={["即使速度大小不变，只要方向发生变化，加速度也不为0。"]}
      />,
    );

    expect(screen.getByText("即使速度大小不变，只要方向发生变化，加速度也不为0。").tagName).toBe(
      "MARK",
    );
  });

  it("highlights an exact D6 delivery tone substring", () => {
    render(<HighlightProbe text="安抚但纠正" evidence={["安抚但纠正"]} />);

    expect(screen.getByText("安抚但纠正").tagName).toBe("MARK");
  });

  it("does not highlight unmatched evidence", () => {
    render(<HighlightProbe text="安抚但纠正" evidence={["不存在"]} />);

    expect(screen.queryByText("不存在")).not.toBeInTheDocument();
    expect(document.querySelector("mark")).not.toBeInTheDocument();
  });

  it("handles multiple exact evidence snippets", () => {
    render(<HighlightProbe text="alpha beta gamma" evidence={["alpha", "gamma"]} />);

    expect(document.querySelectorAll("mark")).toHaveLength(2);
  });

  it("treats HTML-looking user text as normal React text", () => {
    render(
      <HighlightProbe
        text="<img src=x onerror=alert(1)>"
        evidence={["<img src=x onerror=alert(1)>"]}
      />,
    );

    expect(screen.getByText("<img src=x onerror=alert(1)>").tagName).toBe("MARK");
    expect(document.querySelector("img")).not.toBeInTheDocument();
  });
});
