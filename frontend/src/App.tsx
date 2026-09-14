import { useEffect, useState } from "react";
import { AppHeader } from "./components/layout/AppHeader";
import { HomePage } from "./pages/HomePage";
import { ExamplesPage } from "./pages/ExamplesPage";
import { LiveStudioPage } from "./pages/LiveStudioPage";
import { IntentComparePage } from "./pages/IntentComparePage";

const ALIASES: Record<string, string> = {
  "/live": "/studio",
  "/explore": "/examples",
  "/showcase": "/examples",
};
const ROUTES = ["/", "/studio", "/examples", "/compare"];
export default function App() {
  const [location, setLocation] = useState(
    () => window.location.pathname + window.location.search,
  );
  const path = location.split("?")[0].replace(/\/$/, "") || "/";
  const canonical = ALIASES[path] ?? path;
  useEffect(() => {
    function sync() {
      setLocation(window.location.pathname + window.location.search);
      window.scrollTo?.(0, 0);
    }
    function navigate(event: MouseEvent) {
      const anchor = (event.target as Element).closest?.("a");
      if (
        !anchor ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey ||
        anchor.target ||
        anchor.hasAttribute("download")
      )
        return;
      const url = new URL(anchor.href);
      if (
        url.hash ||
        url.origin !== window.location.origin ||
        !ROUTES.includes(url.pathname)
      )
        return;
      event.preventDefault();
      window.history.pushState(null, "", url.pathname + url.search);
      sync();
    }
    document.addEventListener("click", navigate);
    window.addEventListener("popstate", sync);
    return () => {
      document.removeEventListener("click", navigate);
      window.removeEventListener("popstate", sync);
    };
  }, []);
  useEffect(() => {
    if (ALIASES[path])
      window.history.replaceState(null, "", canonical + window.location.search);
    document.title = `${({ "/": "教学意图驱动的语音规划", "/studio": "在线体验", "/examples": "示例库", "/compare": "教学意图对比" } as Record<string, string>)[canonical] ?? "页面未找到"} · TeachIntent`;
  }, [canonical, path]);
  return (
    <>
      <a className="skip-link" href="#main-content">
        跳转到主要内容
      </a>
      <AppHeader current={canonical} />
      <main id="main-content" className="product-main" key={location}>
        {canonical === "/" ? (
          <HomePage />
        ) : canonical === "/studio" ? (
          <LiveStudioPage />
        ) : canonical === "/examples" ? (
          <ExamplesPage />
        ) : canonical === "/compare" ? (
          <IntentComparePage />
        ) : (
          <div className="page-heading">
            <h1>页面未找到</h1>
            <a href="/">返回首页</a>
          </div>
        )}
      </main>
      <footer className="site-footer">
        <span>TeachIntent · 显式规划，清晰教学</span>
        <a
          href="https://github.com/juanmaoxiongmaoQAQ/TeachIntent"
          target="_blank"
          rel="noreferrer"
        >
          开源项目 · GitHub
        </a>
      </footer>
    </>
  );
}
