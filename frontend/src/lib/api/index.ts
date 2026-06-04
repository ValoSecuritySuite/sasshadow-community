/**
 * Typed API layer for SaaSShadow.ai frontend.
 * Centralized endpoints, DTOs, client, and request functions.
 */

export { getApiBaseUrl, DEFAULT_API_BASE_URL } from "./config";
export { endpoints } from "./endpoints";
export type { EndpointMap } from "./endpoints";

export type {
  HealthResponse,
  RuleSetResponse,
  Rule,
  RuleMatch,
  RuleEngineResult,
  RuleEvalRequest,
  TextScanRule,
  RulesInfo,
  Pattern,
  TextFinding,
  OAuthAnalysis,
  OAuthScopeRisk,
  TokenAnalysis,
  CredentialExposure,
  CredentialFinding,
  DataFlowRisk,
  RiskSummary,
  PipelineRequest,
  PipelineResult,
  NormalizedInput,
  DetectionFlags,
  SaaSSignalSummary,
  ScanReport,
  ReportBranding,
  DatasetAnalysisRequest,
  DatasetAnalysisResponse,
  DatasetItemRequest,
  DatasetItemResult,
  DatasetAnalysisSummary,
  PluginInfo,
  PluginsResponse,
  RiskLevel,
  InputKind,
  PatternOp,
  TextScanRuleCategory,
  KeyFindingSummary,
  ScanListItem,
  ScanListResponse,
  ScanDetail,
  ScanCompareResponse,
} from "./types";

export {
  requestJson,
  requestText,
  requestBlob,
  ApiError,
  type RequestConfig,
} from "./client";

export {
  getHealth,
  getHealthReady,
  getRules,
  evaluateRules,
  getPlugins,
  getScanRules,
  analyzeScan,
  getReportJson,
  getReportPdf,
  analyzeDataset,
  analyzeDatasetCsv,
  getScansList,
  getScanDetail,
  compareScans,
  type ListScansParams,
  type CompareScansParams,
} from "./requests";
