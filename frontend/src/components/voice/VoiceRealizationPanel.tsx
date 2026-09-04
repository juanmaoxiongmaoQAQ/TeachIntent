import type { VoiceRealizationResponse } from "../../types/teachintent";
import { Panel } from "../common/Panel";
import { StatusBadge } from "../common/StatusBadge";
import { DeliveryToVoiceTrace } from "./DeliveryToVoiceTrace";
import { VoiceComparisonPlayer } from "./VoiceComparisonPlayer";

interface VoiceRealizationPanelProps {
  voice: VoiceRealizationResponse;
}

export function VoiceRealizationPanel({ voice }: VoiceRealizationPanelProps) {
  if (!voice.available || !voice.delivery_adapter || !voice.neutral || !voice.planned) {
    return (
      <Panel title="Voice Realization" eyebrow="Recorded audio">
        <p className="text-sm leading-6 text-slate-600">
          {voice.reason ?? "Recorded voice artifact unavailable."}
        </p>
      </Panel>
    );
  }

  const hasPlannedInstruction = voice.delivery_adapter.instruct.trim().length > 0;

  return (
    <Panel title="Voice Realization" eyebrow="Curated Qwen3-TTS CustomVoice">
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={hasPlannedInstruction ? "accent" : "muted"}>
            {hasPlannedInstruction
              ? "Controlled comparison"
              : "Default voice realization"}
          </StatusBadge>
          <StatusBadge tone="muted">Recorded public artifact</StatusBadge>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-950">
            From delivery plan to audible realization
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            The renderer uses the exact same spoken words and voice settings;
            only the Qwen3-TTS instruction differs when a supported delivery
            control is mapped.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Exact spoken text
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-800">
            {voice.exact_verbal_text}
          </p>
        </div>
        <DeliveryToVoiceTrace adapter={voice.delivery_adapter} />
        <VoiceComparisonPlayer
          neutral={voice.neutral}
          planned={voice.planned}
          plannedEnabled={hasPlannedInstruction}
        />
        <MoreDetails
          voice={voice}
          showUnsupportedSummary={
            voice.delivery_adapter.unsupported_controls.length === 0
          }
        />
      </div>
    </Panel>
  );
}

function MoreDetails({
  voice,
  showUnsupportedSummary,
}: {
  voice: VoiceRealizationResponse;
  showUnsupportedSummary: boolean;
}) {
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">
        More details
      </summary>
      <div className="mt-4 space-y-4">
        <InvariantCard />
        {showUnsupportedSummary ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm text-slate-600">
              No unsupported renderer controls are present in this case.
            </p>
          </div>
        ) : null}
        {voice.limitations.length ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-950">Limitations</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">
              {voice.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-sm font-semibold text-slate-950">
            Renderer provenance
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {voice.speaker} · {voice.model} · {voice.language} · seed{" "}
            {voice.seed}
          </p>
        </div>
      </div>
    </details>
  );
}

function InvariantCard() {
  const invariants = [
    "Same exact words",
    "Same speaker",
    "Same model",
    "Same language",
    "Same seed / generation path",
    "Only condition difference: TTS instruct",
  ];
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-3">
      <p className="text-sm font-semibold text-slate-950">A/B invariant</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {invariants.map((invariant) => (
          <div
            key={invariant}
            className="rounded-xl border border-indigo-100 bg-white px-3 py-2 text-xs font-medium text-slate-700"
          >
            {invariant}
          </div>
        ))}
      </div>
    </div>
  );
}
