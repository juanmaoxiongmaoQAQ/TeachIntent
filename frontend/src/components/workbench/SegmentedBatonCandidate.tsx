import { useEffect, useMemo, useRef, useState } from "react";

import { renderSegmentedBatonCandidate } from "../../api/teachintent";
import type { SegmentedBatonRenderResponse } from "../../types/teachintent";
import { Panel } from "../common/Panel";

const buttonClass =
  "rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 disabled:opacity-50";

export function SegmentedBatonCandidate({ sessionId }: { sessionId: string }) {
  const [result, setResult] = useState<SegmentedBatonRenderResponse | null>(
    null,
  );
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestEpoch = useRef(0);

  useEffect(
    () => () => {
      requestEpoch.current += 1;
    },
    [],
  );

  async function renderCandidate() {
    if (rendering) return;
    const epoch = ++requestEpoch.current;
    setRendering(true);
    setResult(null); // Unmounting the previous player stops its queue.
    setError(null);
    try {
      const response = await renderSegmentedBatonCandidate(sessionId);
      if (epoch === requestEpoch.current) {
        if (response.session_id !== sessionId)
          throw new Error("语音返回的会话不匹配。");
        setResult(response);
      }
    } catch {
      if (epoch === requestEpoch.current)
        setError("当前未配置语音生成服务，或服务暂不可用。");
    } finally {
      if (epoch === requestEpoch.current) setRendering(false);
    }
  }

  return (
    <Panel title="语音试听（实验性）">
      <p className="text-sm text-slate-600">按教学步骤顺序试听语音。</p>
      <button
        type="button"
        onClick={renderCandidate}
        disabled={rendering}
        className={`${buttonClass} mt-4`}
      >
        {rendering ? "正在生成语音…" : "生成语音"}
      </button>
      {error ? (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      {result ? (
        <SegmentedResponsePlayer
          key={result.run_id ?? "failed"}
          result={result}
        />
      ) : null}
    </Panel>
  );
}

export function SegmentedResponsePlayer({
  result,
}: {
  result: SegmentedBatonRenderResponse;
}) {
  const segments = useMemo(
    () => [...result.segments].sort((a, b) => a.order - b.order),
    [result.segments],
  );
  const audios = useRef<(HTMLAudioElement | null)[]>([]);
  const active = useRef(-1);
  const epoch = useRef(0);
  const [playing, setPlaying] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const playable =
    result.status === "success" &&
    segments.length > 0 &&
    segments.every(
      (segment) => segment.status === "success" && !!segment.audio_url,
    );

  useEffect(() => {
    const elements = [...audios.current];
    return () => {
      epoch.current += 1;
      active.current = -1;
      elements.forEach((audio) => {
        if (audio) {
          audio.pause();
          audio.currentTime = 0;
        }
      });
    };
  }, [segments]);

  function stop() {
    epoch.current += 1;
    active.current = -1;
    audios.current.forEach((audio) => {
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
      }
    });
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
      setError("无法开始播放，请检查浏览器声音权限后重试。");
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
    setError(`第 ${index + 1} 步的音频不可用，已停止播放。`);
  }

  return (
    <div className="mt-4 space-y-3">
      <p role="status" className="text-sm text-slate-700">
        {result.status === "success"
          ? "语音已生成，点击试听。"
          : "部分语音未能生成，暂时无法完整试听。"}
      </p>
      {!playable && result.status === "success" ? (
        <p role="alert">音频不完整，暂时无法完整试听。</p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={restart}
          disabled={!playable || playing !== null}
          className={buttonClass}
        >
          试听完整语音
        </button>
        <button
          type="button"
          onClick={stop}
          disabled={playing === null}
          className={buttonClass}
        >
          停止
        </button>
        <button
          type="button"
          onClick={restart}
          disabled={!playable}
          className={buttonClass}
        >
          从头播放
        </button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <ol className="space-y-1 text-sm text-slate-600">
        {segments.map((segment, index) => (
          <li key={segment.segment_id}>
            第 {index + 1} 步 ·{" "}
            {segment.status === "success" ? "已就绪" : "未完成"}
            {segment.duration_seconds != null
              ? ` · ${segment.duration_seconds.toFixed(2)} 秒`
              : ""}
            {playing === index ? " · 播放中" : ""}
            {segment.status === "success" && segment.audio_url ? (
              <audio
                ref={(node) => {
                  audios.current[index] = node;
                }}
                aria-label={`第 ${index + 1} 步语音`}
                preload="auto"
                src={segment.audio_url}
                onEnded={() => ended(index)}
                onError={() => audioError(index)}
              />
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
