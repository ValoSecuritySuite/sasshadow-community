"use client";

import * as React from "react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { QueryErrorCard } from "@/components/ui/query-error-card";
import { ScoreBadge } from "@/components/ui/score-badge";
import { RiskLevelBadge } from "@/components/ui/risk-level-badge";
import { StatCard } from "@/components/ui/stat-card";
import { useScansList, useScanCompare } from "@/hooks/api/use-scans";
import { formatTimestamp } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  History,
  RefreshCw,
  GitCompareArrows,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import type { KeyFindingSummary } from "@/lib/api/types";

function FindingList({
  title,
  findings,
  tone,
}: {
  title: string;
  findings: KeyFindingSummary[];
  tone: "new" | "mitigated";
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">
        {title} ({findings.length})
      </p>
      {findings.length === 0 ? (
        <p className="text-xs text-muted-foreground">None.</p>
      ) : (
        <ul className="space-y-1">
          {findings.slice(0, 8).map((f, i) => (
            <li
              key={`${f.rule_id}-${i}`}
              className={cn(
                "flex items-center justify-between gap-2 rounded border px-2 py-1.5 text-xs",
                tone === "new"
                  ? "border-destructive/30 bg-destructive/5"
                  : "border-emerald-500/30 bg-emerald-500/5",
              )}
            >
              <span className="truncate font-mono">{f.rule_id}</span>
              <span className="shrink-0 text-muted-foreground">{f.category}</span>
            </li>
          ))}
          {findings.length > 8 && (
            <li className="text-xs text-muted-foreground">
              … and {findings.length - 8} more
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function CompareControl() {
  const [target, setTarget] = React.useState("");
  const [submitted, setSubmitted] = React.useState("");
  const compare = useScanCompare(submitted);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(target.trim());
  };

  const data = compare.data;
  const delta = data?.score_delta ?? 0;

  return (
    <SectionCard
      title="Compare scans"
      description="Compare the last two scans for a target: score delta and finding diff."
    >
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="min-w-[240px] flex-1 space-y-2">
          <label htmlFor="compare-target" className="text-sm font-medium">
            Target
          </label>
          <input
            id="compare-target"
            type="text"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="e.g. acme-slack-integration"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <Button type="submit" disabled={!target.trim() || compare.isFetching}>
          <GitCompareArrows
            className={cn("mr-1.5 h-3.5 w-3.5", compare.isFetching && "animate-spin")}
          />
          Compare
        </Button>
      </form>

      {compare.isError && submitted && (
        <div className="mt-4">
          <QueryErrorCard
            title="Comparison unavailable"
            message={
              compare.error instanceof Error
                ? compare.error.message
                : "Need at least two scans for this target."
            }
          />
        </div>
      )}

      {data && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              label="Score before"
              value={<ScoreBadge value={data.score_before} kind="risk" />}
              subtitle={formatTimestamp(data.timestamp_before, {
                dateStyle: "short",
                timeStyle: "short",
              })}
              padding="compact"
            />
            <StatCard
              label="Score after"
              value={<ScoreBadge value={data.score_after} kind="risk" />}
              subtitle={formatTimestamp(data.timestamp_after, {
                dateStyle: "short",
                timeStyle: "short",
              })}
              padding="compact"
            />
            <StatCard
              label="Delta"
              value={
                <span className="inline-flex items-center gap-1.5">
                  {delta > 0 ? (
                    <TrendingUp className="h-4 w-4 text-destructive" />
                  ) : delta < 0 ? (
                    <TrendingDown className="h-4 w-4 text-emerald-500" />
                  ) : null}
                  <span className="tabular-nums">{delta.toFixed(1)}</span>
                </span>
              }
              subtitle={`${data.risk_level_before} → ${data.risk_level_after}`}
              padding="compact"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FindingList
              title="New findings"
              findings={data.new_findings}
              tone="new"
            />
            <FindingList
              title="Mitigated findings"
              findings={data.mitigated_findings}
              tone="mitigated"
            />
          </div>
        </div>
      )}
    </SectionCard>
  );
}

export default function ScansPage() {
  const [filter, setFilter] = React.useState("");
  const { data, isLoading, isError, error, refetch, isRefetching } = useScansList({
    target: filter.trim() || undefined,
    limit: 50,
  });
  const scans = data?.scans ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scan History"
        description="Browse persisted scans and compare results for a target over time."
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", isRefetching && "animate-spin")} />
          Refresh
        </Button>
      </PageHeader>

      <CompareControl />

      <SectionCard
        title="Scans"
        description="Most recent persisted scans across all targets."
        action={
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by target…"
            className="w-56 rounded-md border border-input bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        }
      >
        {isError && (
          <QueryErrorCard
            title="Failed to load scans"
            message={error instanceof Error ? error.message : String(error)}
            onRetry={() => refetch()}
            isRetrying={isRefetching}
          />
        )}

        {!isError && isLoading && (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}

        {!isError && !isLoading && scans.length === 0 && (
          <EmptyState
            icon={<History className="h-10 w-10" />}
            title="No scans found"
            description="Run a scan or sync a connector to populate scan history."
            compact
          />
        )}

        {!isError && !isLoading && scans.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-3">Target</th>
                  <th className="py-2 pr-3">Timestamp</th>
                  <th className="py-2 pr-3">Risk level</th>
                  <th className="py-2 pr-3">Score</th>
                  <th className="py-2 pr-3 text-right">Findings</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.id} className="border-b border-border/60">
                    <td className="py-2 pr-3">
                      <button
                        type="button"
                        onClick={() => setFilter(s.target)}
                        className="truncate font-mono text-xs text-primary hover:underline"
                      >
                        {s.target}
                      </button>
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">
                      {formatTimestamp(s.timestamp, {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </td>
                    <td className="py-2 pr-3">
                      <RiskLevelBadge value={s.risk_level.toLowerCase()} />
                    </td>
                    <td className="py-2 pr-3">
                      <ScoreBadge value={s.score} kind="risk" />
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {s.findings_count ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
