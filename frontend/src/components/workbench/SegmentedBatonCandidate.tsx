import { useEffect, useMemo, useRef, useState } from "react";

import { renderSegmentedBatonCandidate } from "../../api/teachintent";
import type { SegmentedBatonRenderResponse } from "../../types/teachintent";
import { Panel } from "../common/Panel";

const buttonClass = "rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 disabled:opacity-50";

export function SegmentedBatonCandidate({ sessionId }: { sessionId: string }) {
  const [result, setResult] = useState<SegmentedBatonRenderResponse | null>(null);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestEpoch = useRef(0);

  useEffect(() => () => { requestEpoch.current += 1; }, []);

  async function renderCandidate() {
    if (rendering) return;
    const epoch = ++requestEpoch.current;
    setRendering(true);
    setResult(null); // Unmounting the previous player stops its queue.
    setError(null);
    try {
      const response = await renderSegmentedBatonCandidate(sessionId);
      if (epoch === requestEpoch.current) {
        if (response.session_id !== sessionId) throw new Error("Unexpected session response.");
        setResult(response);
      }
    } catch {
      if (epoch === requestEpoch.current) setError("Segmented rendering is unavailable. No replacement audio was generated.");
    } finally {
      if (epoch === requestEpoch.current) setRendering(false);
    }
  }

  return (
    <Panel title="Segmented Baton candidate · Experimental">
      <p className="text-sm text-slate-600">Listen to the teaching response in segment order and assess how naturally the boundaries flow.</p>
      <button type="button" onClick={renderCandidate} disabled={rendering} className={`${buttonClass} mt-4`}>
        {rendering ? "Rendering segmented candidate…" : "Render segmented candidate"}
      </button>
      {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
      {result ? <SegmentedResponsePlayer key={result.run_id ?? "failed"} result={result} /> : null}
    </Panel>
  );
}

export function SegmentedResponsePlayer({ result }: { result: SegmentedBatonRenderResponse }) {
  const segments = useMemo(() => [...result.segments].sort((a, b) => a.order - b.order), [result.segments]);
  const audios = useRef<(HTMLAudioElement | null)[]>([]);
  const active = useRef(-1);
  const epoch = useRef(0);
  const [playing, setPlaying] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const playable = result.status === "success" && segments.length > 0
    && segments.every((segment) => segment.status === "success" && !!segment.audio_url);

  useEffect(() => {
    const elements = [...audios.current];
    return () => {
      epoch.current += 1;
      active.current = -1;
      elements.forEach((audio) => { if (audio) { audio.pause(); audio.currentTime = 0; } });
    };
  }, [segments]);

  function stop() {
    epoch.current += 1;
    active.current = -1;
    audios.current.forEach((audio) => { if (audio) { audio.pause(); audio.currentTime = 0; } });
    setPlaying(null);
  }

  function play(index: number) {
    const audio = audios.current[index];
    if (!audio) return;
    active.current = index;
    setPlaying(index);
    const started = epoch.current;
    audio.currentTime = 0;
    void audio.play().catch(() => {
      if (started !== epoch.current) return;
      stop();
      setError("Playback could not start. Check browser audio permissions and try Play again.");
    });
  }

  function restart() {
    if (!playable) return;
    stop();
    setError(null);
    play(0);
  }

  function ended(index: number) {
    if (active.current !== index) return;
    if (index + 1 < segments.length) play(index + 1);
    else stop();
  }

  function audioError(index: number) {
    stop();
    setError(`Audio unavailable for ${segments[index].segment_id}. Playback stopped without skipping a segment.`);
  }

  return (
    <div className="mt-4 space-y-3">
      <p role="status" className="text-sm text-slate-700">
        {result.status === "success" ? "Segmented render complete." : `Segmented render: ${result.status}. Full playback is unavailable.`}
      </p>
      {!playable && result.status === "success" ? <p role="alert">Segment audio is incomplete. Full playback is unavailable.</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={restart} disabled={!playable || playing !== null} className={buttonClass}>Play full segmented response</button>
        <button type="button" onClick={stop} disabled={playing === null} className={buttonClass}>Stop</button>
        <button type="button" onClick={restart} disabled={!playable} className={buttonClass}>Restart from first segment</button>
      </div>
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      <ol className="space-y-1 text-sm text-slate-600">
        {segments.map((segment, index) => (
          <li key={segment.segment_id}>
            {segment.segment_id} · {segment.status}
            {segment.duration_seconds != null ? ` · ${segment.duration_seconds.toFixed(2)} s` : ""}
            {playing === index ? " · Playing" : ""}
            {segment.status === "success" && segment.audio_url ? (
              <audio ref={(node) => { audios.current[index] = node; }}
                aria-label={`Segment audio ${segment.segment_id}`} preload="auto" src={segment.audio_url}
                onEnded={() => ended(index)} onError={() => audioError(index)} />
            ) : null}
          </li>
        ))}
      </ol>
      <details className="text-sm text-slate-600">
        <summary>Segmented render diagnostics</summary>
        <pre className="mt-2 max-h-64 overflow-auto text-xs">{JSON.stringify(result, null, 2)}</pre>
      </details>
    </div>
  );
}
