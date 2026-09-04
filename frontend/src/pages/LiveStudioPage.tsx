import { FlaskConical } from "lucide-react";

import { Panel } from "../components/common/Panel";
import { StatusBadge } from "../components/common/StatusBadge";

export function LiveStudioPage() {
  return (
    <Panel className="mt-2">
      <div className="flex max-w-3xl gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50">
          <FlaskConical className="h-5 w-5 text-indigo-600" aria-hidden="true" />
        </div>
        <div>
          <div className="mb-3">
            <StatusBadge tone="muted">Extension point</StatusBadge>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            Live Studio
          </h2>
          <p className="mt-3 text-base leading-7 text-slate-700">
            Generate and evaluate a Speech Plan from your own teaching scenario.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Coming in the next application stage.
          </p>
        </div>
      </div>
    </Panel>
  );
}
