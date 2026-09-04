import {
  evidenceTextsForVerbalSegment,
  type EvidenceTarget,
} from "../../lib/evidence";
import { highlightExactText } from "../../lib/highlight";
import { cn } from "../../lib/utils";
import type { VerbalSegment } from "../../types/teachintent";

interface VerbalPlanSectionProps {
  segments: VerbalSegment[];
  evidenceTargets: EvidenceTarget[];
}

export function VerbalPlanSection({
  segments,
  evidenceTargets,
}: VerbalPlanSectionProps) {
  return (
    <section>
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        What to say
      </p>
      <div className="space-y-3">
        {segments.map((segment, index) => {
          const evidenceTexts = evidenceTextsForVerbalSegment(
            evidenceTargets,
            index,
          );
          const hasHighlight = evidenceTexts.some((text) =>
            segment.text.includes(text),
          );
          return (
            <article
              key={segment.segment_id}
              className={cn(
                "rounded-xl border bg-slate-50 p-4",
                hasHighlight
                  ? "border-amber-300 bg-amber-50/50"
                  : "border-slate-200",
              )}
            >
              <p className="mb-2 font-mono text-xs text-slate-500">
                {segment.segment_id}
              </p>
              <div className="whitespace-pre-wrap text-sm leading-6 text-slate-950">
                {highlightExactText(segment.text, evidenceTexts)}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
