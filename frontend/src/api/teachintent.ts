import { getJson } from "./client";
import type { ExampleSummary, WorkbenchResponse } from "../types/teachintent";

export function fetchExamples(): Promise<ExampleSummary[]> {
  return getJson<ExampleSummary[]>("/api/examples");
}

export function fetchWorkbench(exampleId: string): Promise<WorkbenchResponse> {
  return getJson<WorkbenchResponse>(`/api/examples/${exampleId}`);
}
