import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchExamples, fetchWorkbench } from "../api/teachintent";
import { EmptyState } from "../components/common/EmptyState";
import { Panel } from "../components/common/Panel";
import { StatusBadge } from "../components/common/StatusBadge";
import { Workbench } from "../components/workbench/Workbench";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import type {
  ExampleId,
  ExampleSummary,
  WorkbenchResponse,
} from "../types/teachintent";

const DEFAULT_EXAMPLE: ExampleId = "corrective-feedback";

export function ExplorePage() {
  const [examples, setExamples] = useState<ExampleSummary[]>([]);
  const [selectedExample, setSelectedExample] =
    useState<ExampleId>(DEFAULT_EXAMPLE);
  const [workbench, setWorkbench] = useState<WorkbenchResponse | null>(null);
  const [loadingExamples, setLoadingExamples] = useState(true);
  const [loadingWorkbench, setLoadingWorkbench] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoadingExamples(true);
    fetchExamples()
      .then((payload) => {
        if (!active) {
          return;
        }
        setExamples(payload);
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoadingExamples(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoadingWorkbench(true);
    setError(null);
    fetchWorkbench(selectedExample)
      .then((payload) => {
        if (active) {
          setWorkbench(payload);
        }
      })
      .catch((err: Error) => {
        if (active) {
          setWorkbench(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoadingWorkbench(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selectedExample]);

  const recommended = workbench?.example.recommended;

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Demo case
            </p>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
              Explore recorded TeachIntent evidence
            </h2>
            {workbench ? (
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                {workbench.example.description}
              </p>
            ) : null}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {recommended ? (
              <StatusBadge tone="accent">Recommended showcase</StatusBadge>
            ) : null}
            <CaseSelect
              examples={examples}
              value={selectedExample}
              disabled={loadingExamples}
              onChange={setSelectedExample}
            />
          </div>
        </div>
      </section>

      {error ? (
        <EmptyState
          title="API unavailable"
          description={error}
        />
      ) : null}

      {loadingWorkbench ? <WorkbenchSkeleton /> : null}

      {!loadingWorkbench && workbench ? (
        <>
          <Workbench
            mode="recorded"
            input={workbench.input}
            speechPlan={workbench.speech_plan}
            evaluation={workbench.evaluation}
          />
          <Panel title="Voice Realization">
            <p className="text-sm text-slate-600">
              Recorded A/B audio assets are not bundled in the F0 web client yet.
            </p>
          </Panel>
          <TechnicalDetails workbench={workbench} />
        </>
      ) : null}
    </div>
  );
}

interface CaseSelectProps {
  examples: ExampleSummary[];
  value: ExampleId;
  disabled: boolean;
  onChange: (value: ExampleId) => void;
}

function CaseSelect({ examples, value, disabled, onChange }: CaseSelectProps) {
  return (
    <Select
      value={value}
      disabled={disabled}
      onValueChange={(next) => onChange(next as ExampleId)}
    >
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {examples.map((example) => (
          <SelectItem key={example.id} value={example.id}>
            {example.id}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function WorkbenchSkeleton() {
  return (
    <div className="grid gap-5 xl:grid-cols-3" aria-label="Loading workbench">
      {[0, 1, 2].map((item) => (
        <div
          key={item}
          className="min-h-96 animate-pulse rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <div className="h-5 w-32 rounded bg-slate-200" />
          <div className="mt-6 space-y-3">
            <div className="h-20 rounded-xl bg-slate-100" />
            <div className="h-20 rounded-xl bg-slate-100" />
            <div className="h-20 rounded-xl bg-slate-100" />
          </div>
        </div>
      ))}
      <div className="sr-only">
        <Loader2 aria-hidden="true" />
      </div>
    </div>
  );
}

function TechnicalDetails({ workbench }: { workbench: WorkbenchResponse }) {
  const details = {
    example_id: workbench.example.id,
    prompt_version: workbench.prompt_version,
    speech_plan_schema_version: workbench.speech_plan.schema_version,
    evaluator_version: workbench.evaluation.evaluator_version,
    judge_prompt_version: workbench.evaluation.judge_prompt_version,
    source_run_id: workbench.evaluation.source_run_id,
  };
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">
        Technical details
      </summary>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <SafeJson title="Provenance" value={details} />
        <SafeJson title="Validated input JSON" value={workbench.input} />
        <SafeJson title="Validated Speech Plan JSON" value={workbench.speech_plan} />
      </div>
    </details>
  );
}

function SafeJson({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        {title}
      </p>
      <pre className="max-h-80 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-5 text-slate-100">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
