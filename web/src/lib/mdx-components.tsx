"use client";

import { Callout } from "@/components/doc/callout";
import { CodeBlock } from "@/components/doc/code-block";
import { Mermaid } from "@/components/doc/mermaid";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import React from "react";

export const MDXComponents = {
  // Prose components
  h1: ({ children, ...props }: React.ComponentProps<"h1">) => (
    <h1
      className="scroll-m-20 text-4xl font-bold tracking-tight mt-6 mb-4"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: React.ComponentProps<"h2">) => (
    <h2
      className="scroll-m-20 border-b border-border pb-2 text-3xl font-semibold tracking-tight mt-10 mb-4"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.ComponentProps<"h3">) => (
    <h3
      className="scroll-m-20 text-2xl font-semibold tracking-tight mt-8 mb-4"
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ children, ...props }: React.ComponentProps<"h4">) => (
    <h4
      className="scroll-m-20 text-xl font-semibold tracking-tight mt-6 mb-3"
      {...props}
    >
      {children}
    </h4>
  ),
  p: ({ children, ...props }: React.ComponentProps<"p">) => (
    <p className="leading-7 mb-4" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }: React.ComponentProps<"ul">) => (
    <ul className="list-disc list-inside mb-4 space-y-2" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: React.ComponentProps<"ol">) => (
    <ol className="list-decimal list-inside mb-4 space-y-2" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: React.ComponentProps<"li">) => (
    <li className="leading-7" {...props}>
      {children}
    </li>
  ),
  a: ({ children, ...props }: React.ComponentProps<"a">) => (
    <a className="text-primary hover:underline" {...props}>
      {children}
    </a>
  ),
  blockquote: ({ children, ...props }: React.ComponentProps<"blockquote">) => (
    <blockquote
      className="border-l-4 border-primary pl-4 py-2 my-4 italic text-muted-foreground"
      {...props}
    >
      {children}
    </blockquote>
  ),

  // Custom doc components
  Callout,
  CodeBlock,
  Mermaid,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Alert,
  AlertTitle,
  AlertDescription,

  // Table
  table: ({ children, ...props }: React.ComponentProps<"table">) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-border">
      <table className="w-full" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }: React.ComponentProps<"thead">) => (
    <thead className="bg-muted" {...props}>
      {children}
    </thead>
  ),
  th: ({ children, ...props }: React.ComponentProps<"th">) => (
    <th className="px-4 py-2 text-left font-semibold" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }: React.ComponentProps<"td">) => (
    <td className="border-t border-border px-4 py-2" {...props}>
      {children}
    </td>
  ),
};
