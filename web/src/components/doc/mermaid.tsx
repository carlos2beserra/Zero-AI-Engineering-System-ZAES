"use client";

import { useEffect, useState } from "react";

let mermaidInitialized = false;

export function Mermaid({ chart }: { chart: string }) {
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chart.trim()) return;
    let cancelled = false;

    import("mermaid")
      .then((m) => {
        if (!mermaidInitialized) {
          m.default.initialize({
            startOnLoad: false,
            theme: "neutral",
            securityLevel: "loose",
            fontFamily: "inherit",
          });
          mermaidInitialized = true;
        }
        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        return m.default.render(id, chart.trim());
      })
      .then(({ svg }) => {
        if (!cancelled) setSvg(svg);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err?.message ?? err));
      });

    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <pre className="text-sm text-muted-foreground bg-muted p-4 rounded-lg overflow-x-auto my-6">
        {chart}
      </pre>
    );
  }

  if (!svg) {
    return <div className="my-6 h-32 animate-pulse rounded-lg bg-muted" />;
  }

  return (
    <div
      className="my-6 overflow-x-auto flex justify-center [&_svg]:max-w-full [&_svg]:h-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
