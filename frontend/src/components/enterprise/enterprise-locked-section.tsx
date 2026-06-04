"use client";

import { Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useEditionContext } from "@/contexts/edition-context";
import {
  ENTERPRISE_FEATURE_COPY,
  ENTERPRISE_LEARN_MORE_URL,
  type EnterpriseFeatureKey,
} from "@/config/enterprise-features";

interface EnterpriseLockedSectionProps {
  feature: EnterpriseFeatureKey;
  title: string;
  description?: string;
  children?: React.ReactNode;
}

/** Shows children in Enterprise; locked placeholder in Community. */
export function EnterpriseLockedSection({
  feature,
  title,
  description,
  children,
}: EnterpriseLockedSectionProps) {
  const { isCommunity } = useEditionContext();
  const copy = ENTERPRISE_FEATURE_COPY[feature] ?? ENTERPRISE_FEATURE_COPY.default;

  if (!isCommunity) {
    return <>{children}</>;
  }

  return (
    <div className="relative rounded-xl border border-dashed border-amber-500/35 bg-muted/30 p-6">
      <div className="pointer-events-none select-none opacity-50 blur-[1px]">
        {children ?? (
          <div className="space-y-3">
            <div className="h-10 w-full rounded-md bg-muted" />
            <div className="h-10 w-2/3 rounded-md bg-muted" />
          </div>
        )}
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl bg-background/80 px-4 text-center backdrop-blur-[2px]">
        <Lock className="h-5 w-5 text-amber-600 dark:text-amber-400" aria-hidden />
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="max-w-md text-xs text-muted-foreground">
          {description ?? copy.description}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Badge variant="outline" className="text-[10px] font-semibold uppercase">
            Enterprise only
          </Badge>
          <span className="text-[11px] text-muted-foreground">
            Not in Community Edition
          </span>
        </div>
        <a
          href={ENTERPRISE_LEARN_MORE_URL}
          className="text-xs font-medium text-primary underline-offset-4 hover:underline"
          target="_blank"
          rel="noreferrer"
        >
          Learn about Enterprise
        </a>
      </div>
    </div>
  );
}
