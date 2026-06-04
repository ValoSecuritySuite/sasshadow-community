"use client";

import * as React from "react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import {
  FileJson,
  FileText,
  LayoutTemplate,
  Play,
  Download,
  FileDown,
  AlertCircle,
  Shield,
  Key,
  Lock,
  ArrowRightLeft,
  Hash,
  Clock,
  AlertTriangle,
  Check,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useAnalyzeScan, useReportJson, useReportPdf } from "@/hooks/api";
import { apiKeys } from "@/hooks/api/query-keys";
import { useLastActivity } from "@/contexts/last-activity-context";
import { useToast } from "@/contexts/toast-context";
import type {
  PipelineRequest,
  PipelineResult,
  ReportBranding,
  OAuthAnalysis,
  TokenAnalysis,
  CredentialExposure,
  DataFlowRisk,
  RiskSummary,
  RuleMatch,
  TextFinding,
} from "@/lib/api/types";
import { StatCard } from "@/components/ui/stat-card";
import { ScoreBadge } from "@/components/ui/score-badge";
import { RiskLevelBadge } from "@/components/ui/risk-level-badge";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { formatTimestamp } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useEditionContext } from "@/contexts/edition-context";
import { EnterpriseLockedSection } from "@/components/enterprise/enterprise-locked-section";
import { IntegrationGraphCanvas } from "@/components/graph/IntegrationGraphCanvas";
import { riskGraphToFlow } from "@/components/graph/adapters";
import { Network } from "lucide-react";

const SAMPLE_JSON = `{
  "integration": "sample-app",
  "oauth_scopes": ["read:user", "write:repo"],
  "config": {
    "api_endpoint": "https://api.example.com",
    "auth_type": "bearer"
  }
}`;

