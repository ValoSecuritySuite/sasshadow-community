import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const sectionCardVariants = cva(
  "rounded-xl border border-border bg-card text-card-foreground shadow-sm",
  {
    variants: {
      padding: {
        default: "p-6",
        none: "p-0",
        compact: "p-4",
        relaxed: "p-8",
      },
    },
    defaultVariants: {
      padding: "default",
    },
  },
);

export interface SectionCardProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title">,
    VariantProps<typeof sectionCardVariants> {
  /** Section title. */
  title?: React.ReactNode;
  /** Optional description below title. */
  description?: React.ReactNode;
  /** Optional action(s) in the header (right-aligned). */
  action?: React.ReactNode;
}

const SectionCard = React.forwardRef<HTMLDivElement, SectionCardProps>(
  (
    {
      className,
      title,
      description,
      action,
      padding,
      children,
      ...props
    },
    ref,
  ) => {
    const hasHeader = title != null || description != null || action != null;
    const contentPadding =
      padding === "none" ? "" : padding === "compact" ? "p-4" : padding === "relaxed" ? "p-8" : "p-6";

    return (
      <div
        ref={ref}
        className={cn(sectionCardVariants({ padding: hasHeader ? "none" : padding }), className)}
        {...props}
      >
        {hasHeader && (
          <div
            className={cn(
              "flex flex-col gap-1 border-b border-border sm:flex-row sm:items-start sm:justify-between",
              contentPadding,
            )}
          >
            <div className="min-w-0">
              {title != null && (
                <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
              )}
              {description != null && (
                <div className="mt-0.5 text-sm text-muted-foreground">
                  {description}
                </div>
              )}
            </div>
            {action != null && (
              <div className="mt-2 shrink-0 sm:mt-0">{action}</div>
            )}
          </div>
        )}
        {children != null && (
          <div className={hasHeader ? contentPadding : undefined}>{children}</div>
        )}
      </div>
    );
  },
);
SectionCard.displayName = "SectionCard";

export { SectionCard, sectionCardVariants };
