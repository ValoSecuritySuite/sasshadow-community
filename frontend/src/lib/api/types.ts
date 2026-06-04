/**
 * Typed DTOs for SaaSShadow.ai API.
 * Mirrors backend Pydantic models for health, rules, plugins, pipeline, report, dataset, and scan.
 */

// ─── Enums / literals ─────────────────────────────────────────────────────

export type InputKind = "text" | "json" | "bytes";

export type PatternOp =
  | "eq"
  | "neq"
  | "in"
  | "not_in"
  | "contains"
  | "not_contains"
  | "gte"
  | "lte"
  | "gt"
  | "lt"
  | "matches"
  | "exists"
  | "not_exists";

export type TextScanRuleCategory = "regex" | "keyword" | "entropy";

export type RiskLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "MINIMAL";

// ─── Health ────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
}

// ─── Rules ─────────────────────────────────────────────────────────────────

export interface Pattern {
  field: string;
  op: PatternOp;
  value?: unknown;
}

export interface Rule {
  name: string;
  severity: number;
  weight: number;
  enabled: boolean;
  patterns: Pattern[];
}

export interface TextScanRule {
  id: string;
  category: TextScanRuleCategory;
  pattern: string;
  severity: number;
  weight: number;
  enabled: boolean;
  description?: string | null;
}

export interface ContextRuleSummary {
  name: string;
  severity: number;
  weight: number;
  enabled: boolean;
  pattern_count: number;
}

export interface TextScanRuleSummary {
  id: string;
  category: string;
  severity: number;
  weight: number;
  enabled: boolean;
  description?: string | null;
}

export interface RulesInfo {
  filename: string;
  filepath: string;
  context_rule_count: number;
  text_scan_rule_count: number;
  total_rule_count: number;
  context_rules: ContextRuleSummary[];
  text_scan_rules: TextScanRuleSummary[];
}

export interface RuleSetResponse {
  rules: Rule[];
  text_scan_rules: TextScanRule[];
  rules_info?: RulesInfo | null;
}

export interface RuleMatch {
  rule_name: string;
  severity: number;
  weight: number;
  matched: boolean;
}

export interface RuleEngineResult {
  matched_rules: RuleMatch[];
  total_score: number;
  passed_count: number;
  failed_count: number;
}

export interface RuleEvalRequest {
  context: Record<string, unknown>;
}

// ─── Text findings ───────────────────────────────────────────────────────────

export interface TextFinding {
  rule_id: string;
  category: string;
  severity: number;
  weight: number;
  evidence: string;
  match_start?: number | null;
  match_end?: number | null;
}

// ─── OAuth / Token / Credential / Data flow ──────────────────────────────────

export interface OAuthScopeRisk {
  scope: string;
  risk_level: RiskLevel;
  severity: number;
  description: string;
  is_wildcard: boolean;
}

export interface OAuthAnalysis {
  total_scopes: number;
  scopes: string[];
  high_risk_scopes: OAuthScopeRisk[];
  wildcard_scopes: string[];
  safe_scopes: string[];
  over_permissioned: boolean;
  scope_risk_score: number;
}

export interface TokenAnalysis {
  tokens_found: number;
  misuse_patterns: string[];
  high_entropy_tokens: number;
  weak_tokens: number;
  tokens_in_urls: number;
  long_lived_tokens: number;
  rotation_disabled: boolean;
  shared_across_integrations: boolean;
  token_risk_score: number;
}

export interface CredentialFinding {
  credential_type: string;
  risk: RiskLevel;
  location: string;
  evidence: string;
  match_start?: number | null;
  match_end?: number | null;
  severity: number;
  detection_method: "regex" | "entropy";
  integration_context?: Record<string, unknown> | null;
}

export interface CredentialExposure {
  exposed_credentials: number;
  exposure_types: string[];
  findings: TextFinding[];
  credential_risk_score: number;
  credential_scan_findings: CredentialFinding[];
}

export interface DataFlowRisk {
  source_app?: string | null;
  destination_app?: string | null;
  data_types: string[];
  sensitive_data_exposed: boolean;
  cross_platform_risk: boolean;
  flow_risk_score: number;
}

// ─── Risk summary ────────────────────────────────────────────────────────────

