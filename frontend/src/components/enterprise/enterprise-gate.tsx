"use client";

import { useEditionContext } from "@/contexts/edition-context";
import { EnterpriseUpsell } from "@/components/enterprise/enterprise-upsell";
import type { EnterpriseFeatureKey } from "@/config/enterprise-features";

interface EnterpriseGateProps {
  feature: EnterpriseFeatureKey;
  children?: React.ReactNode;
}

export function EnterpriseGate({ feature, children }: EnterpriseGateProps) {
  const { isCommunity, isLoading } = useEditionContext();

  if (isLoading) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
        Loading edition…
      </div>
    );
  }

  if (isCommunity) {
    return <EnterpriseUpsell feature={feature} />;
  }

  return <>{children}</>;
}
