import {
  evidenceTextsForDeliveryField,
  type EvidenceTarget,
} from "../../lib/evidence";
import { highlightExactText } from "../../lib/highlight";
import { cn } from "../../lib/utils";
import type {
  BoundaryAfter,
  DeliveryFieldKey,
  DeliveryPlan,
  GlobalDelivery,
  ProminenceTarget,
  SegmentOverride,
} from "../../types/teachintent";
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
  if (Object.keys(deliveryPlan).length === 0) {
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
        {deliveryPlan.global ? (
          <GlobalControl
            global={deliveryPlan.global}
            evidenceTargets={evidenceTargets}
          />
        ) : null}
        {deliveryPlan.segment_overrides?.length ? (
          <SegmentControls
            overrides={deliveryPlan.segment_overrides}
            evidenceTargets={evidenceTargets}
          />
        ) : null}
      </article>
    </section>
  );
}

function GlobalControl({
  global,
  evidenceTargets,
}: {
  global: GlobalDelivery;
  evidenceTargets: EvidenceTarget[];
}) {
  const allFields: DeliveryField[] = [
    {
      key: "delivery_plan.global.attitudinal_tone",
      label: "Attitudinal tone",
      value: global.attitudinal_tone,
    },
    {
      key: "delivery_plan.global.emotion",
      label: "Emotion",
      value: global.emotion,
    },
    {
      key: "delivery_plan.global.prosody.speaking_rate",
      label: "Speaking rate",
      value: global.prosody?.speaking_rate,
    },
    {
      key: "delivery_plan.global.prosody.pitch_level",
      label: "Pitch level",
      value: global.prosody?.pitch_level,
    },
    {
      key: "delivery_plan.global.prosody.pitch_range",
      label: "Pitch range",
      value: global.prosody?.pitch_range,
    },
    {
      key: "delivery_plan.global.prosody.volume",
      label: "Volume",
      value: global.prosody?.volume,
    },
  ];
  const fields = allFields.filter((field) => field.value);

  if (fields.length === 0) {
    return null;
  }
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        Global control
      </p>
      {fields.map((field) => (
        <DeliveryValue
          key={field.key}
          field={field}
          evidenceTargets={evidenceTargets}
        />
      ))}
    </div>
  );
}

function SegmentControls({
  overrides,
  evidenceTargets,
}: {
  overrides: SegmentOverride[];
  evidenceTargets: EvidenceTarget[];
}) {
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        Segment controls
      </p>
      {overrides.map((override, index) => (
        <SegmentControl
          key={`${override.segment_id}-${index}`}
          override={override}
          index={index}
          evidenceTargets={evidenceTargets}
        />
      ))}
    </div>
  );
}

function SegmentControl({
  override,
  index,
  evidenceTargets,
}: {
  override: SegmentOverride;
  index: number;
  evidenceTargets: EvidenceTarget[];
}) {
  const fields: DeliveryField[] = [
    {
      key: `delivery_plan.segment_overrides[${index}].attitudinal_tone`,
      label: "Attitudinal tone",
      value: override.attitudinal_tone,
    },
    {
      key: `delivery_plan.segment_overrides[${index}].emotion`,
      label: "Emotion",
      value: override.emotion,
    },
    {
      key: `delivery_plan.segment_overrides[${index}].prosody.speaking_rate`,
      label: "Speaking rate",
      value: override.prosody?.speaking_rate,
    },
    {
      key: `delivery_plan.segment_overrides[${index}].prosody.pitch_level`,
      label: "Pitch level",
      value: override.prosody?.pitch_level,
    },
    {
      key: `delivery_plan.segment_overrides[${index}].prosody.pitch_range`,
      label: "Pitch range",
      value: override.prosody?.pitch_range,
    },
    {
      key: `delivery_plan.segment_overrides[${index}].prosody.volume`,
      label: "Volume",
      value: override.prosody?.volume,
    },
    {
      key: `delivery_plan.segment_overrides[${index}].contour_shape`,
      label: "Contour shape",
      value: override.contour_shape,
    },
  ].filter((field) => field.value) as DeliveryField[];

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Segment control
        </p>
        <p className="mt-1 font-mono text-sm font-semibold text-slate-950">
          {override.segment_id}
        </p>
      </div>
      {fields.map((field) => (
        <DeliveryValue
          key={field.key}
          field={field}
          evidenceTargets={evidenceTargets}
        />
      ))}
      {override.prominence_targets?.map((target, targetIndex) => (
        <ProminenceTargetView
          key={`${target.text}-${targetIndex}`}
          target={target}
          segmentIndex={index}
          targetIndex={targetIndex}
          evidenceTargets={evidenceTargets}
        />
      ))}
      {override.boundary_after ? (
        <BoundaryAfterView
          boundaryAfter={override.boundary_after}
          segmentIndex={index}
          evidenceTargets={evidenceTargets}
        />
      ) : null}
    </div>
  );
}

function DeliveryValue({
  field,
  evidenceTargets,
}: {
  field: DeliveryField;
  evidenceTargets: EvidenceTarget[];
}) {
  const evidenceTexts = evidenceTextsForDeliveryField(evidenceTargets, field.key);
  const value = field.value ?? "";
  const hasHighlight = evidenceTexts.some((text) => value.includes(text));
  return (
    <div
      className={cn(
        "rounded-lg border bg-white p-3",
        hasHighlight ? "border-amber-300 bg-amber-50/60" : "border-slate-200",
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
}

function ProminenceTargetView({
  target,
  segmentIndex,
  targetIndex,
  evidenceTargets,
}: {
  target: ProminenceTarget;
  segmentIndex: number;
  targetIndex: number;
  evidenceTargets: EvidenceTarget[];
}) {
  const textKey =
    `delivery_plan.segment_overrides[${segmentIndex}].prominence_targets[${targetIndex}].text` as DeliveryFieldKey;
  const levelKey =
    `delivery_plan.segment_overrides[${segmentIndex}].prominence_targets[${targetIndex}].level` as DeliveryFieldKey;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        Prominence target
      </p>
      <DeliveryValue
        field={{ key: textKey, label: "Text", value: target.text }}
        evidenceTargets={evidenceTargets}
      />
      {target.level ? (
        <div className="mt-2">
          <DeliveryValue
            field={{ key: levelKey, label: "Level", value: target.level }}
            evidenceTargets={evidenceTargets}
          />
        </div>
      ) : null}
    </div>
  );
}

function BoundaryAfterView({
  boundaryAfter,
  segmentIndex,
  evidenceTargets,
}: {
  boundaryAfter: BoundaryAfter;
  segmentIndex: number;
  evidenceTargets: EvidenceTarget[];
}) {
  if (!boundaryAfter.strength) {
    return null;
  }
  const strengthKey =
    `delivery_plan.segment_overrides[${segmentIndex}].boundary_after.strength` as DeliveryFieldKey;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        Boundary after
      </p>
      <DeliveryValue
        field={{ key: strengthKey, label: "Strength", value: boundaryAfter.strength }}
        evidenceTargets={evidenceTargets}
      />
    </div>
  );
}
