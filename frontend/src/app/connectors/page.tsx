"use client";

import * as React from "react";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { QueryErrorCard } from "@/components/ui/query-error-card";
import { ScoreBadge } from "@/components/ui/score-badge";
import {
  useConnectors,
  useEntraSync,
  useSlackSync,
} from "@/hooks/api";
import { useToast } from "@/contexts/toast-context";
import type { ConnectorInfo, ConnectorSyncResponse } from "@/lib/api/types";
import { useEditionContext } from "@/contexts/edition-context";
import { EnterpriseUpsell } from "@/components/enterprise/enterprise-upsell";
import { ENTERPRISE_CONNECTOR_STUBS } from "@/config/enterprise-connectors";
import type { EnterpriseConnectorStub } from "@/config/enterprise-connectors";
import { Badge } from "@/components/ui/badge";
import {
  Plug,
  RefreshCw,
  Cloud,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Lock,
} from "lucide-react";

const CONNECTOR_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  entra: Cloud,
  slack: MessageSquare,
};

function ConnectorCard({
  connector,
  children,
}: {
  connector: ConnectorInfo;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const Icon = CONNECTOR_ICONS[connector.id] ?? Plug;

  return (
    <SectionCard className="overflow-hidden">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h3 className="font-semibold tracking-tight">{connector.name}</h3>
              <p className="mt-0.5 text-sm text-muted-foreground">{connector.description}</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setExpanded((e) => !e)}
            className="shrink-0"
          >
            {expanded ? (
              <>
                <ChevronUp className="mr-1.5 h-3.5 w-3.5" />
                Hide
              </>
            ) : (
              <>
                <ChevronDown className="mr-1.5 h-3.5 w-3.5" />
                Run sync
              </>
            )}
          </Button>
        </div>
        {expanded && (
          <div className="rounded-lg border border-border bg-muted/20 p-4">
            {children}
          </div>
        )}
      </div>
    </SectionCard>
  );
}

function LockedConnectorCard({ stub }: { stub: EnterpriseConnectorStub }) {
  const [showDetail, setShowDetail] = React.useState(false);

  return (
    <SectionCard className="overflow-hidden border-dashed border-amber-500/30 bg-muted/20">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Lock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold tracking-tight">{stub.name}</h3>
                <Badge
                  variant="outline"
                  className="text-[10px] font-semibold uppercase tracking-wide"
                >
                  Enterprise only
                </Badge>
              </div>
              <p className="mt-0.5 text-sm text-muted-foreground">{stub.description}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Not available in Community Edition.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={() => setShowDetail((v) => !v)}
          >
            {showDetail ? "Hide" : "Why locked?"}
          </Button>
        </div>
        {showDetail ? <EnterpriseUpsell feature={stub.feature} compact /> : null}
      </div>
    </SectionCard>
  );
}

