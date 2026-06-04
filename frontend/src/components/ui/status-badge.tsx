import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { formatStatus, normalizeStatus, type EntityStatus } from "@/lib/format";

const statusBadgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      status: {
        active:
          "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300",
        inactive:
          "border-border bg-muted text-muted-foreground",
        pending:
          "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300",
        running:
          "border-primary/30 bg-primary/10 text-primary dark:bg-primary/20",
        success:
          "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300",
        failed:
          "border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300",
        warning:
          "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300",
        cancelled:
          "border-border bg-muted text-muted-foreground",
        unknown:
          "border-border bg-muted/80 text-muted-foreground",
      },
    },
    defaultVariants: {
      status: "unknown",
    },
  },
);

export interface StatusBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children">,
    VariantProps<typeof statusBadgeVariants> {
  /** Status value (e.g. from API). */
  value: EntityStatus | string;
  /** Override label (default: formatted status). */
  children?: React.ReactNode;
}

const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ className, value, status, children, ...props }, ref) => {
    const resolved = (status ?? normalizeStatus(value)) as EntityStatus;
    const label = children ?? formatStatus(resolved);
    return (
      <span
        ref={ref}
        className={cn(statusBadgeVariants({ status: resolved }), className)}
        {...props}
      >
        {label}
      </span>
    );
  },
);
StatusBadge.displayName = "StatusBadge";

export { StatusBadge, statusBadgeVariants };