function parseJsonSafe(value: string): Record<string, unknown> | null {
  const t = value.trim();
  if (!t) return null;
  try {
    const out = JSON.parse(t);
    return typeof out === "object" && out !== null ? (out as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function buildPayload(
  target: string,
  inputTab: string,
  jsonPayload: string,
  rawText: string,
  metadataJson: string,
  companyName: string,
  includeBranding = true,
): { request: PipelineRequest; error: string | null } {
  const targetTrim = target.trim();
  if (!targetTrim) {
    return { request: null as unknown as PipelineRequest, error: "Target is required." };
  }

  let text: string | null = null;
  let json_data: Record<string, unknown> | null = null;

  if (inputTab === "json") {
    const parsed = parseJsonSafe(jsonPayload);
    if (!parsed) {
      return { request: null as unknown as PipelineRequest, error: "Enter valid JSON in the JSON Payload tab." };
    }
    json_data = parsed;
  } else if (inputTab === "text") {
    const t = rawText.trim();
    if (!t) {
      return { request: null as unknown as PipelineRequest, error: "Enter content in the Raw Text tab." };
    }
    text = t;
  } else {
    const parsed = parseJsonSafe(jsonPayload);
    if (!parsed) {
      return { request: null as unknown as PipelineRequest, error: "Sample template is invalid JSON. Fix it or switch tab." };
    }
    json_data = parsed;
  }

  const metadata = parseJsonSafe(metadataJson) ?? undefined;
  const report_branding: ReportBranding | null =
    includeBranding && companyName.trim()
      ? { company_name: companyName.trim(), logo_base64: null }
      : null;

  const request: PipelineRequest = {
    target: targetTrim,
    text: text ?? undefined,
    json_data: json_data ?? undefined,
    metadata: metadata && Object.keys(metadata).length > 0 ? metadata : undefined,
    report_branding: report_branding ?? undefined,
  };

  if (!request.text && !request.json_data) {
    return { request: null as unknown as PipelineRequest, error: "Provide either raw text or JSON payload." };
  }
  return { request, error: null };
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function isRiskSummary(
  r: RiskSummary | Record<string, unknown> | null | undefined,
): r is RiskSummary {
  return (
    r != null &&
    typeof r === "object" &&
    "integration" in r &&
    "risk_score" in r &&
    "severity" in r
  );
}

/** Map numeric severity (e.g. 1–4) to SeverityLevel for badges. */
function severityLevelFromNumber(n: number): string {
  if (n >= 4) return "critical";
  if (n >= 3) return "high";
  if (n >= 2) return "medium";
  if (n >= 1) return "low";
  return "info";
}

const EVIDENCE_TRUNCATE_LEN = 80;

function EvidenceCell({ evidence }: { evidence: string }) {
  const [expanded, setExpanded] = React.useState(false);
  const isLong = evidence.length > EVIDENCE_TRUNCATE_LEN;
  const display =
    isLong && !expanded
      ? `${evidence.slice(0, EVIDENCE_TRUNCATE_LEN).trim()}\u2026`
      : evidence;
  return (
    <div className="min-w-0">
      <code className="block break-all rounded border border-border bg-muted/40 px-2 py-1 font-mono text-xs">
        {display}
      </code>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-1 text-xs font-medium text-primary hover:underline"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

type SortDir = "asc" | "desc";

function MatchedRulesTable({ rules }: { rules: RuleMatch[] }) {
  const [matchedFilter, setMatchedFilter] = React.useState<"all" | "matched" | "failed">("all");
  const [sortCol, setSortCol] = React.useState<"rule_name" | "severity" | "weight" | "matched">(
    "severity",
  );
  const [sortDir, setSortDir] = React.useState<SortDir>("desc");

  const filtered = React.useMemo(() => {
    if (matchedFilter === "matched") return rules.filter((r) => r.matched);
    if (matchedFilter === "failed") return rules.filter((r) => !r.matched);
    return rules;
  }, [rules, matchedFilter]);

  const sorted = React.useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "rule_name":
          cmp = (a.rule_name ?? "").localeCompare(b.rule_name ?? "");
          break;
        case "severity":
          cmp = (a.severity ?? 0) - (b.severity ?? 0);
          break;
        case "weight":
          cmp = (a.weight ?? 0) - (b.weight ?? 0);
          break;
        case "matched":
          cmp = (a.matched === b.matched ? 0 : a.matched ? 1 : -1);
          break;
        default:
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortCol, sortDir]);

  const toggleSort = (col: typeof sortCol) => {
    if (sortCol === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(col);
      setSortDir(col === "rule_name" ? "asc" : "desc");
    }
  };

  const Th = ({
    col,
    label,
    className,
  }: {
    col: typeof sortCol;
    label: string;
    className?: string;
  }) => (
    <th className={cn("text-left font-medium", className)}>
      <button
        type="button"
        onClick={() => toggleSort(col)}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        {sortCol === col ? (
          sortDir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/60" />
        )}
      </button>
    </th>
  );

  if (rules.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-muted/20 py-8 text-center text-sm text-muted-foreground">
        No matched rules.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Filter:</span>
        {(["all", "matched", "failed"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setMatchedFilter(f)}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
              matchedFilter === f
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-background text-muted-foreground hover:bg-muted/50",
            )}
          >
            {f === "all" ? "All" : f === "matched" ? "Matched" : "Failed"}
          </button>
        ))}
        <span className="text-xs text-muted-foreground">
          {sorted.length} of {rules.length} rule(s)
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[600px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <Th col="rule_name" label="Rule name" className="py-3 pl-4 pr-2" />
              <th className="py-3 pl-2 pr-2 text-left font-medium text-muted-foreground">
                Rule type
              </th>
              <Th col="severity" label="Severity" className="py-3 pl-2 pr-2" />
              <Th col="weight" label="Weight" className="py-3 pl-2 pr-2" />
              <Th col="matched" label="Matched" className="py-3 pl-2 pr-4" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr
                key={`${r.rule_name}-${i}`}
                className="border-b border-border/80 last:border-b-0 hover:bg-muted/20"
              >
                <td className="py-2.5 pl-4 pr-2 font-medium">{r.rule_name}</td>
                <td className="py-2.5 pl-2 pr-2 text-muted-foreground">—</td>
                <td className="py-2.5 pl-2 pr-2">
                  <SeverityBadge value={severityLevelFromNumber(r.severity)} />
                </td>
                <td className="py-2.5 pl-2 pr-2 tabular-nums">{r.weight}</td>
                <td className="py-2.5 pl-2 pr-4">
                  {r.matched ? (
                    <span className="text-amber-600 dark:text-amber-400">Matched</span>
                  ) : (
                    <span className="text-muted-foreground">No</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TextFindingsTable({
  findings,
}: {
  findings: TextFinding[];
}) {
  const [sortCol, setSortCol] = React.useState<"rule_id" | "category" | "severity">("severity");
  const [sortDir, setSortDir] = React.useState<SortDir>("desc");
  const [categoryFilter, setCategoryFilter] = React.useState<string>("all");
  const categories = React.useMemo(
    () => Array.from(new Set(findings.map((f) => f.category).filter(Boolean))).sort(),
    [findings],
  );

  const filtered = React.useMemo(() => {
    if (categoryFilter === "all") return findings;
    return findings.filter((f) => f.category === categoryFilter);
  }, [findings, categoryFilter]);

  const sorted = React.useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "rule_id":
          cmp = (a.rule_id ?? "").localeCompare(b.rule_id ?? "");
          break;
        case "category":
          cmp = (a.category ?? "").localeCompare(b.category ?? "");
          break;
        case "severity":
          cmp = (a.severity ?? 0) - (b.severity ?? 0);
          break;
        default:
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortCol, sortDir]);

  const toggleSort = (col: typeof sortCol) => {
    if (sortCol === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(col);
      setSortDir(col === "severity" ? "desc" : "asc");
    }
  };

  const Th = ({
    col,
    label,
    className,
  }: {
    col: typeof sortCol;
    label: string;
    className?: string;
  }) => (
    <th className={cn("text-left font-medium", className)}>
      <button
        type="button"
        onClick={() => toggleSort(col)}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        {sortCol === col ? (
          sortDir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/60" />
        )}
      </button>
    </th>
  );

  if (findings.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-muted/20 py-8 text-center text-sm text-muted-foreground">
        No text findings.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Category:</span>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border border-input bg-background px-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground">
          {sorted.length} of {findings.length} finding(s)
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[700px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <Th col="rule_id" label="Rule ID" className="py-3 pl-4 pr-2" />
              <Th col="category" label="Category" className="py-3 pl-2 pr-2" />
              <Th col="severity" label="Severity" className="py-3 pl-2 pr-2" />
              <th className="py-3 pl-2 pr-2 text-left font-medium">Evidence</th>
              <th className="py-3 pl-2 pr-4 text-left font-medium">Match positions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((f, i) => (
              <tr
                key={`${f.rule_id}-${i}-${f.evidence?.slice(0, 20)}`}
                className="border-b border-border/80 last:border-b-0 hover:bg-muted/20"
              >
                <td className="py-2.5 pl-4 pr-2 font-mono text-xs">{f.rule_id}</td>
                <td className="py-2.5 pl-2 pr-2">{f.category}</td>
                <td className="py-2.5 pl-2 pr-2">
                  <SeverityBadge value={severityLevelFromNumber(f.severity)} />
                </td>
                <td className="min-w-[120px] max-w-[320px] py-2.5 pl-2 pr-2">
                  <EvidenceCell evidence={f.evidence ?? ""} />
                </td>
                <td className="py-2.5 pl-2 pr-4 font-mono text-xs text-muted-foreground">
                  {f.match_start != null && f.match_end != null
                    ? `${f.match_start}-${f.match_end}`
                    : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RiskGraphSection({
  riskGraph,
}: {
  riskGraph: Record<string, unknown>;
}) {
  const normalized = React.useMemo(
    () => riskGraphToFlow(riskGraph),
    [riskGraph],
  );

  if (normalized.nodes.length === 0) {
    return null;
  }

  const description =
    normalized.edges.length > 0
      ? `${normalized.nodes.length} system${normalized.nodes.length === 1 ? "" : "s"}, ${normalized.edges.length} connection${normalized.edges.length === 1 ? "" : "s"}. Click a node or edge for details.`
      : `${normalized.nodes.length} system${normalized.nodes.length === 1 ? "" : "s"} discovered. No cross-system connections detected.`;

  return (
    <SectionCard
      title={
        <span className="inline-flex items-center gap-2">
          <Network className="h-4 w-4 text-muted-foreground" />
          Risk graph
        </span>
      }
      description={description}
      padding="none"
    >
      <IntegrationGraphCanvas data={normalized} height={420} />
    </SectionCard>
  );
}

// ─── Results overview (after successful /scan/analyze) ─────────────────────────

function ScanResultsOverview({ data }: { data: PipelineResult }) {
  const report = data.report ?? null;
  const scanId = report?.scan_id ?? null;
  const timestamp = report?.timestamp ?? null;
  const riskLevel = report?.risk_level ?? undefined;
  const maxSeverity = report?.max_severity_found;
  const severityCeiling = report?.severity_ceiling_applied;
  const riskSummary = data.risk_summary ?? report?.risk_summary;

  const oauth = report?.oauth_analysis ?? data.saas_signals?.oauth;
  const tokens = report?.token_analysis ?? data.saas_signals?.tokens;
  const credentials = report?.credential_exposure ?? data.saas_signals?.credentials;
  const dataFlow = report?.data_flow_risk ?? data.saas_signals?.data_flow;

  return (
    <div className="space-y-6">
      <SectionCard
        title="Scan overview"
        description="Identification and high-level risk from this analysis run."
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {scanId != null && (
            <StatCard
              label="Scan ID"
              value={<code className="break-all text-sm font-mono">{scanId}</code>}
              icon={<Hash className="h-4 w-4" />}
              padding="compact"
            />
          )}
          {timestamp != null && (
            <StatCard
              label="Timestamp"
              value={formatTimestamp(timestamp, { dateStyle: "short", timeStyle: "short" })}
              icon={<Clock className="h-4 w-4" />}
              padding="compact"
            />
          )}
          <StatCard
            label="Combined risk score"
            value={<ScoreBadge value={data.combined_score} kind="risk" />}
            padding="compact"
          />
          {riskLevel != null && (
            <StatCard
              label="Risk level"
              value={
                <RiskLevelBadge
                  value={
                    typeof riskLevel === "string"
                      ? (riskLevel as string).toLowerCase()
                      : riskLevel
                  }
                />
              }
              padding="compact"
            />
          )}
          {maxSeverity != null && (
            <StatCard
              label="Max severity"
              value={
                <SeverityBadge
                  value={
                    typeof maxSeverity === "number"
                      ? severityLevelFromNumber(maxSeverity)
                      : maxSeverity
                  }
                />
              }
              padding="compact"
            />
          )}
          <StatCard
            label="Severity ceiling"
            value={
              severityCeiling === true ? (
                <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" /> Applied
                </span>
              ) : severityCeiling === false ? (
                <span className="inline-flex items-center gap-1 text-muted-foreground">
                  <Check className="h-3.5 w-3.5" /> Not applied
                </span>
              ) : (
                "—"
              )
            }
            padding="compact"
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Scores"
        description="Context, text-scan, and combined scores from the pipeline."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard
            label="Context score"
            value={<ScoreBadge value={data.context_score} kind="risk" />}
            subtitle="Rule context evaluation"
            padding="compact"
          />
          <StatCard
            label="Text-scan score"
            value={<ScoreBadge value={data.text_scan_score} kind="risk" />}
            subtitle="Text findings and patterns"
            padding="compact"
          />
          <StatCard
            label="Combined score"
            value={<ScoreBadge value={data.combined_score} kind="risk" />}
            subtitle="Overall risk"
            padding="compact"
          />
        </div>
      </SectionCard>

      {(oauth != null || tokens != null || credentials != null || dataFlow != null) && (
        <SectionCard
          title="SaaS signal summary"
          description="OAuth, token, credential, and data flow analysis."
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {oauth != null && (
              <StatCard
                label="OAuth analysis"
                value={<ScoreBadge value={(oauth as OAuthAnalysis).scope_risk_score} kind="risk" />}
                subtitle={
                  (oauth as OAuthAnalysis).over_permissioned
                    ? "Over-permissioned"
                    : `${(oauth as OAuthAnalysis).total_scopes} scope(s)`
                }
                icon={<Shield className="h-4 w-4" />}
                padding="compact"
              />
            )}
            {tokens != null && (
              <StatCard
                label="Token analysis"
                value={<ScoreBadge value={(tokens as TokenAnalysis).token_risk_score} kind="risk" />}
                subtitle={`${(tokens as TokenAnalysis).tokens_found} token(s)`}
                icon={<Key className="h-4 w-4" />}
                padding="compact"
              />
            )}
            {credentials != null && (
              <StatCard
                label="Credential exposure"
                value={
                  <ScoreBadge
                    value={(credentials as CredentialExposure).credential_risk_score}
                    kind="risk"
                  />
                }
                subtitle={`${(credentials as CredentialExposure).exposed_credentials} exposed`}
                icon={<Lock className="h-4 w-4" />}
                padding="compact"
              />
            )}
            {dataFlow != null && (
              <StatCard
                label="Data flow risk"
                value={
                  <ScoreBadge value={(dataFlow as DataFlowRisk).flow_risk_score} kind="risk" />
                }
                subtitle={
                  (dataFlow as DataFlowRisk).sensitive_data_exposed
                    ? "Sensitive data exposed"
                    : (dataFlow as DataFlowRisk).data_types?.length > 0
                      ? `${(dataFlow as DataFlowRisk).data_types.length} data type(s)`
                      : "Flow evaluated"
                }
                icon={<ArrowRightLeft className="h-4 w-4" />}
                padding="compact"
              />
            )}
          </div>
        </SectionCard>
      )}

      {report?.risk_graph != null && (
        <RiskGraphSection riskGraph={report.risk_graph} />
      )}

      {riskSummary != null && (
        <SectionCard
          title="Risk summary"
          description="Aggregated risk and dimension scores for this integration."
        >
          {isRiskSummary(riskSummary) ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm font-medium text-muted-foreground">Integration</span>
                <span className="font-medium">{riskSummary.integration}</span>
                <RiskLevelBadge
                  value={
                    typeof riskSummary.severity === "string"
                      ? riskSummary.severity.toLowerCase()
                      : riskSummary.severity
                  }
                />
                <ScoreBadge value={riskSummary.risk_score} kind="risk" />
              </div>
              {riskSummary.dimension_scores != null &&
                Object.keys(riskSummary.dimension_scores).length > 0 && (
                  <div>
                    <p className="mb-2 text-sm font-medium text-muted-foreground">
                      Dimension scores
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(riskSummary.dimension_scores).map(([key, val]) => (
                        <span
                          key={key}
                          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-2.5 py-1 text-xs"
                        >
                          <span className="text-muted-foreground">{key}</span>
                          <ScoreBadge value={val} kind="risk" />
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              {riskSummary.findings?.length > 0 && (
                <p className="text-sm text-muted-foreground">
                  {riskSummary.findings.length} finding(s) in this summary.
                </p>
              )}
            </div>
          ) : (
            <pre className="overflow-auto rounded-lg border border-border bg-muted/30 p-4 text-xs">
              {JSON.stringify(riskSummary, null, 2)}
            </pre>
          )}
        </SectionCard>
      )}

      <SectionCard
        title="Matched rules"
        description="Context and text-scan rule evaluation: name, severity, weight, and matched state."
      >
        <MatchedRulesTable rules={data.matched_rules ?? []} />
      </SectionCard>

      <SectionCard
        title="Text findings"
        description="Evidence and match positions for each finding."
      >
        <TextFindingsTable findings={data.text_findings ?? []} />
      </SectionCard>
    </div>
  );
}

export default function ScanPage() {
  const { isCommunity } = useEditionContext();
  const [target, setTarget] = React.useState("");
  const [inputTab, setInputTab] = React.useState<"json" | "text" | "sample">("json");
  const [jsonPayload, setJsonPayload] = React.useState("");
  const [rawText, setRawText] = React.useState("");
  const [metadataJson, setMetadataJson] = React.useState("");
  const [companyName, setCompanyName] = React.useState("");
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const analyzeScan = useAnalyzeScan();
  const reportJson = useReportJson();
  const reportPdf = useReportPdf();
  const queryClient = useQueryClient();
  const { setLastScan } = useLastActivity();
  const { addToast } = useToast();

  React.useEffect(() => {
    if (analyzeScan.isSuccess && analyzeScan.data) {
      setLastScan(analyzeScan.data);
      void queryClient.invalidateQueries({ queryKey: apiKeys.scans.all });
      addToast({
        variant: "success",
        title: "Analysis complete",
        description: `Combined score: ${analyzeScan.data.combined_score ?? "—"}. ${analyzeScan.data.matched_rules?.length ?? 0} rules matched. Scan stored.`,
      });
    }
  }, [analyzeScan.isSuccess, analyzeScan.data, setLastScan, addToast, queryClient]);

  React.useEffect(() => {
    if (analyzeScan.isError && analyzeScan.error) {
      addToast({
        variant: "error",
        title: "Analysis failed",
        description: analyzeScan.error.message,
      });
    }
  }, [analyzeScan.isError, analyzeScan.error, addToast]);

  React.useEffect(() => {
    if (reportJson.isSuccess && reportJson.data) {
      void queryClient.invalidateQueries({ queryKey: apiKeys.scans.all });
      addToast({ variant: "success", title: "JSON report downloaded" });
    }
  }, [reportJson.isSuccess, reportJson.data, addToast, queryClient]);

  React.useEffect(() => {
    if (reportJson.isError && reportJson.error) {
      addToast({
        variant: "error",
        title: "JSON report failed",
        description: reportJson.error.message,
      });
    }
  }, [reportJson.isError, reportJson.error, addToast]);

  React.useEffect(() => {
    if (reportPdf.isSuccess) {
      addToast({ variant: "success", title: "PDF report downloaded" });
    }
  }, [reportPdf.isSuccess, addToast]);

  React.useEffect(() => {
    if (reportPdf.isError && reportPdf.error) {
      addToast({
        variant: "error",
        title: "PDF report failed",
        description: reportPdf.error.message,
      });
    }
  }, [reportPdf.isError, reportPdf.error, addToast]);

  const handleAnalyze = () => {
    setSubmitError(null);
    const { request, error } = buildPayload(
      target,
      inputTab,
      jsonPayload,
      rawText,
      metadataJson,
      companyName,
      !isCommunity,
    );
    if (error) {
      setSubmitError(error);
      return;
    }
    analyzeScan.mutate(request);
  };

  const handleExportJson = () => {
    setSubmitError(null);
    const { request, error } = buildPayload(
      target,
      inputTab,
      jsonPayload,
      rawText,
      metadataJson,
      companyName,
      !isCommunity,
    );
    if (error) {
      setSubmitError(error);
      return;
    }
    reportJson.mutate(request);
  };

  const handleExportPdf = () => {
    setSubmitError(null);
    const { request, error } = buildPayload(
      target,
      inputTab,
      jsonPayload,
      rawText,
      metadataJson,
      companyName,
      !isCommunity,
    );
    if (error) {
      setSubmitError(error);
      return;
    }
    reportPdf.mutate(request);
  };

  React.useEffect(() => {
    if (reportJson.isSuccess && reportJson.data) {
      const blob = new Blob([JSON.stringify(reportJson.data, null, 2)], {
        type: "application/json",
      });
      triggerDownload(blob, `scan-report-${reportJson.data.scan_id}.json`);
    }
  }, [reportJson.isSuccess, reportJson.data]);

  React.useEffect(() => {
    if (reportPdf.isSuccess && reportPdf.data) {
      const filename = reportPdf.data.filename ?? "scan-report.pdf";
      triggerDownload(reportPdf.data.blob, filename);
    }
  }, [reportPdf.isSuccess, reportPdf.data]);

  const isFormDisabled =
    analyzeScan.isPending || reportJson.isPending || reportPdf.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Single Scan"
        description="Analyze a single SaaS integration payload for security risks. Provide JSON or raw text, then run analysis or export a report."
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
        title="Target"
        description="Identifier for this integration (e.g. application or tenant name)."
      >
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="e.g. acme-slack-integration"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          aria-required
          aria-invalid={!!submitError && !target.trim()}
        />
      </SectionCard>

      <SectionCard
        title="Input"
        description="Provide integration data as JSON or raw text. At least one is required."
      >
        <div className="space-y-4">
          <div className="flex rounded-lg border border-border p-0.5">
            <button
              type="button"
              onClick={() => setInputTab("json")}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
                inputTab === "json"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <FileJson className="h-4 w-4" />
              JSON Payload
            </button>
            <button
              type="button"
              onClick={() => setInputTab("text")}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
                inputTab === "text"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <FileText className="h-4 w-4" />
              Raw Text
            </button>
            <button
              type="button"
              onClick={() => {
                setInputTab("sample");
                if (!jsonPayload.trim()) setJsonPayload(SAMPLE_JSON);
              }}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
                inputTab === "sample"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <LayoutTemplate className="h-4 w-4" />
              Sample Template
            </button>
          </div>

          {inputTab === "json" && (
            <textarea
              value={jsonPayload}
              onChange={(e) => setJsonPayload(e.target.value)}
              placeholder='{ "integration": "...", ... }'
              rows={14}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="JSON payload"
            />
          )}

          {inputTab === "text" && (
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste or type raw configuration or log content here..."
              rows={14}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Raw text input"
            />
          )}

          {inputTab === "sample" && (
            <textarea
              value={jsonPayload}
              onChange={(e) => setJsonPayload(e.target.value)}
              placeholder="Sample JSON (edit as needed)"
              rows={14}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Sample template JSON"
            />
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Optional metadata"
        description="Key-value context for the scan (JSON object)."
        padding="compact"
      >
        <textarea
          value={metadataJson}
          onChange={(e) => setMetadataJson(e.target.value)}
          placeholder='{ "source": "manual", "env": "production" }'
          rows={3}
          className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Metadata JSON"
        />
      </SectionCard>

      <SectionCard
        title="Report branding"
        description="Company name and logo on exported PDF reports."
        padding="compact"
      >
        <EnterpriseLockedSection
          feature="branding"
          title="Custom report branding"
          description="Company name and logo on exported PDF reports."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="company-name"
                className="mb-1 block text-sm font-medium text-foreground"
              >
                Company name
              </label>
              <input
                id="company-name"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Your organization name"
                disabled={isCommunity}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
              />
            </div>
          </div>
        </EnterpriseLockedSection>
      </SectionCard>

      <SectionCard
        title="Actions"
        description="Run analysis or export a JSON or PDF report. Each action runs the full pipeline."
      >
        <div className="flex flex-wrap items-center gap-3">
          <Button
            onClick={handleAnalyze}
            disabled={isFormDisabled}
            aria-busy={analyzeScan.isPending}
          >
            {analyzeScan.isPending ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            <span className="ml-2">Analyze</span>
          </Button>
          <Button
            variant="outline"
            onClick={handleExportJson}
            disabled={isFormDisabled}
            aria-busy={reportJson.isPending}
          >
            {reportJson.isPending ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            <span className="ml-2">Export JSON Report</span>
          </Button>
          <Button
            variant="outline"
            onClick={handleExportPdf}
            disabled={isFormDisabled}
            aria-busy={reportPdf.isPending}
          >
            {reportPdf.isPending ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <FileDown className="h-4 w-4" />
            )}
            <span className="ml-2">Export PDF Report</span>
          </Button>
        </div>

        {analyzeScan.isSuccess && analyzeScan.data && (
          <div className="mt-4 rounded-lg border border-border bg-muted/30 px-4 py-3">
            <p className="text-sm font-medium text-foreground">Analysis complete</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Results overview is shown below.
            </p>
          </div>
        )}

        {(analyzeScan.isError || reportJson.isError || reportPdf.isError) && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            <AlertCircle className="h-5 w-5 shrink-0" />
            {analyzeScan.error?.message ?? reportJson.error?.message ?? reportPdf.error?.message}
          </div>
        )}
      </SectionCard>

      {analyzeScan.isSuccess && analyzeScan.data && (
        <ScanResultsOverview data={analyzeScan.data} />
      )}
    </div>
  );
}
