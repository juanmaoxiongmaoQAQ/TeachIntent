import type { IntentCompareRequest, PedagogicalIntent } from "../types/teachintent";

export const INTENTS: PedagogicalIntent[] = [
  "elicitation",
  "scaffolding",
  "explanation",
  "corrective_feedback",
  "supportive_feedback",
  "extension",
];

export const EMPTY_COMPARE_FORM: IntentCompareRequest = {
  content_anchor: "",
  teaching_scenario: "",
  learner_utterance: "",
  learner_level: "",
  knowledge_state: "",
  affective_state: "",
  left_intent: "corrective_feedback",
  right_intent: "scaffolding",
};

export const SHOWCASE_COMPARE_FORM: IntentCompareRequest = {
  content_anchor:
    "速度是描述物体运动快慢和方向的物理量；加速度描述速度随时间的变化，也就是速度大小或方向变化的快慢。速度大小很大并不意味着加速度大小一定很大。若速度的大小和方向都保持不变，则加速度为0；即使速度大小不变，只要方向发生变化，加速度也不为0。",
  teaching_scenario:
    "学生已经连续几次把“速度大小不变”和“没有加速度”直接等同起来，现在有些挫败。学生刚刚再次作出明确错误判断。",
  learner_utterance:
    "汽车转弯的时候速度大小没变，所以它的加速度就是0。",
  learner_level: "high_school",
  knowledge_state: "misconception",
  affective_state: "slightly_frustrated",
  left_intent: "corrective_feedback",
  right_intent: "scaffolding",
};
