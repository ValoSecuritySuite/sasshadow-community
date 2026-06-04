import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { formatSeverity, normalizeSeverity, type SeverityLevel } from "@/lib/format";

const severityBadgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      severity: {
        critical:
          "border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300",
        high: "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/50 dark:bg-orange-950/50 dark:text-orange-300",
        medium:
          "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300",
        low: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300",
        info: "border-border bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      severity: "info",
    },
  },
);

export interface SeverityBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children">,
    VariantProps<typeof severityBadgeVariants> {
  /** Severity value (display label is derived if not provided). */
  value: SeverityLevel | string;
  /** Override label (default: formatted severity). */
  children?: React.ReactNode;
}

const SeverityBadge = React.forwardRef<HTMLSpanElement, SeverityBadgeProps>(
  ({ className, value, severity, children, ...props }, ref) => {
    const level = (severity ?? normalizeSeverity(value)) as SeverityLevel;
    const label = children ?? formatSeverity(level);
    return (
      <span
        ref={ref}
        className={cn(severityBadgeVariants({ severity: level }), className)}
        {...props}
      >
        {label}
      </span>
    );
  },
);
SeverityBadge.displayName = "SeverityBadge";

export { SeverityBadge, severityBadgeVariants };
