"use client";

import * as React from "react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { QueryErrorCard } from "@/components/ui/query-error-card";
import { StatCard } from "@/components/ui/stat-card";
import { useIspmCategories, useIspmProviders } from "@/hooks/api";
import { ShieldCheck, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

export default function IspmPage() {
  const categories = useIspmCategories();
  const providers = useIspmProviders();

  const config = categories.data?.config;
  const categoryList = React.useMemo(
    () => config?.categories ?? [],
    [config],
  );
  const providerList = providers.data?.providers ?? [];

  const categoryLabel = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const c of categoryList) map.set(c.id, c.label);
    return map;
  }, [categoryList]);

  const isLoading = categories.isLoading || providers.isLoading;
  const isRefetching = categories.isRefetching || providers.isRefetching;

  return (
    <div className="space-y-6">
      <PageHeader
        title="ISPM Catalog"
        description="Integration Security Posture Management catalog: category definitions and the provider-to-category mapping."
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            void categories.refetch();
            void providers.refetch();
          }}
          disabled={isRefetching}
        >
          <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", isRefetching && "animate-spin")} />
          Refresh
        </Button>
      </PageHeader>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Categories"
          value={
            categories.isLoading ? (
              <Skeleton className="h-6 w-12" />
            ) : (
              categoryList.length
            )
          }
          padding="compact"
        />
        <StatCard
          label="Providers mapped"
          value={
            providers.isLoading ? (
              <Skeleton className="h-6 w-12" />
            ) : (
              providerList.length
            )
          }
          padding="compact"
        />
        <StatCard
          label="Default category"
          value={
            categories.isLoading ? (
              <Skeleton className="h-6 w-24" />
            ) : (
              <span className="text-base">
                {config
                  ? categoryLabel.get(config.default_category_id) ??
                    config.default_category_id
                  : "-"}
              </span>
            )
          }
          padding="compact"
        />
      </section>

      {(categories.isError || providers.isError) && (
        <QueryErrorCard
          title="Failed to load ISPM catalog"
          message={
            categories.error instanceof Error
              ? categories.error.message
              : providers.error instanceof Error
                ? providers.error.message
                : "Unknown error"
          }
          onRetry={() => {
            void categories.refetch();
            void providers.refetch();
          }}
          isRetrying={isRefetching}
        />
      )}

      <SectionCard
        title="Category catalog"
        description="Defined ISPM categories and their posture thresholds."
      >
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-28 w-full rounded-lg" />
            ))}
          </div>
        ) : categoryList.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {categoryList.map((cat) => (
              <div
                key={cat.id}
                className="rounded-lg border border-border bg-card p-4"
              >
                <p className="font-medium text-sm">{cat.label}</p>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                  {cat.id}
                </p>
                {cat.description ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {cat.description}
                  </p>
                ) : null}
                <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
                  <span>Compliant &lt; {cat.posture_thresholds.compliant}</span>
                  <span>At risk &lt; {cat.posture_thresholds.at_risk}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<ShieldCheck className="h-10 w-10" />}
            title="No categories defined"
            description="The ISPM configuration has no categories yet."
            compact
          />
        )}
      </SectionCard>

      <SectionCard
        title="Provider mapping"
        description="How known providers map to ISPM categories."
      >
        {isLoading ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : providerList.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-3">Provider</th>
                  <th className="py-2 pr-3">Provider ID</th>
                  <th className="py-2 pr-3">Category</th>
                </tr>
              </thead>
              <tbody>
                {providerList.map((p) => (
                  <tr key={p.provider_id} className="border-b border-border/60">
                    <td className="py-2 pr-3">{p.label || p.provider_id}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{p.provider_id}</td>
                    <td className="py-2 pr-3">
                      {categoryLabel.get(p.category_id) ?? p.category_id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No providers mapped yet.
          </p>
        )}
      </SectionCard>
    </div>
  );
}