export interface RiskSummary {
  integration: string;
  risk_score: number;
  severity: RiskLevel;
  findings: TextFinding[];
  dimension_scores: Record<string, number>;
  weights: Record<string, number>;
}

// ─── Report branding & pipeline request ─────────────────────────────────────

export interface ReportBranding {
  company_name?: string | null;
  logo_base64?: string | null;
}

export interface PipelineRequest {
  text?: string | null;
  json_data?: Record<string, unknown> | null;
  target: string;
  metadata?: Record<string, unknown>;
  report_branding?: ReportBranding | null;
  customer_id?: string | null;
}

// ─── Normalizer & detection ──────────────────────────────────────────────────

export interface NormalizedInput {
  target: string;
  content: string;
  metadata: Record<string, unknown>;
  input_kind: InputKind;
  content_length: number;
  encoding?: string | null;
}

export interface DetectionFlags {
  content_type: string;
  detected_language?: string | null;
  token_count: number;
  line_count: number;
  flags: string[];
}

// ─── SaaS signal summary ────────────────────────────────────────────────────

export interface SaaSSignalSummary {
  oauth: OAuthAnalysis;
  tokens: TokenAnalysis;
  credentials: CredentialExposure;
  data_flow: DataFlowRisk;
}

// ─── Scan report (full) ─────────────────────────────────────────────────────

export interface ScanReport {
  scan_id: string;
  timestamp: string; // ISO datetime
  risk_score: number;
  risk_level: RiskLevel;
  max_severity_found: number;
  severity_ceiling_applied: boolean;
  risk_summary?: RiskSummary | Record<string, unknown> | null;
  oauth_analysis?: OAuthAnalysis | null;
  token_analysis?: TokenAnalysis | null;
  credential_exposure?: CredentialExposure | null;
  data_flow_risk?: DataFlowRisk | null;
  findings: TextFinding[];
  matched_rules: RuleMatch[];
  metadata: Record<string, unknown>;
  executive_summary?: Record<string, unknown> | null;
  integration_visibility_summary?: Record<string, unknown> | null;
  top_risky_connections: Record<string, unknown>[];
  ai_data_flow_risks?: Record<string, unknown> | null;
  compliance_mapping: Record<string, unknown>[];
  remediation_recommendations: Record<string, unknown>[];
  risk_graph?: Record<string, unknown> | null;
  analyzed_input_overview?: Record<string, unknown> | null;
  integration_metadata?: Record<string, unknown> | null;
  detection_signals?: Record<string, unknown> | null;
  analyzer_breakdown?: Record<string, unknown> | null;
  risk_graph_summary?: Record<string, unknown> | null;
  dataset_context?: Record<string, unknown> | null;
  pipeline_trace?: string[] | null;
  attack_scenario?: Record<string, unknown> | null;
}

// ─── Pipeline result ────────────────────────────────────────────────────────

export interface PipelineResult {
  normalized: NormalizedInput;
  detection: DetectionFlags;
  matched_rules: RuleMatch[];
  context_score: number;
  passed_count: number;
  failed_count: number;
  text_findings: TextFinding[];
  text_scan_score: number;
  text_matched_count: number;
  saas_signals: SaaSSignalSummary;
  combined_score: number;
  risk_summary?: RiskSummary | Record<string, unknown> | null;
  report?: ScanReport | null;
}

// ─── Dataset (batch) ────────────────────────────────────────────────────────

export interface DatasetItemRequest {
  integration_id: string;
  text?: string | null;
  json_data?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
}

export interface DatasetAnalysisRequest {
  dataset_name: string;
  items: DatasetItemRequest[];
  report_branding?: ReportBranding | null;
}

export interface DatasetItemResult {
  integration_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  oauth_over_permission_detected: boolean;
  token_misuse_detected: boolean;
  credential_exposure_detected: boolean;
  cross_platform_risk_detected: boolean;
  report: ScanReport;
}

export interface DatasetAnalysisSummary {
  total_integrations: number;
  high_risk_integrations: number;
  average_risk_score: number;
  oauth_over_permission_hits: number;
  token_misuse_hits: number;
  credential_exposure_hits: number;
  cross_platform_risk_hits: number;
}

