"use client";

import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { useHealth, useHealthReady } from "@/hooks/api";
import { ApiError, getApiBaseUrl } from "@/lib/api";

function LivenessCard() {
  const { data, isLoading, isError, error, refetch, isRefetching } = useHealth();

  if (isLoading) {
    return (
      <SectionCard title="Liveness" description="API server is running and accepting requests.">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-6 w-20 rounded-md" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
      </SectionCard>
    );
  }

  const isOk = !isError && data?.status === "ok";
  const errorMessage = isError && error instanceof Error ? error.message : null;

  return (
    <SectionCard
      title="Liveness"
      description="API server is running and accepting requests."
      action={
        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
          aria-label="Refresh liveness"
        >
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {isOk ? (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              OK
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300">
              <AlertCircle className="h-3.5 w-3.5" />
              {isError ? "Unavailable" : "Unknown"}
            </span>
          )}
        </div>
        {isOk && (
          <p className="text-sm text-muted-foreground">
            The API is up and responding. Liveness checks are used by orchestrators to determine
            whether to restart the process.
          </p>
        )}
        {isError && (
          <>
            {errorMessage && (
              <p className="text-sm text-destructive">{errorMessage}</p>
            )}
            <Button size="sm" variant="outline" onClick={() => refetch()} disabled={isRefetching}>
              Try again
            </Button>
          </>
        )}
      </div>
    </SectionCard>
  );
}

function ReadinessCard() {
  const { data, isLoading, isError, error, refetch, isRefetching } = useHealthReady();

  if (isLoading) {
    return (
      <SectionCard
        title="Readiness"
        description="Service is ready to handle traffic (e.g. rules loaded)."
      >
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-6 w-24 rounded-md" />
            <Skeleton className="h-4 w-56" />
          </div>
        </div>
      </SectionCard>
    );
  }

  const isReady = !isError && data?.status === "ok";
  const is503 = isError && error instanceof ApiError && error.status === 503;
  const reason =
    is503 && error instanceof ApiError && error.detail && typeof error.detail === "object" && "reason" in error.detail
      ? String((error.detail as { reason?: string }).reason)
      : null;
  const errorMessage = isError && error instanceof Error ? error.message : null;

  const reasonLabel =
    reason === "rules_file_missing"
      ? "Rules file is missing or not loaded."
      : reason
        ? reason.replace(/_/g, " ")
        : null;

  return (
    <SectionCard
      title="Readiness"
      description="Service is ready to handle traffic (e.g. rules loaded)."
      action={
        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
          aria-label="Refresh readiness"
        >
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {isReady ? (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/50 dark:text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Ready
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/50 dark:text-amber-300">
              <AlertCircle className="h-3.5 w-3.5" />
              Not ready
            </span>
          )}
        </div>
        {isReady && (
          <p className="text-sm text-muted-foreground">
            The service has loaded its configuration and is ready to run scans and evaluate rules.
          </p>
        )}
        {!isReady && reasonLabel && (
          <p className="text-sm text-muted-foreground">{reasonLabel}</p>
        )}
        {isError && !is503 && (
          <>
            {errorMessage && (
              <p className="text-sm text-destructive">{errorMessage}</p>
            )}
            <p className="text-xs text-muted-foreground">
              API base: <code className="rounded bg-muted px-1 py-0.5 font-mono">{getApiBaseUrl()}</code>
            </p>
            <Button size="sm" variant="outline" onClick={() => refetch()} disabled={isRefetching}>
              Try again
            </Button>
          </>
        )}
      </div>
    </SectionCard>
  );
}

function OperationalSummary() {
  const live = useHealth();
  const ready = useHealthReady();

  const platformAvailable = !live.isError && live.data?.status === "ok";
  const rulesReady = !ready.isError && ready.data?.status === "ok";
  const loading = live.isLoading || ready.isLoading;

  if (loading) {
    return (
      <SectionCard
        title="Operational summary"
        description="Rules file readiness and platform availability at a glance."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
      </SectionCard>
    );
  }

  const items = [
    {
      label: "Rules file readiness",
      value: rulesReady ? "Ready" : "Not ready",
      icon: rulesReady ? CheckCircle2 : AlertCircle,
      status: rulesReady ? "success" : "warning",
    },
    {
      label: "Platform availability",
      value: platformAvailable ? "Available" : "Unavailable",
      icon: platformAvailable ? CheckCircle2 : AlertCircle,
      status: platformAvailable ? "success" : "error",
    },
  ] as const;

  return (
    <SectionCard
      title="Operational summary"
      description="Rules file readiness and platform availability at a glance."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {items.map(({ label, value, icon: Icon, status }) => (
          <div
            key={label}
            className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-3"
          >
            <span
              className={
                status === "success"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : status === "warning"
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-red-600 dark:text-red-400"
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted-foreground">{label}</p>
              <p className="text-sm font-medium">{value}</p>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export default function HealthPage() {
  const live = useHealth();
  const ready = useHealthReady();

  const refetchAll = () => {
    live.refetch();
    ready.refetch();
  };

  const apiBase = getApiBaseUrl();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Health"
        description="Monitor API health, readiness, and system status for platform operations."
      >
        <Button
          size="sm"
          variant="outline"
          onClick={refetchAll}
          disabled={live.isRefetching || ready.isRefetching}
          aria-label="Refresh all health checks"
        >
          <RefreshCw
            className={`mr-1.5 h-3.5 w-3.5 ${live.isRefetching || ready.isRefetching ? "animate-spin" : ""}`}
          />
          Refresh all
        </Button>
      </PageHeader>

      <p className="text-xs text-muted-foreground">
        Backend: <code className="rounded bg-muted px-1.5 py-0.5 font-mono">{apiBase}</code>
        {" — "}
        Override with <code className="rounded bg-muted px-1 py-0.5 font-mono">NEXT_PUBLIC_API_URL</code> in .env.local or your deployment environment.
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        <LivenessCard />
        <ReadinessCard />
      </div>

      <OperationalSummary />
    </div>
  );
}
