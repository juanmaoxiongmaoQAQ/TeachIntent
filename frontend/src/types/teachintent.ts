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
  | "delivery_plan.global.prosody.pitch_level"
  | "delivery_plan.global.prosody.pitch_range"
  | "delivery_plan.global.prosody.volume"
  | `delivery_plan.segment_overrides[${number}].attitudinal_tone`
  | `delivery_plan.segment_overrides[${number}].emotion`
  | `delivery_plan.segment_overrides[${number}].prosody.speaking_rate`
  | `delivery_plan.segment_overrides[${number}].prosody.pitch_level`
  | `delivery_plan.segment_overrides[${number}].prosody.pitch_range`
  | `delivery_plan.segment_overrides[${number}].prosody.volume`
  | `delivery_plan.segment_overrides[${number}].contour_shape`
  | `delivery_plan.segment_overrides[${number}].prominence_targets[${number}]`
  | `delivery_plan.segment_overrides[${number}].prominence_targets[${number}].text`
  | `delivery_plan.segment_overrides[${number}].prominence_targets[${number}].level`
  | `delivery_plan.segment_overrides[${number}].boundary_after`
  | `delivery_plan.segment_overrides[${number}].boundary_after.strength`;

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
  global?: GlobalDelivery;
  segment_overrides?: SegmentOverride[];
}

export interface GlobalDelivery {
  attitudinal_tone?: string;
  emotion?: string;
  prosody?: GlobalProsody;
}

export interface GlobalProsody {
  speaking_rate?: string;
  pitch_level?: string;
  pitch_range?: string;
  volume?: string;
}

export interface SegmentOverride {
  segment_id: string;
  attitudinal_tone?: string;
  emotion?: string;
  prosody?: SegmentProsody;
  contour_shape?: string;
  prominence_targets?: ProminenceTarget[];
  boundary_after?: BoundaryAfter;
}

export interface SegmentProsody {
  speaking_rate?: string;
  pitch_level?: string;
  pitch_range?: string;
  volume?: string;
}

export interface ProminenceTarget {
  text: string;
  level?: string;
}

export interface BoundaryAfter {
  strength?: string;
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
  failure_type?: string | null;
  failure_summary?: string | null;
}

export interface SupportedControl {
  path: string;
  value: unknown;
  instruction_fragment: string;
  realization: string;
}

export interface UnsupportedControl {
  path: string;
  value: unknown;
  reason: string;
}

export interface DeliveryAdapterInfo {
  instruct: string;
  supported_controls: SupportedControl[];
  unsupported_controls: UnsupportedControl[];
}

export interface VoiceCondition {
  instruct: string;
  audio_file: string;
  audio_url: string;
  audio_sha256: string;
  duration_seconds: number;
}

export interface VoiceRealizationResponse {
  available: boolean;
  mode: "recorded";
  reason?: string | null;
  exact_verbal_text?: string | null;
  exact_verbal_text_sha256?: string | null;
  speaker?: string | null;
  model?: string | null;
  language?: string | null;
  seed?: number | null;
  delivery_adapter?: DeliveryAdapterInfo | null;
  ab_invariants: Record<string, unknown>;
  neutral?: VoiceCondition | null;
  planned?: VoiceCondition | null;
  limitations: string[];
}

export interface WorkbenchResponse {
  example: ExampleSummary;
  prompt_version: string;
  input: TeachIntentInput;
  speech_plan: SpeechPlan;
  evaluation: EvaluationArtifact;
  voice_realization: VoiceRealizationResponse;
}

export interface GenerateRequest {
  content_anchor: string;
  teaching_scenario: string;
  learner_utterance?: string | null;
  learner_level: string;
  knowledge_state: string;
  affective_state?: string | null;
  pedagogical_intent: PedagogicalIntent;
}

export interface IntentCompareRequest {
  content_anchor: string;
  teaching_scenario: string;
  learner_utterance?: string | null;
  learner_level: string;
  knowledge_state: string;
  affective_state?: string | null;
  left_intent: PedagogicalIntent;
  right_intent: PedagogicalIntent;
}

export interface GenerationMetadata {
  prompt_version: string;
  requested_model: string;
  reported_model: string | null;
  duration_seconds: number;
}

export interface LiveGenerationResponse {
  session_id: string;
  mode: "live";
  input: TeachIntentInput;
  speech_plan: SpeechPlan;
  generation: GenerationMetadata;
  evaluation: null;
}

export interface EvaluateRequest {
  session_id: string;
}

export interface LiveEvaluationResponse {
  session_id: string;
  evaluation: EvaluationArtifact;
}

export interface ComparisonInvariants {
  changed_input_field: "input.pedagogical_intent.primary";
  left_intent: PedagogicalIntent;
  right_intent: PedagogicalIntent;
  all_other_input_fields_equal: boolean;
  prompt_version: string;
  same_prompt_version: boolean;
  same_requested_model: boolean;
}

export interface CompareGenerationResult {
  input: TeachIntentInput;
  speech_plan: SpeechPlan;
  generation: GenerationMetadata;
}

export interface StructuralContrast {
  verbal_segments: {
    left: number;
    right: number;
  };
  delivery_decision: {
    left: "default" | "selective";
    right: "default" | "selective";
  };
  verbal_text_identical: boolean;
  delivery_plan_identical: boolean;
  left_control_paths: string[];
  right_control_paths: string[];
}

export interface IntentCompareResponse {
  mode: "intent_compare";
  comparison: ComparisonInvariants;
  base_context: Omit<TeachIntentInput, "pedagogical_intent">;
  left: CompareGenerationResult;
  right: CompareGenerationResult;
  structural_contrast: StructuralContrast;
}

export interface HealthResponse {
  status: "ok";
  application: "TeachIntent";
}
