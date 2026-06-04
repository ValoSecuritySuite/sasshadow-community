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
  BookOpen,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronRight,
  Filter,
  FileCode,
  ListChecks,
} from "lucide-react";
import { useRules } from "@/hooks/api";
import type { Rule, TextScanRule, Pattern, RuleSetResponse } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const SEVERITY_LABELS: Record<number, string> = {
  1: "1 – Low",
  2: "2",
  3: "3 – Medium",
  4: "4",
  5: "5 – Critical",
};

function severityColor(severity: number): string {
  if (severity >= 5) return "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300";
  if (severity >= 4) return "bg-orange-100 text-orange-800 dark:bg-orange-950/60 dark:text-orange-300";
  if (severity >= 3) return "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300";
  if (severity >= 2) return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300";
  return "bg-muted text-muted-foreground";
}

function useRulesStats(data: RuleSetResponse | undefined) {
  return React.useMemo(() => {
    if (!data) return { context: 0, textScan: 0, total: 0, bySeverity: {} as Record<number, number> };
    const context = data.rules?.length ?? 0;
    const textScan = data.text_scan_rules?.length ?? 0;
    const bySeverity: Record<number, number> = {};
    const add = (s: number) => {
      bySeverity[s] = (bySeverity[s] ?? 0) + 1;
    };
    data.rules?.forEach((r) => add(r.severity));
    data.text_scan_rules?.forEach((r) => add(r.severity));
    return {
      context,
      textScan,
      total: (data.rules_info?.total_rule_count ?? context + textScan),
      bySeverity,
    };
  }, [data]);
}

function useFilteredContextRules(
  rules: Rule[] | undefined,
  search: string,
  enabledFilter: "all" | "enabled" | "disabled",
) {
  return React.useMemo(() => {
    if (!rules?.length) return [];
    let out = rules;
    const q = search.trim().toLowerCase();
    if (q) {
      out = out.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          String(r.severity).includes(q) ||
          String(r.weight).includes(q),
      );
    }
    if (enabledFilter === "enabled") out = out.filter((r) => r.enabled);
    if (enabledFilter === "disabled") out = out.filter((r) => !r.enabled);
    return out;
  }, [rules, search, enabledFilter]);
}

function useFilteredTextScanRules(
  rules: TextScanRule[] | undefined,
  search: string,
  enabledFilter: "all" | "enabled" | "disabled",
  categoryFilter: string,
) {
  return React.useMemo(() => {
    if (!rules?.length) return [];
    let out = rules;
    const q = search.trim().toLowerCase();
    if (q) {
      out = out.filter(
        (r) =>
          r.id.toLowerCase().includes(q) ||
          (r.description ?? "").toLowerCase().includes(q) ||
          (r.pattern ?? "").toLowerCase().includes(q) ||
          r.category.toLowerCase().includes(q) ||
          String(r.severity).includes(q) ||
          String(r.weight).includes(q),
      );
    }
    if (enabledFilter === "enabled") out = out.filter((r) => r.enabled);
    if (enabledFilter === "disabled") out = out.filter((r) => !r.enabled);
    if (categoryFilter) {
      out = out.filter((r) => r.category.toLowerCase() === categoryFilter.toLowerCase());
    }
    return out;
  }, [rules, search, enabledFilter, categoryFilter]);
}

function PatternSummary({ patterns }: { patterns: Pattern[] }) {
  if (!patterns?.length) return <span className="text-muted-foreground">No patterns</span>;
  const first = patterns[0];
  const rest = patterns.length - 1;
  return (
    <span className="font-mono text-xs">
      {first.field} {first.op} {first.value != null ? JSON.stringify(first.value) : "—"}
      {rest > 0 && ` (+${rest})`}
    </span>
  );
}

