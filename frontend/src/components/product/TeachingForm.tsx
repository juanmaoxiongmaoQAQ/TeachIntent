import {
  DEFAULT_FORM,
  EXAMPLES,
  FRACTION_FORM,
  INTENT_OPTIONS,
  formFromInput,
  fieldText,
} from "../../lib/product";
import { fetchWorkbench } from "../../api/teachintent";
import { useEffect, useRef, useState } from "react";
import type { GenerateRequest } from "../../types/teachintent";

export function TeachingForm({
  form,
  onChange,
  disabled = false,
  showIntent = true,
  onLoadingChange,
}: {
  form: GenerateRequest;
  onChange: (value: GenerateRequest) => void;
  disabled?: boolean;
  showIntent?: boolean;
  onLoadingChange?: (value: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const epoch = useRef(0);
  useEffect(
    () => () => {
      epoch.current++;
    },
    [],
  );
  function update<K extends keyof GenerateRequest>(
    key: K,
    value: GenerateRequest[K],
  ) {
    onChange({ ...form, [key]: value });
  }
  async function example(id: string) {
    if (!id) return;
    const request = ++epoch.current;
    setMessage("");
    if (id === "fractions") {
      onChange({ ...FRACTION_FORM, prompt_version: form.prompt_version });
      setLoading(false);
      setMessage("已填入示例。确认内容后，再生成教学计划。");
      return;
    }
    setLoading(true);
    onLoadingChange?.(true);
    try {
      const response = await fetchWorkbench(id);
      if (request === epoch.current) {
        onChange(formFromInput(response.input, form.prompt_version));
        setMessage("已填入示例。确认内容后，再生成教学计划。");
      }
    } catch {
      if (request === epoch.current)
        setMessage("示例加载失败，请检查连接后重新选择。");
    } finally {
      if (request === epoch.current) {
        setLoading(false);
        onLoadingChange?.(false);
      }
    }
  }
  return (
    <fieldset disabled={disabled || loading} className="teaching-form">
      <div className="form-top">
        <h2>填写教学情况</h2>
        <label className="example-picker">
          使用示例
          <select
            aria-label="使用示例"
            value=""
            onChange={(event) => void example(event.target.value)}
          >
            <option value="">选择一个教学场景</option>
            <option value="fractions">分数大小纠错</option>
            {EXAMPLES.map((item, index) => (
              <option key={item.id} value={item.id}>
                {["圆周运动纠错", "遗传学支架", "支持性反馈"][index]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading || message ? (
        <p role="status" className="subtle">
          {loading ? "正在填入示例…" : message}
        </p>
      ) : null}
      <Field
        label="教学内容"
        helper="AI 教师需要围绕什么知识进行教学？"
        value={form.content_anchor}
        onChange={(v) => update("content_anchor", v)}
        required
        rows={2}
        placeholder="例如：同一个整体中，单位分数的分母越大，每一份越小。"
      />
      <Field
        label="学生当前回答"
        helper="学生刚刚说了什么？如果没有学生发言，可以留空。"
        value={form.learner_utterance ?? ""}
        onChange={(v) => update("learner_utterance", v)}
        rows={2}
        placeholder="例如：我觉得 1/4 比 1/3 大，因为 4 比 3 大。"
      />
      {showIntent ? (
        <fieldset className="intent-field">
          <legend>教学意图</legend>
          <p className="field-helper">这一次，你希望 AI 教师怎样帮助学生？</p>
          <div className="intent-options">
            {INTENT_OPTIONS.map((item) => (
              <label
                key={item.value}
                className={
                  form.pedagogical_intent === item.value ? "selected" : ""
                }
              >
                <input
                  type="radio"
                  name="pedagogical-intent"
                  value={item.value}
                  checked={form.pedagogical_intent === item.value}
                  onChange={() => update("pedagogical_intent", item.value)}
                />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}
      <details className="disclosure supplemental">
        <summary>补充学生与教学信息</summary>
        <p className="subtle">可保留通用默认值，也可补充更具体的情况。</p>
        <Field
          label="教学情境"
          value={form.teaching_scenario}
          onChange={(v) => update("teaching_scenario", v)}
          placeholder={DEFAULT_FORM.teaching_scenario}
          rows={2}
          required
        />
        <Field
          label="学生水平"
          value={fieldText(form.learner_level)}
          onChange={(v) => update("learner_level", v)}
          required
        />
        <Field
          label="已有知识 / 当前理解"
          value={fieldText(form.knowledge_state)}
          onChange={(v) => update("knowledge_state", v)}
          required
          rows={2}
        />
        <Field
          label="当前情绪"
          value={fieldText(form.affective_state ?? "")}
          onChange={(v) => update("affective_state", v)}
        />
      </details>
    </fieldset>
  );
}
function Field({
  label,
  helper,
  value,
  onChange,
  rows,
  required = false,
  placeholder,
}: {
  label: string;
  helper?: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  required?: boolean;
  placeholder?: string;
}) {
  const id = `field-${label}`;
  return (
    <div className="field">
      <label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {helper ? (
        <p id={`${id}-help`} className="field-helper">
          {helper}
        </p>
      ) : null}
      {rows ? (
        <textarea
          id={id}
          aria-describedby={helper ? `${id}-help` : undefined}
          aria-required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={rows}
          placeholder={placeholder}
        />
      ) : (
        <input
          id={id}
          aria-describedby={helper ? `${id}-help` : undefined}
          aria-required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  );
}
