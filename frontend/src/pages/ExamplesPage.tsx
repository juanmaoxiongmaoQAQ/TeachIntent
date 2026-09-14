import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { fetchWorkbench } from "../api/teachintent";
import { EXAMPLES, humanText } from "../lib/product";
import { PlanView } from "../components/product/PlanView";
import { QualityCheck } from "../components/product/QualityCheck";
import { TechnicalDetails } from "../components/product/TechnicalDetails";
import type { ExampleId, WorkbenchResponse } from "../types/teachintent";

export function ExamplesPage() {
  const query = new URLSearchParams(window.location.search).get("case");
  const [selected, setSelected] = useState<ExampleId | null>(
    EXAMPLES.some((item) => item.id === query) ? (query as ExampleId) : null,
  );
  const [data, setData] = useState<WorkbenchResponse | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError(false);
    if (selected)
      fetchWorkbench(selected)
        .then((result) => {
          if (active) setData(result);
        })
        .catch(() => {
          if (active) setError(true);
        });
    return () => {
      active = false;
    };
  }, [selected, attempt]);
  const item = EXAMPLES.find((item) => item.id === selected);
  return (
    <div className="page-stack">
      <header className="page-heading">
        {!selected ? <p className="eyebrow">从真实案例理解教学规划</p> : null}
        <h1>示例库</h1>
        {!selected ? <p>查看教学情况如何转成教学步骤，以及表达方式为什么需要调整。</p> : null}
      </header>
      {!selected ? (
        <div className="example-list">
          {EXAMPLES.map((item, index) => (
            <button
              key={item.id}
              className="example-row"
              onClick={() => setSelected(item.id)}
            >
              <span className="example-index">0{index + 1}</span>
              <span>
                <span className="eyebrow">{item.intent}</span>
                <strong>{item.title}</strong>
                <span className="subtle">{item.summary}</span>
              </span>
              <ArrowRight aria-hidden="true" size={22} />
            </button>
          ))}
        </div>
      ) : (
        <>
          <div className="case-toolbar">
            <button className="text-link" onClick={() => setSelected(null)}>
              <ArrowLeft size={16} aria-hidden="true" />
              返回示例库
            </button>
            <div role="group" aria-label="切换案例">
              {EXAMPLES.map((item) => (
                <button
                  key={item.id}
                  aria-pressed={selected === item.id}
                  onClick={() => setSelected(item.id)}
                >
                  {item.intent}
                </button>
              ))}
            </div>
          </div>
          {error ? (
            <div role="alert" className="notice">
              <p>示例暂时无法加载，请检查服务连接后重试。</p>
              <button
                className="button-secondary"
                onClick={() => setAttempt((v) => v + 1)}
              >
                重新加载
              </button>
            </div>
          ) : !data ? (
            <p role="status" className="loading-space">
              正在读取示例…
            </p>
          ) : (
            <div key={selected} className="page-stack example-detail">
              <div className="example-context">
                <div>
                  <p className="eyebrow">{item?.intent}</p>
                  <h2>{item?.title}</h2>
                  <p>{item?.summary}</p>
                  <details className="disclosure">
                    <summary>查看教学场景与学生状态</summary>
                    <h3>教学场景</h3>
                    <p>{data.input.pedagogical_context.scenario}</p>
                    <h3>学生状态</h3>
                    <p>
                      {[
                        data.input.learner.level,
                        data.input.learner.knowledge_state,
                        data.input.learner.affective_state,
                      ]
                        .filter(Boolean)
                        .map((v) => humanText(v))
                        .join(" · ")}
                    </p>
                    <h3>教学内容</h3>
                    <p>{data.input.instructional_content.content_anchor}</p>
                  </details>
                </div>
                <blockquote>
                  <span className="eyebrow">学生当前回答</span>
                  <p>
                    {data.input.pedagogical_context.learner_utterance ??
                      "此场景未提供学生发言。"}
                  </p>
                </blockquote>
              </div>
              <PlanView plan={data.speech_plan} />
              <QualityCheck evaluation={data.evaluation} />
              <section aria-label="语音试听" className="audio-section">
                <h2>语音试听</h2>
                <p className="subtle">
                  已有合成示例音频，点击后播放。来自
                  Qwen3-TTS，不是本次实时生成。
                </p>
                {data.voice_realization.available &&
                data.voice_realization.neutral &&
                data.voice_realization.planned ? (
                  <>
                    <div className="audio-pair">
                      {[
                        ["基础语音", data.voice_realization.neutral],
                        ["规划后语音", data.voice_realization.planned],
                      ].map(
                        ([label, condition]) =>
                          typeof condition === "object" && (
                            <label key={label as string}>
                              {label as string}
                              <audio
                                controls
                                preload="metadata"
                                aria-label={label as string}
                                src={condition.audio_url}
                              />
                            </label>
                          ),
                      )}
                    </div>
                    {data.voice_realization.neutral.audio_sha256 ===
                    data.voice_realization.planned.audio_sha256 ? (
                      <p className="subtle">
                        此计划无需额外表达控制，两段音频相同。
                      </p>
                    ) : null}
                  </>
                ) : (
                  <p className="status-note">
                    此示例的可选音频暂不可用，教学计划和质量检查仍可查看。
                  </p>
                )}
              </section>
              <TechnicalDetails
                data={{
                  "Prompt 与 Schema": {
                    prompt_version: data.prompt_version,
                    input_schema: data.input.schema_version,
                    speech_plan_schema: data.speech_plan.schema_version,
                    evaluator_version: data.evaluation.evaluator_version,
                  },
                  "原始输入 JSON": data.input,
                  "原始 Speech Plan JSON": data.speech_plan,
                  "原始评价 JSON": data.evaluation,
                  语音来源与映射: data.voice_realization,
                }}
              />
              <div className="example-actions">
                <a className="button-secondary" href="/studio">
                  用自己的教学情况开始体验
                  <ArrowRight size={16} aria-hidden="true" />
                </a>
                <a className="text-link" href="/compare">比较不同教学意图 →</a>
              </div>
            </div>
          )}
        </>
      )}
      {!selected ? <aside className="advanced-entry">
        <div>
          <h2>想进一步比较教学策略？</h2>
          <p className="subtle">
            高级功能：保持教学情况不变，比较不同教学意图的计划。
          </p>
        </div>
        <a className="text-link" href="/compare">
          比较不同教学意图 <ArrowRight size={16} aria-hidden="true" />
        </a>
      </aside> : null}
    </div>
  );
}
