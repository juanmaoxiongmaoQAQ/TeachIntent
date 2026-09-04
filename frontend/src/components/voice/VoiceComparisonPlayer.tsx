import { useRef, useState } from "react";

import type { VoiceCondition } from "../../types/teachintent";
import { VoiceConditionCard } from "./VoiceConditionCard";

type ConditionName = "neutral" | "planned";

interface VoiceComparisonPlayerProps {
  neutral: VoiceCondition;
  planned: VoiceCondition;
  plannedEnabled: boolean;
}

export function VoiceComparisonPlayer({
  neutral,
  planned,
  plannedEnabled,
}: VoiceComparisonPlayerProps) {
  const neutralRef = useRef<HTMLAudioElement | null>(null);
  const plannedRef = useRef<HTMLAudioElement | null>(null);
  const [active, setActive] = useState<ConditionName | null>(null);
  const [times, setTimes] = useState<Record<ConditionName, number>>({
    neutral: 0,
    planned: 0,
  });

  async function toggle(condition: ConditionName) {
    const currentRef = condition === "neutral" ? neutralRef : plannedRef;
    const otherRef = condition === "neutral" ? plannedRef : neutralRef;
    if (active === condition) {
      currentRef.current?.pause();
      setActive(null);
      return;
    }
    otherRef.current?.pause();
    try {
      await currentRef.current?.play();
      setActive(condition);
    } catch {
      setActive(null);
    }
  }

  function reset(condition: ConditionName) {
    const ref = condition === "neutral" ? neutralRef : plannedRef;
    if (ref.current) {
      ref.current.currentTime = 0;
      ref.current.pause();
    }
    setTimes((previous) => ({ ...previous, [condition]: 0 }));
    if (active === condition) {
      setActive(null);
    }
  }

  function updateTime(condition: ConditionName) {
    const ref = condition === "neutral" ? neutralRef : plannedRef;
    setTimes((previous) => ({
      ...previous,
      [condition]: ref.current?.currentTime ?? 0,
    }));
  }

  function ended(condition: ConditionName) {
    if (active === condition) {
      setActive(null);
    }
  }

  if (!plannedEnabled) {
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <VoiceConditionCard
          title="Default voice realization"
          subtitle="No additional delivery control selected."
          condition={neutral}
          active={active === "neutral"}
          audioRef={neutralRef}
          currentTime={times.neutral}
          duration={neutral.duration_seconds}
          onToggle={() => toggle("neutral")}
          onReset={() => reset("neutral")}
          onTimeUpdate={() => updateTime("neutral")}
          onEnded={() => ended("neutral")}
        />
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
          No additional delivery control selected. The renderer therefore uses
          its default instruction.
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <VoiceConditionCard
        title="Neutral"
        subtitle="Default instruction"
        condition={neutral}
        active={active === "neutral"}
        audioRef={neutralRef}
        currentTime={times.neutral}
        duration={neutral.duration_seconds}
        onToggle={() => toggle("neutral")}
        onReset={() => reset("neutral")}
        onTimeUpdate={() => updateTime("neutral")}
        onEnded={() => ended("neutral")}
      />
      <VoiceConditionCard
        title="TeachIntent"
        subtitle="Planned TTS instruction"
        condition={planned}
        active={active === "planned"}
        audioRef={plannedRef}
        currentTime={times.planned}
        duration={planned.duration_seconds}
        onToggle={() => toggle("planned")}
        onReset={() => reset("planned")}
        onTimeUpdate={() => updateTime("planned")}
        onEnded={() => ended("planned")}
      />
    </div>
  );
}
