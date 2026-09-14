import { BookOpen } from "lucide-react";
import { AppNavigation } from "./AppNavigation";
export function AppHeader({ current }: { current: string }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="brand" href="/" aria-label="TeachIntent 首页">
          <BookOpen size={24} aria-hidden="true" />
          <span>TeachIntent</span>
        </a>
        <AppNavigation current={current} />
      </div>
    </header>
  );
}
