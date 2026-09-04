import { getJson } from "./client";
import type {
  EvaluateRequest,
  ExampleSummary,
  GenerateRequest,
  IntentCompareRequest,
  IntentCompareResponse,
  LiveEvaluationResponse,
  LiveGenerationResponse,
  WorkbenchResponse,
} from "../types/teachintent";

export function fetchExamples(): Promise<ExampleSummary[]> {
  return getJson<ExampleSummary[]>("/api/examples");
}

export function fetchWorkbench(exampleId: string): Promise<WorkbenchResponse> {
  return getJson<WorkbenchResponse>(`/api/examples/${exampleId}`);
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as
      | { detail?: { error?: { message?: string } } | string }
      | null;
    let message = `Request failed with HTTP ${response.status}`;
    if (typeof payload?.detail === "string") {
      message = payload.detail;
    } else if (payload?.detail?.error?.message) {
      message = payload.detail.error.message;
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function generateSpeechPlan(
  request: GenerateRequest,
): Promise<LiveGenerationResponse> {
  return postJson<LiveGenerationResponse>("/api/generate", request);
}

export function evaluateSpeechPlan(
  request: EvaluateRequest,
): Promise<LiveEvaluationResponse> {
  return postJson<LiveEvaluationResponse>("/api/evaluate", request);
}

export function compareIntents(
  request: IntentCompareRequest,
): Promise<IntentCompareResponse> {
  return postJson<IntentCompareResponse>("/api/compare-intents", request);
}
