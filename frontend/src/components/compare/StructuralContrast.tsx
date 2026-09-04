import type { StructuralContrast as StructuralContrastModel } from "../../types/teachintent";
import { Panel } from "../common/Panel";

interface StructuralContrastProps {
  contrast: StructuralContrastModel;
}

export function StructuralContrast({ contrast }: StructuralContrastProps) {
  return (
    <Panel title="Structural Contrast">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Verbal segments"
          left={String(contrast.verbal_segments.left)}
          right={String(contrast.verbal_segments.right)}
        />
        <Metric
          label="Delivery decision"
          left={capitalize(contrast.delivery_decision.left)}
          right={capitalize(contrast.delivery_decision.right)}
        />
        <Metric
          label="Verbal realization"
          left={contrast.verbal_text_identical ? "Same" : "Different"}
          right={contrast.verbal_text_identical ? "Same" : "Different"}
        />
        <Metric
          label="Delivery plan"
          left={contrast.delivery_plan_identical ? "Same" : "Different"}
          right={contrast.delivery_plan_identical ? "Same" : "Different"}
        />
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <ControlPaths title="Intent A control paths" paths={contrast.left_control_paths} />
        <ControlPaths title="Intent B control paths" paths={contrast.right_control_paths} />
      </div>
    </Panel>
  );
}

function Metric({
  label,
  left,
  right,
}: {
  label: string;
  left: string;
  right: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
        <p>
          <span className="text-slate-500">A:</span>{" "}
          <span className="font-semibold text-slate-900">{left}</span>
        </p>
        <p>
          <span className="text-slate-500">B:</span>{" "}
          <span className="font-semibold text-slate-900">{right}</span>
        </p>
      </div>
    </div>
  );
}

function ControlPaths({ title, paths }: { title: string; paths: string[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {paths.length ? (
        <ul className="mt-2 space-y-1">
          {paths.map((path) => (
            <li key={path} className="font-mono text-xs leading-5 text-slate-700">
              {path}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-600">None</p>
      )}
    </div>
  );
}

function capitalize(value: string) {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;
}
