"use client";

import Link from "next/link";
import { Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ENTERPRISE_FEATURE_COPY,
  ENTERPRISE_LEARN_MORE_URL,
  type EnterpriseFeatureKey,
} from "@/config/enterprise-features";

interface EnterpriseUpsellProps {
  feature?: EnterpriseFeatureKey;
  compact?: boolean;
}

export function EnterpriseUpsell({
  feature = "default",
  compact = false,
}: EnterpriseUpsellProps) {
  const copy = ENTERPRISE_FEATURE_COPY[feature] ?? ENTERPRISE_FEATURE_COPY.default;

  if (compact) {
    return (
      <div
        className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 px-4 py-3"
        role="status"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Lock className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
          <span className="text-sm font-medium text-foreground">{copy.title}</span>
          <Badge variant="outline" className="text-[10px] font-semibold uppercase tracking-wide">
            Enterprise only
          </Badge>
        </div>
        <p className="mt-1.5 text-sm text-muted-foreground">{copy.description}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Not available in Community Edition.
        </p>
      </div>
    );
  }

  return (
    <section
      className="mx-auto max-w-2xl rounded-xl border bg-card p-8 shadow-sm"
      aria-labelledby="enterprise-upsell-title"
    >
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        SaaSShadow Enterprise
      </p>
      <h2 id="enterprise-upsell-title" className="mt-2 text-2xl font-bold tracking-tight">
        {copy.title}
      </h2>
      <p className="mt-2 text-muted-foreground">{copy.description}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        <Badge className="bg-amber-600/90 hover:bg-amber-600/90">Enterprise only</Badge>
        <Badge variant="outline">Not in Community Edition</Badge>
      </div>

      <p className="mt-4 text-sm text-muted-foreground">
        Community Edition includes integration scanning, scan history, JSON and PDF
        reports, Entra and Slack connectors, the read-only ISPM catalog, YAML rules,
        and the basic dashboard. Enterprise adds the capabilities above plus extended
        connectors and custom report branding.
      </p>

      <div className="mt-6 flex flex-wrap gap-3">
        <Button variant="outline" asChild>
          <Link href="/dashboard">Back to Dashboard</Link>
        </Button>
        <Button asChild>
          <a href={ENTERPRISE_LEARN_MORE_URL} target="_blank" rel="noreferrer">
            Learn about Enterprise
          </a>
        </Button>
      </div>
    </section>
  );
}
