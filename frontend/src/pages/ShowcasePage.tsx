import { ArrowRight, AudioLines, CheckCircle2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchWorkbench } from "../api/teachintent";
import { DIMENSIONS } from "../lib/dimensions";
import type { ExampleId, GlobalDelivery, SegmentOverride, WorkbenchResponse } from "../types/teachintent";

const CASES: Array<{ id: ExampleId; label: string; subject: string }> = [
  { id: "corrective-feedback", label: "Corrective Feedback", subject: "Physics · repair a misconception" },
  { id: "scaffolding", label: "Scaffolding", subject: "Genetics · guide the next step" },
  { id: "supportive-feedback", label: "Supportive Feedback", subject: "Graph reading · recognize progress" },
];

function deliveryLabels(delivery?: GlobalDelivery | SegmentOverride): string[] {
  if (!delivery) return [];
  const labels = [delivery.attitudinal_tone, delivery.emotion];
  for (const [key, value] of Object.entries(delivery.prosody ?? {})) {
    const name = { speaking_rate: "pace", pitch_level: "pitch", pitch_range: "pitch range", volume: "volume" }[key] ?? key;
    labels.push(`${value} ${name}`);
  }
  if ("prominence_targets" in delivery) {
    labels.push(...(delivery.prominence_targets ?? []).map((target) => `Emphasize “${target.text}”${target.level ? ` · ${target.level}` : ""}`));
  }
  if ("boundary_after" in delivery && delivery.boundary_after?.strength) labels.push(`${delivery.boundary_after.strength} boundary`);
  if ("contour_shape" in delivery && delivery.contour_shape) labels.push(delivery.contour_shape);
  return labels.filter((value): value is string => Boolean(value));
}

