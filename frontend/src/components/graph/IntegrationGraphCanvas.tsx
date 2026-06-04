"use client";

import * as React from "react";
import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type EdgeMouseHandler,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import { Maximize2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { NormalizedGraph, NormalizedNode } from "./adapters";
import {
  autoLayout,
  type IntegrationFlowEdge,
  type IntegrationFlowNode,
  type LayoutDirection,
} from "./layout";
import IntegrationNode from "./nodes/IntegrationNode";
import IntegrationEdge from "./edges/IntegrationEdge";
import { DetailsPanel, type GraphSelection } from "./details-panel";
import { GraphLegend } from "./legend";

import "@xyflow/react/dist/style.css";

const nodeTypes = { integration: IntegrationNode };
const edgeTypes = { integration: IntegrationEdge };

export interface IntegrationGraphCanvasProps {
  data: NormalizedGraph;
  /** Optional set of node ids to dim; non-matching nodes/edges fade to ~25%. */
  highlightNodeIds?: Set<string> | null;
  /** Optional set of allowed connection types for additional dimming. */
  highlightConnectionTypes?: Set<string> | null;
  height?: number;
  direction?: LayoutDirection;
  /** Optional empty state to render when nodes is empty. */
  emptyState?: React.ReactNode;
  className?: string;
}

function applyDimming(
  nodes: IntegrationFlowNode[],
  edges: IntegrationFlowEdge[],
  highlightNodeIds: Set<string> | null,
  highlightConnectionTypes: Set<string> | null,
): { nodes: IntegrationFlowNode[]; edges: IntegrationFlowEdge[] } {
  const hasNodeFilter = highlightNodeIds != null && highlightNodeIds.size > 0;
  const hasConnFilter =
    highlightConnectionTypes != null && highlightConnectionTypes.size > 0;
  if (!hasNodeFilter && !hasConnFilter) {
    return { nodes, edges };
  }

  const dimmedNodes = nodes.map((n) => {
    const dim = hasNodeFilter && !highlightNodeIds!.has(n.id);
    return dim
      ? ({ ...n, data: { ...n.data, dimmed: true } } as IntegrationFlowNode)
      : n;
  });

  const dimmedEdges = edges.map((e) => {
    const matchesConn =
      !hasConnFilter ||
      highlightConnectionTypes!.has(String(e.data?.connectionType));
    const matchesEndpoints =
      !hasNodeFilter ||
      (highlightNodeIds!.has(e.source) && highlightNodeIds!.has(e.target));
    const dim = !matchesConn || !matchesEndpoints;
    return dim
      ? ({ ...e, data: { ...e.data, dimmed: true } } as IntegrationFlowEdge)
      : e;
  });

  return { nodes: dimmedNodes, edges: dimmedEdges };
}

function CanvasInner({
  data,
  highlightNodeIds,
  highlightConnectionTypes,
  height,
  direction = "LR",
}: Required<
  Pick<IntegrationGraphCanvasProps, "data">
> &
  Pick<
    IntegrationGraphCanvasProps,
    "highlightNodeIds" | "highlightConnectionTypes" | "height" | "direction"
  >) {
  const { fitView } = useReactFlow();
  const [selection, setSelection] = React.useState<GraphSelection>(null);

  const laidOut = React.useMemo(
    () => autoLayout(data.nodes, data.edges, { direction }),
    [data.nodes, data.edges, direction],
  );

  const { nodes, edges } = React.useMemo(
    () =>
      applyDimming(
        laidOut.nodes,
        laidOut.edges,
        highlightNodeIds ?? null,
        highlightConnectionTypes ?? null,
      ),
    [laidOut.nodes, laidOut.edges, highlightNodeIds, highlightConnectionTypes],
  );

  const nodeIndex = React.useMemo(() => {
    const map = new Map<string, NormalizedNode>();
    for (const n of data.nodes) map.set(n.id, n);
    return map;
  }, [data.nodes]);

  // Re-fit when the dataset shape changes (node/edge ids); preserves zoom on
  // pure dimming updates.
  const datasetKey = React.useMemo(
    () =>
      `${data.nodes.length}-${data.edges.length}-${data.nodes
        .map((n) => n.id)
        .join(",")}`,
    [data.nodes, data.edges],
  );
  React.useEffect(() => {
    const handle = window.requestAnimationFrame(() => {
      fitView({ padding: 0.15, duration: 250 });
    });
    return () => window.cancelAnimationFrame(handle);
  }, [datasetKey, fitView]);

  const onNodeClick = React.useCallback<NodeMouseHandler>(
    (_evt, node: Node) => {
      const original = nodeIndex.get(node.id);
      if (!original) return;
      setSelection({ kind: "node", node: original });
    },
    [nodeIndex],
  );

  const onEdgeClick = React.useCallback<EdgeMouseHandler>(
    (_evt, edge: Edge) => {
      const original = data.edges.find((e) => e.id === edge.id);
      if (!original) return;
      const sourceLabel =
        nodeIndex.get(original.source)?.label ?? original.source;
      const targetLabel =
        nodeIndex.get(original.target)?.label ?? original.target;
      setSelection({
        kind: "edge",
        edge: original,
        sourceLabel,
        targetLabel,
      });
    },
    [data.edges, nodeIndex],
  );

  const onPaneClick = React.useCallback(() => {
    setSelection(null);
  }, []);

  return (
    <div
      className="relative w-full"
      style={{ height: height ?? 560 }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{
          type: "integration",
          markerEnd: { type: MarkerType.ArrowClosed, color: "currentColor" },
          markerStart: { type: MarkerType.ArrowClosed, color: "currentColor" },
        }}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
        <Controls className="!border !border-border !bg-background !text-foreground" />
        <MiniMap
          pannable
          zoomable
          className="!border !border-border !bg-background"
          maskColor="hsl(var(--muted) / 0.6)"
          nodeColor={(n) => {
            const grade = (n.data as { postureGrade?: string } | undefined)
              ?.postureGrade;
            if (grade === "CRITICAL") return "rgb(239 68 68)";
            if (grade === "AT_RISK") return "rgb(245 158 11)";
            if (grade === "COMPLIANT") return "rgb(16 185 129)";
            return "rgb(148 163 184)";
          }}
        />
        <Panel position="top-left">
          <GraphLegend />
        </Panel>
        <Panel position="top-right">
          <Button
            size="sm"
            variant="outline"
            onClick={() => fitView({ padding: 0.15, duration: 250 })}
          >
            <Maximize2 className="mr-1.5 h-3.5 w-3.5" />
            Fit view
          </Button>
        </Panel>
      </ReactFlow>
      <DetailsPanel
        selection={selection}
        onOpenChange={(open) => {
          if (!open) setSelection(null);
        }}
      />
    </div>
  );
}

export function IntegrationGraphCanvas({
  data,
  highlightNodeIds,
  highlightConnectionTypes,
  height,
  direction = "LR",
  emptyState,
  className,
}: IntegrationGraphCanvasProps) {
  if (data.nodes.length === 0) {
    return (
      <div className={className}>
        {emptyState ?? (
          <div
            className="flex items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 text-sm text-muted-foreground"
            style={{ height: height ?? 320 }}
          >
            No integration graph data to render.
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-border bg-card",
        className,
      )}
    >
      <ReactFlowProvider>
        <CanvasInner
          data={data}
          highlightNodeIds={highlightNodeIds}
          highlightConnectionTypes={highlightConnectionTypes}
          height={height}
          direction={direction}
        />
      </ReactFlowProvider>
    </div>
  );
}

export default IntegrationGraphCanvas;
