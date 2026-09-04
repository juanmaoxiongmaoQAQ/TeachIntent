interface EmptyStateProps {
  title: string;
  description: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm">
      <p className="font-medium text-slate-950">{title}</p>
      <p className="mt-1 text-slate-600">{description}</p>
    </div>
  );
}
