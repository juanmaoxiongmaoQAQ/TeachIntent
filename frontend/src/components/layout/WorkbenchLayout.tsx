import type { ReactNode } from "react";

interface WorkbenchLayoutProps {
  context: ReactNode;
  speech: ReactNode;
  evaluation: ReactNode;
}

export function WorkbenchLayout({
  context,
  speech,
  evaluation,
}: WorkbenchLayoutProps) {
  return (
    <div className="grid gap-5 xl:grid-cols-[32fr_34fr_34fr]">
      {context}
      {speech}
      {evaluation}
    </div>
  );
}
