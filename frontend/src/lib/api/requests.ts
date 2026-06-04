/**
 * Typed request functions for SaaSShadow.ai API.
 * Uses the centralized client (requestJson, requestBlob) and endpoint map.
 */

import { endpoints } from "./endpoints";
import { requestJson, requestBlob, requestText, type RequestConfig } from "./client";
import type {
  HealthResponse,
  RuleSetResponse,
  RuleEngineResult,
  RuleEvalRequest,
  PluginsResponse,
  PipelineRequest,
  PipelineResult,
  ScanReport,
  DatasetAnalysisRequest,
  DatasetAnalysisResponse,
  ScanListResponse,
  ScanDetail,
  ScanCompareResponse,
  ConnectorsListResponse,
  ConnectorSyncResponse,
  EntraSyncRequest,
  SlackSyncRequest,
  IspmCategoriesResponse,
  IspmProvidersResponse,
  DashboardOverview,
  RiskTrendResponse,
  RiskDistribution,
  CriticalFindingsResponse,
  TrendBucket,
  EditionMeta,
} from "./types";

// ─── Health ───────────────────────────────────────────────────────────────────

export function getHealth(config?: RequestConfig): Promise<HealthResponse> {
  return requestJson<HealthResponse>(endpoints.health.root, { method: "GET", config });
}

export function getHealthReady(config?: RequestConfig): Promise<HealthResponse> {
  return requestJson<HealthResponse>(endpoints.health.ready, { method: "GET", config });
}

export function getEditionMeta(config?: RequestConfig): Promise<EditionMeta> {
  return requestJson<EditionMeta>(endpoints.meta.edition, { method: "GET", config });
}

// ─── Rules ───────────────────────────────────────────────────────────────────

export function getRules(config?: RequestConfig): Promise<RuleSetResponse> {
  return requestJson<RuleSetResponse>(endpoints.rules.list, { method: "GET", config });
}

export function evaluateRules(
  body: RuleEvalRequest,
  config?: RequestConfig,
): Promise<RuleEngineResult> {
  return requestJson<RuleEngineResult>(endpoints.rules.evaluate, {
    method: "POST",
    body: JSON.stringify(body),
    config,
  });
}

// ─── Plugins ──────────────────────────────────────────────────────────────────

/** GET /plugins — list loaded plugins. Backend serves at /plugins; /plugins/list may be aliased. */
export function getPlugins(config?: RequestConfig): Promise<PluginsResponse> {
  return requestJson<PluginsResponse>(endpoints.plugins.root, { method: "GET", config });
}

// ─── Scan history (GET /scans) ────────────────────────────────────────────────

export interface ListScansParams {
  target?: string;
  customer_id?: string;
  from_ts?: string;
  to_ts?: string;
  limit?: number;
  offset?: number;
}

/** GET /scans — list persisted scans from DB. */
export function getScansList(
  params?: ListScansParams,
  config?: RequestConfig,
): Promise<ScanListResponse> {
  const query: Record<string, string> = {};
  if (params?.limit != null) query.limit = String(params.limit);
  if (params?.offset != null) query.offset = String(params.offset);
  if (params?.target) query.target = params.target;
  if (params?.customer_id) query.customer_id = params.customer_id;
  if (params?.from_ts) query.from_ts = params.from_ts;
  if (params?.to_ts) query.to_ts = params.to_ts;
  return requestJson<ScanListResponse>(endpoints.scans.list, {
    method: "GET",
    query: Object.keys(query).length > 0 ? query : undefined,
    config,
  });
}

/** GET /scans/{id} — get one persisted scan by id. */
export function getScanDetail(
  scanId: string,
  options?: { includeCorrelation?: boolean },
  config?: RequestConfig,
): Promise<ScanDetail> {
  const query: Record<string, string> | undefined =
    options?.includeCorrelation === false
      ? { include_correlation: "false" }
      : undefined;
  return requestJson<ScanDetail>(endpoints.scans.detail(scanId), {
    method: "GET",
    query,
    config,
  });
}

export interface CompareScansParams {
  target?: string;
  before?: string;
  after?: string;
}

/** GET /scans/compare - compare two scans for a target (score delta, finding diff). */
export function compareScans(
  params: CompareScansParams,
  config?: RequestConfig,
): Promise<ScanCompareResponse> {
  const query: Record<string, string> = {};
  if (params.target) query.target = params.target;
  if (params.before) query.before = params.before;
  if (params.after) query.after = params.after;
  return requestJson<ScanCompareResponse>(endpoints.scans.compare, {
    method: "GET",
    query: Object.keys(query).length > 0 ? query : undefined,
    config,
  });
}

// ─── Scan (run analysis) ─────────────────────────────────────────────────────

/** GET /scan/rules — rules for scan context (when implemented). Falls back to global rules via getRules() if 404. */
export function getScanRules(config?: RequestConfig): Promise<RuleSetResponse> {
  return requestJson<RuleSetResponse>(endpoints.scan.rules, { method: "GET", config });
}

export function analyzeScan(
  body: PipelineRequest,
  config?: RequestConfig,
): Promise<PipelineResult> {
  return requestJson<PipelineResult>(endpoints.scan.analyze, {
    method: "POST",
    body: JSON.stringify(body),
    config,
  });
}

