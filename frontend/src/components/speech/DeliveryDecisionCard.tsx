import {
  evidenceTextsForDeliveryField,
  type EvidenceTarget,
} from "../../lib/evidence";
import { highlightExactText } from "../../lib/highlight";
import { cn } from "../../lib/utils";
import type { DeliveryFieldKey, DeliveryPlan } from "../../types/teachintent";
import { StatusBadge } from "../common/StatusBadge";

interface DeliveryDecisionCardProps {
  deliveryPlan: DeliveryPlan;
  evidenceTargets: EvidenceTarget[];
}

interface DeliveryField {
  key: DeliveryFieldKey;
  label: string;
  value: string | undefined;
}

export function DeliveryDecisionCard({
  deliveryPlan,
  evidenceTargets,
}: DeliveryDecisionCardProps) {
  const global = deliveryPlan.global;
  const allFields: DeliveryField[] = [
    {
      key: "delivery_plan.global.attitudinal_tone",
      label: "Attitudinal tone",
      value: global?.attitudinal_tone,
    },
    {
      key: "delivery_plan.global.emotion",
      label: "Emotion",
      value: global?.emotion,
    },
    {
      key: "delivery_plan.global.prosody.speaking_rate",
      label: "Speaking rate",
      value: global?.prosody?.speaking_rate,
    },
    {
      key: "delivery_plan.global.prosody.volume",
      label: "Volume",
      value: global?.prosody?.volume,
    },
  ];
  const fields = allFields.filter((field) => field.value);

  if (fields.length === 0) {
    return (
      <section>
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          How to say
        </p>
        <article className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
          <p className="text-sm font-semibold text-slate-950">
            Delivery decision
          </p>
          <div className="mt-3">
            <StatusBadge tone="accent">Default rendering selected</StatusBadge>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">
            TeachIntent selected no additional delivery control for this case.
          </p>
        </article>
      </section>
    );
  }

  return (
    <section>
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        How to say
      </p>
      <article className="space-y-3 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">
            Delivery decision
          </p>
          <div className="mt-3">
            <StatusBadge tone="accent">Selective delivery control added</StatusBadge>
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Scope
          </p>
          <p className="text-sm text-slate-950">Global</p>
        </div>
        {fields.map((field) => {
          const evidenceTexts = evidenceTextsForDeliveryField(
            evidenceTargets,
            field.key,
          );
          const value = field.value ?? "";
          const hasHighlight = evidenceTexts.some((text) =>
            value.includes(text),
          );
          return (
            <div
              key={field.key}
              className={cn(
                "rounded-lg border bg-white p-3",
                hasHighlight
                  ? "border-amber-300 bg-amber-50/60"
                  : "border-slate-200",
              )}
            >
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                {field.label}
              </p>
              <p className="text-sm text-slate-950">
                {highlightExactText(value, evidenceTexts)}
              </p>
            </div>
          );
        })}
      </article>
    </section>
  );
}
