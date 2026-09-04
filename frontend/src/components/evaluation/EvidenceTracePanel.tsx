import {
  resolveJudgmentEvidence,
  type EvidenceTarget,
} from "../../lib/evidence";
import type {
  DimensionId,
  DimensionJudgment,
  EvaluationArtifact,
} from "../../types/teachintent";
import { EmptyState } from "../common/EmptyState";
import { DIMENSIONS } from "../../lib/dimensions";

interface EvidenceTracePanelProps {
  evaluation: EvaluationArtifact;
  selectedDimension: DimensionId;
}

function selectedDimensionMeta(dimensionId: DimensionId) {
  return DIMENSIONS.find((dimension) => dimension.id === dimensionId) ?? DIMENSIONS[0];
}

function groupedLabels(targets: EvidenceTarget[]): string[] {
  return Array.from(new Set(targets.map((target) => target.label)));
}

function unresolvedTargets(targets: EvidenceTarget[]): EvidenceTarget[] {
  return targets.filter((target) => !target.resolved);
}

export function EvidenceTracePanel({
  evaluation,
  selectedDimension,
}: EvidenceTracePanelProps) {
  const dimension = selectedDimensionMeta(selectedDimension);
  const judgment: DimensionJudgment | undefined = evaluation.scores[selectedDimension];

  if (!evaluation.available) {
    return (
      <EmptyState
        title="Recorded evaluator artifact unavailable."
        description={evaluation.reason ?? "No portable public evaluator artifact was loaded."}
      />
    );
  }
  if (!judgment) {
    return (
      <EmptyState
        title="No dimension judgment"
        description="The selected dimension is not present in the evaluator artifact."
      />
    );
  }

  const targets = resolveJudgmentEvidence(judgment);
  const unresolved = unresolvedTargets(targets);
  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          Evidence Trace
        </p>
        <h3 className="mt-1 text-[13px] font-semibold text-slate-950">
          {dimension.key} {dimension.label}
        </h3>
        <p className="mt-1 text-sm font-semibold text-slate-800">
          Score {judgment.score} / 4
        </p>
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Grounded in
        </p>
        <div className="flex flex-wrap gap-2">
          {groupedLabels(targets).map((label) => (
            <span
              key={label}
              className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700"
            >
              {label}
            </span>
          ))}
        </div>
      </div>
      {unresolved.map((target) => (
        <div
          key={`${target.source}-${target.text}`}
          className="rounded-lg border border-amber-200 bg-amber-50 p-3"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-900">
            Unresolved grounded excerpt
          </p>
          <blockquote className="mt-2 text-sm text-slate-900">
            “{target.text}”
          </blockquote>
          <p className="mt-2 font-mono text-xs text-slate-500">
            source: {target.source}
          </p>
        </div>
      ))}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Judge rationale
        </p>
        <p className="max-w-prose text-sm leading-6 text-slate-800">
          {judgment.brief_justification}
        </p>
      </div>
    </section>
  );
}
