"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

import {
  CONNECTION_COLOR,
  CONNECTION_LABEL,
} from "./edges/IntegrationEdge";

const POSTURE_LABEL: Record<string, string> = {
  CRITICAL: "Critical",
  AT_RISK: "At risk",
  COMPLIANT: "Compliant",
};

const POSTURE_DOT: Record<string, string> = {
  CRITICAL: "bg-red-500",
  AT_RISK: "bg-amber-500",
  COMPLIANT: "bg-emerald-500",
};

export interface GraphLegendProps {
  showPosture?: boolean;
  className?: string;
}

const CONNECTION_ORDER = [
  "oauth",
  "api",
  "webhook",
  "connector",
  "workflow",
  "unknown",
] as const;

const POSTURE_ORDER = ["CRITICAL", "AT_RISK", "COMPLIANT"] as const;

export function GraphLegend({
  showPosture = true,
  className,
}: GraphLegendProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-popover/95 px-3 py-2 text-[11px] text-popover-foreground shadow-sm backdrop-blur",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="font-medium text-muted-foreground">Connection</span>
        {CONNECTION_ORDER.map((key) => (
          <span
            key={key}
            className={cn("inline-flex items-center gap-1", CONNECTION_COLOR[key])}
          >
            <span
              className="inline-block h-0.5 w-4 rounded"
              style={{ backgroundColor: "currentColor" }}
            />
            <span className="text-foreground">{CONNECTION_LABEL[key]}</span>
          </span>
        ))}
      </div>
      {showPosture && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-border/60 pt-1.5">
          <span className="font-medium text-muted-foreground">Posture</span>
          {POSTURE_ORDER.map((g) => (
            <span key={g} className="inline-flex items-center gap-1">
              <span className={cn("h-1.5 w-1.5 rounded-full", POSTURE_DOT[g])} />
              <span className="text-foreground">{POSTURE_LABEL[g]}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default GraphLegend;
