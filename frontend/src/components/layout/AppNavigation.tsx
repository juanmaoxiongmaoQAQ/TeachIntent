import { cn } from "../../lib/utils";

type Page = "explore" | "live" | "compare";

interface AppNavigationProps {
  current: Page;
  onChange: (page: Page) => void;
}

export function AppNavigation({ current, onChange }: AppNavigationProps) {
  const items: Array<{ id: Page; label: string }> = [
    { id: "explore", label: "Explore" },
    { id: "live", label: "Live Studio" },
    { id: "compare", label: "Intent Compare" },
  ];
  return (
    <nav className="mx-auto flex max-w-[1400px] gap-2 px-6 py-4">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={cn(
            "rounded-xl px-4 py-2 text-sm font-medium transition-colors",
            current === item.id
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
          )}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
