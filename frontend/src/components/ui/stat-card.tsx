import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const statCardVariants = cva(
  "rounded-xl border border-border bg-card text-card-foreground shadow-sm transition-colors",
  {
    variants: {
      padding: {
        default: "p-6",
        compact: "p-4",
        relaxed: "p-8",
      },
    },
    defaultVariants: {
      padding: "default",
    },
  },
);

export interface StatCardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof statCardVariants> {
  /** Primary label (e.g. "Total scans"). */
  label: React.ReactNode;
  /** Main value (e.g. number or "12"). */
  value: React.ReactNode;
  /** Optional secondary line (e.g. unit or subtitle). */
  subtitle?: React.ReactNode;
  /** Optional icon or trend indicator. */
  icon?: React.ReactNode;
  /** Optional trend: "up" | "down" | "neutral" for semantic styling. */
  trend?: "up" | "down" | "neutral";
}

const StatCard = React.forwardRef<HTMLDivElement, StatCardProps>(
  ({ className, label, value, subtitle, icon, trend, padding, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(statCardVariants({ padding }), className)}
        {...props}
      >
        <div className="flex flex-col gap-1">
          <div className="flex items-start justify-between gap-2">
            <div className="text-sm font-medium text-muted-foreground">
              {label}
            </div>
            {icon != null && (
              <span className="text-muted-foreground [&_svg]:size-4 [&_svg]:shrink-0">
                {icon}
              </span>
            )}
          </div>
          <div className="text-2xl font-semibold tracking-tight tabular-nums">
            {value}
          </div>
          {(subtitle != null || trend != null) && (
            <div className="flex items-center gap-2">
              {subtitle != null && (
                <span className="text-xs text-muted-foreground">{subtitle}</span>
              )}
              {trend === "up" && (
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  ↑
                </span>
              )}
              {trend === "down" && (
                <span className="text-xs font-medium text-destructive">↓</span>
              )}
            </div>
          )}
        </div>
      </div>
    );
  },
);
StatCard.displayName = "StatCard";

export { StatCard, statCardVariants };
