/**
 * Centralized query keys for TanStack Query.
 * Enables consistent invalidation and deduplication across hooks.
 */

export const apiKeys = {
  all: ["api"] as const,
  health: {
    all: ["api", "health"] as const,
    root: () => [...apiKeys.health.all, "root"] as const,
    ready: () => [...apiKeys.health.all, "ready"] as const,
  },
  meta: {
    all: ["api", "meta"] as const,
    edition: () => [...apiKeys.meta.all, "edition"] as const,
  },
  rules: {
    all: ["api", "rules"] as const,
    list: () => [...apiKeys.rules.all, "list"] as const,
    scanRules: () => [...apiKeys.rules.all, "scan"] as const,
  },
  plugins: {
    all: ["api", "plugins"] as const,
    list: () => [...apiKeys.plugins.all, "list"] as const,
  },
  scans: {
    all: ["api", "scans"] as const,
    list: (params?: { limit?: number; offset?: number; target?: string }) =>
      [...apiKeys.scans.all, "list", params ?? {}] as const,
    detail: (id: string) => [...apiKeys.scans.all, "detail", id] as const,
  },
  connectors: {
    all: ["api", "connectors"] as const,
    list: () => [...apiKeys.connectors.all, "list"] as const,
  },
  ispm: {
    all: ["api", "ispm"] as const,
    categories: (customerId?: string) =>
      [...apiKeys.ispm.all, "categories", customerId ?? ""] as const,
    providers: (customerId?: string) =>
      [...apiKeys.ispm.all, "providers", customerId ?? ""] as const,
  },
  dashboard: {
    all: ["api", "dashboard"] as const,
    overview: (window?: string) =>
      [...apiKeys.dashboard.all, "overview", window ?? ""] as const,
    riskTrend: (window?: string, bucket?: string) =>
      [
        ...apiKeys.dashboard.all,
        "risk-trend",
        window ?? "",
        bucket ?? "day",
      ] as const,
    riskDistribution: () =>
      [...apiKeys.dashboard.all, "risk-distribution"] as const,
    critical: (limit?: number) =>
      [...apiKeys.dashboard.all, "critical", limit ?? 20] as const,
  },
} as const;
