"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { getEditionMeta } from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type { EditionMeta } from "@/lib/api/types";

export function editionQueryOptions(
  options?: Partial<UseQueryOptions<EditionMeta>>,
): UseQueryOptions<EditionMeta> {
  return {
    queryKey: apiKeys.meta.edition(),
    queryFn: () => getEditionMeta(),
    staleTime: 60 * 1000,
    enabled: typeof window !== "undefined",
    ...options,
  };
}

export function useEdition(
  options?: Partial<UseQueryOptions<EditionMeta>>,
) {
  return useQuery(editionQueryOptions(options));
}

export function isCommunityEdition(meta: EditionMeta | undefined): boolean {
  if (!meta?.edition) return true;
  return meta.edition.toLowerCase() === "community";
}
