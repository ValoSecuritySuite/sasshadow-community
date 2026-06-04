"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { getIspmCategories, getIspmProviders } from "@/lib/api/requests";
import { apiKeys } from "./query-keys";
import type {
  IspmCategoriesResponse,
  IspmProvidersResponse,
} from "@/lib/api/types";

export function useIspmCategories(
  options?: Partial<UseQueryOptions<IspmCategoriesResponse>>,
) {
  return useQuery({
    queryKey: apiKeys.ispm.categories(),
    queryFn: () => getIspmCategories(),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function useIspmProviders(
  options?: Partial<UseQueryOptions<IspmProvidersResponse>>,
) {
  return useQuery({
    queryKey: apiKeys.ispm.providers(),
    queryFn: () => getIspmProviders(),
    staleTime: 60 * 1000,
    ...options,
  });
}
