"use client";

import { useMutation, type UseMutationOptions } from "@tanstack/react-query";
import { analyzeScan, getReportJson, getReportPdf } from "@/lib/api/requests";
import type {
  PipelineRequest,
  PipelineResult,
  ScanReport,
} from "@/lib/api/types";

// ─── Mutation hooks ───────────────────────────────────────────────────────────

/**
 * POST /scan/analyze — run full pipeline analysis.
 * Returns PipelineResult (normalized input, detection, matched rules, text findings, scores, report).
 */
export function useAnalyzeScan(
  options?: UseMutationOptions<PipelineResult, Error, PipelineRequest>,
) {
  return useMutation({
    mutationFn: (body: PipelineRequest) => analyzeScan(body),
    ...options,
  });
}

/**
 * POST /scan/report/json — run analysis and return JSON report.
 */
export function useReportJson(
  options?: UseMutationOptions<ScanReport, Error, PipelineRequest>,
) {
  return useMutation({
    mutationFn: (body: PipelineRequest) => getReportJson(body),
    ...options,
  });
}

/**
 * POST /scan/report/pdf — run analysis and return PDF blob.
 * Use onSuccess to trigger download or open in new tab.
 */
export function useReportPdf(
  options?: UseMutationOptions<
    { blob: Blob; filename: string | null },
    Error,
    PipelineRequest
  >,
) {
  return useMutation({
    mutationFn: (body: PipelineRequest) => getReportPdf(body),
    ...options,
  });
}
