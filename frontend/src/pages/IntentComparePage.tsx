import { useEffect, useRef, useState } from "react";
import { compareIntents } from "../api/teachintent";
import { TeachingForm } from "../components/product/TeachingForm";
import { PlanView } from "../components/product/PlanView";
import { TechnicalDetails } from "../components/product/TechnicalDetails";
import { DEFAULT_FORM, INTENT_OPTIONS, intentLabel } from "../lib/product";
import type {
  GenerateRequest,
  IntentCompareResponse,
  PedagogicalIntent,
} from "../types/teachintent";

export function IntentComparePage() {
  const [form, setForm] = useState<GenerateRequest>({ ...DEFAULT_FORM });
  const [left, setLeft] = useState<PedagogicalIntent>("corrective_feedback");
  const [right, setRight] = useState<PedagogicalIntent>("scaffolding");
  const [result, setResult] = useState<IntentCompareResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingExample, setLoadingExample] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState("");
  const epoch = useRef(0);
  useEffect(
    () => () => {
      epoch.current++;
    },
    [],
  );
  async function generate() {
    if (busy || loadingExample || left === right) return;
    if (
      ![
        form.content_anchor,
        form.teaching_scenario,
        form.learner_level,
        form.knowledge_state,
      ].every((v) => v.trim())
    ) {
      setError("请填写教学内容，并确认补充信息完整。");
      return;
    }
    setBusy(true);
    setError("");
    setDetail("");
    setResult(null);
    const request = ++epoch.current;
    try {
      const response = await compareIntents({
        content_anchor: form.content_anchor,
        teaching_scenario: form.teaching_scenario,
        learner_utterance: form.learner_utterance?.trim() || null,
        learner_level: form.learner_level,
        knowledge_state: form.knowledge_state,
        affective_state: form.affective_state?.trim() || null,
        left_intent: left,
        right_intent: right,
      });
      if (request === epoch.current) setResult(response);
    } catch (e) {
      if (request === epoch.current) {
        setError("对比生成失败，请检查服务配置后重试。");
        setDetail(e instanceof Error ? e.message : "对比请求失败");
      }
    } finally {
      if (request === epoch.current) setBusy(false);
    }
  }
  const controls = (
    <>
      <TeachingForm
        form={form}
        onChange={setForm}
        showIntent={false}
        disabled={busy}
        onLoadingChange={setLoadingExample}
      />
      <fieldset disabled={busy} className="compare-selectors">
        {[
          ["教学意图 A", left, setLeft],
          ["教学意图 B", right, setRight],
        ].map(([label, value, update]) => (
          <label key={label as string}>
            {label as string}
            <select
              value={value as string}
              onChange={(e) =>
                (update as typeof setLeft)(e.target.value as PedagogicalIntent)
              }
            >
              {INTENT_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        ))}
        <button
          className="button-secondary"
          onClick={() => {
            setLeft(right);
            setRight(left);
          }}
        >
          交换意图
        </button>
      </fieldset>
      {left === right ? (
        <p role="alert" className="status-note">
          请选择两种不同的教学意图。
        </p>
      ) : null}
      <button
        className="button-primary"
        onClick={generate}
        disabled={busy || loadingExample || left === right}
      >
        {busy ? "正在生成两份教学计划…" : "生成对比计划"}
      </button>
    </>
  );
  return (
    <div className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">高级功能</p>
        <h1>教学意图对比</h1>
        <p>
          保持教学内容与学生状态不变，只改变教学意图，观察教学策略如何变化。
        </p>
      </header>
      {result ? (
        <details className="disclosure">
          <summary>调整对比条件</summary>
          {controls}
        </details>
      ) : (
        <section className="studio-form-section">{controls}</section>
      )}
      {error ? (
        <p role="alert" className="notice">
          {error}
        </p>
      ) : null}
      {busy ? <p role="status">正在分别规划两种教学回应…</p> : null}
      {result ? (
        <>
          <p className="status-note">
            {result.comparison.all_other_input_fields_equal
              ? "两份计划使用相同教学情况，仅教学意图不同。"
              : "输入条件存在差异，请展开技术详情核对。"}
          </p>
          <div className="compare-results">
            {[
              ["A", result.left, result.comparison.left_intent],
              ["B", result.right, result.comparison.right_intent],
            ].map(
              ([label, response, intent]) =>
                typeof response === "object" && (
                  <section key={label as string}>
                    <h2 className="compare-title">
                      {label as string} ·{" "}
                      {intentLabel(intent as PedagogicalIntent)}
                    </h2>
                    <PlanView plan={response.speech_plan} />
                  </section>
                ),
            )}
          </div>
          <p className="subtle">
            教学步骤：A 为 {result.structural_contrast.verbal_segments.left}{" "}
            步，B 为 {result.structural_contrast.verbal_segments.right}{" "}
            步。对比描述结构差异，不代表哪种意图更好。
          </p>
          <p className="subtle">
            如需独立质量检查，请在<a href="/studio">在线体验</a>
            中生成并检查计划。
          </p>
        </>
      ) : null}
      <TechnicalDetails
        data={{
          对比信息与版本: result?.comparison,
          "A 原始输入与计划": result?.left,
          "B 原始输入与计划": result?.right,
          结构差异: result?.structural_contrast,
          请求错误详情: detail || null,
        }}
      />
    </div>
  );
}
