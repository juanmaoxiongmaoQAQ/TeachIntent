import { useEffect, useRef, useState } from "react";
import { evaluateSpeechPlan, generateSpeechPlan } from "../api/teachintent";
import { TeachingForm } from "../components/product/TeachingForm";
import { PlanView } from "../components/product/PlanView";
import { QualityCheck } from "../components/product/QualityCheck";
import { SpeechAudio } from "../components/product/SpeechAudio";
import { TechnicalDetails } from "../components/product/TechnicalDetails";
import { DEFAULT_FORM, FRACTION_FORM } from "../lib/product";
import type {
  EvaluationArtifact,
  GenerateRequest,
  LiveGenerationResponse,
} from "../types/teachintent";

export function LiveStudioPage() {
  const [form, setForm] = useState<GenerateRequest>(() =>
    new URLSearchParams(window.location.search).get("example") === "fractions"
      ? { ...FRACTION_FORM }
      : { ...DEFAULT_FORM },
  );
  const [generation, setGeneration] = useState<LiveGenerationResponse | null>(
    null,
  );
  const [evaluation, setEvaluation] = useState<EvaluationArtifact | null>(null);
  const [busy, setBusy] = useState<"generate" | "evaluate" | null>(null);
  const [error, setError] = useState("");
  const [technicalError, setTechnicalError] = useState("");
  const [audioDetails, setAudioDetails] = useState<unknown>(null);
  const [audioMode, setAudioMode] = useState<"segmented" | "single">(
    "segmented",
  );
  const [formLoading, setFormLoading] = useState(false);
  const epoch = useRef(0);
  const resultHeading = useRef<HTMLDivElement>(null);
  useEffect(
    () => () => {
      epoch.current++;
    },
    [],
  );
  function change(value: GenerateRequest) {
    setForm(value);
    setError("");
  }
  async function generate() {
    if (busy || formLoading) return;
    if (
      ![
        form.content_anchor,
        form.teaching_scenario,
        form.learner_level,
        form.knowledge_state,
      ].every((v) => v.trim())
    ) {
      setError(
        "请填写教学内容；补充信息中的教学情境、学生水平和当前理解也不能为空。",
      );
      return;
    }
    const request = ++epoch.current;
    setBusy("generate");
    setError("");
    setTechnicalError("");
    setGeneration(null);
    setEvaluation(null);
    setAudioDetails(null);
    try {
      const response = await generateSpeechPlan({
        ...form,
        learner_utterance: form.learner_utterance?.trim() || null,
        affective_state: form.affective_state?.trim() || null,
      });
      if (request === epoch.current) {
        setGeneration(response);
        requestAnimationFrame(() => {
          resultHeading.current?.focus();
          resultHeading.current?.scrollIntoView?.({
            behavior: "smooth",
            block: "start",
          });
        });
      }
    } catch (err) {
      if (request === epoch.current) {
        setError("生成失败，请检查服务配置后重试。");
        setTechnicalError(err instanceof Error ? err.message : "生成请求失败");
      }
    } finally {
      if (request === epoch.current) setBusy(null);
    }
  }
  async function evaluate() {
    if (!generation || busy) return;
    const request = epoch.current;
    setBusy("evaluate");
    try {
      const response = await evaluateSpeechPlan({
        session_id: generation.session_id,
      });
      if (request === epoch.current) setEvaluation(response.evaluation);
    } catch (err) {
      if (request === epoch.current) {
        setTechnicalError(err instanceof Error ? err.message : "质量检查失败");
        setEvaluation({
          available: false,
          scores: {},
          critical_flags: [],
          evaluator_version: null,
          judge_prompt_version: null,
          source_run_id: null,
        });
      }
    } finally {
      if (request === epoch.current) setBusy(null);
    }
  }
  const input = (
    <>
      <TeachingForm
        form={form}
        onChange={change}
        disabled={!!busy}
        onLoadingChange={setFormLoading}
      />
      <div className="form-actions">
        <button
          className="button-primary"
          onClick={generate}
          disabled={!!busy || formLoading}
        >
          {busy === "generate" ? "正在生成教学计划…" : "生成教学计划"}
        </button>
        <span className="subtle">由 Hy3 进行教学规划</span>
      </div>
    </>
  );
  return (
    <div className="studio-page page-stack">
      <header className="page-heading">
        <h1>在线体验</h1>
        <p>填写教学情况，生成可检查的教学步骤，再按需试听语音。</p>
      </header>
      <ol className="task-progress" aria-label="体验流程">
        <li className="active">1 填写教学情况</li>
        <li className={generation ? "active" : ""}>2 查看教学计划</li>
        <li className={evaluation?.available ? "active" : ""}>
          3 检查计划质量
        </li>
      </ol>
      {generation ? (
        <details className="disclosure edit-context">
          <summary>调整教学情况并重新生成</summary>
          <p className="subtle">
            下方结果来自上一次生成；修改表单后需重新生成。
          </p>
          {input}
        </details>
      ) : (
        <section className="studio-form-section">{input}</section>
      )}
      {error ? (
        <div role="alert" className="notice">
          <p>{error}</p>
          <a href="/examples">也可以先查看已有示例</a>
        </div>
      ) : null}
      {busy === "generate" ? (
        <p role="status" className="loading-space">
          正在规划教学步骤和表达方式，请稍候…
        </p>
      ) : generation ? (
        <>
          <div
            ref={resultHeading}
            tabIndex={-1}
            className="success-note"
            role="status"
          >
            教学计划已生成
          </div>
          <PlanView plan={generation.speech_plan} />
          <QualityCheck
            evaluation={evaluation}
            loading={busy === "evaluate"}
            onEvaluate={evaluate}
          />
          <SpeechAudio
            key={`${generation.session_id}-${audioMode}`}
            sessionId={generation.session_id}
            mode={audioMode}
            onDetails={setAudioDetails}
          />
        </>
      ) : !error ? (
        <p className="empty-hint">
          不知道从哪里开始？选择“使用示例”，确认内容后点击生成。
        </p>
      ) : null}
      <TechnicalDetails
        data={{
          "原始输入 JSON": generation?.input ?? form,
          "原始 Speech Plan JSON": generation?.speech_plan,
          生成信息: generation
            ? { session_id: generation.session_id, ...generation.generation }
            : null,
          原始评价与版本: evaluation,
          语音执行与映射: audioDetails,
          请求错误详情: technicalError || null,
        }}
      >
        <div className="technical-controls">
          <label>
            Prompt 版本
            <select
              value={form.prompt_version}
              disabled={!!busy}
              onChange={(event) =>
                change({
                  ...form,
                  prompt_version: event.target
                    .value as GenerateRequest["prompt_version"],
                })
              }
            >
              <option value="v0.2">v0.2（兼容默认）</option>
              <option value="v0.3">v0.3（稀疏局部表达）</option>
              <option value="v0.4">v0.4（表达性稀疏规划）</option>
            </select>
          </label>
          <label>
            语音执行方式
            <select
              value={audioMode}
              onChange={(event) => {
                setAudioMode(event.target.value as "segmented" | "single");
                setAudioDetails(null);
              }}
            >
              <option value="segmented">BatonVoice 分段执行（实验性）</option>
              <option value="single">BatonVoice 整段执行</option>
            </select>
          </label>
        </div>
        <p className="subtle">
          语音服务由服务器端配置；分段执行逐段合成并在浏览器顺序播放。切换方式不会自动调用服务。
        </p>
      </TechnicalDetails>
      <aside className="advanced-entry">
        <span className="subtle">
          高级功能 · 保持教学情况不变，观察教学意图带来的差别
        </span>
        <a href="/compare" className="text-link">
          比较不同教学意图 →
        </a>
      </aside>
    </div>
  );
}
