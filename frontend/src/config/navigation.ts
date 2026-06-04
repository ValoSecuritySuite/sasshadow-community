import {
  LayoutDashboard,
  Search,
  Database,
  History,
  BookOpen,
  Puzzle,
  Plug,
  HeartPulse,
  ShieldCheck,
  Settings,
  LineChart,
  Network,
  Wrench,
  Workflow,
  GitBranch,
  FileBarChart,
  Sparkles,
  Shield,
  type LucideIcon,
} from "lucide-react";
import type { EnterpriseFeatureKey } from "@/config/enterprise-features";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  disabled?: boolean;
  /** Visible in Community but requires Enterprise to use. */
  enterpriseOnly?: boolean;
  enterpriseFeature?: EnterpriseFeatureKey;
}

export interface NavGroup {
  label: string;
  enterpriseOnly?: boolean;
  items: NavItem[];
}

export const navigation: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      {
        title: "Executive Dashboard",
        href: "/executive",
        icon: LineChart,
        enterpriseOnly: true,
        enterpriseFeature: "executive",
      },
    ],
  },
  {
    label: "Analysis",
    items: [
      { title: "Single Scan", href: "/scan", icon: Search },
      { title: "Dataset Analysis", href: "/datasets", icon: Database },
      { title: "Scan History", href: "/scans", icon: History },
      { title: "ISPM Catalog", href: "/ispm", icon: ShieldCheck },
      {
        title: "ISPM Posture",
        href: "/ispm/posture",
        icon: Shield,
        enterpriseOnly: true,
        enterpriseFeature: "ispmPosture",
      },
      {
        title: "SaaS Map",
        href: "/saas-map",
        icon: Network,
        enterpriseOnly: true,
        enterpriseFeature: "saasMap",
      },
    ],
  },
  {
    label: "Operations",
    enterpriseOnly: true,
    items: [
      {
        title: "Remediation",
        href: "/remediation",
        icon: Wrench,
        enterpriseOnly: true,
        enterpriseFeature: "remediation",
      },
      {
        title: "Playbooks",
        href: "/playbooks",
        icon: Workflow,
        enterpriseOnly: true,
        enterpriseFeature: "playbooks",
      },
      {
        title: "Correlations",
        href: "/correlations",
        icon: GitBranch,
        enterpriseOnly: true,
        enterpriseFeature: "correlations",
      },
    ],
  },
  {
    label: "Reporting",
    enterpriseOnly: true,
    items: [
      {
        title: "Automated Reports",
        href: "/reports",
        icon: FileBarChart,
        enterpriseOnly: true,
        enterpriseFeature: "reports",
      },
      {
        title: "Learning Loop",
        href: "/learning",
        icon: Sparkles,
        enterpriseOnly: true,
        enterpriseFeature: "learning",
      },
    ],
  },
  {
    label: "Configuration",
    items: [
      { title: "Rules", href: "/rules", icon: BookOpen },
      { title: "Plugins", href: "/plugins", icon: Puzzle },
      { title: "Connectors", href: "/connectors", icon: Plug },
    ],
  },
  {
    label: "System",
    items: [
      { title: "Health", href: "/health", icon: HeartPulse },
      { title: "Settings", href: "/settings", icon: Settings },
    ],
  },
];
