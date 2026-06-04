/**
 * Data access hooks for SaaSShadow.ai API (TanStack Query).
 * Domain-separated: health, rules, plugins, scan, dataset.
 */

export { apiKeys } from "./query-keys";

export {
  useHealth,
  useHealthReady,
  healthQueryOptions,
  healthReadyQueryOptions,
} from "./use-health";

export {
  useRules,
  useScanRules,
  useEvaluateRules,
  rulesQueryOptions,
  scanRulesQueryOptions,
} from "./use-rules";

export {
  usePlugins,
  pluginsQueryOptions,
} from "./use-plugins";

export {
  useAnalyzeScan,
  useReportJson,
  useReportPdf,
} from "./use-scan";

export {
  useAnalyzeDataset,
} from "./use-dataset";

export {
  useScansList,
  useScanDetail,
  scansListQueryOptions,
  scanDetailQueryOptions,
} from "./use-scans";

export {
  useConnectors,
  useEntraSync,
  useSlackSync,
  connectorsQueryOptions,
} from "./use-connectors";

export {
  useIspmCategories,
  useIspmProviders,
} from "./use-ispm";

export {
  useDashboardOverview,
  useDashboardRiskTrend,
  useDashboardRiskDistribution,
  useDashboardCritical,
  useInvalidateDashboard,
} from "./use-dashboard";
