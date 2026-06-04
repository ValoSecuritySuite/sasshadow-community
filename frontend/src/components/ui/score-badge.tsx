import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { formatScore, getRiskLevelFromScore, type ScoreKind } from "@/lib/format";

const scoreBadgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold tabular-nums transition-colors",
  {
    variants: {
      /** Semantic band for color (derived from score when kind is risk/quality). */
      band: {
        critical:
          "border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300",
        high: "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/50 dark:bg-orange-950/50 dark:text-orange-300",
        medium:
          "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300",
        low: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300",
        neutral: "border-border bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      band: "neutral",
    },
  },
);

type ScoreBand = "critical" | "high" | "medium" | "low" | "neutral";

function getBandFromScore(score: number, kind: ScoreKind): ScoreBand {
  if (kind === "risk") {
    const level = getRiskLevelFromScore(score);
    if (level === "minimal") return "low";
    if (level === "none") return "neutral";
    return level;
  }
  if (kind === "quality") {
    if (score >= 80) return "low";
    if (score >= 60) return "medium";
    if (score >= 40) return "high";
    return "critical";
  }
  return "neutral";
}

export interface ScoreBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children">,
    VariantProps<typeof scoreBadgeVariants> {
  /** Numeric score (e.g. 0–100). */
  value: number | null | undefined;
  /** Score semantics: risk (higher = worse), quality (higher = better), neutral. */
  kind?: ScoreKind;
  /** Optional suffix (e.g. "%"). */
  suffix?: string;
  /** Decimal places (default 0). */
  decimals?: number;
  /** Override band color (default: derived from value + kind). */
  band?: "critical" | "high" | "medium" | "low" | "neutral";
}

const ScoreBadge = React.forwardRef<HTMLSpanElement, ScoreBadgeProps>(
  (
    {
      className,
      value,
      kind = "neutral",
      suffix = "",
      decimals = 0,
      band: bandProp,
      ...props
    },
    ref,
  ) => {
    const display = formatScore(value, { decimals, suffix, empty: "—" });
    const band =
      bandProp ??
      (value != null && !Number.isNaN(value)
        ? getBandFromScore(value, kind)
        : "neutral");
    return (
      <span
        ref={ref}
        className={cn(scoreBadgeVariants({ band }), className)}
        {...props}
      >
        {display}
      </span>
    );
  },
);
ScoreBadge.displayName = "ScoreBadge";

export { ScoreBadge, scoreBadgeVariants };
