import * as React from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  /** Icon or illustration (e.g. Lucide icon). */
  icon?: React.ReactNode;
  /** Primary title. */
  title: React.ReactNode;
  /** Optional description. */
  description?: React.ReactNode;
  /** Optional primary action (e.g. Button). */
  action?: React.ReactNode;
  /** Optional secondary action or link. */
  secondaryAction?: React.ReactNode;
  /** Compact layout (less vertical padding). */
  compact?: boolean;
}

const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  (
    {
      className,
      icon,
      title,
      description,
      action,
      secondaryAction,
      compact = false,
      ...props
    },
    ref,
  ) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 text-center",
          compact ? "py-8 px-4" : "py-12 px-6",
          className,
        )}
        {...props}
      >
        {icon != null && (
          <span className="mb-3 text-muted-foreground [&_svg]:size-10 [&_svg]:shrink-0">
            {icon}
          </span>
        )}
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        {description != null && (
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            {description}
          </p>
        )}
        {(action != null || secondaryAction != null) && (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            {action}
            {secondaryAction}
          </div>
        )}
      </div>
    );
  },
);
EmptyState.displayName = "EmptyState";

export { EmptyState };
