'use client'

import { cn } from "@/lib/utils";
import { Check, Copy } from "lucide-react";
import * as React from "react";

interface CodeBlockProps extends React.HTMLAttributes<HTMLPreElement> {
  language?: string;
  title?: string;
  highlightLines?: number[];
}

interface CopyButtonProps {
  code: string;
}

function CopyButton({ code }: CopyButtonProps) {
  const [copied, setCopied] = React.useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={copy}
      className="absolute right-2 top-2 inline-flex items-center gap-2 rounded bg-muted px-2 py-1 text-xs text-muted-foreground hover:bg-muted/80 hover:text-foreground transition-colors"
      aria-label={copied ? "Copied" : "Copy code"}
    >
      {copied ? (
        <>
          <Check className="h-3 w-3" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          Copy
        </>
      )}
    </button>
  );
}

const CodeBlock = React.forwardRef<HTMLPreElement, CodeBlockProps>(
  ({ className, language, title, children, ...props }, ref) => {
    const code = React.useMemo(() => {
      if (typeof children === "string") return children.trim();
      return "";
    }, [children]);

    return (
      <div className="relative my-4 rounded-lg border border-border bg-muted">
        {title && (
          <div className="border-b border-border bg-muted/50 px-4 py-2 text-xs font-medium text-muted-foreground">
            {title}
          </div>
        )}
        {language && (
          <div className="absolute right-2 top-2 text-xs text-muted-foreground">
            {language}
          </div>
        )}
        <pre
          ref={ref}
          className={cn(
            "overflow-x-auto p-4 text-sm leading-relaxed",
            title && "rounded-b-lg",
            !title && "rounded-lg",
            className,
          )}
          {...props}
        >
          <code className="font-mono text-foreground">{children}</code>
        </pre>
        <CopyButton code={code} />
      </div>
    );
  },
);

CodeBlock.displayName = "CodeBlock";

export { CodeBlock };
