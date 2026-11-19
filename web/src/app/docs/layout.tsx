import { source } from "@/lib/source";
import { DocsLayout } from "fumadocs-ui/layouts/docs";
import type { ReactNode } from "react";
import { SiteHeader } from "@/components/layout/SiteHeader";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader section="docs" />
      <DocsLayout
        tree={source.pageTree}
        nav={{ enabled: false }}
        containerProps={{
          className: "md:[&>aside]:top-14 md:[&>aside]:h-[calc(100dvh-3.5rem)]",
        }}
      >
        {children}
      </DocsLayout>
    </>
  );
}
