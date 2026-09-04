import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface PanelProps {
  title?: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, eyebrow, children, className }: PanelProps) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm",
        className,
      )}
    >
      {eyebrow ? (
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          {eyebrow}
        </p>
      ) : null}
      {title ? (
        <h2 className="mb-4 text-lg font-semibold text-slate-950">{title}</h2>
      ) : null}
      {children}
    </section>
  );
}
