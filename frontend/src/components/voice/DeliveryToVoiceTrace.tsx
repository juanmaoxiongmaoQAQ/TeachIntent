import { ArrowDown, Circle, CheckCircle2 } from "lucide-react";

import type { DeliveryAdapterInfo } from "../../types/teachintent";
import { StatusBadge } from "../common/StatusBadge";

interface DeliveryToVoiceTraceProps {
  adapter: DeliveryAdapterInfo;
}

export function DeliveryToVoiceTrace({ adapter }: DeliveryToVoiceTraceProps) {
  const hasInstruction = adapter.instruct.trim().length > 0;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Trace
        </p>
        <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:items-center">
          <TraceStep label="Speech Plan" />
          <Arrow />
          <TraceStep label="Delivery control" />
          <Arrow />
          <TraceStep label="Qwen3-TTS instruction" />
          <Arrow />
          <TraceStep label={hasInstruction ? "A/B audio" : "Default audio"} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-950">
              Supported controls
            </p>
            <StatusBadge tone="accent">
              {String(adapter.supported_controls.length)}
            </StatusBadge>
          </div>
          <div className="mt-3 space-y-3">
            {adapter.supported_controls.length ? (
              adapter.supported_controls.map((control) => (
                <div key={control.path} className="rounded-xl bg-white p-3">
                  <div className="flex gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <div>
                      <p className="font-mono text-xs text-slate-600">
                        {control.path}
                      </p>
                      <p className="mt-1 text-sm text-slate-900">
                        {formatValue(control.value)}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-600">
                        {control.instruction_fragment}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm leading-6 text-slate-600">
                No Speech Plan delivery control is mapped to a TTS instruction
                for this case.
              </p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-950">TTS instruction</p>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            {adapter.instruct || "No extra TTS instruction."}
          </p>
        </div>
      </div>

      {adapter.unsupported_controls.length ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-950">
              {adapter.unsupported_controls.length} controls preserved but not
              realized by this renderer
            </p>
            <StatusBadge tone="muted">
              {String(adapter.unsupported_controls.length)}
            </StatusBadge>
          </div>
          <div className="mt-3 space-y-3">
            {adapter.unsupported_controls.map((control) => (
              <div key={control.path} className="rounded-xl bg-white p-3">
                <div className="flex gap-2">
                  <Circle className="mt-1 h-3.5 w-3.5 shrink-0 text-amber-600" />
                  <div>
                    <p className="font-mono text-xs text-slate-600">
                      {control.path}
                    </p>
                    <p className="mt-1 text-sm text-slate-900">
                      {formatValue(control.value)}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">
                      Preserved in Speech Plan; not realized by current adapter.
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      {control.reason}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TraceStep({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-center font-medium text-slate-800">
      {label}
    </div>
  );
}

function Arrow() {
  return (
    <>
      <ArrowDown className="mx-auto h-4 w-4 text-slate-400 sm:hidden" />
      <span className="hidden text-slate-400 sm:inline">→</span>
    </>
  );
}

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}
