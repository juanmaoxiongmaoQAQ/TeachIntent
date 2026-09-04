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
  evaluation: EvaluationArtifact;
  selectedDimension: DimensionId;
  onDimensionChange: (dimension: DimensionId) => void;
}

export function EvaluationPanel({
  evaluation,
  selectedDimension,
  onDimensionChange,
}: EvaluationPanelProps) {
  const selectedEvidenceCount = useMemo(() => {
    return resolveJudgmentEvidence(evaluation.scores[selectedDimension]).length;
  }, [evaluation, selectedDimension]);

  return (
    <Panel title="Evaluation">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusBadge tone="accent">Recorded Evaluator v0.1</StatusBadge>
        <StatusBadge tone="muted">Recorded evidence</StatusBadge>
      </div>
      {!evaluation.available ? (
        <EmptyState
          title="Recorded evaluator artifact unavailable."
          description={evaluation.reason ?? "No portable public evaluator artifact was loaded."}
        />
      ) : (
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
      )}
    </Panel>
  );
}
