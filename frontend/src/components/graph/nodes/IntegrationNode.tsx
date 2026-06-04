"use client";

import * as React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot, Network, Plug, Workflow } from "lucide-react";

import { ScoreBadge } from "@/components/ui/score-badge";
import { cn } from "@/lib/utils";

import type { IntegrationFlowNode } from "../layout";

const POSTURE_BORDER: Record<string, string> = {
  CRITICAL: "border-red-500/60 dark:border-red-400/60",
  AT_RISK: "border-amber-500/60 dark:border-amber-400/60",
  COMPLIANT: "border-emerald-500/60 dark:border-emerald-400/60",
};

const POSTURE_DOT: Record<string, string> = {
  CRITICAL: "bg-red-500",
  AT_RISK: "bg-amber-500",
  COMPLIANT: "bg-emerald-500",
};

const POSTURE_LABEL: Record<string, string> = {
  CRITICAL: "Critical",
  AT_RISK: "At risk",
  COMPLIANT: "Compliant",
};

function nodeIcon(nodeType: string): React.ReactNode {
  const t = nodeType.toLowerCase();
  if (t === "ai") return <Bot className="h-4 w-4" />;
  if (t === "connector") return <Plug className="h-4 w-4" />;
  if (t === "workflow") return <Workflow className="h-4 w-4" />;
  return <Network className="h-4 w-4" />;
}

/**
 * Border tint priority: explicit posture grade first; otherwise derive a
 * visual band from the risk score so per-scan RiskGraph nodes (which carry
 * no posture grade) still get a meaningful color.
 */
function borderForNode(
  postureGrade: string | undefined,
  riskScore: number,
): string {
  if (postureGrade && POSTURE_BORDER[postureGrade]) {
    return POSTURE_BORDER[postureGrade];
  }
  if (riskScore >= 70) return "border-red-500/60 dark:border-red-400/60";
  if (riskScore >= 40) return "border-amber-500/60 dark:border-amber-400/60";
  if (riskScore > 0) return "border-emerald-500/60 dark:border-emerald-400/60";
  return "border-border";
}

export function IntegrationNode({
  data,
  selected,
  sourcePosition,
  targetPosition,
}: NodeProps<IntegrationFlowNode>) {
  const {
    label,
    nodeType,
    riskScore,
    categoryLabel,
    postureGrade,
    dimmed,
  } = data;

  const border = borderForNode(postureGrade, riskScore);
  const sp = sourcePosition ?? Position.Right;
  const tp = targetPosition ?? Position.Left;

  return (
    <div
      className={cn(
        "group relative w-[220px] rounded-xl border-2 bg-card text-card-foreground shadow-sm transition-all",
        border,
        selected && "ring-2 ring-ring ring-offset-2 ring-offset-background",
        dimmed && "opacity-30 hover:opacity-60",
      )}
    >
      <Handle
        type="target"
        position={tp}
        className="!h-2 !w-2 !border !border-border !bg-background"
      />
      <div className="flex items-start gap-2 p-3">
        <span
          className={cn(
            "mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground",
            postureGrade === "CRITICAL" &&
              "bg-red-500/10 text-red-600 dark:text-red-300",
            postureGrade === "AT_RISK" &&
              "bg-amber-500/10 text-amber-700 dark:text-amber-300",
            postureGrade === "COMPLIANT" &&
              "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
          )}
        >
          {nodeIcon(nodeType)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold leading-tight">
            {label}
          </p>
          {categoryLabel ? (
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
              {categoryLabel}
            </p>
          ) : (
            <p className="mt-0.5 truncate text-[11px] uppercase tracking-wide text-muted-foreground">
              {nodeType || "node"}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-border/60 px-3 py-2">
        {postureGrade ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                POSTURE_DOT[postureGrade] ?? "bg-muted-foreground",
              )}
            />
            {POSTURE_LABEL[postureGrade] ?? postureGrade}
          </span>
        ) : (
          <span className="text-[11px] text-muted-foreground">Risk</span>
        )}
        <ScoreBadge value={riskScore} kind="risk" />
      </div>
      <Handle
        type="source"
        position={sp}
        className="!h-2 !w-2 !border !border-border !bg-background"
      />
    </div>
  );
}

export default IntegrationNode;
