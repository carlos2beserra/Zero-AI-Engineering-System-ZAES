import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, CheckCircle, Info } from "lucide-react";
import * as React from "react";

const calloutVariants = cva(
  "relative w-full rounded-lg border px-4 py-3 text-sm [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-current",
  {
    variants: {
      type: {
        info: "border-primary/50 bg-primary/5 text-primary dark:border-primary/50 [&>svg]:text-primary",
        warning:
          "border-warning/50 bg-warning/5 text-warning dark:border-warning/50 [&>svg]:text-warning",
        danger:
          "border-destructive/50 bg-destructive/5 text-destructive dark:border-destructive/50 [&>svg]:text-destructive",
        success:
          "border-success/50 bg-success/5 text-success dark:border-success/50 [&>svg]:text-success",
      },
    },
    defaultVariants: {
      type: "info",
    },
  },
);

interface CalloutProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof calloutVariants> {
  title?: string;
}

const iconMap = {
  info: Info,
  warning: AlertTriangle,
  danger: AlertCircle,
  success: CheckCircle,
};

const Callout = React.forwardRef<HTMLDivElement, CalloutProps>(
  ({ className, type = "info", title, children, ...props }, ref) => {
    const Icon = iconMap[type as keyof typeof iconMap];

    return (
      <div
        ref={ref}
        className={cn(calloutVariants({ type }), className)}
        {...props}
      >
        <Icon className="h-4 w-4" />
        <div>
          {title && <p className="font-semibold">{title}</p>}
          <div className="text-sm">{children}</div>
        </div>
      </div>
    );
  },
);

Callout.displayName = "Callout";

export { Callout, calloutVariants };
