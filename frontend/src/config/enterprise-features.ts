export type EnterpriseFeatureKey =
  | "executive"
  | "saasMap"
  | "remediation"
  | "playbooks"
  | "correlations"
  | "reports"
  | "learning"
  | "ispmPosture"
  | "branding"
  | "connectorGoogle"
  | "connectorOkta"
  | "connectorGithub"
  | "connectorAtlassian"
  | "default";

export interface EnterpriseFeatureCopy {
  title: string;
  description: string;
}

export const ENTERPRISE_FEATURE_COPY: Record<
  EnterpriseFeatureKey,
  EnterpriseFeatureCopy
> = {
  executive: {
    title: "Executive Dashboard",
    description:
      "Posture rollups, top SaaS providers, compliance signals, automation activity, and board-ready PDF packs across your tenant.",
  },
  saasMap: {
    title: "SaaS Mapping Engine",
    description:
      "Tenant-wide graph of SaaS integrations, data flows, and provider relationships for portfolio visibility.",
  },
  remediation: {
    title: "Automated Remediation",
    description:
      "Local execution engine and remediation actions to close risky integrations without leaving the platform.",
  },
  playbooks: {
    title: "Response Playbooks",
    description:
      "Playbook runs and an inbound action inbox to coordinate response workflows across your security team.",
  },
  correlations: {
    title: "Cross-Tool Correlation",
    description:
      "Correlate SaaSShadow findings with signals from your broader security stack for unified investigation.",
  },
  reports: {
    title: "Reporting Automation",
    description:
      "Scheduled reports, a report store, and automated executive PDF delivery on a cadence you define.",
  },
  learning: {
    title: "Learning Loop",
    description:
      "Feedback dispositions and rule-tuning proposals that refine detection using analyst outcomes.",
  },
  ispmPosture: {
    title: "ISPM Posture Management",
    description:
      "Per-tenant ISPM overrides, integration posture rollups, and admin writes beyond the read-only catalog.",
  },
  branding: {
    title: "Custom Report Branding",
    description:
      "Company name and logo on exported PDF reports for customer-ready deliverables.",
  },
  connectorGoogle: {
    title: "Google Workspace Connector",
    description:
      "Sync OAuth and app grants from Google Workspace into scan history automatically.",
  },
  connectorOkta: {
    title: "Okta Connector",
    description:
      "Pull Okta application and scope data into SaaSShadow for continuous integration monitoring.",
  },
  connectorGithub: {
    title: "GitHub Connector",
    description:
      "Discover GitHub app installations and token scopes tied to your SaaS risk posture.",
  },
  connectorAtlassian: {
    title: "Atlassian Connector",
    description:
      "Sync Jira and Atlassian cloud app integrations for cross-platform risk analysis.",
  },
  default: {
    title: "SaaSShadow Enterprise",
    description:
      "This capability is not included in Community Edition. Upgrade to SaaSShadow Enterprise to enable it.",
  },
};

export const ENTERPRISE_LEARN_MORE_URL =
  "https://github.com/valo-ai/sasshadow-community#enterprise";
