"use client";

import * as React from "react";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

export interface QueryErrorCardProps {
  /** Short title (e.g. "Unable to load rules"). */
  title: string;
  /** Error message or description. */
  message?: string;
  /** Retry handler (e.g. refetch). */
  onRetry?: () => void;
  /** Whether a retry is in progress. */
  isRetrying?: boolean;
  /** Optional class for the wrapper. */
  className?: string;
  /** Optional action node (replaces default Retry button if provided). */
  action?: React.ReactNode;
}

export function QueryErrorCard({
  title,
  message = "Something went wrong. Please try again.",
  onRetry,
  isRetrying = false,
  className,
  action,
}: QueryErrorCardProps) {
  return (
    <SectionCard
      title={title}
      description={message}
      className={cn("border-red-200 dark:border-red-900/50", className)}
      action={
        action ??
        (onRetry ? (
          <Button
            size="sm"
            variant="outline"
            onClick={onRetry}
            disabled={isRetrying}
            aria-label="Try again"
          >
            <RefreshCw
              className={cn("mr-1.5 h-3.5 w-3.5", isRetrying && "animate-spin")}
            />
            Try again
          </Button>
        ) : undefined)
      }
    >
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
        <span>{message}</span>
      </div>
    </SectionCard>
  );
}
