"use client";

import * as React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";

import { cn } from "@/lib/utils";

import type { IntegrationFlowEdge } from "../layout";

/**
 * Stroke color for an edge keyed by its connection type. Tailwind text-*
 * tokens are used so the canvas inherits dark/light theme automatically.
 *
 * Returned as a CSS variable resolution so we can keep `currentColor` for
 * the SVG marker-end arrowhead.
 */
export const CONNECTION_COLOR: Record<string, string> = {
  oauth: "text-violet-500 dark:text-violet-400",
  api: "text-sky-500 dark:text-sky-400",
  webhook: "text-amber-500 dark:text-amber-400",
  connector: "text-emerald-500 dark:text-emerald-400",
  workflow: "text-fuchsia-500 dark:text-fuchsia-400",
  unknown: "text-muted-foreground",
};

export const CONNECTION_LABEL: Record<string, string> = {
  oauth: "OAuth",
  api: "API",
  webhook: "Webhook",
  connector: "Connector",
  workflow: "Workflow",
  unknown: "Unknown",
};

/**
 * Map an edge's risk score (or severity for per-scan graphs) to a stroke
 * width band. Uses 1.5/2.5/3.5 to keep things crisp at typical zoom.
 */
function strokeWidthFor(riskScore: number, severity?: number): number {
  const s = severity ?? 0;
  if (s >= 4 || riskScore >= 70) return 3.5;
  if (s >= 3 || riskScore >= 40) return 2.5;
  return 1.5;
}

export function IntegrationEdge(props: EdgeProps<IntegrationFlowEdge>) {
  const {
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    data,
    selected,
    markerEnd,
    markerStart,
  } = props;

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 12,
  });

  const connectionType = data?.connectionType ?? "unknown";
  const direction = data?.direction ?? "unknown";
  const riskScore = data?.riskScore ?? 0;
  const severity = data?.severity;
  const dimmed = data?.dimmed ?? false;

  const colorClass = CONNECTION_COLOR[connectionType] ?? CONNECTION_COLOR.unknown;
  const width = strokeWidthFor(riskScore, severity);
  const isBidirectional = direction === "bidirectional";
  const isInbound = direction === "inbound";

  const [hovered, setHovered] = React.useState(false);

  return (
    <g
      className={cn("transition-opacity", colorClass, dimmed && "opacity-25")}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <BaseEdge
        id={props.id}
        path={edgePath}
        markerEnd={isInbound ? undefined : markerEnd}
        markerStart={isBidirectional || isInbound ? markerStart : undefined}
        style={{
          stroke: "currentColor",
          strokeWidth: selected ? width + 1 : width,
          strokeDasharray: isBidirectional ? "6 4" : undefined,
          opacity: selected ? 1 : 0.85,
        }}
      />
      {(hovered || selected) && (
        <EdgeLabelRenderer>
          <div
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
            className={cn(
              "pointer-events-none absolute z-10 rounded-md border border-border bg-popover px-2 py-1 text-[11px] font-medium text-popover-foreground shadow-sm",
              "tabular-nums",
            )}
          >
            <span className="mr-1.5">{CONNECTION_LABEL[connectionType]}</span>
            <span className="text-muted-foreground">{direction}</span>
            {severity != null && severity > 0 && (
              <span className="ml-1.5 text-muted-foreground">sev {severity}</span>
            )}
          </div>
        </EdgeLabelRenderer>
      )}
    </g>
  );
}

export default IntegrationEdge;
