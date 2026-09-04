import type {
  ContextFieldKey,
  DeliveryFieldKey,
  DimensionJudgment,
  EvidenceItem,
} from "../types/teachintent";

export type EvidenceArea = "context" | "speech" | "unknown";

export interface EvidenceTarget {
  area: EvidenceArea;
  source: string;
  text: string;
  contextField?: ContextFieldKey;
  verbalSegmentIndex?: number;
  deliveryField?: DeliveryFieldKey;
  label: string;
  resolved: boolean;
}

export function classifyEvidenceSource(source: string): EvidenceArea {
  if (source.startsWith("input.")) {
    return "context";
  }
  if (source.startsWith("plan.") || source.startsWith("speech_plan.")) {
    return "speech";
  }
  return "unknown";
}

export function resolveEvidenceTarget(evidence: EvidenceItem): EvidenceTarget {
  const { source, text } = evidence;
  const inputPrefix = "input.";
  if (source.startsWith(inputPrefix)) {
    const field = source.slice(inputPrefix.length) as ContextFieldKey;
    const labels: Partial<Record<ContextFieldKey, string>> = {
      "instructional_content.content_anchor": "Teaching Context · Content anchor",
      "pedagogical_context.scenario": "Teaching Context · Scenario",
      "pedagogical_context.learner_utterance":
        "Teaching Context · Learner utterance",
      "learner.level": "Teaching Context · Learner level",
      "learner.knowledge_state": "Teaching Context · Knowledge state",
      "learner.affective_state": "Teaching Context · Affective state",
      "pedagogical_intent.primary": "Teaching Context · Pedagogical intent",
    };
    if (labels[field]) {
      return {
        area: "context",
        source,
        text,
        contextField: field,
        label: labels[field],
        resolved: true,
      };
    }
  }

  const verbalMatch = source.match(
    /^(plan|speech_plan)\.verbal_plan\.segments\[(\d+)\]\.text$/,
  );
  if (verbalMatch) {
    return {
      area: "speech",
      source,
      text,
      verbalSegmentIndex: Number(verbalMatch[2]),
      label: `Speech Plan · Verbal segment ${Number(verbalMatch[2]) + 1}`,
      resolved: true,
    };
  }

  const deliveryLabels: Record<string, { key: DeliveryFieldKey; label: string }> = {
    "plan.delivery_plan.global.attitudinal_tone": {
      key: "delivery_plan.global.attitudinal_tone",
      label: "Speech Plan · Attitudinal tone",
    },
    "speech_plan.delivery_plan.global.attitudinal_tone": {
      key: "delivery_plan.global.attitudinal_tone",
      label: "Speech Plan · Attitudinal tone",
    },
    "plan.delivery_plan.global.emotion": {
      key: "delivery_plan.global.emotion",
      label: "Speech Plan · Emotion",
    },
    "speech_plan.delivery_plan.global.emotion": {
      key: "delivery_plan.global.emotion",
      label: "Speech Plan · Emotion",
    },
    "plan.delivery_plan.global.prosody.speaking_rate": {
      key: "delivery_plan.global.prosody.speaking_rate",
      label: "Speech Plan · Speaking rate",
    },
    "speech_plan.delivery_plan.global.prosody.speaking_rate": {
      key: "delivery_plan.global.prosody.speaking_rate",
      label: "Speech Plan · Speaking rate",
    },
    "plan.delivery_plan.global.prosody.volume": {
      key: "delivery_plan.global.prosody.volume",
      label: "Speech Plan · Volume",
    },
    "speech_plan.delivery_plan.global.prosody.volume": {
      key: "delivery_plan.global.prosody.volume",
      label: "Speech Plan · Volume",
    },
  };
  const delivery = deliveryLabels[source];
  if (delivery) {
    return {
      area: "speech",
      source,
      text,
      deliveryField: delivery.key,
      label: delivery.label,
      resolved: true,
    };
  }

  return {
    area: classifyEvidenceSource(source),
    source,
    text,
    label: "Unresolved grounded excerpt",
    resolved: false,
  };
}

export function resolveJudgmentEvidence(
  judgment: DimensionJudgment | undefined,
): EvidenceTarget[] {
  return judgment?.evidence.map(resolveEvidenceTarget) ?? [];
}

export function evidenceTextsForContextField(
  targets: EvidenceTarget[],
  field: ContextFieldKey,
): string[] {
  return targets
    .filter((target) => target.contextField === field)
    .map((target) => target.text);
}

export function evidenceTextsForVerbalSegment(
  targets: EvidenceTarget[],
  index: number,
): string[] {
  return targets
    .filter((target) => target.verbalSegmentIndex === index)
    .map((target) => target.text);
}

export function evidenceTextsForDeliveryField(
  targets: EvidenceTarget[],
  field: DeliveryFieldKey,
): string[] {
  return targets
    .filter((target) => target.deliveryField === field)
    .map((target) => target.text);
}
