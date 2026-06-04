"use client";

import * as React from "react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { QueryErrorCard } from "@/components/ui/query-error-card";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Puzzle,
  RefreshCw,
  User,
  Tag,
  Code2,
  ChevronRight,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { usePlugins } from "@/hooks/api";
import type { PluginInfo } from "@/lib/api/types";

function usePluginStats(plugins: PluginInfo[] | undefined) {
  return React.useMemo(() => {
    if (!plugins?.length) {
      return { loaded: 0, enabled: 0, uniqueHooks: 0 };
    }
    const enabled = plugins.filter((p) => p.enabled).length;
    const allHooks = new Set(plugins.flatMap((p) => p.hook_names ?? []));
    return {
      loaded: plugins.length,
      enabled,
      uniqueHooks: allHooks.size,
    };
  }, [plugins]);
}

function PluginCard({
  plugin,
  onSelect,
}: {
  plugin: PluginInfo;
  onSelect: () => void;
}) {
  const hasHooks = plugin.hook_names?.length ? plugin.hook_names.length > 0 : false;
  const hasTags = plugin.tags?.length ? plugin.tags.length > 0 : false;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className="group flex cursor-pointer flex-col rounded-xl border border-border bg-card p-5 text-left shadow-sm transition-colors hover:border-primary/30 hover:bg-card/95 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      aria-label={`View details for ${plugin.name}`}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <Puzzle className="h-5 w-5" />
        </span>
        <Badge
          variant={plugin.enabled ? "default" : "secondary"}
          className={
            plugin.enabled
              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300"
              : "border-border bg-muted text-muted-foreground"
          }
        >
          {plugin.enabled ? (
            <>
              <CheckCircle2 className="mr-1 h-3 w-3" />
              Enabled
            </>
          ) : (
            <>
              <XCircle className="mr-1 h-3 w-3" />
              Disabled
            </>
          )}
        </Badge>
      </div>

      <h3 className="mb-0.5 font-semibold tracking-tight">{plugin.name}</h3>
      <p className="mb-2 text-xs text-muted-foreground">
        v{plugin.version}
        {plugin.author ? (
          <>
            {" · "}
            <span className="inline-flex items-center gap-0.5">
              <User className="h-3 w-3" />
              {plugin.author}
            </span>
          </>
        ) : null}
      </p>

      {plugin.description ? (
        <p className="mb-3 line-clamp-2 text-sm text-muted-foreground">
          {plugin.description}
        </p>
      ) : null}

      {hasTags && (
        <div className="mb-2 flex flex-wrap gap-1">
          {(plugin.tags ?? []).slice(0, 4).map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-0.5 rounded border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
            >
              <Tag className="h-2.5 w-2.5" />
              {t}
            </span>
          ))}
          {(plugin.tags?.length ?? 0) > 4 && (
            <span className="text-[10px] text-muted-foreground">
              +{(plugin.tags?.length ?? 0) - 4}
            </span>
          )}
        </div>
      )}

      {hasHooks && (
        <div className="mt-auto flex flex-wrap items-center gap-1 border-t border-border pt-3">
          <Code2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            {(plugin.hook_names ?? []).slice(0, 3).join(", ")}
            {(plugin.hook_names?.length ?? 0) > 3 &&
              ` +${(plugin.hook_names?.length ?? 0) - 3}`}
          </span>
        </div>
      )}

      <div className="mt-2 flex justify-end">
        <span className="inline-flex items-center text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
          View details
          <ChevronRight className="ml-0.5 h-3.5 w-3.5" />
        </span>
      </div>
    </div>
  );
}

