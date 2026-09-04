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
  evidenceValues?: Partial<Record<DeliveryFieldKey, string>>;
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
    "plan.delivery_plan.global.prosody.pitch_level": {
      key: "delivery_plan.global.prosody.pitch_level",
      label: "Speech Plan · Pitch level",
    },
    "speech_plan.delivery_plan.global.prosody.pitch_level": {
      key: "delivery_plan.global.prosody.pitch_level",
      label: "Speech Plan · Pitch level",
    },
    "plan.delivery_plan.global.prosody.pitch_range": {
      key: "delivery_plan.global.prosody.pitch_range",
      label: "Speech Plan · Pitch range",
    },
    "speech_plan.delivery_plan.global.prosody.pitch_range": {
      key: "delivery_plan.global.prosody.pitch_range",
      label: "Speech Plan · Pitch range",
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

  const segmentScalarMatch = source.match(
    /^(plan|speech_plan)\.delivery_plan\.segment_overrides\[(\d+)\]\.(attitudinal_tone|emotion|contour_shape)$/,
  );
  if (segmentScalarMatch) {
    const segmentIndex = Number(segmentScalarMatch[2]);
    const fieldName = segmentScalarMatch[3];
    const key =
      `delivery_plan.segment_overrides[${segmentIndex}].${fieldName}` as DeliveryFieldKey;
    return {
      area: "speech",
      source,
      text,
      deliveryField: key,
      label: `Speech Plan · Segment control ${segmentIndex + 1} · ${labelForSegmentField(fieldName)}`,
      resolved: true,
    };
  }

  const segmentProsodyMatch = source.match(
    /^(plan|speech_plan)\.delivery_plan\.segment_overrides\[(\d+)\]\.prosody\.(speaking_rate|pitch_level|pitch_range|volume)$/,
  );
  if (segmentProsodyMatch) {
    const segmentIndex = Number(segmentProsodyMatch[2]);
    const fieldName = segmentProsodyMatch[3];
    const key =
      `delivery_plan.segment_overrides[${segmentIndex}].prosody.${fieldName}` as DeliveryFieldKey;
    return {
      area: "speech",
      source,
      text,
      deliveryField: key,
      label: `Speech Plan · Segment control ${segmentIndex + 1} · ${labelForSegmentField(fieldName)}`,
      resolved: true,
    };
  }

  const prominenceMatch = source.match(
    /^(plan|speech_plan)\.delivery_plan\.segment_overrides\[(\d+)\]\.prominence_targets\[(\d+)\](?:\.(text|level))?$/,
  );
  if (prominenceMatch) {
    const segmentIndex = Number(prominenceMatch[2]);
    const prominenceIndex = Number(prominenceMatch[3]);
    const leaf = prominenceMatch[4];
    const objectKey =
      `delivery_plan.segment_overrides[${segmentIndex}].prominence_targets[${prominenceIndex}]` as DeliveryFieldKey;
    const key = (leaf ? `${objectKey}.${leaf}` : objectKey) as DeliveryFieldKey;
    return {
      area: "speech",
      source,
      text,
      deliveryField: key,
      evidenceValues: leaf
        ? undefined
        : evidenceValuesFromJsonObject(text, objectKey, ["text", "level"]),
      label: `Speech Plan · Segment control ${segmentIndex + 1} · Prominence target ${prominenceIndex + 1}`,
      resolved: true,
    };
  }

  const boundaryMatch = source.match(
    /^(plan|speech_plan)\.delivery_plan\.segment_overrides\[(\d+)\]\.boundary_after(?:\.strength)?$/,
  );
  if (boundaryMatch) {
    const segmentIndex = Number(boundaryMatch[2]);
    const objectKey =
      `delivery_plan.segment_overrides[${segmentIndex}].boundary_after` as DeliveryFieldKey;
    const key = source.endsWith(".strength")
      ? (`${objectKey}.strength` as DeliveryFieldKey)
      : objectKey;
    return {
      area: "speech",
      source,
      text,
      deliveryField: key,
      evidenceValues: source.endsWith(".strength")
        ? undefined
        : evidenceValuesFromJsonObject(text, objectKey, ["strength"]),
      label: `Speech Plan · Segment control ${segmentIndex + 1} · Boundary after`,
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

function labelForSegmentField(fieldName: string): string {
  const labels: Record<string, string> = {
    attitudinal_tone: "Attitudinal tone",
    emotion: "Emotion",
    contour_shape: "Contour shape",
    speaking_rate: "Speaking rate",
    pitch_level: "Pitch level",
    pitch_range: "Pitch range",
    volume: "Volume",
  };
  return labels[fieldName] ?? fieldName;
}

function evidenceValuesFromJsonObject(
  evidenceText: string,
  objectKey: DeliveryFieldKey,
  fields: string[],
): Partial<Record<DeliveryFieldKey, string>> {
  try {
    const parsed = JSON.parse(evidenceText) as Record<string, unknown>;
    return fields.reduce<Partial<Record<DeliveryFieldKey, string>>>(
      (values, field) => {
        const value = parsed[field];
        if (typeof value === "string") {
          values[`${objectKey}.${field}` as DeliveryFieldKey] = value;
        }
        return values;
      },
      {},
    );
  } catch {
    return {};
  }
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
  const texts: string[] = [];
  for (const target of targets) {
    if (target.deliveryField === field) {
      texts.push(target.text);
    }
    const value = target.evidenceValues?.[field];
    if (value) {
      texts.push(value);
    }
  }
  return texts;
}
