import type { ReactNode } from "react";
export function TechnicalDetails({
  data,
  children,
}: {
  data: Record<string, unknown>;
  children?: ReactNode;
}) {
  return (
    <details className="technical-details">
      <summary>技术详情</summary>
      {children}
      <div className="technical-grid">
        {Object.entries(data).map(([label, value]) => (
          <div key={label}>
            <h3>{label}</h3>
            <pre>{JSON.stringify(value ?? "暂无数据", null, 2)}</pre>
          </div>
        ))}
      </div>
    </details>
  );
}
