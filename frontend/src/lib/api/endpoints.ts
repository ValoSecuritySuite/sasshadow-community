/**
 * Centralized API endpoint map for SaaSShadow.ai frontend.
 * Paths: /health, /health/ready, /rules, /rules/evaluate, /plugins, /plugins/list,
 * /scan/analyze, /scan/report/json, /scan/report/pdf, /scan/dataset, /scan/rules.
 * Backend currently serves plugin list at GET /plugins; /plugins/list may be added as alias.
 * GET /scan/rules may return rules scoped to scan context when implemented.
 */

const BASE = "";

export const endpoints = {
  health: {
    root: `${BASE}/health`,
    ready: `${BASE}/health/ready`,
  },
  rules: {
    list: `${BASE}/rules`,
    evaluate: `${BASE}/rules/evaluate`,
  },
  plugins: {
    root: `${BASE}/plugins`,
    list: `${BASE}/plugins/list`,
  },
  scan: {
    analyze: `${BASE}/scan/analyze`,
    reportJson: `${BASE}/scan/report/json`,
    reportPdf: `${BASE}/scan/report/pdf`,
    dataset: `${BASE}/scan/dataset`,
    rules: `${BASE}/scan/rules`,
  },
  /** Scan history (persisted scans from DB). */
  scans: {
    list: `${BASE}/scans`,
    detail: (id: string) => `${BASE}/scans/${encodeURIComponent(id)}`,
    compare: `${BASE}/scans/compare`,
  },
  /** Connectors — sync from external SaaS platforms. */
  connectors: {
    list: `${BASE}/connectors`,
    entraSync: `${BASE}/connectors/entra/sync`,
    slackSync: `${BASE}/connectors/slack/sync`,
  },
  /** ISPM catalog endpoints. */
  ispm: {
    categories: `${BASE}/ispm/categories`,
    providers: `${BASE}/ispm/providers`,
  },
  meta: {
    edition: `${BASE}/meta/edition`,
  },
  /** Executive dashboard. */
  dashboard: {
    overview: `${BASE}/dashboard/overview`,
    riskTrend: `${BASE}/dashboard/risk-trend`,
    riskDistribution: `${BASE}/dashboard/risk-distribution`,
    critical: `${BASE}/dashboard/critical`,
    exportCsv: `${BASE}/dashboard/export.csv`,
    exportJson: `${BASE}/dashboard/export.json`,
    cacheClear: `${BASE}/dashboard/cache/clear`,
  },
} as const;

export type EndpointMap = typeof endpoints;