export interface DatasetAnalysisResponse {
  dataset_name: string;
  summary: DatasetAnalysisSummary;
  results: DatasetItemResult[];
}

// ─── Scan history (GET /scans, GET /scans/{id}) ─────────────────────────────

export interface KeyFindingSummary {
  rule_id: string;
  category: string;
  severity: number;
  evidence: string;
}

export interface ScanListItem {
  id: string;
  target: string;
  timestamp: string;
  score: number;
  risk_level: string;
  customer_id?: string | null;
  findings_count?: number;
}

export interface ScanDetail {
  id: string;
  target: string;
  timestamp: string;
  score: number;
  risk_level: string;
  customer_id?: string | null;
  key_findings: KeyFindingSummary[];
}

export interface ScanListResponse {
  scans: ScanListItem[];
}

export interface ScanCompareResponse {
  target: string;
  before_scan_id: string;
  after_scan_id: string;
  timestamp_before: string;
  timestamp_after: string;
  score_before: number;
  score_after: number;
  score_delta: number;
  risk_level_before: string;
  risk_level_after: string;
  new_findings: KeyFindingSummary[];
  mitigated_findings: KeyFindingSummary[];
}

// ─── Plugins (backend returns plain dict) ────────────────────────────────────

export interface PluginInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  hook_names: string[];
  tags?: string[];
}

export interface PluginsResponse {
  plugins: PluginInfo[];
}

// ─── Connectors (GET /connectors, POST /connectors/.../sync) ─────────────────

export interface ConnectorInfo {
  id: string;
  name: string;
  description: string;
}

export interface ConnectorsListResponse {
  connectors: ConnectorInfo[];
}

export interface ConnectorSyncResponse {
  connector: string;
  synced: number;
  scans: Array<{ scan_id: string; target: string; risk_score: number }>;
  errors: string[];
}

export interface EntraSyncRequest {
  tenant_id: string;
  client_id: string;
  client_secret: string;
  customer_id?: string | null;
}

export interface SlackSyncRequest {
  token: string;
  customer_id?: string | null;
}

// --- ISPM catalog ----------------------------------------------------------

export interface PostureThresholds {
  compliant: number;
  at_risk: number;
}

export interface IspmCategory {
  id: string;
  label: string;
  description?: string | null;
  posture_thresholds: PostureThresholds;
}

export interface IspmConfig {
  categories: IspmCategory[];
  provider_map: Record<string, string>;
  default_category_id: string;
  default_thresholds: PostureThresholds;
}

export interface IspmCategoriesResponse {
  config: IspmConfig;
  customer_id?: string | null;
}

export interface IspmProviderEntry {
  provider_id: string;
  category_id: string;
  label: string;
}

export interface IspmProvidersResponse {
  providers: IspmProviderEntry[];
}

// --- Dashboard -------------------------------------------------------------

export type TrendBucket = "hour" | "day" | "week";
export type DashboardWindow = "24h" | "7d" | "30d" | "90d";

export interface DashboardOverview {
  window_days: number;
  scans_total: number;
  scans_in_window: number;
  integrations_tracked: number;
  integrations_in_window: number;
  avg_risk_score: number;
  median_risk_score: number;
  portfolio_risk_level: RiskLevel;
  critical_integrations: number;
  risk_delta_vs_prior_window: number;
  generated_at: string;
}

export interface RiskTrendPoint {
  bucket_start: string;
  avg_risk_score: number;
  max_risk_score: number;
  scans: number;
}

export interface RiskTrendResponse {
  window_days: number;
  bucket: TrendBucket;
  points: RiskTrendPoint[];
}

export interface RiskDistributionEntry {
  risk_level: RiskLevel;
  count: number;
}

export interface RiskDistribution {
  total_integrations: number;
  entries: RiskDistributionEntry[];
}

export interface CriticalFindingEntry {
  scan_id: string;
  target: string;
  customer_id?: string | null;
  created_at: string;
  risk_score: number;
  risk_level: RiskLevel;
  rule_id?: string | null;
  category?: string | null;
  severity: number;
  summary: string;
}

export interface CriticalFindingsResponse {
  limit: number;
  findings: CriticalFindingEntry[];
}

export interface EditionMeta {
  edition: string;
  connectors?: string[];
}