function EntraSyncForm() {
  const [tenantId, setTenantId] = React.useState("");
  const [clientId, setClientId] = React.useState("");
  const [clientSecret, setClientSecret] = React.useState("");
  const [customerId, setCustomerId] = React.useState("");
  const { addToast } = useToast();
  const entraSync = useEntraSync();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = tenantId.trim();
    const c = clientId.trim();
    const s = clientSecret.trim();
    if (!t || !c || !s) {
      addToast({ variant: "warning", title: "Missing fields", description: "Tenant ID, Client ID, and Client Secret are required." });
      return;
    }
    entraSync.mutate(
      {
        tenant_id: t,
        client_id: c,
        client_secret: s,
        customer_id: customerId.trim() || undefined,
      },
      {
        onSuccess: (data: ConnectorSyncResponse) => {
          if (data.errors.length > 0 && data.synced === 0) {
            addToast({
              variant: "error",
              title: "Entra sync failed",
              description: data.errors.slice(0, 2).join(" "),
            });
          } else {
            addToast({
              variant: "success",
              title: "Entra sync complete",
              description: `Synced ${data.synced} app(s). ${data.errors.length ? `${data.errors.length} error(s).` : ""}`,
            });
          }
        },
        onError: (err: Error) => {
          addToast({ variant: "error", title: "Entra sync failed", description: err.message });
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label htmlFor="entra-tenant" className="text-sm font-medium">
            Tenant ID
          </label>
          <input
            id="entra-tenant"
            type="text"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            autoComplete="off"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="entra-client" className="text-sm font-medium">
            Client ID
          </label>
          <input
            id="entra-client"
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Application (client) ID"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            autoComplete="off"
          />
        </div>
      </div>
      <div className="space-y-2">
        <label htmlFor="entra-secret" className="text-sm font-medium">
          Client secret
        </label>
        <input
          id="entra-secret"
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          placeholder="Client secret value"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          autoComplete="off"
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="entra-customer" className="text-sm font-medium text-muted-foreground">
          Customer ID (optional)
        </label>
        <input
          id="entra-customer"
          type="text"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          placeholder="Tag for this tenant"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      </div>
      <Button type="submit" disabled={entraSync.isPending}>
        {entraSync.isPending ? (
          <>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            Syncing…
          </>
        ) : (
          <>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Sync from Entra
          </>
        )}
      </Button>
      {entraSync.data && (
        <SyncResult data={entraSync.data} />
      )}
    </form>
  );
}

function SlackSyncForm() {
  const [token, setToken] = React.useState("");
  const [customerId, setCustomerId] = React.useState("");
  const { addToast } = useToast();
  const slackSync = useSlackSync();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = token.trim();
    if (!t) {
      addToast({ variant: "warning", title: "Missing token", description: "Slack bot or user token is required." });
      return;
    }
    slackSync.mutate(
      { token: t, customer_id: customerId.trim() || undefined },
      {
        onSuccess: (data: ConnectorSyncResponse) => {
          if (data.errors.length > 0 && data.synced === 0) {
            addToast({
              variant: "error",
              title: "Slack sync failed",
              description: data.errors.slice(0, 2).join(" "),
            });
          } else {
            addToast({
              variant: "success",
              title: "Slack sync complete",
              description: `Synced ${data.synced} integration(s). ${data.errors.length ? `${data.errors.length} error(s).` : ""}`,
            });
          }
        },
        onError: (err: Error) => {
          addToast({ variant: "error", title: "Slack sync failed", description: err.message });
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="slack-token" className="text-sm font-medium">
          Bot or user token
        </label>
        <input
          id="slack-token"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="xoxb-… or xoxp-…"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 font-mono"
          autoComplete="off"
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="slack-customer" className="text-sm font-medium text-muted-foreground">
          Customer ID (optional)
        </label>
        <input
          id="slack-customer"
          type="text"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          placeholder="Tag for this workspace"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      </div>
      <Button type="submit" disabled={slackSync.isPending}>
        {slackSync.isPending ? (
          <>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            Syncing…
          </>
        ) : (
          <>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Sync from Slack
          </>
        )}
      </Button>
      {slackSync.data && (
        <SyncResult data={slackSync.data} />
      )}
    </form>
  );
}

function SyncResult({ data }: { data: ConnectorSyncResponse }) {
  return (
    <div className="mt-4 space-y-3 rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        {data.synced > 0 ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        ) : data.errors.length > 0 ? (
          <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
        ) : null}
        {data.synced} integration(s) synced
      </div>
      {data.scans.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Stored scans</p>
          <ul className="space-y-1">
            {data.scans.map((s) => (
              <li
                key={s.scan_id}
                className="flex items-center justify-between gap-2 rounded border border-border bg-muted/20 px-2 py-1.5 text-sm"
              >
                <span className="truncate font-mono">{s.target}</span>
                <ScoreBadge value={s.risk_score} kind="risk" />
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.errors.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Errors</p>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-muted-foreground">
            {data.errors.slice(0, 5).map((err, i) => (
              <li key={i}>{err}</li>
            ))}
            {data.errors.length > 5 && (
              <li>… and {data.errors.length - 5} more</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ConnectorsPage() {
  const { isCommunity } = useEditionContext();
  const { data, isLoading, isError, error, refetch, isRefetching } = useConnectors();
  const connectors = (data?.connectors ?? []).filter(
    (c) => c.id === "entra" || c.id === "slack",
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Connectors"
        description="Sync OAuth and app data from Microsoft Entra and Slack. Each sync runs the risk pipeline and stores results."
      >
        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </PageHeader>

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      )}

      {isError && (
        <QueryErrorCard
          title="Failed to load connectors"
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => refetch()}
          isRetrying={isRefetching}
        />
      )}

      {!isLoading && !isError && connectors.length === 0 && (
        <EmptyState
          icon={<Plug className="h-10 w-10" />}
          title="No connectors available"
          description="Connectors will appear here when the API exposes them. Ensure the backend is running and /connectors is configured."
        />
      )}

      {!isLoading && !isError && connectors.length > 0 && (
        <div className="space-y-4">
          {connectors.map((c) => (
            <ConnectorCard key={c.id} connector={c}>
              {c.id === "entra" && <EntraSyncForm />}
              {c.id === "slack" && <SlackSyncForm />}
            </ConnectorCard>
          ))}
          {isCommunity
            ? ENTERPRISE_CONNECTOR_STUBS.map((stub) => (
                <LockedConnectorCard key={stub.id} stub={stub} />
              ))
            : null}
        </div>
      )}
    </div>
  );
}
