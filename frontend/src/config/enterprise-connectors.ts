import type { EnterpriseFeatureKey } from "@/config/enterprise-features";

export interface EnterpriseConnectorStub {
  id: string;
  name: string;
  description: string;
  feature: EnterpriseFeatureKey;
}

export const ENTERPRISE_CONNECTOR_STUBS: EnterpriseConnectorStub[] = [
  {
    id: "google_workspace",
    name: "Google Workspace",
    description: "Sync OAuth grants and app access from Google Workspace.",
    feature: "connectorGoogle",
  },
  {
    id: "okta",
    name: "Okta",
    description: "Pull Okta applications and scopes into scan history.",
    feature: "connectorOkta",
  },
  {
    id: "github",
    name: "GitHub",
    description: "Discover GitHub app installations and token scopes.",
    feature: "connectorGithub",
  },
  {
    id: "atlassian",
    name: "Atlassian",
    description: "Sync Jira and Atlassian cloud integrations.",
    feature: "connectorAtlassian",
  },
];
