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
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Learner profile
          </p>
          <div className="grid gap-2">
            <ProfileRow
              label="Level"
              value={input.learner.level}
              evidenceTexts={evidenceTextsForContextField(
                evidenceTargets,
                "learner.level",
              )}
            />
            <ProfileRow
              label="Knowledge"
              value={input.learner.knowledge_state}
              evidenceTexts={evidenceTextsForContextField(
                evidenceTargets,
                "learner.knowledge_state",
              )}
            />
            <ProfileRow
              label="Affect"
              value={input.learner.affective_state}
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

function ProfileRow({
  label,
  value,
  evidenceTexts,
}: {
  label: string;
  value: string | undefined;
  evidenceTexts: string[];
}) {
  return (
    <ContextField
      label={label}
      value={value}
      compact
      evidenceTexts={evidenceTexts}
    />
  );
}
