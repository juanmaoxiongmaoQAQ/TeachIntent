import { BrainCircuit } from "lucide-react";

export function AppHeader() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-6 py-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50">
          <BrainCircuit className="h-5 w-5 text-indigo-600" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">
            TeachIntent
          </h1>
          <p className="text-sm text-slate-600">
            Pedagogical Speech Control for AI Tutors
          </p>
        </div>
        <p className="ml-auto hidden text-sm text-slate-600 md:block">
          让 AI Tutor 不仅知道说什么，也知道怎么说
        </p>
      </div>
    </header>
  );
}
