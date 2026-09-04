import type { EvidenceTarget } from "../../lib/evidence";
import type { SpeechPlan } from "../../types/teachintent";
import { Panel } from "../common/Panel";
import { DeliveryDecisionCard } from "./DeliveryDecisionCard";
import { VerbalPlanSection } from "./VerbalPlanSection";

interface SpeechPlanPanelProps {
  speechPlan: SpeechPlan;
  evidenceTargets: EvidenceTarget[];
}

export function SpeechPlanPanel({
  speechPlan,
  evidenceTargets,
}: SpeechPlanPanelProps) {
  return (
    <Panel title="Speech Plan">
      <div className="space-y-6">
        <VerbalPlanSection
          segments={speechPlan.verbal_plan.segments}
          evidenceTargets={evidenceTargets}
        />
        <DeliveryDecisionCard
          deliveryPlan={speechPlan.delivery_plan}
          evidenceTargets={evidenceTargets}
        />
      </div>
    </Panel>
  );
}
