"use client";

import { useQuery, useMutation, useQueryClient, type UseQueryOptions } from "@tanstack/react-query";
import {
  getConnectors,
  syncEntra,
  syncSlack,
} from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type {
  ConnectorsListResponse,
  EntraSyncRequest,
  SlackSyncRequest,
} from "@/lib/api/types";

// ─── Query options ───────────────────────────────────────────────────────────

export function connectorsQueryOptions(
  options?: Partial<UseQueryOptions<ConnectorsListResponse>>,
): UseQueryOptions<ConnectorsListResponse> {
  return {
    queryKey: apiKeys.connectors.list(),
    queryFn: () => getConnectors(),
    staleTime: 5 * 60 * 1000,
    ...options,
  };
}

// ─── Query hooks ─────────────────────────────────────────────────────────────

/**
 * GET /connectors — list available connectors (entra, slack).
 */
export function useConnectors(
  options?: Partial<UseQueryOptions<ConnectorsListResponse>>,
) {
  return useQuery(connectorsQueryOptions(options));
}

// ─── Mutations ───────────────────────────────────────────────────────────────

/**
 * POST /connectors/entra/sync — sync from Microsoft Entra (Azure AD).
 */
export function useEntraSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EntraSyncRequest) => syncEntra(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: apiKeys.scans.all });
    },
  });
}

/**
 * POST /connectors/slack/sync — sync from Slack.
 */
export function useSlackSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SlackSyncRequest) => syncSlack(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: apiKeys.scans.all });
    },
  });
}
