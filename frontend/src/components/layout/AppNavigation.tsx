import { cn } from "../../lib/utils";

type Page = "explore" | "live" | "compare";

interface AppNavigationProps {
  current: Page;
  onChange: (page: Page) => void;
}

export function AppNavigation({ current, onChange }: AppNavigationProps) {
  const items: Array<{ id: Page; label: string; description: string }> = [
    {
      id: "explore",
      label: "Explore",
      description: "Inspect validated examples",
    },
    {
      id: "live",
      label: "Live Studio",
      description: "Generate your own Speech Plan",
    },
    {
      id: "compare",
      label: "Intent Compare",
      description: "Change only the teaching intent",
    },
  ];
  return (
    <nav className="mx-auto flex max-w-[1400px] flex-wrap gap-2 px-6 py-4">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={cn(
            "rounded-xl px-4 py-2 text-left transition-colors",
            current === item.id
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
          )}
        >
          <span className="block text-sm font-semibold">{item.label}</span>
          <span
            className={cn(
              "hidden text-xs sm:block",
              current === item.id ? "text-slate-300" : "text-slate-500",
            )}
          >
            {item.description}
          </span>
        </button>
      ))}
    </nav>
  );
}
