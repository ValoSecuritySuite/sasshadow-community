"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export interface CopyButtonProps
  extends Omit<React.ComponentProps<typeof Button>, "onClick"> {
  /** Text to copy to clipboard. */
  value: string;
  /** Optional label for tooltip (default: "Copy"). */
  copyLabel?: string;
  /** Label after copy (default: "Copied!"). */
  copiedLabel?: string;
  /** Callback when copy succeeds. */
  onCopy?: () => void;
}

const CopyButton = React.forwardRef<HTMLButtonElement, CopyButtonProps>(
  (
    {
      className,
      value,
      copyLabel = "Copy",
      copiedLabel = "Copied!",
      onCopy,
      variant = "ghost",
      size = "icon",
      ...props
    },
    ref,
  ) => {
    const [copied, setCopied] = React.useState(false);

    const handleCopy = React.useCallback(async () => {
      try {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        onCopy?.();
        const t = setTimeout(() => setCopied(false), 2000);
        return () => clearTimeout(t);
      } catch {
        setCopied(false);
      }
    }, [value, onCopy]);

    return (
      <TooltipProvider delayDuration={300}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              ref={ref}
              type="button"
              variant={variant}
              size={size}
              className={cn("[&_svg]:size-4", className)}
              onClick={handleCopy}
              aria-label={copied ? copiedLabel : copyLabel}
              {...props}
            >
              {copied ? (
                <Check className="text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">
            {copied ? copiedLabel : copyLabel}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  },
);
CopyButton.displayName = "CopyButton";

export { CopyButton };
