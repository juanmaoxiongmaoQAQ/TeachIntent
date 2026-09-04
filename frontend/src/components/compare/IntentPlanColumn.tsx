import type { CompareGenerationResult, PedagogicalIntent } from "../../types/teachintent";
import { Panel } from "../common/Panel";
import { StatusBadge } from "../common/StatusBadge";
import { SpeechPlanPanel } from "../speech/SpeechPlanPanel";

interface IntentPlanColumnProps {
  label: "Intent A" | "Intent B";
  intent: PedagogicalIntent;
  result: CompareGenerationResult;
}

export function IntentPlanColumn({ label, intent, result }: IntentPlanColumnProps) {
  return (
    <div className="space-y-4">
      <Panel>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          {label}
        </p>
        <p className="mt-1 font-mono text-lg font-semibold text-slate-950">
          {intent}
        </p>
        <div className="mt-3">
          <StatusBadge tone="accent">Live Hy3 · Prompt v0.2</StatusBadge>
        </div>
      </Panel>
      <SpeechPlanPanel speechPlan={result.speech_plan} evidenceTargets={[]} />
    </div>
  );
}
