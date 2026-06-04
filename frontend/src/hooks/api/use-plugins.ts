"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { getPlugins } from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type { PluginsResponse } from "@/lib/api/types";

// ─── Query options ───────────────────────────────────────────────────────────

export function pluginsQueryOptions(
  options?: Partial<UseQueryOptions<PluginsResponse>>,
): UseQueryOptions<PluginsResponse> {
  return {
    queryKey: apiKeys.plugins.list(),
    queryFn: () => getPlugins(),
    staleTime: 2 * 60 * 1000,
    ...options,
  };
}

// ─── Query hooks ─────────────────────────────────────────────────────────────

/**
 * GET /plugins — list loaded plugins (metadata only).
 * States: isLoading, isSuccess, isError, data, error.
 */
export function usePlugins(
  options?: Partial<UseQueryOptions<PluginsResponse>>,
) {
  return useQuery(pluginsQueryOptions(options));
}
