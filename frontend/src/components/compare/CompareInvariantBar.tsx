import type { ComparisonInvariants } from "../../types/teachintent";
import { StatusBadge } from "../common/StatusBadge";

interface CompareInvariantBarProps {
  comparison: ComparisonInvariants;
}

export function CompareInvariantBar({ comparison }: CompareInvariantBarProps) {
  return (
    <section className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone="accent">Controlled input comparison</StatusBadge>
        <StatusBadge tone="muted">Input controlled</StatusBadge>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-[1.2fr_1fr_1fr]">
        <InvariantItem
          label="Only changed input field"
          value="Pedagogical intent"
          emphasized
        />
        <InvariantItem label="Intent A" value={comparison.left_intent} />
        <InvariantItem label="Intent B" value={comparison.right_intent} />
      </div>
      <div className="mt-4 grid gap-2 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-5">
        <CheckItem label="Same content" ok={comparison.all_other_input_fields_equal} />
        <CheckItem
          label="Same teaching scenario"
          ok={comparison.all_other_input_fields_equal}
        />
        <CheckItem
          label="Same learner state"
          ok={comparison.all_other_input_fields_equal}
        />
        <CheckItem label="Same prompt v0.2" ok={comparison.same_prompt_version} />
        <CheckItem
          label="Same requested model"
          ok={comparison.same_requested_model}
        />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        All non-intent input fields are exactly equal. This is an
        application-level controlled input comparison, not a statistical
        experiment or causal claim.
      </p>
    </section>
  );
}

function InvariantItem({
  label,
  value,
  emphasized = false,
}: {
  label: string;
  value: string;
  emphasized?: boolean;
}) {
  return (
    <div
      className={
        emphasized
          ? "rounded-xl border border-indigo-300 bg-white p-3 ring-2 ring-indigo-100"
          : "rounded-xl border border-slate-200 bg-white p-3"
      }
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p
        className={
          emphasized
            ? "mt-1 text-base font-semibold text-slate-950"
            : "mt-1 font-mono text-sm font-semibold text-slate-950"
        }
      >
        {value}
      </p>
    </div>
  );
}

function CheckItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
      <span className={ok ? "text-emerald-700" : "text-red-700"}>
        {ok ? "✓" : "!"}
      </span>{" "}
      {label}
    </div>
  );
}
