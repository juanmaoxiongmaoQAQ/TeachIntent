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
        "rounded-xl border bg-slate-50",
        compact ? "px-3 py-2" : "p-4",
        hasHighlight ? "border-amber-300 bg-amber-50/50" : "border-slate-200",
      )}
    >
      <p
        className={cn(
          "text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500",
          compact ? "mb-1" : "mb-2",
        )}
      >
        {label}
      </p>
      <div
        className={cn(
          "whitespace-pre-wrap text-sm text-slate-900",
          compact ? "leading-5" : "leading-6",
        )}
      >
        {highlighted}
      </div>
    </div>
  );
}
