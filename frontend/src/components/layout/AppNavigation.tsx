export function AppNavigation({ current }: { current: string }) {
  return (
    <nav aria-label="主导航">
      <a href="/" aria-current={current === "/" ? "page" : undefined}>
        首页
      </a>
      <a
        href="/studio"
        aria-current={current === "/studio" ? "page" : undefined}
      >
        在线体验
      </a>
      <a
        href="/examples"
        aria-current={current === "/examples" ? "page" : undefined}
      >
        示例库
      </a>
      <a
        href="https://github.com/juanmaoxiongmaoQAQ/TeachIntent"
        target="_blank"
        rel="noreferrer"
      >
        GitHub <span aria-hidden="true">↗</span>
      </a>
    </nav>
  );
}
