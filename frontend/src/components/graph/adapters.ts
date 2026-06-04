/**
 * Adapters that turn backend graph payloads into a single normalized shape
 * the canvas understands. The per-scan risk graph (`RiskGraph`, served as
 * `report.risk_graph`) flows through the adapter here and ends up in the
 * `NormalizedGraph` form.
 */

export type ConnectionType =
  | "oauth"
  | "api"
  | "webhook"
  | "connector"
  | "workflow"
  | "unknown";

export type FlowDirection =
  | "inbound"
  | "outbound"
  | "bidirectional"
  | "unknown";

export interface NormalizedNode {
  id: string;
  label: string;
  nodeType: string;
  riskScore: number;
  categoryId?: string;
  categoryLabel?: string;
  postureGrade?: string;
  /** Optional, present on per-scan RiskGraph nodes via downstream enrichment. */
  meta?: Record<string, unknown>;
}

export interface NormalizedEdge {
  id: string;
  source: string;
  target: string;
  connectionType: ConnectionType;
  direction: FlowDirection;
  riskScore: number;
  /** 1..5 from RiskGraph; undefined for SaaSMapGraph edges. */
  severity?: number;
  findingsCount?: number;
  findingsSummary?: string[];
  dataTypes?: string[];
}

export interface NormalizedGraph {
  source: "saas_map" | "risk_graph";
  nodes: NormalizedNode[];
  edges: NormalizedEdge[];
  maxRiskScore: number;
}

const KNOWN_CONNECTION_TYPES: ReadonlySet<ConnectionType> = new Set([
  "oauth",
  "api",
  "webhook",
  "connector",
  "workflow",
  "unknown",
]);

const KNOWN_DIRECTIONS: ReadonlySet<FlowDirection> = new Set([
  "inbound",
  "outbound",
  "bidirectional",
  "unknown",
]);

function asConnectionType(value: unknown): ConnectionType {
  if (typeof value !== "string") return "unknown";
  const v = value.toLowerCase();
  return KNOWN_CONNECTION_TYPES.has(v as ConnectionType)
    ? (v as ConnectionType)
    : "unknown";
}

function asDirection(value: unknown): FlowDirection {
  if (typeof value !== "string") return "unknown";
  const v = value.toLowerCase();
  return KNOWN_DIRECTIONS.has(v as FlowDirection)
    ? (v as FlowDirection)
    : "unknown";
}

function safeNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

function safeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x): x is string => typeof x === "string");
}

/**
 * Collapse repeated node ids into a single entry, keeping the one with the
 * highest risk score. The backend can occasionally emit the same provider
 * id twice (e.g. when an integration is mapped from two different scans),
 * which would otherwise trigger React's duplicate-key warning in MiniMap.
 */
function dedupeNodes(nodes: NormalizedNode[]): NormalizedNode[] {
  const byId = new Map<string, NormalizedNode>();
  for (const n of nodes) {
    if (!n.id) continue;
    const existing = byId.get(n.id);
    if (!existing || n.riskScore > existing.riskScore) {
      byId.set(n.id, n);
    }
  }
  return Array.from(byId.values());
}

/**
 * Ensure edge ids are unique. Adapter-generated ids already include the
 * source array index so collisions are rare, but fall back to a numeric
 * suffix in case the same `source__target__i` slug recurs.
 */
function dedupeEdges(edges: NormalizedEdge[]): NormalizedEdge[] {
  const seen = new Map<string, number>();
  return edges.map((e) => {
    const count = seen.get(e.id) ?? 0;
    seen.set(e.id, count + 1);
    return count === 0 ? e : { ...e, id: `${e.id}__${count}` };
  });
}

/**
 * Convert a per-scan `RiskGraph` (serialized from
 * `app/analysis/risk_graph.py` and exposed as `ScanReport.risk_graph`,
 * typed loosely on the client as `Record<string, unknown> | null`) into
 * the same normalized shape used by the canvas.
 */
export function riskGraphToFlow(
  graph: Record<string, unknown> | null | undefined,
): NormalizedGraph {
  if (!graph || typeof graph !== "object") {
    return {
      source: "risk_graph",
      nodes: [],
      edges: [],
      maxRiskScore: 0,
    };
  }

  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const rawEdges = Array.isArray(graph.edges) ? graph.edges : [];

  const nodes: NormalizedNode[] = rawNodes
    .filter(
      (n): n is Record<string, unknown> => typeof n === "object" && n !== null,
    )
    .map((n) => {
      const id = typeof n.id === "string" ? n.id : String(n.id ?? "");
      const label =
        typeof n.label === "string" && n.label ? n.label : id || "node";
      const nodeType =
        typeof n.node_type === "string" && n.node_type ? n.node_type : "saas";
      return {
        id,
        label,
        nodeType,
        riskScore: safeNumber(n.risk_score),
      };
    })
    .filter((n) => n.id);

  let maxRisk = 0;

  const edges: NormalizedEdge[] = rawEdges
    .filter(
      (e): e is Record<string, unknown> => typeof e === "object" && e !== null,
    )
    .map((e, i) => {
      const source = typeof e.source === "string" ? e.source : String(e.source ?? "");
      const target = typeof e.target === "string" ? e.target : String(e.target ?? "");
      const riskScore = safeNumber(e.risk_score);
      maxRisk = Math.max(maxRisk, riskScore);
      return {
        id: `${source}__${target}__${i}`,
        source,
        target,
        connectionType: asConnectionType(e.connection_type),
        direction: asDirection(e.direction),
        riskScore,
        severity: safeNumber(e.severity, 0) || undefined,
        findingsCount: safeNumber(e.findings_count, 0) || undefined,
        findingsSummary: safeStringArray(e.findings_summary),
        dataTypes: safeStringArray(e.data_types),
      };
    })
    .filter((e) => e.source && e.target);

  const dedupedNodes = dedupeNodes(nodes);
  const nodeIds = new Set(dedupedNodes.map((n) => n.id));
  const validEdges = dedupeEdges(
    edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target)),
  );

  return {
    source: "risk_graph",
    nodes: dedupedNodes,
    edges: validEdges,
    maxRiskScore: safeNumber(
      (graph as { total_risk_score?: unknown }).total_risk_score,
      maxRisk,
    ),
  };
}
