import type { ReactNode } from "react";

import { highlightExactText } from "../../lib/highlight";
import { cn } from "../../lib/utils";

interface ContextFieldProps {
  label: string;
  value: string | undefined;
  evidenceTexts?: string[];
  compact?: boolean;
}

export function ContextField({
  label,
  value,
  evidenceTexts = [],
  compact = false,
}: ContextFieldProps) {
  if (!value) {
    return null;
  }
  const highlighted: ReactNode[] = highlightExactText(value, evidenceTexts);
  const hasHighlight = evidenceTexts.some((text) => text && value.includes(text));
  return (
    <div
      className={cn(
        "rounded-xl border bg-slate-50 p-4",
        compact ? "p-3" : "p-4",
        hasHighlight ? "border-amber-300 bg-amber-50/50" : "border-slate-200",
      )}
    >
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <div className="whitespace-pre-wrap text-sm leading-6 text-slate-900">
        {highlighted}
      </div>
    </div>
  );
}
