"use client";

import * as React from "react";
import Link from "next/link";
import {
  ShieldAlert,
  Activity,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { StatCard } from "@/components/ui/stat-card";
import { ScoreBadge } from "@/components/ui/score-badge";
import { RiskLevelBadge } from "@/components/ui/risk-level-badge";
import {
  useDashboardOverview,
  useDashboardRiskTrend,
  useDashboardRiskDistribution,
  useDashboardCritical,
} from "@/hooks/api/use-dashboard";
import { useScansList } from "@/hooks/api/use-scans";
import { formatTimestamp } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/api/types";

type Window = "24h" | "7d" | "30d" | "90d";

const WINDOWS: Window[] = ["24h", "7d", "30d", "90d"];

const RISK_LEVEL_ORDER: RiskLevel[] = [
  "CRITICAL",
  "HIGH",
  "MEDIUM",
  "LOW",
  "MINIMAL",
];

function TrendLineChart({
  points,
}: {
  points: { bucket_start: string; avg_risk_score: number }[];
}) {
  if (points.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
        Not enough data to draw a trend.
      </p>
    );
  }
  const width = 600;
  const height = 160;
  const padding = 16;
  const max = Math.max(1, ...points.map((p) => p.avg_risk_score));
  const min = 0;
  const xStep = (width - padding * 2) / Math.max(1, points.length - 1);
  const yScale = (value: number) => {
    if (max === min) return height / 2;
    return (
      height -
      padding -
      ((value - min) / (max - min)) * (height - padding * 2)
    );
  };
  const path = points
    .map((p, i) => {
      const x = padding + i * xStep;
      const y = yScale(p.avg_risk_score);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-40 w-full"
      role="img"
      aria-label="Risk trend over time"
    >
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        className="text-primary"
      />
      {points.map((p, i) => (
        <circle
          key={p.bucket_start + i}
          cx={padding + i * xStep}
          cy={yScale(p.avg_risk_score)}
          r={2}
          className="fill-primary"
        />
      ))}
    </svg>
  );
}

export default function DashboardPage() {
  const [windowKey, setWindowKey] = React.useState<Window>("7d");
  const overview = useDashboardOverview(windowKey);
  const trend = useDashboardRiskTrend(windowKey);
  const distribution = useDashboardRiskDistribution();
  const critical = useDashboardCritical(10);
  const recentScans = useScansList({ limit: 10 });

  const o = overview.data;
  const dist = distribution.data;
  const maxDist = Math.max(1, ...(dist?.entries.map((e) => e.count) ?? []));

  const delta = o?.risk_delta_vs_prior_window ?? 0;
  const deltaIcon =
    delta > 0.5 ? (
      <TrendingUp className="h-4 w-4 text-destructive" />
    ) : delta < -0.5 ? (
      <TrendingDown className="h-4 w-4 text-emerald-500" />
    ) : (
      <span className="text-xs text-muted-foreground">~</span>
    );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Portfolio risk overview across stored scans."
      >
        <div className="inline-flex overflow-hidden rounded-lg border border-border">
          {WINDOWS.map((win) => (
            <button
              key={win}
              type="button"
              onClick={() => setWindowKey(win)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium transition-colors",
                windowKey === win
                  ? "bg-primary text-primary-foreground"
                  : "bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              {win}
            </button>
          ))}
        </div>
      </PageHeader>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Average risk score"
          value={
            overview.isLoading ? (
              <span className="text-muted-foreground">…</span>
            ) : (
              <ScoreBadge value={o?.avg_risk_score ?? 0} kind="risk" />
            )
          }
          subtitle={
            o ? (
              <span className="inline-flex items-center gap-1">
                {deltaIcon}
                {delta.toFixed(1)} vs prior {windowKey}
              </span>
            ) : undefined
          }
          padding="compact"
        />
        <StatCard
          label="Critical integrations"
          value={
            overview.isLoading ? (
              <span className="text-muted-foreground">…</span>
            ) : (
              <span className="tabular-nums">{o?.critical_integrations ?? 0}</span>
            )
          }
          subtitle={`${o?.integrations_in_window ?? 0} scanned in window`}
          icon={<ShieldAlert className="h-4 w-4" />}
          padding="compact"
        />
        <StatCard
          label="Scans in window"
          value={
            overview.isLoading ? (
              <span className="text-muted-foreground">…</span>
            ) : (
              <span className="tabular-nums">{o?.scans_in_window ?? 0}</span>
            )
          }
          subtitle={`${o?.scans_total ?? 0} total stored`}
          icon={<Activity className="h-4 w-4" />}
          padding="compact"
        />
        <StatCard
          label="Portfolio risk"
          value={
            overview.isLoading ? (
              <span className="text-muted-foreground">…</span>
            ) : o?.portfolio_risk_level ? (
              <RiskLevelBadge value={o.portfolio_risk_level.toLowerCase()} />
            ) : (
              <span className="text-muted-foreground">-</span>
            )
          }
          subtitle={`Median ${o?.median_risk_score?.toFixed(1) ?? "0"}`}
          padding="compact"
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard
          title="Risk trend"
          description={`Avg risk score by day across the ${windowKey} window.`}
          className="lg:col-span-2"
        >
          {trend.isLoading ? (
            <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              Loading trend…
            </p>
          ) : (
            <TrendLineChart points={trend.data?.points ?? []} />
          )}
        </SectionCard>

        <SectionCard
          title="Risk distribution"
          description="Integrations per risk level (latest scan)."
        >
          {dist == null || dist.total_integrations === 0 ? (
            <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              No stored scans yet.
            </p>
          ) : (
            <div className="space-y-3">
              {RISK_LEVEL_ORDER.map((level) => {
                const entry = dist.entries.find((e) => e.risk_level === level);
                const count = entry?.count ?? 0;
                const pct = maxDist > 0 ? (count / maxDist) * 100 : 0;
                return (
                  <div key={level} className="flex items-center gap-3">
                    <span className="w-20 shrink-0 text-xs font-medium text-muted-foreground">
                      {level}
                    </span>
                    <div className="flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-2 rounded-full transition-all",
                          level === "CRITICAL" && "bg-red-500",
                          level === "HIGH" && "bg-orange-500",
                          level === "MEDIUM" && "bg-amber-500",
                          level === "LOW" && "bg-blue-500",
                          level === "MINIMAL" && "bg-emerald-500",
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-8 shrink-0 text-right text-sm tabular-nums">
                      {count}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard
          title="Recent scans"
          description="Most recently stored scans."
          action={
            <Link
              href="/scans"
              className="text-sm font-medium text-primary hover:underline"
            >
              View all
            </Link>
          }
        >
          {recentScans.isLoading ? (
            <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              Loading scans…
            </p>
          ) : (recentScans.data?.scans.length ?? 0) === 0 ? (
            <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              No stored scans yet.
            </p>
          ) : (
            <div className="space-y-2">
              {recentScans.data?.scans.map((s) => (
                <Link
                  key={s.id}
                  href={`/scans?target=${encodeURIComponent(s.target)}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/10 p-3 transition-colors hover:bg-muted/30"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-sm">{s.target}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatTimestamp(s.timestamp, {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <RiskLevelBadge value={s.risk_level.toLowerCase()} />
                    <ScoreBadge value={s.score} kind="risk" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Critical findings"
          description="Most recent CRITICAL or HIGH findings."
        >
          {critical.data == null || critical.data.findings.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              No critical findings in scope.
            </p>
          ) : (
            <div className="space-y-2">
              {critical.data.findings.map((f, i) => (
                <div
                  key={`${f.scan_id}-${f.rule_id ?? "norule"}-${i}`}
                  className="rounded-lg border border-border bg-muted/10 p-3 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs">{f.target}</p>
                      <p className="mt-1 line-clamp-2 text-sm">{f.summary}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-destructive">
                        Sev {f.severity}
                      </span>
                      <ScoreBadge value={f.risk_score} kind="risk" />
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatTimestamp(f.created_at, {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                    {f.rule_id ? ` · ${f.rule_id}` : null}
                  </p>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
