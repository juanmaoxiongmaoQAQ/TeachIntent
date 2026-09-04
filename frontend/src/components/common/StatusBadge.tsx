import { cn } from "../../lib/utils";

interface StatusBadgeProps {
  children: string;
  tone?: "default" | "accent" | "muted" | "warning";
}

export function StatusBadge({ children, tone = "default" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        tone === "default" && "border-slate-200 bg-slate-50 text-slate-700",
        tone === "accent" && "border-indigo-200 bg-indigo-50 text-indigo-700",
        tone === "muted" && "border-slate-200 bg-white text-slate-500",
        tone === "warning" && "border-amber-200 bg-amber-50 text-amber-800",
      )}
    >
      {children}
    </span>
  );
}