function ContextRuleRow({
  rule,
  expanded,
  onToggle,
}: {
  rule: Rule;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-inset"
        aria-expanded={expanded}
      >
        <span className="text-muted-foreground">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>
        <span className="min-w-0 flex-1 truncate font-medium">{rule.name}</span>
        <span className={cn("rounded px-2 py-0.5 text-xs font-medium", severityColor(rule.severity))}>
          {SEVERITY_LABELS[rule.severity] ?? rule.severity}
        </span>
        <span className="tabular-nums text-muted-foreground">{rule.weight}</span>
        <Badge variant={rule.enabled ? "default" : "secondary"} className="shrink-0">
          {rule.enabled ? "Enabled" : "Disabled"}
        </Badge>
        <span className="shrink-0 text-xs text-muted-foreground">Context</span>
        <span className="min-w-[140px] truncate text-right text-xs text-muted-foreground">
          <PatternSummary patterns={rule.patterns} />
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border bg-muted/20 px-4 py-3 pl-11">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Matching logic — {rule.patterns.length} pattern(s)
          </h4>
          <ul className="space-y-2">
            {rule.patterns.map((p, i) => (
              <li key={i} className="rounded border border-border bg-background px-3 py-2 font-mono text-sm">
                <span className="text-foreground">{p.field}</span>
                <span className="mx-2 text-muted-foreground">{p.op}</span>
                {p.value !== undefined && p.value !== null ? (
                  <span className="text-foreground">{JSON.stringify(p.value)}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TextScanRuleRow({
  rule,
  expanded,
  onToggle,
}: {
  rule: TextScanRule;
  expanded: boolean;
  onToggle: () => void;
}) {
  const patternPreview = rule.pattern
    ? rule.pattern.length > 48
      ? `${rule.pattern.slice(0, 48)}…`
      : rule.pattern
    : "—";

  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-inset"
        aria-expanded={expanded}
      >
        <span className="text-muted-foreground">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>
        <span className="min-w-0 flex-1 truncate font-mono text-sm">{rule.id}</span>
        <span className={cn("rounded px-2 py-0.5 text-xs font-medium", severityColor(rule.severity))}>
          {SEVERITY_LABELS[rule.severity] ?? rule.severity}
        </span>
        <span className="tabular-nums text-muted-foreground">{rule.weight}</span>
        <Badge variant={rule.enabled ? "default" : "secondary"} className="shrink-0">
          {rule.enabled ? "Enabled" : "Disabled"}
        </Badge>
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs">{rule.category}</span>
        <span className="min-w-[120px] truncate text-right font-mono text-xs text-muted-foreground">
          {patternPreview}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border bg-muted/20 px-4 py-3 pl-11">
          {rule.description && (
            <>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Description
              </h4>
              <p className="mb-3 text-sm text-foreground">{rule.description}</p>
            </>
          )}
          <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Pattern
          </h4>
          <pre className="overflow-x-auto rounded border border-border bg-background p-3 font-mono text-xs">
            {rule.pattern || "(empty)"}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function RulesPage() {
  const { data, isLoading, isError, error, refetch, isRefetching } = useRules();
  const stats = useRulesStats(data);
  const [tab, setTab] = React.useState<"context" | "text">("context");
  const [search, setSearch] = React.useState("");
  const [enabledFilter, setEnabledFilter] = React.useState<"all" | "enabled" | "disabled">("all");
  const [categoryFilter, setCategoryFilter] = React.useState("");
  const [expandedContext, setExpandedContext] = React.useState<string | null>(null);
  const [expandedText, setExpandedText] = React.useState<string | null>(null);

  const filteredContext = useFilteredContextRules(data?.rules, search, enabledFilter);
  const filteredText = useFilteredTextScanRules(
    data?.text_scan_rules,
    search,
    enabledFilter,
    categoryFilter,
  );

  const categories = React.useMemo(() => {
    const set = new Set<string>();
    data?.text_scan_rules?.forEach((r) => set.add(r.category));
    return Array.from(set).sort();
  }, [data?.text_scan_rules]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rules"
        description="Inspect detection rules and security policies for integration analysis and compliance review."
      >
        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
          aria-label="Refresh rules"
        >
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </PageHeader>

      {isLoading && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-10 w-48 rounded-lg" />
          <Skeleton className="h-[400px] w-full rounded-xl" />
        </>
      )}

      {isError && (
        <QueryErrorCard
          title="Unable to load rules"
          message={error instanceof Error ? error.message : "Something went wrong. Please try again."}
          onRetry={() => refetch()}
          isRetrying={isRefetching}
        />
      )}

      {!isLoading && !isError && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Total rules</p>
              <p className="text-2xl font-semibold tabular-nums">{stats.total}</p>
            </SectionCard>
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Context rules</p>
              <p className="text-2xl font-semibold tabular-nums">{stats.context}</p>
            </SectionCard>
            <SectionCard padding="compact" className="border-border bg-muted/20">
              <p className="text-xs font-medium text-muted-foreground">Text-scan rules</p>
              <p className="text-2xl font-semibold tabular-nums">{stats.textScan}</p>
            </SectionCard>
            <SectionCard padding="compact" className="border-border bg-muted/20 lg:col-span-2">
              <p className="mb-2 text-xs font-medium text-muted-foreground">Severity distribution</p>
              <div className="flex flex-wrap gap-2">
                {[1, 2, 3, 4, 5].map((s) => (
                  <span
                    key={s}
                    className={cn(
                      "rounded px-2 py-0.5 text-xs font-medium tabular-nums",
                      severityColor(s),
                    )}
                  >
                    {SEVERITY_LABELS[s] ?? s}: {stats.bySeverity[s] ?? 0}
                  </span>
                ))}
              </div>
            </SectionCard>
          </div>

          {stats.total === 0 ? (
            <EmptyState
              icon={<BookOpen className="h-10 w-10" />}
              title="No rules loaded"
              description="Rules will appear here once the backend loads them. Check the rules file path and API health."
              action={
                <Button size="sm" variant="outline" onClick={() => refetch()}>
                  Refresh
                </Button>
              }
            />
          ) : (
          <>
          <SectionCard padding="none">
            <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
                <div className="relative flex-1 sm:max-w-xs">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="search"
                    placeholder="Search rules..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    aria-label="Search rules"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <select
                    value={enabledFilter}
                    onChange={(e) =>
                      setEnabledFilter(e.target.value as "all" | "enabled" | "disabled")
                    }
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    aria-label="Filter by enabled state"
                  >
                    <option value="all">All</option>
                    <option value="enabled">Enabled only</option>
                    <option value="disabled">Disabled only</option>
                  </select>
                  {tab === "text" && categories.length > 0 && (
                    <select
                      value={categoryFilter}
                      onChange={(e) => setCategoryFilter(e.target.value)}
                      className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      aria-label="Filter by category"
                    >
                      <option value="">All categories</option>
                      {categories.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
              <div className="flex rounded-lg border border-border p-0.5">
                <button
                  type="button"
                  onClick={() => setTab("context")}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    tab === "context"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <ListChecks className="h-4 w-4" />
                  Context rules
                </button>
                <button
                  type="button"
                  onClick={() => setTab("text")}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    tab === "text"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <FileCode className="h-4 w-4" />
                  Text-scan rules
                </button>
              </div>
            </div>

            <div className="border-t border-border">
              <div className="grid grid-cols-[auto_1fr_auto_auto_auto_auto_1fr] gap-3 px-4 py-2 text-xs font-medium text-muted-foreground">
                <span className="w-6" />
                <span>{tab === "context" ? "Name" : "ID"}</span>
                <span>Severity</span>
                <span>Weight</span>
                <span>State</span>
                <span>Type</span>
                <span className="text-right">
                  {tab === "context" ? "Matching logic" : "Pattern preview"}
                </span>
              </div>

              {tab === "context" && (
                <>
                  {filteredContext.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No context rules match the current filters.
                    </div>
                  ) : (
                    filteredContext.map((rule) => (
                      <ContextRuleRow
                        key={rule.name}
                        rule={rule}
                        expanded={expandedContext === rule.name}
                        onToggle={() =>
                          setExpandedContext((id) => (id === rule.name ? null : rule.name))
                        }
                      />
                    ))
                  )}
                </>
              )}

              {tab === "text" && (
                <>
                  {filteredText.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No text-scan rules match the current filters.
                    </div>
                  ) : (
                    filteredText.map((rule) => (
                      <TextScanRuleRow
                        key={rule.id}
                        rule={rule}
                        expanded={expandedText === rule.id}
                        onToggle={() =>
                          setExpandedText((id) => (id === rule.id ? null : rule.id))
                        }
                      />
                    ))
                  )}
                </>
              )}
            </div>
          </SectionCard>

          {data.rules_info && (
            <p className="text-xs text-muted-foreground">
              Source: {data.rules_info.filename}
              {data.rules_info.filepath ? ` · ${data.rules_info.filepath}` : ""}
            </p>
          )}
          </>
          )}
        </>
      )}
    </div>
  );
}
