import { useEffect, useRef, useState } from "react";
import {
  renderSegmentedBatonCandidate,
  renderWithBatonVoice,
} from "../../api/teachintent";
import { SegmentedResponsePlayer } from "../workbench/SegmentedBatonCandidate";
import type {
  BatonVoiceRenderResponse,
  SegmentedBatonRenderResponse,
} from "../../types/teachintent";

export function SpeechAudio({
  sessionId,
  mode,
  onDetails,
}: {
  sessionId: string;
  mode: "segmented" | "single";
  onDetails: (value: unknown) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<
    BatonVoiceRenderResponse | SegmentedBatonRenderResponse | null
  >(null);
  const epoch = useRef(0);
  const singleAudio = useRef<HTMLAudioElement>(null);
  useEffect(
    () => () => {
      epoch.current++;
    },
    [],
  );
  useEffect(() => {
    const audio = singleAudio.current;
    return () => {
      audio?.pause();
    };
  }, [result]);
  async function generate() {
    if (busy) return;
    const request = ++epoch.current;
    setBusy(true);
    setResult(null);
    setMessage("");
    try {
      const response =
        mode === "segmented"
          ? await renderSegmentedBatonCandidate(sessionId)
          : await renderWithBatonVoice(sessionId);
      if (request !== epoch.current) return;
      if (response.session_id !== sessionId)
        throw new Error("语音返回的会话不匹配。");
      setResult(response);
      onDetails(response);
      if (response.status === "unavailable")
        setMessage("当前未配置语音生成服务。");
      else if (response.status !== "success")
        setMessage("语音生成未完成，教学计划和质量检查不受影响。");
    } catch (error) {
      if (request !== epoch.current) return;
      const detail = error instanceof Error ? error.message : "语音请求失败";
      onDetails({ error: detail });
      setMessage(
        /unavailable|not configured|not available|503|未配置/i.test(detail)
          ? "当前未配置语音生成服务。"
          : "语音生成失败，请检查服务配置后重试。",
      );
    } finally {
      if (request === epoch.current) setBusy(false);
    }
  }
  return (
    <section aria-label="语音试听" className="audio-section">
      <div className="section-heading">
        <div>
          <h2>
            语音试听{" "}
            <span className="subtle">
              {mode === "segmented" ? "可选 · 实验性" : "可选"}
            </span>
          </h2>
          <p className="subtle">
            将计划转成语音需要单独配置语音服务。不会自动生成或播放。
          </p>
        </div>
        <button className="button-secondary" disabled={busy} onClick={generate}>
          {busy
            ? "正在生成语音…"
            : result?.status === "success"
              ? "重新生成语音"
              : "生成语音"}
        </button>
      </div>
      {message ? (
        <p role="status" className="status-note">
          {message}
        </p>
      ) : null}
      {result?.renderer === "batonvoice_segmented" ? (
        <SegmentedResponsePlayer result={result} />
      ) : result?.status === "success" && result.audio_url ? (
        <audio
          ref={singleAudio}
          controls
          preload="metadata"
          aria-label="试听生成的语音"
          src={result.audio_url}
        />
      ) : null}
    </section>
  );
}
