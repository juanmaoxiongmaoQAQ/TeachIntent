import { cn } from "../../lib/utils";
import type { DimensionId, EvaluationArtifact } from "../../types/teachintent";
import { DIMENSIONS } from "../../lib/dimensions";

interface DimensionSelectorProps {
  evaluation: EvaluationArtifact;
  selectedDimension: DimensionId;
  onChange: (dimension: DimensionId) => void;
}

export function DimensionSelector({
  evaluation,
  selectedDimension,
  onChange,
}: DimensionSelectorProps) {
  return (
    <div className="grid gap-2">
      {DIMENSIONS.map((dimension) => {
        const judgment = evaluation.scores[dimension.id];
        const selected = selectedDimension === dimension.id;
        return (
          <button
            key={dimension.id}
            type="button"
            onClick={() => onChange(dimension.id)}
            className={cn(
              "flex items-center justify-between rounded-xl border p-3 text-left transition-colors",
              selected
                ? "border-indigo-300 bg-indigo-50"
                : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50",
            )}
          >
            <span>
              <span className="mr-2 font-mono text-xs text-slate-500">
                {dimension.key}
              </span>
              <span className="text-sm font-medium text-slate-950">
                {dimension.shortLabel}
              </span>
            </span>
            <span className="text-sm font-semibold text-slate-900">
              {judgment ? `${judgment.score}/4` : "—"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
