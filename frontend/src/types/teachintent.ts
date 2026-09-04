export type ExampleId =
  | "corrective-feedback"
  | "scaffolding"
  | "supportive-feedback";

export type PedagogicalIntent =
  | "elicitation"
  | "scaffolding"
  | "explanation"
  | "corrective_feedback"
  | "supportive_feedback"
  | "extension";

export type ContextFieldKey =
  | "instructional_content.content_anchor"
  | "pedagogical_context.scenario"
  | "pedagogical_context.learner_utterance"
  | "learner.level"
  | "learner.knowledge_state"
  | "learner.affective_state"
  | "pedagogical_intent.primary";

export type DeliveryFieldKey =
  | "delivery_plan.global.attitudinal_tone"
  | "delivery_plan.global.emotion"
  | "delivery_plan.global.prosody.speaking_rate"
  | "delivery_plan.global.prosody.volume";

export type DimensionId =
  | "pedagogical_intent_fidelity"
  | "content_faithfulness_boundary"
  | "learner_state_compatibility"
  | "intent_specific_instructional_adequacy"
  | "delivery_necessity_sparsity"
  | "delivery_pedagogy_alignment";

export interface ExampleSummary {
  id: ExampleId;
  title: string;
  description: string;
  recommended: boolean;
}

export interface TeachIntentInput {
  schema_version: string;
  output_language: string;
  instructional_content: {
    subject?: string;
    topic?: string;
    content_anchor: string;
  };
  pedagogical_context: {
    scenario: string;
    learner_utterance?: string;
  };
  learner: {
    level: string;
    knowledge_state: string;
    affective_state?: string;
  };
  pedagogical_intent: {
    primary: PedagogicalIntent;
  };
}

export interface VerbalSegment {
  segment_id: string;
  text: string;
}

export interface SpeechPlan {
  schema_version: string;
  verbal_plan: {
    segments: VerbalSegment[];
  };
  delivery_plan: DeliveryPlan;
}

export interface DeliveryPlan {
  global?: {
    attitudinal_tone?: string;
    emotion?: string;
    prosody?: {
      speaking_rate?: string;
      volume?: string;
    };
  };
}

export interface EvidenceItem {
  source: string;
  text: string;
}

export interface DimensionJudgment {
  score: number;
  evidence: EvidenceItem[];
  brief_justification: string;
}

export interface CriticalFlag {
  flag: string;
  evidence: EvidenceItem[];
  brief_justification: string;
}

export interface EvaluationArtifact {
  available: boolean;
  evaluator_version: string | null;
  judge_prompt_version: string | null;
  source_run_id: string | null;
  scores: Partial<Record<DimensionId, DimensionJudgment>>;
  critical_flags: CriticalFlag[];
  reason?: string | null;
}

export interface WorkbenchResponse {
  example: ExampleSummary;
  prompt_version: string;
  input: TeachIntentInput;
  speech_plan: SpeechPlan;
  evaluation: EvaluationArtifact;
}

export interface HealthResponse {
  status: "ok";
  application: "TeachIntent";
}
