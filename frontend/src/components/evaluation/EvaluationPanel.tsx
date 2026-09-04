import { useMemo } from "react";

import { resolveJudgmentEvidence } from "../../lib/evidence";
import type { DimensionId, EvaluationArtifact } from "../../types/teachintent";
import { EmptyState } from "../common/EmptyState";
import { Panel } from "../common/Panel";
import { StatusBadge } from "../common/StatusBadge";
import { CriticalFlags } from "./CriticalFlags";
import { DimensionSelector } from "./DimensionSelector";
import { EvidenceTracePanel } from "./EvidenceTracePanel";

interface EvaluationPanelProps {
  evaluation: EvaluationArtifact | null;
  mode: "recorded" | "live";
  selectedDimension: DimensionId;
  onDimensionChange: (dimension: DimensionId) => void;
  evaluating?: boolean;
  onEvaluate?: () => void;
}

export function EvaluationPanel({
  evaluation,
  mode,
  selectedDimension,
  onDimensionChange,
  evaluating = false,
  onEvaluate,
}: EvaluationPanelProps) {
  const selectedEvidenceCount = useMemo(() => {
    return resolveJudgmentEvidence(evaluation?.scores[selectedDimension]).length;
  }, [evaluation, selectedDimension]);

  return (
    <Panel title="Evaluation">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusBadge tone="accent">
          {mode === "recorded"
            ? "Recorded Evaluator v0.1"
            : "Live Evaluator v0.1"}
        </StatusBadge>
        <StatusBadge tone="muted">
          {mode === "recorded" ? "Recorded evidence" : "Independent Judge"}
        </StatusBadge>
      </div>
      {evaluation === null ? (
        <div className="space-y-4">
          <EmptyState
            title="Evaluation not run yet"
            description="Generate the Speech Plan first, then run the independent Evaluator."
          />
          {onEvaluate ? (
            <button
              type="button"
              onClick={onEvaluate}
              disabled={evaluating}
              className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {evaluating ? "Evaluating…" : "Evaluate this plan"}
            </button>
          ) : null}
        </div>
      ) : null}
      {evaluation !== null && !evaluation.available ? (
        <EmptyState
          title={
            mode === "recorded"
              ? "Recorded evaluator artifact unavailable."
              : "Evaluation unavailable"
          }
          description={
            evaluation.failure_summary ??
            evaluation.reason ??
            "No evaluator artifact was loaded."
          }
        />
      ) : (
        evaluation !== null && (
        <div className="space-y-4">
          <DimensionSelector
            evaluation={evaluation}
            selectedDimension={selectedDimension}
            onChange={onDimensionChange}
          />
          <p className="text-xs text-slate-500">
            Selected dimension uses {selectedEvidenceCount} grounded evidence item
            {selectedEvidenceCount === 1 ? "" : "s"}.
          </p>
          <EvidenceTracePanel
            evaluation={evaluation}
            selectedDimension={selectedDimension}
          />
          <CriticalFlags evaluation={evaluation} />
        </div>
        )
      )}
    </Panel>
  );
}
