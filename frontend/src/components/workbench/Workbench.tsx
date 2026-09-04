import { useMemo, useState } from "react";

import { resolveJudgmentEvidence } from "../../lib/evidence";
import type {
  DimensionId,
  EvaluationArtifact,
  GenerationMetadata,
  SpeechPlan,
  TeachIntentInput,
} from "../../types/teachintent";
import { Panel } from "../common/Panel";
import { StatusBadge } from "../common/StatusBadge";
import { TeachingContextPanel } from "../context/TeachingContextPanel";
import { EvaluationPanel } from "../evaluation/EvaluationPanel";
import { WorkbenchLayout } from "../layout/WorkbenchLayout";
import { SpeechPlanPanel } from "../speech/SpeechPlanPanel";

const DEFAULT_DIMENSION: DimensionId = "pedagogical_intent_fidelity";

interface WorkbenchProps {
  input: TeachIntentInput;
  speechPlan: SpeechPlan;
  evaluation: EvaluationArtifact | null;
  mode: "recorded" | "live";
  generationMeta?: GenerationMetadata;
  evaluating?: boolean;
  onEvaluate?: () => void;
}

export function Workbench({
  input,
  speechPlan,
  evaluation,
  mode,
  generationMeta,
  evaluating = false,
  onEvaluate,
}: WorkbenchProps) {
  const [selectedDimension, setSelectedDimension] =
    useState<DimensionId>(DEFAULT_DIMENSION);
  const selectedJudgment = evaluation?.scores[selectedDimension];
  const evidenceTargets = useMemo(
    () => resolveJudgmentEvidence(selectedJudgment),
    [selectedJudgment],
  );

  return (
    <div className="space-y-5">
      {mode === "live" ? (
        <Panel>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="accent">Live Hy3 · Prompt v0.2</StatusBadge>
            {evaluation?.available ? (
              <StatusBadge tone="accent">
                Live Evaluator v0.1 · Independent Judge
              </StatusBadge>
            ) : null}
            {generationMeta ? (
              <StatusBadge tone="muted">
                Live application evaluation · Not part of frozen research results
              </StatusBadge>
            ) : null}
          </div>
        </Panel>
      ) : null}
      <WorkbenchLayout
        context={
          <TeachingContextPanel
            input={input}
            evidenceTargets={evidenceTargets}
          />
        }
        speech={
          <SpeechPlanPanel
            speechPlan={speechPlan}
            evidenceTargets={evidenceTargets}
          />
        }
        evaluation={
          <EvaluationPanel
            evaluation={evaluation}
            mode={mode}
            selectedDimension={selectedDimension}
            onDimensionChange={setSelectedDimension}
            evaluating={evaluating}
            onEvaluate={onEvaluate}
          />
        }
      />
    </div>
  );
}