export function ShowcasePage({ onOpenLive }: { onOpenLive: () => void }) {
  const [selected, setSelected] = useState<ExampleId>("corrective-feedback");
  const [data, setData] = useState<WorkbenchResponse | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError(false);
    fetchWorkbench(selected).then((result) => {
      if (active) setData(result);
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [selected, attempt]);

  return (
    <div className="space-y-5">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"><Sparkles size={14} aria-hidden="true" /> Inspect the plan before the tutor speaks</p>
          <h2 className="text-3xl font-semibold tracking-tight">TeachIntent Showcase</h2>
          <p className="mt-2 text-sm text-slate-600">Pedagogical Intent–Driven Speech Planning for AI Tutors</p>
        </div>
        <div className="text-right text-xs leading-6 text-slate-500">
          <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700"><CheckCircle2 size={14} aria-hidden="true" /> Existing recorded examples · no live model calls</span>
          <p>Current planner supports v0.2 / v0.3 / v0.4</p>
        </div>
      </section>

      <section aria-label="TeachIntent execution chain" className="rounded-2xl bg-slate-950 px-5 py-4 text-white">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3 text-sm">
          <div><span className="font-medium">Teaching Context</span><p className="text-xs text-slate-400">+ Learner State + Pedagogical Intent</p></div>
          <ArrowRight size={16} className="text-slate-500" aria-hidden="true" />
          <span className="rounded-lg bg-indigo-500 px-3 py-2 font-semibold">Hy3</span>
          <ArrowRight size={16} className="text-slate-500" aria-hidden="true" />
          <div><span className="font-semibold">Pedagogical Speech Plan</span><p className="text-xs text-indigo-200">WHAT TO SAY + HOW TO SAY</p></div>
          <ArrowRight size={16} className="text-slate-500" aria-hidden="true" />
          <div className="space-y-1 border-l border-slate-700 pl-4"><p>Independent Evaluator <span className="text-xs text-slate-400">→ plan evidence</span></p><p>Renderer <span className="text-xs text-slate-400">→ speech</span></p></div>
        </div>
      </section>

      <div className="grid gap-2 sm:grid-cols-3" aria-label="Showcase cases">
        {CASES.map((item) => <button key={item.id} type="button" aria-pressed={selected === item.id} onClick={() => setSelected(item.id)} className={`rounded-xl border px-4 py-3 text-left transition-colors ${selected === item.id ? "border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600" : "border-slate-200 bg-white hover:border-indigo-300"}`}><span className="block text-sm font-semibold">{item.label}</span><span className="mt-1 block text-xs text-slate-500">{item.subject}</span></button>)}
      </div>

      {error ? <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-5"><p>Recorded showcase could not load. Check the TeachIntent backend connection.</p><button className="mt-2 font-semibold underline" onClick={() => setAttempt((value) => value + 1)}>Reload recorded case</button></div> : !data ? <p role="status" className="p-8 text-center text-slate-500">Loading recorded case…</p> : <CaseView key={selected} data={data} />}

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-5 py-4">
        <div><p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Speech Execution · Live Segmented BatonVoice</p><div className="mt-2 flex flex-wrap items-center gap-3 text-sm"><span className="text-slate-500">Single-pass: observed drift / weak boundaries</span><ArrowRight size={16} aria-hidden="true" /><span className="font-medium">Segmented: independent synthesis → sequential playback</span></div><p className="mt-1 text-xs text-slate-500">Experimental reference renderer. Live generation needs provider access; speech needs the separate Baton runtime.</p></div>
        <a href="/live" onClick={(event) => { if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onOpenLive(); } }} className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white">Open Live Studio <ArrowRight size={15} aria-hidden="true" /></a>
      </section>
    </div>
  );
}

function CaseView({ data }: { data: WorkbenchResponse }) {
  const { input, speech_plan: plan, evaluation, voice_realization: voice } = data;
  const global = deliveryLabels(plan.delivery_plan.global);
  const local = plan.delivery_plan.segment_overrides ?? [];
  const hasDelivery = global.length > 0 || local.some((item) => deliveryLabels(item).length > 0);
  return <>
    <div className="grid items-start gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
      <section aria-label="Teaching Context" className="space-y-4 px-1 py-2">
        <div><p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Pedagogical Intent</p><p className="mt-2 text-lg font-semibold text-indigo-700">{input.pedagogical_intent.primary.replaceAll("_", " ")}</p></div>
        <Context label="Teaching Scenario" value={input.pedagogical_context.scenario} />
        <Context label="Learner Utterance" value={input.pedagogical_context.learner_utterance ?? "Not supplied"} />
        <div><p className="text-xs font-semibold text-slate-500">Learner State</p><p className="mt-1 text-sm leading-6">{[input.learner.level, input.learner.knowledge_state, input.learner.affective_state].filter(Boolean).map((value) => value!.replaceAll("_", " ")).join(" · ")}</p></div>
        <Context label="Content / Knowledge Anchor" value={input.instructional_content.content_anchor} />
      </section>
      <div className="space-y-4">
      <section aria-label="Pedagogical Speech Plan" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-6 py-4"><h3 className="text-lg font-semibold">Pedagogical Speech Plan</h3><span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">Recorded Hy3 · Prompt {data.prompt_version}</span></div>
        <div className="grid md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="space-y-5 p-6"><h4 className="text-xs font-semibold tracking-[0.16em] text-slate-500">WHAT TO SAY</h4>{plan.verbal_plan.segments.map((segment, index) => <div key={segment.segment_id} className="flex gap-4"><span className="pt-1 font-mono text-xs text-indigo-500">{String(index + 1).padStart(2, "0")}</span><p className="text-lg leading-9 text-slate-900">{segment.text}</p></div>)}</div>
          <div className="space-y-4 border-t border-slate-100 bg-slate-50/70 p-6 md:border-l md:border-t-0"><h4 className="text-xs font-semibold tracking-[0.16em] text-slate-500">HOW TO SAY</h4>{!hasDelivery ? <><p className="font-medium leading-7 text-emerald-800">No additional delivery control required.</p><p className="text-xs leading-6 text-slate-500">Sparse planning can deliberately leave delivery unspecified.</p></> : <>{global.length > 0 ? <div><p className="mb-2 text-xs text-slate-500">Across the response</p><Labels values={global} /></div> : null}{plan.verbal_plan.segments.map((segment, index) => { const labels = deliveryLabels(local.find((item) => item.segment_id === segment.segment_id)); return labels.length ? <div key={segment.segment_id}><p className="mb-2 text-xs text-slate-500">Segment {String(index + 1).padStart(2, "0")}</p><Labels values={labels} /></div> : null; })}<p className="text-xs leading-6 text-slate-500">Only explicitly planned controls are shown.</p></>}</div>
        </div>
      </section>
    <section aria-label="Plan Evaluation" className="rounded-2xl border border-slate-200 bg-white px-5 py-4">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h3 className="font-semibold">Plan Evaluation</h3><p className="text-xs text-slate-500">Independent Evaluator {evaluation.evaluator_version ?? ""} · recorded evidence · evaluates the plan, not audio</p></div>
      {!evaluation.available ? <p className="text-sm text-amber-700">Recorded evaluator artifact unavailable.</p> : <><div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">{DIMENSIONS.map((dimension) => { const judgment = evaluation.scores[dimension.id]; return <div key={dimension.id} className="border-l-2 border-indigo-100 pl-3"><div className="flex items-baseline gap-2"><span className="text-xs font-semibold text-indigo-500">{dimension.key}</span><strong className="text-xl tabular-nums">{judgment ? `${judgment.score}/4` : "Unavailable"}</strong></div><p className="mt-1 text-xs font-medium leading-5">{dimension.label}</p>{judgment?.evidence[0] ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{judgment.evidence[0].text}</p> : null}</div>; })}</div>
      <details className="mt-4 border-t border-slate-100 pt-3"><summary className="cursor-pointer text-sm font-medium text-indigo-700">View evaluator details</summary><div className="mt-3 grid gap-4 lg:grid-cols-2">{DIMENSIONS.map((dimension) => { const judgment = evaluation.scores[dimension.id]; return judgment ? <div key={dimension.id} className="rounded-xl bg-slate-50 p-4"><h4 className="text-sm font-semibold">{dimension.key} · {dimension.label} · {judgment.score}/4</h4><p className="mt-2 text-sm leading-6">{judgment.brief_justification}</p>{judgment.evidence.map((item, index) => <blockquote key={index} className="mt-2 border-l-2 border-indigo-200 pl-3 text-sm leading-6 text-slate-600">{item.text}<cite className="block break-all text-xs not-italic text-slate-400">{item.source}</cite></blockquote>)}</div> : null; })}</div></details>
      {evaluation.critical_flags.length ? <div className="mt-3 text-sm text-amber-800"><p className="font-semibold">Critical flags</p>{evaluation.critical_flags.map((flag) => <p key={flag.flag}>{flag.flag}: {flag.brief_justification}</p>)}</div> : <p className="mt-3 text-xs text-emerald-700">No critical flags recorded.</p>}</>}
    </section>

      </div>
    </div>

    <section aria-label="Demo Audio" className="rounded-2xl border border-slate-200 bg-white px-5 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h3 className="flex items-center gap-2 font-semibold"><AudioLines size={18} className="text-indigo-500" aria-hidden="true" />Demo Audio</h3><p className="text-xs text-slate-500">Recorded synthetic Qwen3-TTS · click to play · not live BatonVoice</p></div>
      {voice.available && voice.neutral && voice.planned ? <><div className="grid gap-4 md:grid-cols-2">{([ ["Neutral", voice.neutral], ["Planned", voice.planned] ] as const).map(([label, condition]) => <label key={label} className="block text-xs font-medium text-slate-600">{label}<audio aria-label={`${label} demo audio`} className="mt-2 h-10 w-full" controls preload="metadata" src={condition.audio_url} /></label>)}</div>{!hasDelivery ? <p className="mt-2 text-xs text-slate-500">Identical A/B audio: this recorded plan adds no delivery instruction.</p> : null}</> : <p className="text-sm text-slate-500">Optional recorded audio unavailable.</p>}
    </section>
  </>;
}

function Labels({ values }: { values: string[] }) {
  return <div className="flex flex-wrap gap-2">{values.map((value, index) => <span key={index} className="rounded-lg border border-indigo-100 bg-white px-3 py-2 text-sm leading-6 text-indigo-800">{value}</span>)}</div>;
}

function Context({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs font-semibold text-slate-500">{label}</p><p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-700">{value}</p><details className="mt-1"><summary className="cursor-pointer text-xs text-indigo-600">Details</summary><p className="mt-2 text-sm leading-6 text-slate-700">{value}</p></details></div>;
}
