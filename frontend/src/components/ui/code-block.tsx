import * as React from "react";
import { cn } from "@/lib/utils";
import { CopyButton } from "@/components/ui/copy-button";

export interface CodeBlockProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Code content. */
  children: React.ReactNode;
  /** Optional language label (e.g. "json", "bash") for display only. */
  language?: string;
  /** Show copy button (default true). */
  showCopy?: boolean;
  /** Optional filename or title. */
  title?: string;
  /** Explicit string to copy when children is not a string (e.g. preformatted node). */
  copyValue?: string;
}

const CodeBlock = React.forwardRef<HTMLDivElement, CodeBlockProps>(
  (
    {
      className,
      children,
      language,
      showCopy = true,
      title,
      copyValue,
      ...props
    },
    ref,
  ) => {
    const copyText =
      copyValue ??
      (typeof children === "string" ? children : "");

    return (
      <div
        ref={ref}
        className={cn(
          "relative overflow-hidden rounded-lg border border-border bg-muted/50 font-mono text-sm",
          className,
        )}
        {...props}
      >
        {(title != null || language != null || showCopy) && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/70 px-3 py-2">
            <div className="flex items-center gap-2">
              {title != null && (
                <span className="text-xs font-medium text-muted-foreground">
                  {title}
                </span>
              )}
              {language != null && (
                <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                  {language}
                </span>
              )}
            </div>
            {showCopy && (
              <CopyButton
                value={copyText}
                size="sm"
                variant="ghost"
                className="h-7 w-7 shrink-0"
              />
            )}
          </div>
        )}
        <pre className="overflow-x-auto p-4 text-foreground [&>code]:text-sm">
          {typeof children === "string" ? (
            <code>{children}</code>
          ) : (
            children
          )}
        </pre>
      </div>
    );
  },
);
CodeBlock.displayName = "CodeBlock";

export { CodeBlock };
