import {
  evidenceTextsForContextField,
  type EvidenceTarget,
} from "../../lib/evidence";
import type { TeachIntentInput } from "../../types/teachintent";
import { Panel } from "../common/Panel";
import { ContextField } from "./ContextField";

interface TeachingContextPanelProps {
  input: TeachIntentInput;
  evidenceTargets: EvidenceTarget[];
  hidePedagogicalIntent?: boolean;
}

export function TeachingContextPanel({
  input,
  evidenceTargets,
  hidePedagogicalIntent = false,
}: TeachingContextPanelProps) {
  return (
    <Panel title="Teaching Context">
      <div className="space-y-3">
        <ContextField
          label="Content anchor"
          value={input.instructional_content.content_anchor}
          evidenceTexts={evidenceTextsForContextField(
            evidenceTargets,
            "instructional_content.content_anchor",
          )}
        />
        <ContextField
          label="Teaching scenario"
          value={input.pedagogical_context.scenario}
          evidenceTexts={evidenceTextsForContextField(
            evidenceTargets,
            "pedagogical_context.scenario",
          )}
        />
        <ContextField
          label="Learner utterance"
          value={input.pedagogical_context.learner_utterance}
          evidenceTexts={evidenceTextsForContextField(
            evidenceTargets,
            "pedagogical_context.learner_utterance",
          )}
        />
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Learner profile
          </p>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
            <ContextField
              label="Level"
              value={input.learner.level}
              compact
              evidenceTexts={evidenceTextsForContextField(
                evidenceTargets,
                "learner.level",
              )}
            />
            <ContextField
              label="Knowledge state"
              value={input.learner.knowledge_state}
              compact
              evidenceTexts={evidenceTextsForContextField(
                evidenceTargets,
                "learner.knowledge_state",
              )}
            />
            <ContextField
              label="Affective state"
              value={input.learner.affective_state}
              compact
              evidenceTexts={evidenceTextsForContextField(
                evidenceTargets,
                "learner.affective_state",
              )}
            />
          </div>
        </div>
        {hidePedagogicalIntent ? null : (
          <ContextField
            label="Pedagogical intent"
            value={input.pedagogical_intent.primary}
            evidenceTexts={evidenceTextsForContextField(
              evidenceTargets,
              "pedagogical_intent.primary",
            )}
          />
        )}
      </div>
    </Panel>
  );
}
