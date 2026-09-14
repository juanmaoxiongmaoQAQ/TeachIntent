import { deliveryFor } from "../../lib/product";
import type { SpeechPlan } from "../../types/teachintent";

export function PlanView({ plan }: { plan: SpeechPlan }) {
  return (
    <section aria-label="教学语音计划" className="plan-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">说什么 · 怎么说</p>
          <h2>教学语音计划</h2>
        </div>
        <span className="subtle">
          {plan.verbal_plan.segments.length} 个教学步骤
        </span>
      </div>
      <ol className="teaching-steps">
        {plan.verbal_plan.segments.map((segment, index) => {
          const labels = deliveryFor(plan.delivery_plan, segment.segment_id);
          return (
            <li key={segment.segment_id}>
              <span className="step-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="step-text">{segment.text}</p>
                <p className="delivery-note">
                  <span>表达：</span>
                  {labels.length ? labels.join(" · ") : "本段无需额外表达控制"}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
