import type { EvaluationArtifact, EvidenceItem } from "../../types/teachintent";
import { DIMENSIONS } from "../../lib/dimensions";
import { highlightExactText } from "../../lib/highlight";
import { fieldText } from "../../lib/product";

const TITLES = [
  "教学意图一致性",
  "内容忠实性",
  "学生状态适配",
  "教学策略充分性",
  "表达控制必要性",
  "表达与教学目标一致性",
];
const CONCLUSIONS = [
  ["需重点检查教学意图是否落实。", "教学意图落实仍有不足。", "教学意图基本落实。", "教学意图落实较充分。"],
  ["需重点核对教学内容。", "内容忠实性仍有不足。", "内容基本忠实于教学依据。", "内容忠实于教学依据。"],
  ["需重点检查对学生状态的回应。", "对学生状态的回应仍有不足。", "基本回应了学生状态。", "较充分地回应了学生状态。"],
  ["需重点检查教学策略。", "教学策略仍不够充分。", "教学策略基本充分。", "教学策略较充分。"],
  ["需重点检查表达控制是否必要。", "表达控制的必要性仍需核对。", "表达控制基本符合必要性要求。", "表达控制符合必要性要求。"],
  ["需重点检查表达与教学目标的配合。", "表达与教学目标的配合仍有不足。", "表达基本配合教学目标。", "表达与教学目标配合较好。"],
];
function conclusion(score: number, index: number) {
  return CONCLUSIONS[index][score >= 4 ? 3 : score === 3 ? 2 : score === 2 ? 1 : 0];
}

// Display labels only: do not change evidence resolution or grounding rules.
function sourceLabel(source: string): string {
  const segment = source.match(/^(?:plan|speech_plan)\.verbal_plan\.segments\[(\d+)\]\.text$/);
  if (segment && Number.isSafeInteger(Number(segment[1]) + 1))
    return `教学步骤 · 第 ${Number(segment[1]) + 1} 段`;
  const labels: [RegExp, string][] = [
    [/^(?:plan|speech_plan)\.verbal_plan(?:\.|$)/, "教学步骤"],
    [/^(?:plan|speech_plan)\.delivery_plan(?:\.|$)/, "表达计划"],
    [/^input\.instructional_content(?:\.|$)/, "教学内容"],
    [/^input\.learner(?:\.|$)/, "学生状态"],
    [/^input\.pedagogical_context\.learner_utterance$/, "学生回答"],
    [/^input\.pedagogical_context(?:\.|$)/, "教学情境"],
    [/^input\.pedagogical_intent(?:\.|$)/, "教学意图"],
  ];
  return labels.find(([pattern]) => pattern.test(source))?.[1] ?? "评价证据（来源未识别）";
}
const FIELD_PATH = /\b(?:input|plan|speech_plan)(?:\.[a-zA-Z_]\w*|\[\d+\])+/g;
function readableReason(text: string, evidence: EvidenceItem[] = []) {
  let result = text.replace(FIELD_PATH, (source) => sourceLabel(source));
  for (const item of evidence) {
    if (item.source.includes(".")) result = result.split(item.source).join(sourceLabel(item.source));
  }
  return result;
}
function excerptText(item: EvidenceItem): string | null {
  if (readableReason(item.text, [item]) !== item.text) return null;
  if (!/^[\[{]/.test(item.text.trim())) return item.text;
  // A quoted tone is an existing value inside the supplied JSON evidence,
  // not a new explanation or a change to its original evidence source.
  if (/^(?:plan|speech_plan)\.delivery_plan$/.test(item.source)) {
    try {
      const value: { global?: { attitudinal_tone?: unknown; emotion?: unknown } } = JSON.parse(item.text);
      const tone = value?.global?.attitudinal_tone ?? value?.global?.emotion;
      if (typeof tone === "string" && readableReason(tone) === tone) return tone;
    } catch { /* Preserve malformed or unsupported evidence in the raw disclosure. */ }
  }
  return null;
}
function EvidenceExcerpt({ item, compact = false }: { item: EvidenceItem; compact?: boolean }) {
  const text = excerptText(item);
  const characters = Array.from(text ?? "");
  const excerpt = compact ? characters.slice(0, 72).join("") : text ?? "";
  const highlight = Array.from(excerpt).slice(0, 24).join("");
  const emptyDelivery = /^(?:plan|speech_plan)\.delivery_plan$/.test(item.source) && /^\{\s*\}$/.test(item.text.trim());
  const stateLabel = compact && item.source.startsWith("input.learner.") ? fieldText(item.text) : item.text;
  return (
    <blockquote className="evidence-excerpt">
      {text === null ? (
        <p className="subtle">
          {emptyDelivery ? "未设置额外表达控制（空表达计划）。" : "结构化证据见详细评价中的原始证据定位。"}
        </p>
      ) : stateLabel !== item.text ? (
        <p><mark>{stateLabel}</mark>（状态标签）</p>
      ) : item.text.trim() ? (
        <p>“{highlightExactText(excerpt, [highlight])}{compact && characters.length > 72 ? "…" : ""}”</p>
      ) : <p className="subtle">未提供证据片段。</p>}
      <cite>来源：{sourceLabel(item.source)}</cite>
    </blockquote>
  );
}
function RawEvidence({ reason, evidence }: { reason: string; evidence: EvidenceItem[] }) {
  return (
    <details className="evidence-locations">
      <summary>查看原始评价</summary>
      <pre>{JSON.stringify({ brief_justification: reason, evidence }, null, 2)}</pre>
    </details>
  );
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
          <p className="subtle">检查教学计划的质量，不评价音频。</p>
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
              const primary = judgment?.evidence.find((item) => item.text.trim() && excerptText(item) !== null) ?? judgment?.evidence[0];
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
                  {judgment ? (
                    <dd className="quality-evidence">
                      {primary ? <EvidenceExcerpt item={primary} compact /> : <p className="subtle">未提供证据片段。</p>}
                    </dd>
                  ) : null}
                </div>
              );
            })}
          </dl>
          <details className="disclosure">
            <summary>查看详细评价</summary>
            <p className="subtle">以下展示主要证据；完整理由、证据与字段定位可逐项展开查看。</p>
            {DIMENSIONS.map((dimension, index) => {
              const judgment = evaluation.scores[dimension.id];
              const primary = judgment?.evidence.find((item) => item.text.trim() && excerptText(item) !== null) ?? judgment?.evidence[0];
              return judgment ? (
                <article className="evaluation-detail" key={dimension.id}>
                  <h3>
                    {TITLES[index]} · {judgment.score}/4
                  </h3>
                  {primary ? <EvidenceExcerpt item={primary} compact /> : <p className="subtle">未提供证据片段。</p>}
                  <RawEvidence reason={judgment.brief_justification} evidence={judgment.evidence} />
                </article>
              ) : null;
            })}
            {evaluation.critical_flags.length ? (
              <div>
                <h3>需关注的问题</h3>
                {evaluation.critical_flags.map((flag) => (
                  <article key={flag.flag}>
                    {flag.evidence.map((item, i) => (
                      <EvidenceExcerpt key={i} item={item} />
                    ))}
                    <RawEvidence reason={flag.brief_justification} evidence={flag.evidence} />
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
