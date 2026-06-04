"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  healthQueryOptions,
  healthReadyQueryOptions,
} from "@/hooks/api/use-health";
import { rulesQueryOptions } from "@/hooks/api/use-rules";
import { pluginsQueryOptions } from "@/hooks/api/use-plugins";
import { scansListQueryOptions } from "@/hooks/api/use-scans";

/**
 * Prefetches critical API data on app load so dashboard, rules, plugins, health,
 * and scan history can render from cache immediately.
 * Renders nothing.
 */
export function PrefetchOnStartup() {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (typeof window === "undefined") return;

    void queryClient.prefetchQuery(healthQueryOptions());
    void queryClient.prefetchQuery(healthReadyQueryOptions());
    void queryClient.prefetchQuery(rulesQueryOptions());
    void queryClient.prefetchQuery(pluginsQueryOptions());
    void queryClient.prefetchQuery(scansListQueryOptions({ limit: 20 }));
  }, [queryClient]);

  return null;
}
