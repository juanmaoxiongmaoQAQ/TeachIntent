import { useEffect, useState } from "react";

import { AppHeader } from "./components/layout/AppHeader";
import { AppNavigation } from "./components/layout/AppNavigation";
import { ExplorePage } from "./pages/ExplorePage";
import { IntentComparePage } from "./pages/IntentComparePage";
import { LiveStudioPage } from "./pages/LiveStudioPage";
import { ShowcasePage } from "./pages/ShowcasePage";

type Page = "explore" | "live" | "compare" | "showcase";
const PATHS: Record<Page, string> = { explore: "/explore", live: "/live", compare: "/compare", showcase: "/showcase" };

function currentPage(): Page {
  return (Object.keys(PATHS) as Page[]).find((page) => PATHS[page] === window.location.pathname.replace(/\/$/, "")) ?? "explore";
}

export default function App() {
  const [page, setPage] = useState<Page>(currentPage);
  useEffect(() => {
    const onPopState = () => setPage(currentPage());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  function navigate(next: Page) {
    window.history.pushState(null, "", PATHS[next]);
    setPage(next);
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-950">
      <AppHeader />
      <AppNavigation current={page} onChange={navigate} />
      <main className="mx-auto max-w-[1400px] px-6 pb-12">
        {page === "explore" ? <ExplorePage /> : null}
        {page === "live" ? <LiveStudioPage /> : null}
        {page === "compare" ? <IntentComparePage /> : null}
        {page === "showcase" ? <ShowcasePage onOpenLive={() => navigate("live")} /> : null}
      </main>
    </div>
  );
}
