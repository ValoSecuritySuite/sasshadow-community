import { PageHeader } from "@/components/layout/page-header";
import { EnterpriseGate } from "@/components/enterprise/enterprise-gate";
import type { EnterpriseFeatureKey } from "@/config/enterprise-features";

interface EnterprisePageProps {
  feature: EnterpriseFeatureKey;
  title: string;
  description: string;
}

export function EnterprisePage({ feature, title, description }: EnterprisePageProps) {
  return (
    <div className="space-y-6">
      <PageHeader title={title} description={description} />
      <EnterpriseGate feature={feature} />
    </div>
  );
}
