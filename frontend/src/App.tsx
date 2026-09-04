import { useState } from "react";

import { AppHeader } from "./components/layout/AppHeader";
import { AppNavigation } from "./components/layout/AppNavigation";
import { ExplorePage } from "./pages/ExplorePage";
import { LiveStudioPage } from "./pages/LiveStudioPage";

type Page = "explore" | "live";

export default function App() {
  const [page, setPage] = useState<Page>("explore");

  return (
    <div className="min-h-screen bg-slate-100 text-slate-950">
      <AppHeader />
      <AppNavigation current={page} onChange={setPage} />
      <main className="mx-auto max-w-[1400px] px-6 pb-12">
        {page === "explore" ? <ExplorePage /> : <LiveStudioPage />}
      </main>
    </div>
  );
}
