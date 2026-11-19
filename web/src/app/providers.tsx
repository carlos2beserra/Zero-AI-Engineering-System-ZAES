"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RootProvider } from "fumadocs-ui/provider";
import { useState } from "react";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <RootProvider
        theme={{ defaultTheme: "light", enableSystem: false }}
        search={{ options: { type: "static" } }}
      >
        {children}
      </RootProvider>
    </QueryClientProvider>
  );
}
