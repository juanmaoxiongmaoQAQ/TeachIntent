import type { EvaluationArtifact } from "../../types/teachintent";

interface CriticalFlagsProps {
  evaluation: EvaluationArtifact;
}

export function CriticalFlags({ evaluation }: CriticalFlagsProps) {
  const flags = evaluation.critical_flags;
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-950">Critical flags</h3>
      {flags.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">None</p>
      ) : (
        <div className="mt-3 space-y-3">
          {flags.map((flag, index) => (
            <div
              key={`${flag.flag}-${index}`}
              className="rounded-lg border border-red-200 bg-red-50 p-3"
            >
              <p className="text-sm font-medium text-red-900">{flag.flag}</p>
              {flag.brief_justification ? (
                <p className="mt-1 text-sm text-red-800">
                  {flag.brief_justification}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
