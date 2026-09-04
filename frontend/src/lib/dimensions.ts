import type { DimensionId } from "../types/teachintent";

export const DIMENSIONS: Array<{
  key: string;
  id: DimensionId;
  label: string;
  shortLabel: string;
}> = [
  {
    key: "D1",
    id: "pedagogical_intent_fidelity",
    label: "Pedagogical Intent Fidelity",
    shortLabel: "Intent Fidelity",
  },
  {
    key: "D2",
    id: "content_faithfulness_boundary",
    label: "Content Faithfulness / Boundary",
    shortLabel: "Content Faithfulness",
  },
  {
    key: "D3",
    id: "learner_state_compatibility",
    label: "Learner-State Compatibility",
    shortLabel: "Learner Compatibility",
  },
  {
    key: "D4",
    id: "intent_specific_instructional_adequacy",
    label: "Instructional Adequacy",
    shortLabel: "Instructional Adequacy",
  },
  {
    key: "D5",
    id: "delivery_necessity_sparsity",
    label: "Delivery Necessity / Sparsity",
    shortLabel: "Delivery Sparsity",
  },
  {
    key: "D6",
    id: "delivery_pedagogy_alignment",
    label: "Delivery–Pedagogy Alignment",
    shortLabel: "Delivery Alignment",
  },
];