export function getReportJson(
  body: PipelineRequest,
  config?: RequestConfig,
): Promise<ScanReport> {
  return requestJson<ScanReport>(endpoints.scan.reportJson, {
    method: "POST",
    body: JSON.stringify(body),
    config,
  });
}

export function getReportPdf(
  body: PipelineRequest,
  config?: RequestConfig,
): Promise<{ blob: Blob; filename: string | null }> {
  return requestBlob(endpoints.scan.reportPdf, {
    method: "POST",
    body: JSON.stringify(body),
    config: {
      ...config,
      headers: {
        ...config?.headers,
        "Content-Type": "application/json",
      },
    },
  });
}

export function analyzeDataset(
  body: DatasetAnalysisRequest,
  config?: RequestConfig,
): Promise<DatasetAnalysisResponse> {
  return requestJson<DatasetAnalysisResponse>(endpoints.scan.dataset, {
    method: "POST",
    body: JSON.stringify(body),
    config,
  });
}

/**
 * Dataset analysis as CSV. Backend returns CSV when ?format=csv.
 * Returns raw CSV text (caller may parse or trigger download).
 */
export function analyzeDatasetCsv(
  body: DatasetAnalysisRequest,
  config?: RequestConfig,
): Promise<string> {
  return requestText(`${endpoints.scan.dataset}?format=csv`, {
    method: "POST",
    body: JSON.stringify(body),
    config: {
      ...config,
      headers: {
        ...config?.headers,
        Accept: "text/csv",
      },
    },
  });
}

// ─── Connectors ──────────────────────────────────────────────────────────────

/** GET /connectors — list available connectors (entra, slack). */
export function getConnectors(config?: RequestConfig): Promise<ConnectorsListResponse> {
  return requestJson<ConnectorsListResponse>(endpoints.connectors.list, { method: "GET", config });
}

/** POST /connectors/entra/sync — sync app registrations from Microsoft Entra. */
export function syncEntra(
  body: EntraSyncRequest,
  config?: RequestConfig,
): Promise<ConnectorSyncResponse> {
  return requestJson<ConnectorSyncResponse>(endpoints.connectors.entraSync, {
    method: "POST",
    body: JSON.stringify(body),
    config,
  });
}

/** POST /connectors/slack/sync — sync Slack app for the given token. */
export function syncSlack(
  body: SlackSyncRequest,
  config?: RequestConfig,
): Promise<ConnectorSyncResponse> {
  return requestJson<ConnectorSyncResponse>(endpoints.connectors.slackSync, {
    method: "POST",
    body: JSON.stringify(body),
    config,
  });
}

// --- ISPM catalog ----------------------------------------------------------

export function getIspmCategories(
  config?: RequestConfig,
): Promise<IspmCategoriesResponse> {
  return requestJson<IspmCategoriesResponse>(endpoints.ispm.categories, {
    method: "GET",
    config,
  });
}

export function getIspmProviders(
  config?: RequestConfig,
): Promise<IspmProvidersResponse> {
  return requestJson<IspmProvidersResponse>(endpoints.ispm.providers, {
    method: "GET",
    config,
  });
}

// --- Dashboard -------------------------------------------------------------

export interface DashboardQueryParams {
  window?: string;
  bucket?: TrendBucket;
  limit?: number;
  order?: "risk_desc" | "delta_desc" | "delta_asc" | "recent";
  customer_id?: string;
}

function _dashboardQuery(
  params?: DashboardQueryParams,
): Record<string, string> | undefined {
  if (!params) return undefined;
  const q: Record<string, string> = {};
  if (params.window) q.window = params.window;
  if (params.bucket) q.bucket = params.bucket;
  if (params.limit != null) q.limit = String(params.limit);
  if (params.order) q.order = params.order;
  if (params.customer_id) q.customer_id = params.customer_id;
  return Object.keys(q).length > 0 ? q : undefined;
}

export function getDashboardOverview(
  params?: DashboardQueryParams,
  config?: RequestConfig,
): Promise<DashboardOverview> {
  return requestJson<DashboardOverview>(endpoints.dashboard.overview, {
    method: "GET",
    query: _dashboardQuery(params),
    config,
  });
}

export function getDashboardRiskTrend(
  params?: DashboardQueryParams,
  config?: RequestConfig,
): Promise<RiskTrendResponse> {
  return requestJson<RiskTrendResponse>(endpoints.dashboard.riskTrend, {
    method: "GET",
    query: _dashboardQuery(params),
    config,
  });
}

export function getDashboardRiskDistribution(
  config?: RequestConfig,
): Promise<RiskDistribution> {
  return requestJson<RiskDistribution>(endpoints.dashboard.riskDistribution, {
    method: "GET",
    config,
  });
}

export function getDashboardCritical(
  params?: DashboardQueryParams,
  config?: RequestConfig,
): Promise<CriticalFindingsResponse> {
  return requestJson<CriticalFindingsResponse>(endpoints.dashboard.critical, {
    method: "GET",
    query: _dashboardQuery(params),
    config,
  });
}
