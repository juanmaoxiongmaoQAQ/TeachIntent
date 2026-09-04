import { useState } from "react";

import { compareIntents } from "../api/teachintent";
import {
  IntentCompareForm,
} from "../components/compare/IntentCompareForm";
import { CompareInvariantBar } from "../components/compare/CompareInvariantBar";
import { IntentPlanColumn } from "../components/compare/IntentPlanColumn";
import { StructuralContrast } from "../components/compare/StructuralContrast";
import { EmptyState } from "../components/common/EmptyState";
import { Panel } from "../components/common/Panel";
import { TeachingContextPanel } from "../components/context/TeachingContextPanel";
import { EMPTY_COMPARE_FORM, SHOWCASE_COMPARE_FORM } from "../lib/compare";
import type { IntentCompareRequest, IntentCompareResponse } from "../types/teachintent";

export function IntentComparePage() {
  const [form, setForm] = useState<IntentCompareRequest>(EMPTY_COMPARE_FORM);
  const [comparison, setComparison] = useState<IntentCompareResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadShowcaseScenario() {
    setError(null);
    setForm(SHOWCASE_COMPARE_FORM);
  }

  function swapIntents() {
    setForm((previous) => ({
      ...previous,
      left_intent: previous.right_intent,
      right_intent: previous.left_intent,
    }));
  }

  async function handleCompare() {
    setGenerating(true);
    setError(null);
    try {
      const payload = await compareIntents({
        ...form,
        learner_utterance: form.learner_utterance?.trim()
          ? form.learner_utterance
          : null,
        affective_state: form.affective_state?.trim()
          ? form.affective_state
          : null,
      });
      setComparison(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison incomplete.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-5">
      <Panel>
        <IntentCompareForm
          form={form}
          generating={generating}
          onChange={setForm}
          onLoadShowcase={loadShowcaseScenario}
          onSwap={swapIntents}
          onSubmit={handleCompare}
        />
      </Panel>

      {error ? (
        <EmptyState
          title="Comparison incomplete"
          description={error}
        />
      ) : null}

      {comparison ? (
        <div className="space-y-5">
          <CompareInvariantBar comparison={comparison.comparison} />
          <TeachingContextPanel
            input={comparison.left.input}
            evidenceTargets={[]}
            hidePedagogicalIntent
          />
          <div className="grid gap-5 xl:grid-cols-2">
            <IntentPlanColumn
              label="Intent A"
              intent={comparison.comparison.left_intent}
              result={comparison.left}
            />
            <IntentPlanColumn
              label="Intent B"
              intent={comparison.comparison.right_intent}
              result={comparison.right}
            />
          </div>
          <StructuralContrast contrast={comparison.structural_contrast} />
          <Panel title="Application scope">
            <p className="text-sm leading-6 text-slate-600">
              Intent Compare focuses on planning behavior. Evaluation remains
              available in Live Studio.
            </p>
          </Panel>
          <TechnicalDetails comparison={comparison} />
        </div>
      ) : null}
    </div>
  );
}

function TechnicalDetails({
  comparison,
}: {
  comparison: IntentCompareResponse;
}) {
  const details = {
    mode: comparison.mode,
    changed_input_field: comparison.comparison.changed_input_field,
    all_other_input_fields_equal:
      comparison.comparison.all_other_input_fields_equal,
    prompt_version: comparison.comparison.prompt_version,
    left_requested_model: comparison.left.generation.requested_model,
    left_reported_model: comparison.left.generation.reported_model,
    left_duration_seconds: comparison.left.generation.duration_seconds,
    right_requested_model: comparison.right.generation.requested_model,
    right_reported_model: comparison.right.generation.reported_model,
    right_duration_seconds: comparison.right.generation.duration_seconds,
  };
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">
        Technical details
      </summary>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <SafeJson title="Comparison metadata" value={details} />
        <SafeJson title="Left validated input JSON" value={comparison.left.input} />
        <SafeJson title="Right validated input JSON" value={comparison.right.input} />
        <SafeJson title="Left Speech Plan JSON" value={comparison.left.speech_plan} />
        <SafeJson title="Right Speech Plan JSON" value={comparison.right.speech_plan} />
      </div>
    </details>
  );
}

function SafeJson({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        {title}
      </p>
      <pre className="max-h-80 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-5 text-slate-100">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
