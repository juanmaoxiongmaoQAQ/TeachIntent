import { useState } from "react";

import {
  evaluateSpeechPlan,
  fetchWorkbench,
  generateSpeechPlan,
  renderWithBatonVoice,
} from "../api/teachintent";
import { EmptyState } from "../components/common/EmptyState";
import { Panel } from "../components/common/Panel";
import { StatusBadge } from "../components/common/StatusBadge";
import { Workbench } from "../components/workbench/Workbench";
import { SegmentedBatonCandidate } from "../components/workbench/SegmentedBatonCandidate";
import type {
  EvaluationArtifact,
  GenerateRequest,
  LiveGenerationResponse,
  BatonVoiceRenderResponse,
  PedagogicalIntent,
} from "../types/teachintent";

const INTENTS: PedagogicalIntent[] = [
  "elicitation",
  "scaffolding",
  "explanation",
  "corrective_feedback",
  "supportive_feedback",
  "extension",
];

const EMPTY_FORM: GenerateRequest = {
  content_anchor: "",
  teaching_scenario: "",
  learner_utterance: "",
  learner_level: "",
  knowledge_state: "",
  affective_state: "",
  pedagogical_intent: "corrective_feedback",
  prompt_version: "v0.2",
};

export function LiveStudioPage() {
  const [form, setForm] = useState<GenerateRequest>(EMPTY_FORM);
  const [generation, setGeneration] = useState<LiveGenerationResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationArtifact | null>(null);
  const [generating, setGenerating] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [renderState, setRenderState] = useState<"idle" | "rendering" | "success" | "unavailable" | "error">("idle");
  const [renderResult, setRenderResult] = useState<BatonVoiceRenderResponse | null>(null);

  function update<K extends keyof GenerateRequest>(
    key: K,
    value: GenerateRequest[K],
  ) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  async function loadShowcaseScenario() {
    setError(null);
    try {
      const showcase = await fetchWorkbench("corrective-feedback");
      setForm((previous) => ({
        prompt_version: previous.prompt_version ?? "v0.2",
        content_anchor: showcase.input.instructional_content.content_anchor,
        teaching_scenario: showcase.input.pedagogical_context.scenario,
        learner_utterance:
          showcase.input.pedagogical_context.learner_utterance ?? "",
        learner_level: showcase.input.learner.level,
        knowledge_state: showcase.input.learner.knowledge_state,
        affective_state: showcase.input.learner.affective_state ?? "",
        pedagogical_intent: showcase.input.pedagogical_intent.primary,
      }));
    } catch {
      setError("Could not load the showcase scenario. Check the backend connection and try again.");
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const response = await generateSpeechPlan({
        ...form,
        learner_utterance: form.learner_utterance?.trim()
          ? form.learner_utterance
          : null,
        affective_state: form.affective_state?.trim()
          ? form.affective_state
          : null,
      });
      setGeneration(response);
      setEvaluation(null);
      setRenderState("idle");
      setRenderResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleRender() {
    if (!generation || renderState === "rendering") return;
    setRenderState("rendering");
    setRenderResult(null);
    try {
      const response = await renderWithBatonVoice(generation.session_id);
      setRenderResult(response);
      setRenderState(response.status);
    } catch {
      setRenderState("error");
      setRenderResult({ session_id: generation.session_id, status: "error", renderer: "batonvoice", reason: "Speech rendering failed. Please try again." });
    }
  }

  async function handleEvaluate() {
    if (!generation) {
      return;
    }
    setEvaluating(true);
    setError(null);
    try {
      const response = await evaluateSpeechPlan({
        session_id: generation.session_id,
      });
      setEvaluation(response.evaluation);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Evaluation failed.";
      setEvaluation({
        available: false,
        evaluator_version: null,
        judge_prompt_version: null,
        source_run_id: null,
        scores: {},
        critical_flags: [],
        reason: message,
        failure_summary: message,
        failure_type: "api_error",
      });
    } finally {
      setEvaluating(false);
    }
  }

  return (
    <div className="space-y-5">
      <Panel>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Live Studio
            </p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
              Build a teaching scenario
            </h2>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
                1 Build context
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
                2 Generate Speech Plan
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
                3 Evaluate plan
              </span>
            </div>
          </div>
          <StatusBadge tone="muted">Hy3 generation · user-triggered Judge</StatusBadge>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            <TextArea
              label="Content anchor"
              value={form.content_anchor}
              required
              onChange={(value) => update("content_anchor", value)}
            />
            <TextArea
              label="Teaching scenario"
              value={form.teaching_scenario}
              required
              onChange={(value) => update("teaching_scenario", value)}
            />
            <TextInput
              label="Learner utterance"
              value={form.learner_utterance ?? ""}
              onChange={(value) => update("learner_utterance", value)}
            />
          </div>
          <div className="space-y-4">
            <TextInput
              label="Learner level"
              value={form.learner_level}
              required
              onChange={(value) => update("learner_level", value)}
            />
            <TextArea
              label="Knowledge state"
              value={form.knowledge_state}
              required
              onChange={(value) => update("knowledge_state", value)}
            />
            <TextInput
              label="Affective state"
              value={form.affective_state ?? ""}
              onChange={(value) => update("affective_state", value)}
            />
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-800">
                Pedagogical intent <span className="text-red-600">*</span>
              </span>
              <select
                value={form.pedagogical_intent}
                onChange={(event) =>
                  update(
                    "pedagogical_intent",
                    event.target.value as PedagogicalIntent,
                  )
                }
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              >
                {INTENTS.map((intent) => (
                  <option key={intent} value={intent}>
                    {intent}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-800">Speech Plan prompt</span>
              <select value={form.prompt_version ?? "v0.2"} onChange={(event) => update("prompt_version", event.target.value as GenerateRequest["prompt_version"])} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 shadow-sm">
                <option value="v0.2">v0.2 (compatible default)</option>
                <option value="v0.3">v0.3 (sparse local delivery)</option>
                <option value="v0.4">v0.4 (expressive sparse delivery)</option>
              </select>
            </label>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={loadShowcaseScenario}
            disabled={generating || evaluating}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Load showcase scenario
          </button>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating || evaluating}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {generating ? "Generating…" : "Generate with Hy3"}
          </button>
        </div>
      </Panel>

      {error ? (
        <EmptyState title="Generation unavailable" description={error} />
      ) : null}

      {generation ? (
        <>
          <Workbench
            mode="live"
            input={generation.input}
            speechPlan={generation.speech_plan}
            evaluation={evaluation}
            generationMeta={generation.generation}
            evaluating={evaluating}
            onEvaluate={handleEvaluate}
          />
          <Panel title="Speech Rendering">
            <p className="text-sm leading-6 text-slate-600">Render the generated teaching speech with BatonVoice.</p>
            {renderState === "success" && renderResult?.audio_url ? (
              <div className="mt-4 space-y-2"><span className="text-sm font-medium text-slate-900">BatonVoice</span><audio className="w-full" controls src={renderResult.audio_url} /><p className="text-xs text-slate-500">{formatRenderMetadata(renderResult)}</p></div>
            ) : null}
            {renderState === "unavailable" ? <p className="mt-3 text-sm text-amber-700">BatonVoice is currently unavailable.</p> : null}
            {renderState === "error" ? <p className="mt-3 text-sm text-red-700">Speech rendering failed. Your Speech Plan and evaluation are unchanged.</p> : null}
            <button type="button" onClick={handleRender} disabled={renderState === "rendering"} className="mt-4 rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60">{renderState === "rendering" ? "Rendering…" : renderState === "success" ? "Render again" : "Render with BatonVoice"}</button>
          </Panel>
          <SegmentedBatonCandidate key={generation.session_id} sessionId={generation.session_id} />
          <TechnicalDetails generation={generation} evaluation={evaluation} />
        </>
      ) : null}
    </div>
  );
}

function formatRenderMetadata(result: BatonVoiceRenderResponse) {
  const metadata = result.render_metadata;
  if (!metadata) return "";
  return [metadata.sample_rate ? `${metadata.sample_rate / 1000} kHz` : null, metadata.duration_seconds ? `${metadata.duration_seconds.toFixed(1)} s` : null].filter(Boolean).join(" · ");
}

function TextInput({
  label,
  value,
  required = false,
  onChange,
}: {
  label: string;
  value: string;
  required?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-800">
        {label} {required ? <span className="text-red-600">*</span> : null}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
      />
    </label>
  );
}

function TextArea({
  label,
  value,
  required = false,
  onChange,
}: {
  label: string;
  value: string;
  required?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-800">
        {label} {required ? <span className="text-red-600">*</span> : null}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={5}
        className="w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm leading-6 text-slate-950 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
      />
    </label>
  );
}

function TechnicalDetails({
  generation,
  evaluation,
}: {
  generation: LiveGenerationResponse;
  evaluation: EvaluationArtifact | null;
}) {
  const details = {
    mode: "live",
    prompt_version: generation.generation.prompt_version,
    requested_model: generation.generation.requested_model,
    reported_model: generation.generation.reported_model,
    duration_seconds: generation.generation.duration_seconds,
    speech_plan_schema_version: generation.speech_plan.schema_version,
    evaluator_version: evaluation?.evaluator_version ?? null,
    judge_prompt_version: evaluation?.judge_prompt_version ?? null,
  };
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">
        Technical details
      </summary>
      <pre className="mt-4 max-h-80 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-5 text-slate-100">
        {JSON.stringify(details, null, 2)}
      </pre>
    </details>
  );
}
