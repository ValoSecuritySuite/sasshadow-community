"use client";

import * as React from "react";
import { ArrowRight, Network, Plug, Workflow, Bot } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ScoreBadge } from "@/components/ui/score-badge";
import { cn } from "@/lib/utils";

import type { NormalizedEdge, NormalizedNode } from "./adapters";
import { CONNECTION_COLOR, CONNECTION_LABEL } from "./edges/IntegrationEdge";

export type GraphSelection =
  | { kind: "node"; node: NormalizedNode }
  | { kind: "edge"; edge: NormalizedEdge; sourceLabel: string; targetLabel: string }
  | null;

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

function nodeTypeIcon(nodeType: string): React.ReactNode {
  const t = nodeType.toLowerCase();
  if (t === "ai") return <Bot className="h-4 w-4" />;
  if (t === "connector") return <Plug className="h-4 w-4" />;
  if (t === "workflow") return <Workflow className="h-4 w-4" />;
  return <Network className="h-4 w-4" />;
}

function FieldRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-right text-sm">{children}</span>
    </div>
  );
}

function ChipList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-muted-foreground">None</span>;
  }
  return (
    <div className="flex flex-wrap justify-end gap-1.5">
      {items.map((s, i) => (
        <span
          key={`${s}-${i}`}
          className="rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[11px] font-mono text-muted-foreground"
        >
          {s}
        </span>
      ))}
    </div>
  );
}

function NodeBody({ node }: { node: NormalizedNode }) {
  return (
    <div className="mt-2 space-y-1 divide-y divide-border/60">
      <FieldRow label="Identifier">
        <code className="break-all text-xs font-mono">{node.id}</code>
      </FieldRow>
      <FieldRow label="Node type">
        <span className="inline-flex items-center gap-1.5 capitalize">
          {nodeTypeIcon(node.nodeType)}
          {node.nodeType || "node"}
        </span>
      </FieldRow>
      {node.categoryLabel && (
        <FieldRow label="ISPM category">{node.categoryLabel}</FieldRow>
      )}
      {node.postureGrade && (
        <FieldRow label="Posture">
          <span className="inline-flex items-center gap-1.5">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                POSTURE_DOT[node.postureGrade] ?? "bg-muted-foreground",
              )}
            />
            {POSTURE_LABEL[node.postureGrade] ?? node.postureGrade}
          </span>
        </FieldRow>
      )}
      <FieldRow label="Risk score">
        <ScoreBadge value={node.riskScore} kind="risk" />
      </FieldRow>
    </div>
  );
}

function EdgeBody({
  edge,
  sourceLabel,
  targetLabel,
}: {
  edge: NormalizedEdge;
  sourceLabel: string;
  targetLabel: string;
}) {
  const colorClass =
    CONNECTION_COLOR[edge.connectionType] ?? CONNECTION_COLOR.unknown;
  return (
    <div className="mt-2 space-y-3">
      <div className="rounded-lg border border-border bg-muted/30 p-3">
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="min-w-0 flex-1 truncate font-medium">
            {sourceLabel}
          </span>
          <span className={cn("inline-flex items-center", colorClass)}>
            <span
              className={cn(
                "block h-0.5 w-6",
                edge.direction === "bidirectional" && "border-b border-dashed",
              )}
              style={{
                backgroundColor:
                  edge.direction === "bidirectional"
                    ? "transparent"
                    : "currentColor",
              }}
            />
            <ArrowRight className="h-4 w-4" />
          </span>
          <span className="min-w-0 flex-1 truncate text-right font-medium">
            {targetLabel}
          </span>
        </div>
      </div>

      <div className="space-y-1 divide-y divide-border/60">
        <FieldRow label="Connection type">
          <span className={cn("inline-flex items-center gap-1.5", colorClass)}>
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: "currentColor" }}
            />
            <span className="text-foreground">
              {CONNECTION_LABEL[edge.connectionType] ?? edge.connectionType}
            </span>
          </span>
        </FieldRow>
        <FieldRow label="Direction">
          <span className="capitalize">{edge.direction}</span>
        </FieldRow>
        <FieldRow label="Risk score">
          <ScoreBadge value={edge.riskScore} kind="risk" />
        </FieldRow>
        {edge.severity != null && edge.severity > 0 && (
          <FieldRow label="Severity">
            <span className="tabular-nums">{edge.severity} / 5</span>
          </FieldRow>
        )}
        {edge.findingsCount != null && edge.findingsCount > 0 && (
          <FieldRow label="Findings">
            <span className="tabular-nums">{edge.findingsCount}</span>
          </FieldRow>
        )}
      </div>

      {edge.dataTypes && edge.dataTypes.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <p className="text-xs text-muted-foreground">Data types</p>
          <ChipList items={edge.dataTypes} />
        </div>
      )}

      {edge.findingsSummary && edge.findingsSummary.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <p className="text-xs text-muted-foreground">Findings summary</p>
          <ul className="space-y-1 text-sm">
            {edge.findingsSummary.map((f, i) => (
              <li
                key={`${f}-${i}`}
                className="rounded-md border border-border bg-muted/30 px-2 py-1.5 text-xs"
              >
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function DetailsPanel({
  selection,
  onOpenChange,
}: {
  selection: GraphSelection;
  onOpenChange: (open: boolean) => void;
}) {
  const open = selection != null;
  const isNode = selection?.kind === "node";
  const title = !selection
    ? ""
    : isNode
      ? selection.node.label
      : `${selection.sourceLabel} -> ${selection.targetLabel}`;
  const description = !selection
    ? ""
    : isNode
      ? "Integration node details"
      : "Integration connection details";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-[88vw] max-w-md overflow-y-auto sm:max-w-md"
      >
        <SheetHeader>
          <SheetTitle className="break-all pr-8">
            {title || "Details"}
          </SheetTitle>
          <SheetDescription>{description}</SheetDescription>
        </SheetHeader>
        {selection?.kind === "node" && <NodeBody node={selection.node} />}
        {selection?.kind === "edge" && (
          <EdgeBody
            edge={selection.edge}
            sourceLabel={selection.sourceLabel}
            targetLabel={selection.targetLabel}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

export default DetailsPanel;
