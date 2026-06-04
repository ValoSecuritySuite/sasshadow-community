"use client";

import {
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import {
  getDashboardCritical,
  getDashboardOverview,
  getDashboardRiskDistribution,
  getDashboardRiskTrend,
} from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type {
  CriticalFindingsResponse,
  DashboardOverview,
  RiskDistribution,
  RiskTrendResponse,
  TrendBucket,
} from "@/lib/api/types";

const STALE_MS = 30 * 1000;

export function useDashboardOverview(
  window?: string,
  options?: Partial<UseQueryOptions<DashboardOverview>>,
) {
  return useQuery({
    queryKey: apiKeys.dashboard.overview(window),
    queryFn: () => getDashboardOverview({ window }),
    staleTime: STALE_MS,
    ...options,
  });
}

export function useDashboardRiskTrend(
  window?: string,
  bucket: TrendBucket = "day",
  options?: Partial<UseQueryOptions<RiskTrendResponse>>,
) {
  return useQuery({
    queryKey: apiKeys.dashboard.riskTrend(window, bucket),
    queryFn: () => getDashboardRiskTrend({ window, bucket }),
    staleTime: STALE_MS,
    ...options,
  });
}

export function useDashboardRiskDistribution(
  options?: Partial<UseQueryOptions<RiskDistribution>>,
) {
  return useQuery({
    queryKey: apiKeys.dashboard.riskDistribution(),
    queryFn: () => getDashboardRiskDistribution(),
    staleTime: STALE_MS,
    ...options,
  });
}

export function useDashboardCritical(
  limit: number = 20,
  options?: Partial<UseQueryOptions<CriticalFindingsResponse>>,
) {
  return useQuery({
    queryKey: apiKeys.dashboard.critical(limit),
    queryFn: () => getDashboardCritical({ limit }),
    staleTime: STALE_MS,
    ...options,
  });
}

export function useInvalidateDashboard() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: apiKeys.dashboard.all });
  };
}
