"use client";

import * as React from "react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import {
  Plus,
  Trash2,
  FileJson,
  ListChecks,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Play,
  Shield,
  Key,
  Lock,
  ArrowRightLeft,
  ExternalLink,
} from "lucide-react";
import { useAnalyzeDataset } from "@/hooks/api";
import { useLastActivity } from "@/contexts/last-activity-context";
import { useToast } from "@/contexts/toast-context";
import type {
  DatasetAnalysisRequest,
  DatasetItemRequest,
  DatasetAnalysisResponse,
  DatasetItemResult,
} from "@/lib/api/types";
import { StatCard } from "@/components/ui/stat-card";
import { ScoreBadge } from "@/components/ui/score-badge";
import { RiskLevelBadge } from "@/components/ui/risk-level-badge";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { cn } from "@/lib/utils";
import Link from "next/link";

function severityLevelFromNumber(n: number): string {
  if (n >= 4) return "critical";
  if (n >= 3) return "high";
  if (n >= 2) return "medium";
  if (n >= 1) return "low";
  return "info";
}

const SAMPLE_ITEMS_JSON = `[
  { "integration_id": "sample-app-1", "json_data": { "integration": "app-1", "scopes": ["read"] } },
  { "integration_id": "sample-app-2", "json_data": { "integration": "app-2", "config": {} } }
]`;

function parseJsonSafe<T>(value: string): T | null {
  const t = value.trim();
  if (!t) return null;
  try {
    return JSON.parse(t) as T;
  } catch {
    return null;
  }
}

function buildDatasetRequest(
  datasetName: string,
  items: { integration_id: string; json_data: string; metadata: string }[],
): { request: DatasetAnalysisRequest; error: string | null } {
  const nameTrim = datasetName.trim();
  if (!nameTrim) {
    return { request: null as unknown as DatasetAnalysisRequest, error: "Dataset name is required." };
  }
  if (items.length === 0) {
    return { request: null as unknown as DatasetAnalysisRequest, error: "Add at least one item." };
  }

  const built: DatasetItemRequest[] = [];
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const idTrim = item.integration_id.trim();
    if (!idTrim) {
      return {
        request: null as unknown as DatasetAnalysisRequest,
        error: `Item ${i + 1}: integration_id is required.`,
      };
    }
    const jsonData = parseJsonSafe<Record<string, unknown>>(item.json_data);
    const metadata = item.metadata.trim()
      ? parseJsonSafe<Record<string, unknown>>(item.metadata)
      : undefined;
    if (!jsonData && !item.json_data.trim()) {
      return {
        request: null as unknown as DatasetAnalysisRequest,
        error: `Item ${i + 1} (${idTrim}): provide json_data or text.`,
      };
    }
    if (item.json_data.trim() && !jsonData) {
      return {
        request: null as unknown as DatasetAnalysisRequest,
        error: `Item ${i + 1} (${idTrim}): json_data must be valid JSON.`,
      };
    }
    built.push({
      integration_id: idTrim,
      json_data: jsonData ?? undefined,
      metadata: metadata && Object.keys(metadata).length > 0 ? metadata : undefined,
    });
  }

  return {
    request: { dataset_name: nameTrim, items: built },
    error: null,
  };
}

function parseBulkItemsJson(
  raw: string,
): { items: { integration_id: string; json_data: string; metadata: string }[]; error: string | null } {
  const arr = parseJsonSafe<unknown[]>(raw);
  if (!Array.isArray(arr)) {
    return { items: [], error: "Bulk input must be a JSON array." };
  }
  const out: { integration_id: string; json_data: string; metadata: string }[] = [];
  for (let i = 0; i < arr.length; i++) {
    const el = arr[i];
    if (el == null || typeof el !== "object") {
      return { items: [], error: `Element ${i + 1} must be an object.` };
    }
    const obj = el as Record<string, unknown>;
    const integration_id =
      typeof obj.integration_id === "string" ? obj.integration_id : String(obj.integration_id ?? "");
    if (!integration_id.trim()) {
      return { items: [], error: `Element ${i + 1}: integration_id is required.` };
    }
    let json_data = "";
    if (obj.json_data != null) {
      json_data =
        typeof obj.json_data === "string"
          ? obj.json_data
          : JSON.stringify(obj.json_data, null, 2);
    }
    let metadata = "";
    if (obj.metadata != null && typeof obj.metadata === "object") {
      metadata = JSON.stringify(obj.metadata, null, 2);
    }
    out.push({ integration_id, json_data, metadata });
  }
  if (out.length === 0) {
    return { items: [], error: "Array must contain at least one item." };
  }
  return { items: out, error: null };
}

