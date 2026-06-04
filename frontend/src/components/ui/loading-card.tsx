import * as React from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export interface LoadingCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Number of skeleton lines in the body (default 4). */
  lines?: number;
  /** Show a header skeleton. */
  showHeader?: boolean;
  /** Show a chart/block skeleton (e.g. for dashboard widgets). */
  showChart?: boolean;
}

const LoadingCard = React.forwardRef<HTMLDivElement, LoadingCardProps>(
  (
    {
      className,
      lines = 4,
      showHeader = true,
      showChart = false,
      ...props
    },
    ref,
  ) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm",
          className,
        )}
        {...props}
      >
        {showHeader && (
          <div className="mb-4 space-y-2">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-48" />
          </div>
        )}
        {showChart && (
          <Skeleton className="mb-4 h-[200px] w-full rounded-lg" />
        )}
        <div className="space-y-3">
          {Array.from({ length: lines }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      </div>
    );
  },
);
LoadingCard.displayName = "LoadingCard";

export { LoadingCard };
