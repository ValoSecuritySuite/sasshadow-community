"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { getScansList, getScanDetail, compareScans } from "@/lib/api/requests";
import type { ListScansParams } from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type {
  ScanListResponse,
  ScanDetail,
  ScanCompareResponse,
} from "@/lib/api/types";

// ─── Query options ───────────────────────────────────────────────────────────

export function scansListQueryOptions(
  params?: ListScansParams,
  options?: Partial<UseQueryOptions<ScanListResponse>>,
): UseQueryOptions<ScanListResponse> {
  return {
    queryKey: apiKeys.scans.list(params),
    queryFn: () => getScansList(params),
    staleTime: 30 * 1000,
    ...options,
  };
}

export function scanDetailQueryOptions(
  scanId: string,
  options?: Partial<UseQueryOptions<ScanDetail>>,
): UseQueryOptions<ScanDetail> {
  return {
    queryKey: apiKeys.scans.detail(scanId),
    queryFn: () => getScanDetail(scanId),
    enabled: !!scanId,
    staleTime: 60 * 1000,
    ...options,
  };
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

/**
 * GET /scans — list persisted scans (from DB). Use for dashboard, reports, history.
 */
export function useScansList(
  params?: ListScansParams,
  options?: Partial<UseQueryOptions<ScanListResponse>>,
) {
  return useQuery(scansListQueryOptions(params, options));
}

/**
 * GET /scans/{id} — get one persisted scan by id.
 */
export function useScanDetail(
  scanId: string,
  options?: Partial<UseQueryOptions<ScanDetail>>,
) {
  return useQuery(scanDetailQueryOptions(scanId, options));
}

/**
 * GET /scans/compare?target=… — compare the last two scans for a target.
 */
export function useScanCompare(
  target: string,
  options?: Partial<UseQueryOptions<ScanCompareResponse>>,
) {
  return useQuery({
    queryKey: [...apiKeys.scans.all, "compare", target] as const,
    queryFn: () => compareScans({ target }),
    enabled: !!target,
    staleTime: 30 * 1000,
    retry: false,
    ...options,
  });
}
