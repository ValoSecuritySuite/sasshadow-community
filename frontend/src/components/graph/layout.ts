/**
 * Dagre-based auto layout for the integration graph canvas.
 *
 * The backend never returns positions, so the canvas computes them once per
 * (nodes, edges) input via `useMemo`. Dagre is sync, small, and well-suited
 * to the source-target topology of integration data. For typical tenant
 * sizes (sub-200 nodes) layout completes in under 50ms.
 */

import type { Edge, Node } from "@xyflow/react";
import { Position } from "@xyflow/react";
import dagre from "dagre";

import type { NormalizedEdge, NormalizedNode } from "./adapters";

export type LayoutDirection = "LR" | "TB" | "RL" | "BT";

export interface LayoutOptions {
  direction?: LayoutDirection;
  nodeWidth?: number;
  nodeHeight?: number;
  rankSep?: number;
  nodeSep?: number;
}

export interface IntegrationNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  riskScore: number;
  categoryId?: string;
  categoryLabel?: string;
  postureGrade?: string;
  dimmed?: boolean;
}

export interface IntegrationEdgeData extends Record<string, unknown> {
  connectionType: string;
  direction: string;
  riskScore: number;
  severity?: number;
  findingsCount?: number;
  findingsSummary?: string[];
  dataTypes?: string[];
  dimmed?: boolean;
}

export type IntegrationFlowNode = Node<IntegrationNodeData, "integration">;
export type IntegrationFlowEdge = Edge<IntegrationEdgeData, "integration">;

const DEFAULT_NODE_WIDTH = 220;
const DEFAULT_NODE_HEIGHT = 96;

/**
 * Compute node positions and convert NormalizedGraph parts into the
 * React Flow node/edge format consumed by the canvas.
 */
export function autoLayout(
  nodes: NormalizedNode[],
  edges: NormalizedEdge[],
  options: LayoutOptions = {},
): { nodes: IntegrationFlowNode[]; edges: IntegrationFlowEdge[] } {
  const direction: LayoutDirection = options.direction ?? "LR";
  const nodeWidth = options.nodeWidth ?? DEFAULT_NODE_WIDTH;
  const nodeHeight = options.nodeHeight ?? DEFAULT_NODE_HEIGHT;

  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: direction,
    nodesep: options.nodeSep ?? 40,
    ranksep: options.rankSep ?? 80,
    marginx: 16,
    marginy: 16,
  });

  for (const n of nodes) {
    g.setNode(n.id, { width: nodeWidth, height: nodeHeight });
  }

  // Dagre supports multigraph, but we use the React Flow edge id as the
  // dagre edge "name" to keep parallel edges between the same source/target
  // pair distinct.
  for (const e of edges) {
    if (!g.hasNode(e.source) || !g.hasNode(e.target)) continue;
    g.setEdge(e.source, e.target, {}, e.id);
  }

  dagre.layout(g);

  const isHorizontal = direction === "LR" || direction === "RL";
  const sourcePos = direction === "LR"
    ? Position.Right
    : direction === "RL"
      ? Position.Left
      : direction === "TB"
        ? Position.Bottom
        : Position.Top;
  const targetPos = direction === "LR"
    ? Position.Left
    : direction === "RL"
      ? Position.Right
      : direction === "TB"
        ? Position.Top
        : Position.Bottom;

  const flowNodes: IntegrationFlowNode[] = nodes.map((n) => {
    const pos = g.node(n.id);
    const x = (pos?.x ?? 0) - nodeWidth / 2;
    const y = (pos?.y ?? 0) - nodeHeight / 2;
    return {
      id: n.id,
      type: "integration",
      position: { x, y },
      sourcePosition: sourcePos,
      targetPosition: targetPos,
      data: {
        label: n.label,
        nodeType: n.nodeType,
        riskScore: n.riskScore,
        categoryId: n.categoryId,
        categoryLabel: n.categoryLabel,
        postureGrade: n.postureGrade,
      },
    };
  });

  const flowEdges: IntegrationFlowEdge[] = edges
    .filter((e) => g.hasNode(e.source) && g.hasNode(e.target))
    .map((e) => ({
      id: e.id,
      type: "integration",
      source: e.source,
      target: e.target,
      data: {
        connectionType: e.connectionType,
        direction: e.direction,
        riskScore: e.riskScore,
        severity: e.severity,
        findingsCount: e.findingsCount,
        findingsSummary: e.findingsSummary,
        dataTypes: e.dataTypes,
      },
    }));

  // Suppress unused-var warning for isHorizontal (kept for future tweaks).
  void isHorizontal;

  return { nodes: flowNodes, edges: flowEdges };
}
