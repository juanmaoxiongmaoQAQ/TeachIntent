import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type {
  ExampleId,
  WorkbenchResponse,
  IntentCompareResponse,
} from "../types/teachintent";

export const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
export function generated() {
  const data = recorded("corrective-feedback");
  return {
    mode: "live",
    session_id: "mock-session",
    input: data.input,
    speech_plan: data.speech_plan,
    generation: {
      prompt_version: "v0.2",
      requested_model: "tencent/hy3",
      reported_model: "tencent/hy3",
      duration_seconds: 0.2,
    },
  };
}

export function comparisonResponse(
  leftText = "纠正这个判断。",
  rightText = "先拆成一个小问题。",
): IntentCompareResponse {
  return {
    mode: "intent_compare",
    comparison: {
      changed_input_field: "input.pedagogical_intent.primary",
      left_intent: "corrective_feedback",
      right_intent: "scaffolding",
      all_other_input_fields_equal: true,
      prompt_version: "v0.2",
      same_prompt_version: true,
      same_requested_model: true,
    },
    base_context: {
      schema_version: "1.0.0-rc.2",
      output_language: "zh-CN",
      instructional_content: {
        content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
      },
      pedagogical_context: {
        scenario: "学生有些挫败。",
        learner_utterance: "汽车转弯的时候速度大小没变。",
      },
      learner: {
        level: "high_school",
        knowledge_state: "misconception",
        affective_state: "slightly_frustrated",
      },
    },
    left: {
      input: {
        schema_version: "1.0.0-rc.2",
        output_language: "zh-CN",
        instructional_content: {
          content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
        },
        pedagogical_context: {
          scenario: "学生有些挫败。",
          learner_utterance: "汽车转弯的时候速度大小没变。",
        },
        learner: {
          level: "high_school",
          knowledge_state: "misconception",
          affective_state: "slightly_frustrated",
        },
        pedagogical_intent: { primary: "corrective_feedback" },
      },
      speech_plan: {
        schema_version: "1.0.0-rc.3",
        verbal_plan: {
          segments: [{ segment_id: "seg_01", text: leftText }],
        },
        delivery_plan: {
          global: {
            attitudinal_tone: "安抚但纠正",
          },
        },
      },
      generation: {
        prompt_version: "v0.2",
        requested_model: "tencent/hy3",
        reported_model: "tencent/hy3",
        duration_seconds: 0.2,
      },
    },
    right: {
      input: {
        schema_version: "1.0.0-rc.2",
        output_language: "zh-CN",
        instructional_content: {
          content_anchor: "即使速度大小不变，只要方向发生变化，加速度也不为0。",
        },
        pedagogical_context: {
          scenario: "学生有些挫败。",
          learner_utterance: "汽车转弯的时候速度大小没变。",
        },
        learner: {
          level: "high_school",
          knowledge_state: "misconception",
          affective_state: "slightly_frustrated",
        },
        pedagogical_intent: { primary: "scaffolding" },
      },
      speech_plan: {
        schema_version: "1.0.0-rc.3",
        verbal_plan: {
          segments: [{ segment_id: "seg_01", text: rightText }],
        },
        delivery_plan: {
          segment_overrides: [
            {
              segment_id: "seg_01",
              prominence_targets: [{ text: "小问题", level: "moderate" }],
            },
          ],
        },
      },
      generation: {
        prompt_version: "v0.2",
        requested_model: "tencent/hy3",
        reported_model: "tencent/hy3",
        duration_seconds: 0.3,
      },
    },
    structural_contrast: {
      verbal_segments: { left: 1, right: 1 },
      delivery_decision: { left: "selective", right: "selective" },
      verbal_text_identical: false,
      delivery_plan_identical: false,
      left_control_paths: ["delivery_plan.global.attitudinal_tone"],
      right_control_paths: [
        "delivery_plan.segment_overrides[0].prominence_targets[0].text",
        "delivery_plan.segment_overrides[0].prominence_targets[0].level",
      ],
    },
  };
}

export function recorded(id: ExampleId): WorkbenchResponse {
  const read = (path: string) =>
    JSON.parse(readFileSync(resolve(process.cwd(), "..", path), "utf8"));
  const example = read(`examples/${id.replaceAll("-", "_")}.json`);
  const evaluation = read(`public_demo/evaluator_artifacts/${id}.v0_2.json`);
  const voice = read(`public_demo/voice/${id}/v0_2/manifest.json`);
  return {
    example: {
      id,
      title: example.title,
      description: example.description,
      recommended: false,
    },
    prompt_version: "v0.2",
    input: example.input,
    speech_plan: example.recorded_outputs["v0.2"],
    evaluation: { ...evaluation, available: true },
    voice_realization: {
      ...voice,
      available: true,
      mode: "recorded",
      neutral: {
        ...voice.conditions.neutral,
        audio_url: `/api/audio/${id}/neutral`,
      },
      planned: {
        ...voice.conditions.planned,
        audio_url: `/api/audio/${id}/planned`,
      },
    },
  };
}
