import { createElement, Fragment, type ReactNode } from "react";

interface MatchRange {
  start: number;
  end: number;
}

function findExactMatches(fullText: string, evidenceTexts: string[]): MatchRange[] {
  const ranges: MatchRange[] = [];
  for (const evidenceText of evidenceTexts) {
    if (!evidenceText) {
      continue;
    }
    let searchFrom = 0;
    while (searchFrom < fullText.length) {
      const start = fullText.indexOf(evidenceText, searchFrom);
      if (start === -1) {
        break;
      }
      ranges.push({ start, end: start + evidenceText.length });
      searchFrom = start + evidenceText.length;
    }
  }
  return ranges
    .sort((a, b) => a.start - b.start || b.end - a.end)
    .reduce<MatchRange[]>((accepted, range) => {
      const overlaps = accepted.some(
        (existing) => range.start < existing.end && range.end > existing.start,
      );
      return overlaps ? accepted : [...accepted, range];
    }, []);
}

export function highlightExactText(
  fullText: string,
  evidenceTexts: string[],
): ReactNode[] {
  const ranges = findExactMatches(fullText, evidenceTexts);
  if (ranges.length === 0) {
    return [fullText];
  }

  const nodes: ReactNode[] = [];
  let cursor = 0;
  ranges.forEach((range, index) => {
    if (range.start > cursor) {
      nodes.push(fullText.slice(cursor, range.start));
    }
    nodes.push(
      createElement("mark", { key: `mark-${index}` }, fullText.slice(range.start, range.end)),
    );
    cursor = range.end;
  });
  if (cursor < fullText.length) {
    nodes.push(fullText.slice(cursor));
  }
  return [createElement(Fragment, { key: "highlight-root" }, ...nodes)];
}
