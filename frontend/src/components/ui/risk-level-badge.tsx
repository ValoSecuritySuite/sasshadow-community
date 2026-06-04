import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import {
  formatRiskLevel,
  getRiskLevelFromScore,
  type RiskLevel,
} from "@/lib/format";

const riskLevelBadgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      level: {
        critical:
          "border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300",
        high: "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/50 dark:bg-orange-950/50 dark:text-orange-300",
        medium:
          "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300",
        low: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300",
        minimal:
          "border-border bg-muted/80 text-muted-foreground",
        none: "border-border bg-muted/50 text-muted-foreground",
      },
    },
    defaultVariants: {
      level: "none",
    },
  },
);

export interface RiskLevelBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children">,
    VariantProps<typeof riskLevelBadgeVariants> {
  /** Risk level or numeric score (0–100, higher = worse). If number, level is derived. */
  value: RiskLevel | number | string;
  /** Override label (default: formatted risk level). */
  children?: React.ReactNode;
}

const RiskLevelBadge = React.forwardRef<HTMLSpanElement, RiskLevelBadgeProps>(
  ({ className, value, level, children, ...props }, ref) => {
    const resolvedLevel: RiskLevel =
      level ??
      (typeof value === "number"
        ? getRiskLevelFromScore(value)
        : (value as RiskLevel));
    const label = children ?? formatRiskLevel(resolvedLevel);
    return (
      <span
        ref={ref}
        className={cn(riskLevelBadgeVariants({ level: resolvedLevel }), className)}
        {...props}
      >
        {label}
      </span>
    );
  },
);
RiskLevelBadge.displayName = "RiskLevelBadge";

export { RiskLevelBadge, riskLevelBadgeVariants };
