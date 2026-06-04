"use client";

import { useMutation, type UseMutationOptions } from "@tanstack/react-query";
import { analyzeDataset } from "@/lib/api/requests";
import type {
  DatasetAnalysisRequest,
  DatasetAnalysisResponse,
} from "@/lib/api/types";

// ─── Mutation hooks ───────────────────────────────────────────────────────────

/**
 * POST /scan/dataset — batch dataset analysis.
 * Returns summary and per-integration results (risk score, flags, report).
 */
export function useAnalyzeDataset(
  options?: UseMutationOptions<
    DatasetAnalysisResponse,
    Error,
    DatasetAnalysisRequest
  >,
) {
  return useMutation({
    mutationFn: (body: DatasetAnalysisRequest) => analyzeDataset(body),
    ...options,
  });
}
