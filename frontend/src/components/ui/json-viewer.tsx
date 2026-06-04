"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { CopyButton } from "@/components/ui/copy-button";

export interface JsonViewerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** JSON string or object to display. */
  data: string | object;
  /** Maximum depth to expand by default (default 2). */
  defaultDepth?: number;
  /** Show copy button (default true). */
  showCopy?: boolean;
  /** Optional title. */
  title?: string;
}

function formatJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return JSON.stringify(value, null, 2);
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function parseData(data: string | object): unknown {
  if (typeof data === "object") return data;
  try {
    return JSON.parse(data) as unknown;
  } catch {
    return data;
  }
}

const KEY_CLASS = "text-amber-700 dark:text-amber-300";
const STRING_CLASS = "text-emerald-700 dark:text-emerald-300";
const NUMBER_CLASS = "text-blue-600 dark:text-blue-400";
const BOOLEAN_CLASS = "text-primary";
const NULL_CLASS = "text-muted-foreground";

function JsonNode({
  name,
  value,
  depth,
  defaultDepth,
}: {
  name?: string;
  value: unknown;
  depth: number;
  defaultDepth: number;
}) {
  const [open, setOpen] = React.useState(depth < defaultDepth);

  if (value === null) {
    return (
      <span className="inline">
        {name != null && <span className={KEY_CLASS}>{JSON.stringify(name)}: </span>}
        <span className={NULL_CLASS}>null</span>
      </span>
    );
  }

  if (typeof value === "boolean") {
    return (
      <span className="inline">
        {name != null && <span className={KEY_CLASS}>{JSON.stringify(name)}: </span>}
        <span className={BOOLEAN_CLASS}>{String(value)}</span>
      </span>
    );
  }

  if (typeof value === "number") {
    return (
      <span className="inline">
        {name != null && <span className={KEY_CLASS}>{JSON.stringify(name)}: </span>}
        <span className={NUMBER_CLASS}>{value}</span>
      </span>
    );
  }

  if (typeof value === "string") {
    return (
      <span className="inline">
        {name != null && <span className={KEY_CLASS}>{JSON.stringify(name)}: </span>}
        <span className={STRING_CLASS}>{JSON.stringify(value)}</span>
      </span>
    );
  }

  if (Array.isArray(value)) {
    const isOpen = open;
    return (
      <div className="inline">
        {name != null && <span className={KEY_CLASS}>{JSON.stringify(name)}: </span>}
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="text-left text-muted-foreground hover:text-foreground"
          aria-expanded={isOpen}
        >
          {isOpen ? "▼" : "▶"} [{value.length}]
        </button>
        {isOpen && (
          <div className="ml-4 border-l border-border pl-2">
            {value.map((item, i) => (
              <div key={i}>
                <JsonNode
                  name={String(i)}
                  value={item}
                  depth={depth + 1}
                  defaultDepth={defaultDepth}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const entries = Object.entries(value as Record<string, unknown>);
  const isOpen = open;
  return (
    <div className="inline">
      {name != null && <span className={KEY_CLASS}>{JSON.stringify(name)}: </span>}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-left text-muted-foreground hover:text-foreground"
        aria-expanded={isOpen}
      >
        {isOpen ? "▼" : "▶"} {"{}"}
      </button>
      {isOpen && (
        <div className="ml-4 border-l border-border pl-2">
          {entries.map(([k, v]) => (
            <div key={k}>
              <JsonNode
                name={k}
                value={v}
                depth={depth + 1}
                defaultDepth={defaultDepth}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const JsonViewer = React.forwardRef<HTMLDivElement, JsonViewerProps>(
  (
    {
      className,
      data,
      defaultDepth = 2,
      showCopy = true,
      title,
      ...props
    },
    ref,
  ) => {
    const parsed = React.useMemo(() => parseData(data), [data]);
    const rawString = React.useMemo(() => formatJson(parsed), [parsed]);

    return (
      <div
        ref={ref}
        className={cn(
          "overflow-hidden rounded-lg border border-border bg-muted/50 font-mono text-sm",
          className,
        )}
        {...props}
      >
        {(title != null || showCopy) && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/70 px-3 py-2">
            {title != null && (
              <span className="text-xs font-medium text-muted-foreground">
                {title}
              </span>
            )}
            {showCopy && (
              <CopyButton
                value={rawString}
                size="sm"
                variant="ghost"
                className="ml-auto h-7 w-7 shrink-0"
              />
            )}
          </div>
        )}
        <div className="overflow-x-auto p-4">
          <JsonNode
            value={parsed}
            depth={0}
            defaultDepth={defaultDepth}
          />
        </div>
      </div>
    );
  },
);
JsonViewer.displayName = "JsonViewer";

export { JsonViewer };
