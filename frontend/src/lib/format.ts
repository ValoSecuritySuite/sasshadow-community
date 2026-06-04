/**
 * Semantic formatting utilities for SaaSShadow.ai.
 * Domain-friendly and reusable across dashboard, scan, rules, dataset, and health.
 */

/** Severity levels for findings/alerts (domain-agnostic). */
export type SeverityLevel = "critical" | "high" | "medium" | "low" | "info";

/** Risk level bands (e.g. for scores 0–100). */
export type RiskLevel = "critical" | "high" | "medium" | "low" | "minimal" | "none";

/** Generic status for entities (runs, jobs, checks). */
export type EntityStatus =
  | "active"
  | "inactive"
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "warning"
  | "cancelled"
  | "unknown";

/** Score display context (e.g. risk vs quality: higher = worse vs better). */
export type ScoreKind = "risk" | "quality" | "neutral";

const SEVERITY_LABELS: Record<SeverityLevel, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  minimal: "Minimal",
  none: "None",
};

const STATUS_LABELS: Record<EntityStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  pending: "Pending",
  running: "Running",
  success: "Success",
  failed: "Failed",
  warning: "Warning",
  cancelled: "Cancelled",
  unknown: "Unknown",
};

/**
 * Normalize severity from string (e.g. API) to SeverityLevel.
 */
export function normalizeSeverity(value: string | null | undefined): SeverityLevel {
  if (value == null || value === "") return "info";
  const v = value.toLowerCase();
  if (["critical", "crit"].includes(v)) return "critical";
  if (["high", "error"].includes(v)) return "high";
  if (["medium", "med", "moderate"].includes(v)) return "medium";
  if (["low"].includes(v)) return "low";
  if (["info", "informational"].includes(v)) return "info";
  return "info";
}

/**
 * Format severity for display (title case).
 */
export function formatSeverity(severity: SeverityLevel | string): string {
  return SEVERITY_LABELS[normalizeSeverity(severity)] ?? String(severity);
}

/**
 * Derive risk level from a numeric score (0–100, where higher = worse risk).
 */
export function getRiskLevelFromScore(score: number): RiskLevel {
  if (score >= 90) return "critical";
  if (score >= 70) return "high";
  if (score >= 50) return "medium";
  if (score >= 25) return "low";
  if (score > 0) return "minimal";
  return "none";
}

/**
 * Format risk level for display.
 */
export function formatRiskLevel(level: RiskLevel | string): string {
  const key = Object.keys(RISK_LEVEL_LABELS).includes(level as RiskLevel)
    ? (level as RiskLevel)
    : "none";
  return RISK_LEVEL_LABELS[key] ?? String(level);
}

/**
 * Format a numeric risk/quality score for display (e.g. "72" or "72.5").
 */
export function formatScore(
  value: number | null | undefined,
  options?: { decimals?: number; suffix?: string; empty?: string }
): string {
  if (value == null || Number.isNaN(value)) return options?.empty ?? "—";
  const decimals = options?.decimals ?? 0;
  const num = decimals > 0 ? Number(value).toFixed(decimals) : String(Math.round(value));
  const suffix = options?.suffix ?? "";
  return `${num}${suffix}`;
}

/**
 * Human-friendly label for a score (e.g. "Risk score", "Quality score").
 */
export function getScoreLabel(kind: ScoreKind, options?: { unit?: string }): string {
  const unit = options?.unit ?? "";
  switch (kind) {
    case "risk":
      return unit ? `Risk score (${unit})` : "Risk score";
    case "quality":
      return unit ? `Quality score (${unit})` : "Quality score";
    default:
      return unit ? `Score (${unit})` : "Score";
  }
}

/**
 * Normalize status from string to EntityStatus.
 */
export function normalizeStatus(value: string | null | undefined): EntityStatus {
  if (value == null || value === "") return "unknown";
  const v = value.toLowerCase();
  if (["active", "ok", "up"].includes(v)) return "active";
  if (["inactive", "down", "stopped"].includes(v)) return "inactive";
  if (["pending", "queued"].includes(v)) return "pending";
  if (["running", "in_progress", "in progress"].includes(v)) return "running";
  if (["success", "completed", "done", "pass", "passed"].includes(v)) return "success";
  if (["failed", "failure", "error", "fail"].includes(v)) return "failed";
  if (["warning", "warn"].includes(v)) return "warning";
  if (["cancelled", "canceled"].includes(v)) return "cancelled";
  return "unknown";
}

/**
 * Format status for display.
 */
export function formatStatus(status: EntityStatus | string): string {
  return STATUS_LABELS[normalizeStatus(status)] ?? String(status);
}

/**
 * Format a timestamp for relative display (e.g. "2 hours ago") and absolute (ISO or locale).
 */
export function formatTimestamp(
  value: string | number | Date | null | undefined,
  options?: {
    relative?: boolean;
    locale?: string;
    dateStyle?: "short" | "medium" | "long" | "full";
    timeStyle?: "short" | "medium" | "long";
    empty?: string;
  }
): string {
  if (value == null) return options?.empty ?? "—";
  const date = typeof value === "number" || typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return options?.empty ?? "—";

  if (options?.relative) {
    const now = new Date();
    const sec = (now.getTime() - date.getTime()) / 1000;
    if (sec < 60) return "Just now";
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  }

  return date.toLocaleString(options?.locale, {
    dateStyle: options?.dateStyle ?? "short",
    timeStyle: options?.timeStyle ?? "short",
  });
}

/**
 * Format a number with optional compact notation (e.g. 1.2k, 3M).
 */
export function formatCount(
  value: number | null | undefined,
  options?: { compact?: boolean; empty?: string }
): string {
  if (value == null || Number.isNaN(value)) return options?.empty ?? "—";
  if (!options?.compact || value < 1000) return String(value);
  if (value < 1_000_000) return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  if (value < 1_000_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  return `${(value / 1_000_000_000).toFixed(1).replace(/\.0$/, "")}B`;
}