function PluginDetailDrawer({
  plugin,
  open,
  onOpenChange,
}: {
  plugin: PluginInfo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!plugin) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-muted">
              <Puzzle className="h-6 w-6 text-muted-foreground" />
            </span>
            <div className="min-w-0">
              <SheetTitle className="truncate">{plugin.name}</SheetTitle>
              <SheetDescription>
                v{plugin.version}
                {plugin.author ? ` · ${plugin.author}` : ""}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="mt-6 flex flex-1 flex-col gap-6 overflow-y-auto">
          <div>
            <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Status
            </h4>
            <Badge
              variant={plugin.enabled ? "default" : "secondary"}
              className={
                plugin.enabled
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300"
                  : ""
              }
            >
              {plugin.enabled ? "Enabled" : "Disabled"}
            </Badge>
          </div>

          {plugin.description ? (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Description
              </h4>
              <p className="text-sm text-foreground">{plugin.description}</p>
            </div>
          ) : null}

          {plugin.author ? (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Author
              </h4>
              <p className="text-sm">{plugin.author}</p>
            </div>
          ) : null}

          {plugin.tags?.length ? (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tags
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {plugin.tags.map((t) => (
                  <Badge key={t} variant="outline" className="font-normal">
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          {(plugin.hook_names?.length ?? 0) > 0 ? (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Exposed hooks ({plugin.hook_names!.length})
              </h4>
              <ul className="space-y-1.5">
                {plugin.hook_names!.map((hook) => (
                  <li
                    key={hook}
                    className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 font-mono text-sm"
                  >
                    <Code2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                    {hook}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Exposed hooks
              </h4>
              <p className="text-sm text-muted-foreground">No hooks registered.</p>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function PluginsPage() {
  const { data, isLoading, isError, error, refetch, isRefetching } = usePlugins();
  const stats = usePluginStats(data?.plugins);
  const [selectedPlugin, setSelectedPlugin] = React.useState<PluginInfo | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const openDetail = React.useCallback((plugin: PluginInfo) => {
    setSelectedPlugin(plugin);
    setDrawerOpen(true);
  }, []);

  const closeDetail = React.useCallback(() => {
    setDrawerOpen(false);
    setSelectedPlugin(null);
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plugins"
        description="Platform extensibility — loaded plugins, hooks, and metadata."
      >
        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
          aria-label="Refresh plugins"
        >
          <RefreshCw
            className={`mr-1.5 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </PageHeader>

      {isLoading && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border bg-card p-5">
                <div className="mb-3 flex items-start justify-between">
                  <Skeleton className="h-10 w-10 rounded-lg" />
                  <Skeleton className="h-6 w-16 rounded-full" />
                </div>
                <Skeleton className="mb-2 h-5 w-32" />
                <Skeleton className="mb-4 h-3 w-full" />
                <Skeleton className="h-3 w-full max-w-[75%]" />
                <div className="mt-4 border-t pt-4">
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {isError && (
        <QueryErrorCard
          title="Unable to load plugins"
          message={error instanceof Error ? error.message : "Something went wrong. Please try again."}
          onRetry={() => refetch()}
          isRetrying={isRefetching}
        />
      )}

      {!isLoading && !isError && data?.plugins && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Loaded</p>
              <p className="text-2xl font-semibold tabular-nums">{stats.loaded}</p>
            </SectionCard>
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Enabled</p>
              <p className="text-2xl font-semibold tabular-nums">{stats.enabled}</p>
            </SectionCard>
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Hook diversity</p>
              <p className="text-2xl font-semibold tabular-nums">{stats.uniqueHooks}</p>
            </SectionCard>
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Source</p>
              <p className="text-sm font-medium text-muted-foreground">GET /plugins</p>
            </SectionCard>
          </div>

          {data.plugins.length === 0 ? (
            <EmptyState
              icon={<Puzzle className="h-10 w-10" />}
              title="No plugins loaded"
              description="Plugins will appear here once the backend loads them. Check the API or add plugins to your configuration."
              action={
                <Button size="sm" variant="outline" onClick={() => refetch()}>
                  Refresh
                </Button>
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.plugins.map((plugin) => (
                <PluginCard
                  key={plugin.name}
                  plugin={plugin}
                  onSelect={() => openDetail(plugin)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <PluginDetailDrawer
        plugin={selectedPlugin}
        open={drawerOpen}
        onOpenChange={(open) => {
          setDrawerOpen(open);
          if (!open) closeDetail();
        }}
      />
    </div>
  );
}