type ItemRow = { integration_id: string; json_data: string; metadata: string };

const defaultItem = (): ItemRow => ({
  integration_id: "",
  json_data: "{}",
  metadata: "",
});

export default function DatasetsPage() {
  const [datasetName, setDatasetName] = React.useState("");
  const [items, setItems] = React.useState<ItemRow[]>([defaultItem()]);
  const [inputMode, setInputMode] = React.useState<"builder" | "bulk">("builder");
  const [bulkJson, setBulkJson] = React.useState("");
  const [bulkError, setBulkError] = React.useState<string | null>(null);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [expandedItems, setExpandedItems] = React.useState<Set<number>>(new Set([0]));

  const analyze = useAnalyzeDataset();
  const { setLastDataset } = useLastActivity();
  const { addToast } = useToast();

  React.useEffect(() => {
    if (analyze.isSuccess && analyze.data) {
      setLastDataset(analyze.data);
      const s = analyze.data.summary;
      addToast({
        variant: "success",
        title: "Dataset analysis complete",
        description: `${s?.total_integrations ?? 0} integrations, ${s?.high_risk_integrations ?? 0} high risk. Avg score: ${s?.average_risk_score ?? "—"}.`,
      });
    }
  }, [analyze.isSuccess, analyze.data, setLastDataset, addToast]);

  React.useEffect(() => {
    if (analyze.isError && analyze.error) {
      addToast({
        variant: "error",
        title: "Dataset analysis failed",
        description: analyze.error.message,
      });
    }
  }, [analyze.isError, analyze.error, addToast]);

  const addItem = () => {
    setItems((prev) => [...prev, defaultItem()]);
    setExpandedItems((prev) => new Set([...prev, prev.size]));
  };

  const removeItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
    setExpandedItems((prev) => {
      const next = new Set(prev);
      next.delete(index);
      return new Set([...next].map((i) => (i > index ? i - 1 : i)));
    });
  };

  const updateItem = (index: number, field: keyof ItemRow, value: string) => {
    setItems((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  };

  const toggleExpanded = (index: number) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const loadSample = () => {
    if (inputMode === "bulk") {
      setBulkJson(SAMPLE_ITEMS_JSON);
      setBulkError(null);
    } else {
      const { items: parsed } = parseBulkItemsJson(SAMPLE_ITEMS_JSON);
      if (parsed.length > 0) setItems(parsed);
    }
  };

  const applyBulk = () => {
    setBulkError(null);
    const { items: parsed, error } = parseBulkItemsJson(bulkJson);
    if (error) {
      setBulkError(error);
      return;
    }
    setItems(parsed);
    setExpandedItems(new Set(parsed.map((_, i) => i)));
    setInputMode("builder");
  };

  const handleSubmit = () => {
    setSubmitError(null);
    const { request, error } = buildDatasetRequest(datasetName, items);
    if (error) {
      setSubmitError(error);
      return;
    }
    analyze.mutate(request);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dataset Analysis"
        description="Batch-analyze datasets of SaaS integrations. Add items manually or paste a JSON array."
      />

      {submitError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200"
        >
          <AlertCircle className="h-5 w-5 shrink-0" />
          {submitError}
        </div>
      )}

      <SectionCard
        title="Dataset"
        description="Name for this batch run (e.g. environment or export identifier)."
      >
        <input
          type="text"
          value={datasetName}
          onChange={(e) => setDatasetName(e.target.value)}
          placeholder="e.g. production-export-2024-03"
          className="w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Dataset name"
        />
      </SectionCard>

      <SectionCard
        title="Items"
        description="Each item requires integration_id and json_data (or text). Add manually or paste a JSON array."
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-border p-0.5">
              <button
                type="button"
                onClick={() => setInputMode("builder")}
                className={cn(
                  "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  inputMode === "builder"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <ListChecks className="h-4 w-4" />
                Builder
              </button>
              <button
                type="button"
                onClick={() => setInputMode("bulk")}
                className={cn(
                  "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  inputMode === "bulk"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <FileJson className="h-4 w-4" />
                Bulk JSON
              </button>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={loadSample}>
              Load sample
            </Button>
          </div>

          {inputMode === "builder" && (
            <div className="space-y-3">
              {items.map((item, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-border bg-card overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() => toggleExpanded(index)}
                    className="flex w-full items-center gap-2 border-b border-border bg-muted/30 px-4 py-2.5 text-left text-sm font-medium hover:bg-muted/50"
                  >
                    {expandedItems.has(index) ? (
                      <ChevronDown className="h-4 w-4 shrink-0" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0" />
                    )}
                    <span className="font-mono text-muted-foreground">
                      {item.integration_id || `Item ${index + 1}`}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {items.length > 1 ? `#${index + 1}` : ""}
                    </span>
                    <span className="ml-auto flex items-center gap-2">
                      {items.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 text-destructive hover:text-destructive"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeItem(index);
                          }}
                          aria-label={`Remove item ${index + 1}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </span>
                  </button>
                  {expandedItems.has(index) && (
                    <div className="space-y-3 p-4">
                      <div>
                        <label className="mb-1 block text-xs font-medium text-muted-foreground">
                          integration_id
                        </label>
                        <input
                          type="text"
                          value={item.integration_id}
                          onChange={(e) => updateItem(index, "integration_id", e.target.value)}
                          placeholder="e.g. acme-slack"
                          className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-muted-foreground">
                          json_data
                        </label>
                        <textarea
                          value={item.json_data}
                          onChange={(e) => updateItem(index, "json_data", e.target.value)}
                          placeholder='{ "integration": "...", ... }'
                          rows={4}
                          className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-muted-foreground">
                          metadata (optional)
                        </label>
                        <textarea
                          value={item.metadata}
                          onChange={(e) => updateItem(index, "metadata", e.target.value)}
                          placeholder='{ "source": "..." }'
                          rows={2}
                          className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" onClick={addItem}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Add item
              </Button>
            </div>
          )}

          {inputMode === "bulk" && (
            <div className="space-y-3">
              <textarea
                value={bulkJson}
                onChange={(e) => {
                  setBulkJson(e.target.value);
                  setBulkError(null);
                }}
                placeholder={`[\n  { "integration_id": "id-1", "json_data": { ... } },\n  { "integration_id": "id-2", "json_data": { ... } }\n]`}
                rows={14}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label="Bulk JSON array"
              />
              {bulkError && (
                <p className="text-sm text-destructive">{bulkError}</p>
              )}
              <Button type="button" size="sm" onClick={applyBulk}>
                Apply to builder
              </Button>
            </div>
          )}
        </div>
      </SectionCard>

      <SectionCard title="Run" description="Validate and run batch analysis." padding="compact">
        <Button
          onClick={handleSubmit}
          disabled={analyze.isPending}
          aria-busy={analyze.isPending}
        >
          {analyze.isPending ? (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          <span className="ml-2">Analyze dataset</span>
        </Button>
        {analyze.isError && (
          <p className="mt-3 flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {analyze.error?.message}
          </p>
        )}
      </SectionCard>

      {analyze.isSuccess && analyze.data && (
        <DatasetResultsSummary data={analyze.data} />
      )}
    </div>
  );
}

const TOP_RISKY_COUNT = 10;

function DatasetResultsSummary({ data }: { data: DatasetAnalysisResponse }) {
  const { summary, results } = data;
  const [expandedId, setExpandedId] = React.useState<string | null>(null);
  const topRisky = React.useMemo(
    () =>
      [...results]
        .sort((a, b) => b.risk_score - a.risk_score)
        .slice(0, TOP_RISKY_COUNT),
    [results],
  );
  const maxScore = Math.max(1, ...topRisky.map((r) => r.risk_score));

  return (
    <div className="space-y-6">
      <SectionCard
        title="Dataset summary"
        description="Aggregate metrics from the batch run."
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <StatCard
            label="Total integrations"
            value={summary.total_integrations}
            padding="compact"
          />
          <StatCard
            label="High-risk integrations"
            value={summary.high_risk_integrations}
            subtitle="elevated risk level"
            padding="compact"
            className={summary.high_risk_integrations > 0 ? "border-amber-200 dark:border-amber-900/50" : ""}
          />
          <StatCard
            label="Average risk score"
            value={<ScoreBadge value={summary.average_risk_score} kind="risk" />}
            padding="compact"
          />
          <StatCard
            label="OAuth over-permission"
            value={summary.oauth_over_permission_hits}
            icon={<Shield className="h-4 w-4" />}
            padding="compact"
          />
          <StatCard
            label="Token misuse"
            value={summary.token_misuse_hits}
            icon={<Key className="h-4 w-4" />}
            padding="compact"
          />
          <StatCard
            label="Credential exposure"
            value={summary.credential_exposure_hits}
            icon={<Lock className="h-4 w-4" />}
            padding="compact"
          />
          <StatCard
            label="Cross-platform risk"
            value={summary.cross_platform_risk_hits}
            icon={<ArrowRightLeft className="h-4 w-4" />}
            padding="compact"
          />
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Dataset: <span className="font-mono">{data.dataset_name}</span>
        </p>
      </SectionCard>

      {topRisky.length > 0 && (
        <SectionCard
          title="Top risky integrations"
          description="Comparison by risk score (top 10)."
        >
          <div className="space-y-2">
            {topRisky.map((r, i) => (
              <div key={`${r.integration_id}-${i}`} className="flex items-center gap-3">
                <span className="w-6 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1 truncate font-mono text-sm" title={r.integration_id}>
                  {r.integration_id}
                </span>
                <span className="w-12 shrink-0 text-right text-sm font-semibold tabular-nums">
                  {r.risk_score}
                </span>
                <div
                  className="h-2 w-24 shrink-0 overflow-hidden rounded-full bg-muted"
                  role="presentation"
                  aria-hidden
                >
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.round((r.risk_score / maxScore) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      <SectionCard
        title="Integration results"
        description="Per-integration risk and findings. Use drill-down to view report details."
      >
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="py-3 pl-4 pr-2 text-left font-medium">Integration ID</th>
                <th className="py-3 pl-2 pr-2 text-left font-medium">Risk score</th>
                <th className="py-3 pl-2 pr-2 text-left font-medium">Risk level</th>
                <th className="py-3 pl-2 pr-2 text-left font-medium">Max severity</th>
                <th className="py-3 pl-2 pr-2 text-left font-medium">Findings</th>
                <th className="py-3 pl-2 pr-4 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <React.Fragment key={`${r.integration_id}-${i}`}>
                  <tr className="border-b border-border/80 last:border-b-0 hover:bg-muted/20">
                    <td className="py-2.5 pl-4 pr-2 font-mono text-xs">{r.integration_id}</td>
                    <td className="py-2.5 pl-2 pr-2">
                      <ScoreBadge value={r.risk_score} kind="risk" />
                    </td>
                    <td className="py-2.5 pl-2 pr-2">
                      <RiskLevelBadge
                        value={
                          typeof r.risk_level === "string"
                            ? (r.risk_level as string).toLowerCase()
                            : r.risk_level
                        }
                      />
                    </td>
                    <td className="py-2.5 pl-2 pr-2">
                      {r.report?.max_severity_found != null ? (
                        <SeverityBadge
                          value={severityLevelFromNumber(r.report.max_severity_found)}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-2.5 pl-2 pr-2 tabular-nums">
                      {r.report?.findings?.length ?? 0}
                    </td>
                    <td className="py-2.5 pl-2 pr-4">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedId((id) => (id === r.integration_id ? null : r.integration_id))
                          }
                          className="text-xs font-medium text-primary hover:underline"
                        >
                          {expandedId === r.integration_id ? "Hide details" : "View details"}
                        </button>
                        <Link
                          href={`/scan?target=${encodeURIComponent(r.integration_id)}`}
                          className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
                        >
                          Re-scan <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>
                    </td>
                  </tr>
                  {expandedId === r.integration_id && (
                    <tr className="border-b border-border/80 bg-muted/10">
                      <td colSpan={6} className="p-4">
                        <IntegrationDrillDown result={r} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

function IntegrationDrillDown({ result }: { result: DatasetItemResult }) {
  const report = result.report;
  if (!report) {
    return <p className="text-sm text-muted-foreground">No report data.</p>;
  }
  const findingsCount = report.findings?.length ?? 0;
  const matchedCount = report.matched_rules?.length ?? 0;
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-muted-foreground">Report summary</p>
      <div className="flex flex-wrap gap-4">
        <span className="text-sm">
          Findings: <strong className="tabular-nums">{findingsCount}</strong>
        </span>
        <span className="text-sm">
          Matched rules: <strong className="tabular-nums">{matchedCount}</strong>
        </span>
        {report.risk_summary != null && typeof report.risk_summary === "object" && "integration" in report.risk_summary && (
          <span className="text-sm">
            Integration:{" "}
            <span className="font-medium">
              {(report.risk_summary as { integration?: string }).integration ?? "—"}
            </span>
          </span>
        )}
      </div>
      {findingsCount > 0 && (
        <details className="rounded border border-border bg-background p-3">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            Recent findings ({Math.min(3, findingsCount)} shown)
          </summary>
          <ul className="mt-2 space-y-1 text-xs">
            {(report.findings ?? [])
              .slice(0, 3)
              .map((f, i) => (
                <li key={i} className="flex items-center gap-2">
                  <SeverityBadge value={severityLevelFromNumber(f.severity)} />
                  <span className="truncate font-mono text-muted-foreground">{f.rule_id}</span>
                  <span className="truncate flex-1" title={f.evidence}>
                    {f.evidence?.slice(0, 60)}
                    {(f.evidence?.length ?? 0) > 60 ? "…" : ""}
                  </span>
                </li>
              ))}
          </ul>
        </details>
      )}
    </div>
  );
}
