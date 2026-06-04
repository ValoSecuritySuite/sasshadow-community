"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { getHealth, getHealthReady } from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type { HealthResponse } from "@/lib/api/types";

// ─── Query options (for prefetch / custom options) ───────────────────────────

export function healthQueryOptions(
  options?: Partial<UseQueryOptions<HealthResponse>>,
): UseQueryOptions<HealthResponse> {
  return {
    queryKey: apiKeys.health.root(),
    queryFn: () => getHealth(),
    staleTime: 30 * 1000,
    enabled: typeof window !== "undefined",
    ...options,
  };
}

export function healthReadyQueryOptions(
  options?: Partial<UseQueryOptions<HealthResponse>>,
): UseQueryOptions<HealthResponse> {
  return {
    queryKey: apiKeys.health.ready(),
    queryFn: () => getHealthReady(),
    staleTime: 10 * 1000,
    enabled: typeof window !== "undefined",
    ...options,
  };
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

/**
 * GET /health — liveness check.
 * States: isLoading, isSuccess, isError, data, error.
 */
export function useHealth(
  options?: Partial<UseQueryOptions<HealthResponse>>,
) {
  return useQuery(healthQueryOptions(options));
}

/**
 * GET /health/ready — readiness check (e.g. rules loaded).
 * States: isLoading, isSuccess, isError, data, error.
 */
export function useHealthReady(
  options?: Partial<UseQueryOptions<HealthResponse>>,
) {
  return useQuery(healthReadyQueryOptions(options));
}
