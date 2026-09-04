import type { IntentCompareRequest, PedagogicalIntent } from "../../types/teachintent";
import { INTENTS } from "../../lib/compare";

interface IntentCompareFormProps {
  form: IntentCompareRequest;
  generating: boolean;
  onChange: (form: IntentCompareRequest) => void;
  onLoadShowcase: () => void;
  onSwap: () => void;
  onSubmit: () => void;
}

export function IntentCompareForm({
  form,
  generating,
  onChange,
  onLoadShowcase,
  onSwap,
  onSubmit,
}: IntentCompareFormProps) {
  const sameIntent = form.left_intent === form.right_intent;

  function update<K extends keyof IntentCompareRequest>(
    key: K,
    value: IntentCompareRequest[K],
  ) {
    onChange({ ...form, [key]: value });
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Build one teaching situation
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
          Intent Compare
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Hold the teaching context constant. Change only the pedagogical
          intent.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 text-xs font-medium">
        <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-indigo-700">
          Controlled application comparison
        </span>
        <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-600">
          Hy3 · Prompt v0.2
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="space-y-3">
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
        <div className="space-y-3">
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
        </div>
      </div>

      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 lg:grid-cols-[1fr_auto_1fr] lg:items-end">
        <IntentSelect
          label="Intent A"
          value={form.left_intent}
          onChange={(value) => update("left_intent", value)}
        />
        <button
          type="button"
          onClick={onSwap}
          disabled={generating}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Swap
        </button>
        <IntentSelect
          label="Intent B"
          value={form.right_intent}
          onChange={(value) => update("right_intent", value)}
        />
      </div>
      {sameIntent ? (
        <p className="text-sm font-medium text-red-700">
          Choose two different pedagogical intents.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onLoadShowcase}
          disabled={generating}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Load showcase scenario
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={generating || sameIntent}
          className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
        >
          {generating ? "Generating both plans…" : "Compare intents"}
        </button>
      </div>
    </div>
  );
}

function IntentSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: PedagogicalIntent;
  onChange: (value: PedagogicalIntent) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-800">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as PedagogicalIntent)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
      >
        {INTENTS.map((intent) => (
          <option key={intent} value={intent}>
            {intent}
          </option>
        ))}
      </select>
    </label>
  );
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
        rows={3}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm leading-6 text-slate-950 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
      />
    </label>
  );
}
