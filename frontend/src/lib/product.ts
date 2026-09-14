import type {
  DeliveryPlan,
  ExampleId,
  GenerateRequest,
  PedagogicalIntent,
  TeachIntentInput,
} from "../types/teachintent";

export const INTENT_OPTIONS: {
  value: PedagogicalIntent;
  label: string;
  description: string;
}[] = [
  {
    value: "elicitation",
    label: "了解学情",
    description: "用提问了解学生的想法",
  },
  {
    value: "scaffolding",
    label: "提供支架",
    description: "给出提示，引导下一步",
  },
  {
    value: "explanation",
    label: "讲解知识",
    description: "解释概念与关键联系",
  },
  {
    value: "corrective_feedback",
    label: "纠错反馈",
    description: "回应误解，帮助修正认识",
  },
  {
    value: "supportive_feedback",
    label: "支持性反馈",
    description: "肯定具体进步与有效方法",
  },
  {
    value: "extension",
    label: "拓展提升",
    description: "连接已有知识，延伸思考",
  },
];
export const intentLabel = (value: PedagogicalIntent) =>
  INTENT_OPTIONS.find((item) => item.value === value)?.label ?? "教学意图";
export const EXAMPLES: {
  id: ExampleId;
  title: string;
  intent: string;
  summary: string;
}[] = [
  {
    id: "corrective-feedback",
    title: "速度没变，加速度就是零吗？",
    intent: "纠错反馈",
    summary: "回应学生对转弯时速度与加速度的误解。",
  },
  {
    id: "scaffolding",
    title: "从基因型到配子组合",
    intent: "提供支架",
    summary: "用一个恰当的提示，帮助学生继续遗传学推理。",
  },
  {
    id: "supportive-feedback",
    title: "把读图方法迁移到新学科",
    intent: "支持性反馈",
    summary: "认可学生在不同学科之间迁移读图方法的进步。",
  },
];
export const DEFAULT_FORM: GenerateRequest = {
  content_anchor: "",
  learner_utterance: "",
  pedagogical_intent: "corrective_feedback",
  teaching_scenario:
    "教师根据当前教学内容与学生回答，提供一次有针对性的教学回应。",
  learner_level: "未提供具体学段",
  knowledge_state: "具体理解程度以学生当前回答为依据",
  affective_state: "",
  prompt_version: "v0.2",
};
export const FRACTION_FORM: GenerateRequest = {
  ...DEFAULT_FORM,
  content_anchor:
    "在同一个整体中，单位分数的分母表示平均分成的份数。分母越大，每一份越小，因此 1/4 小于 1/3。",
  teaching_scenario:
    "学生正在比较单位分数的大小，把分母的大小直接当成了分数的大小。",
  learner_utterance: "我觉得 1/4 比 1/3 大，因为 4 比 3 大。",
  learner_level: "小学",
  knowledge_state: "已认识分子和分母，但对单位分数的大小存在误解",
  affective_state: "愿意表达自己的想法",
};
export function formFromInput(
  input: TeachIntentInput,
  version: GenerateRequest["prompt_version"] = "v0.2",
): GenerateRequest {
  return {
    content_anchor: input.instructional_content.content_anchor,
    teaching_scenario: input.pedagogical_context.scenario,
    learner_utterance: input.pedagogical_context.learner_utterance ?? "",
    learner_level: input.learner.level,
    knowledge_state: input.learner.knowledge_state,
    affective_state: input.learner.affective_state ?? "",
    pedagogical_intent: input.pedagogical_intent.primary,
    prompt_version: version,
  };
}
const TERMS: Record<string, string> = {
  high_school: "高中",
  middle_school: "初中",
  elementary_school: "小学",
  misconception: "存在概念误解",
  slightly_frustrated: "有些挫败",
  successful_cross_domain_transfer: "能迁移已有方法",
  seeking_confirmation: "希望得到确认",
  partial_understanding: "已有部分理解",
  uncertain: "尚不确定",
  neutral: "自然",
  supportive: "支持性",
  calm: "平和",
  encouraging: "鼓励",
  firm: "坚定",
  warm: "温和",
  gentle: "柔和",
  soft: "柔和",
  emphasized: "强调",
};
export const fieldText = (value: string) => TERMS[value] ?? value;
export function humanText(value?: string): string {
  if (!value) return "未补充";
  return (
    TERMS[value] ?? (/[\u3400-\u9fff]/.test(value) ? value : "详见原始信息")
  );
}
// Presentation only: local controls override matching global fields; absent controls stay absent.
export function deliveryFor(plan: DeliveryPlan, segmentId: string): string[] {
  const local = plan.segment_overrides?.find(
    (item) => item.segment_id === segmentId,
  );
  const combined = {
    ...plan.global,
    ...local,
    prosody: { ...plan.global?.prosody, ...local?.prosody },
  };
  const labels: string[] = [];
  for (const value of [combined.attitudinal_tone, combined.emotion])
    if (value) labels.push(humanText(value));
  const mappings: Record<string, Record<string, string>> = {
    speaking_rate: { slow: "稍慢", normal: "自然语速", fast: "稍快" },
    pitch_level: { high: "适度提高语调", mid: "自然语调", low: "适度降低语调" },
    pitch_range: {
      wide: "语调变化更丰富",
      normal: "自然语调变化",
      narrow: "语调更平稳",
    },
    volume: { soft: "柔和", normal: "自然音量", loud: "增强表达力度" },
  };
  for (const [key, value] of Object.entries(combined.prosody))
    if (value) labels.push(mappings[key]?.[value] ?? "已指定表达方式");
  for (const item of local?.prominence_targets ?? [])
    labels.push(`强调「${item.text}」`);
  if (local?.boundary_after?.strength) labels.push("注意句间停顿");
  if (local?.contour_shape) labels.push("调整句末语调");
  return [...new Set(labels)];
}
