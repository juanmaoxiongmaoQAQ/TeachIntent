import { Pause, Play, RotateCcw } from "lucide-react";
import { RefObject } from "react";

import { cn } from "../../lib/utils";
import type { VoiceCondition } from "../../types/teachintent";

interface VoiceConditionCardProps {
  title: string;
  subtitle: string;
  condition: VoiceCondition;
  active: boolean;
  audioRef: RefObject<HTMLAudioElement | null>;
  currentTime: number;
  duration: number;
  onToggle: () => void;
  onReset: () => void;
  onTimeUpdate: () => void;
  onEnded: () => void;
}

export function VoiceConditionCard({
  title,
  subtitle,
  condition,
  active,
  audioRef,
  currentTime,
  duration,
  onToggle,
  onReset,
  onTimeUpdate,
  onEnded,
}: VoiceConditionCardProps) {
  return (
    <article
      className={cn(
        "rounded-2xl border bg-white p-4 shadow-sm",
        active ? "border-indigo-300 ring-2 ring-indigo-100" : "border-slate-200",
      )}
    >
      <audio
        ref={audioRef}
        src={condition.audio_url}
        preload="metadata"
        aria-label={`${title} audio`}
        onTimeUpdate={onTimeUpdate}
        onEnded={onEnded}
      />
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">{title}</p>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-slate-950 text-white shadow-sm hover:bg-slate-800"
          aria-label={active ? `Pause ${title}` : `Play ${title}`}
        >
          {active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
      </div>
      {condition.instruct ? (
        <p className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
          {condition.instruct}
        </p>
      ) : (
        <p className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-600">
          Default instruction
        </p>
      )}
      <div className="mt-4">
        <div
          className="h-2 overflow-hidden rounded-full bg-slate-100"
          aria-label={`${title} progress`}
        >
          <div
            className="h-full rounded-full bg-indigo-500"
            style={{
              width: `${duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0}%`,
            }}
          />
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
          <span>
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-slate-600 hover:bg-slate-100"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
        </div>
      </div>
    </article>
  );
}

function formatTime(value: number) {
  const safeValue = Number.isFinite(value) && value > 0 ? value : 0;
  const minutes = Math.floor(safeValue / 60);
  const seconds = Math.floor(safeValue % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
