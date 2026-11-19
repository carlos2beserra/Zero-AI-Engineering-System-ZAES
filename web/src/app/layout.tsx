import { Providers } from "@/app/providers";
import "@/styles/globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MAES — Maxxi AI Engineering System",
  description:
    "Contexto persistente, workflow estruturado e avaliação automática de PRs para times de engenharia que usam IA.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
