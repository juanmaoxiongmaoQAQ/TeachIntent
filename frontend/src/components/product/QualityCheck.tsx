import type { EvaluationArtifact } from "../../types/teachintent";
import { DIMENSIONS } from "../../lib/dimensions";

const TITLES = [
  "教学意图一致性",
  "内容忠实性",
  "学生状态适配",
  "教学策略充分性",
  "表达控制必要性",
  "表达与教学目标一致性",
];
const SUBJECTS = [
  "教学意图的落实",
  "教学内容的忠实程度",
  "对学生状态的回应",
  "教学策略的充分程度",
  "表达控制的必要性",
  "表达与教学目标的配合",
];
function conclusion(score: number, index: number) {
  return `${SUBJECTS[index]}${score === 4 ? "较充分" : score === 3 ? "基本符合要求" : score === 2 ? "仍有不足" : "需要重点检查"}。`;
}
export function QualityCheck({
  evaluation,
  loading = false,
  onEvaluate,
}: {
  evaluation: EvaluationArtifact | null;
  loading?: boolean;
  onEvaluate?: () => void;
}) {
  const complete =
    evaluation?.available &&
    DIMENSIONS.every((item) => evaluation.scores[item.id]);
  return (
    <section aria-label="计划质量检查" className="quality-check">
      <div className="section-heading">
        <div>
          <h2>计划质量检查</h2>
          <p className="subtle">检查 Speech Plan 的教学质量，不评价音频。</p>
        </div>
        {onEvaluate ? (
          <button
            className="button-secondary"
            disabled={loading}
            onClick={onEvaluate}
          >
            {loading
              ? "正在检查计划质量…"
              : evaluation
                ? "重新检查"
                : "检查计划质量"}
          </button>
        ) : null}
      </div>
      {loading ? (
        <p role="status" className="status-note">
          正在检查六个教学维度，请稍候…
        </p>
      ) : !evaluation ? (
        <p className="subtle">
          计划已就绪。你可以先阅读教学步骤，再按需检查质量。
        </p>
      ) : !evaluation.available ? (
        <p role="status" className="status-note">
          暂时无法完成质量检查，请检查服务配置后重试。教学计划仍可查看。
        </p>
      ) : (
        <>
          <p className="quality-summary">
            {evaluation.critical_flags.length
              ? "检查发现需要关注的问题，请展开详细评价。"
              : complete
                ? "六个维度已检查，未报告关键风险。"
                : "已返回部分维度，请结合详细评价阅读。"}
            <span className="subtle">
              {" "}
              以下结论按评分等级概括，不代表学习效果保证。
            </span>
          </p>
          <dl className="quality-grid">
            {DIMENSIONS.map((dimension, index) => {
              const judgment = evaluation.scores[dimension.id];
              return (
                <div key={dimension.id}>
                  <dt>
                    {TITLES[index]}
                    <strong>
                      {judgment ? `${judgment.score}/4` : "未返回"}
                    </strong>
                  </dt>
                  <dd>
                    {judgment
                      ? conclusion(judgment.score, index)
                      : "该维度暂无结果。"}
                  </dd>
                </div>
              );
            })}
          </dl>
          <details className="disclosure">
            <summary>查看详细评价</summary>
            <p className="subtle">以下保留原始评价与证据，可能包含英文。</p>
            {DIMENSIONS.map((dimension, index) => {
              const judgment = evaluation.scores[dimension.id];
              return judgment ? (
                <article className="evaluation-detail" key={dimension.id}>
                  <h3>
                    {TITLES[index]} · {judgment.score}/4
                  </h3>
                  <p>{judgment.brief_justification}</p>
                  {judgment.evidence.map((item, i) => (
                    <blockquote key={i}>
                      {item.text}
                      <cite>{item.source}</cite>
                    </blockquote>
                  ))}
                </article>
              ) : null;
            })}
            {evaluation.critical_flags.length ? (
              <div>
                <h3>需关注的问题</h3>
                {evaluation.critical_flags.map((flag) => (
                  <article key={flag.flag}>
                    <p>{flag.brief_justification}</p>
                    {flag.evidence.map((item, i) => (
                      <blockquote key={i}>{item.text}</blockquote>
                    ))}
                  </article>
                ))}
              </div>
            ) : (
              <p>未报告关键风险。</p>
            )}
          </details>
        </>
      )}
    </section>
  );
}
