"use client";

import {
  useQuery,
  useMutation,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { getRules, getScanRules, evaluateRules } from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type {
  RuleSetResponse,
  RuleEngineResult,
  RuleEvalRequest,
} from "@/lib/api/types";

// ─── Query options ───────────────────────────────────────────────────────────

export function rulesQueryOptions(
  options?: Partial<UseQueryOptions<RuleSetResponse>>,
): UseQueryOptions<RuleSetResponse> {
  return {
    queryKey: apiKeys.rules.list(),
    queryFn: () => getRules(),
    staleTime: 2 * 60 * 1000,
    ...options,
  };
}

export function scanRulesQueryOptions(
  options?: Partial<UseQueryOptions<RuleSetResponse>>,
): UseQueryOptions<RuleSetResponse> {
  return {
    queryKey: apiKeys.rules.scanRules(),
    queryFn: () => getScanRules(),
    staleTime: 2 * 60 * 1000,
    ...options,
  };
}

// ─── Query hooks ─────────────────────────────────────────────────────────────

/**
 * GET /rules — fetch rule set (context + text-scan rules).
 * States: isLoading, isSuccess, isError, data, error.
 */
export function useRules(
  options?: Partial<UseQueryOptions<RuleSetResponse>>,
) {
  return useQuery(rulesQueryOptions(options));
}

/**
 * GET /scan/rules — rules for scan context (when backend implements it).
 * Use enabled: true only when needed; endpoint may 404.
 */
export function useScanRules(
  options?: Partial<UseQueryOptions<RuleSetResponse>>,
) {
  return useQuery(scanRulesQueryOptions(options));
}

// ─── Mutation hooks ───────────────────────────────────────────────────────────

/**
 * POST /rules/evaluate — evaluate context against rules.
 * Does not invalidate rules list (evaluation does not change server state).
 */
export function useEvaluateRules(
  options?: UseMutationOptions<RuleEngineResult, Error, RuleEvalRequest>,
) {
  return useMutation({
    mutationFn: (body: RuleEvalRequest) => evaluateRules(body),
    ...options,
  });
}
