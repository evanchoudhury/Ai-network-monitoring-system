import type { ClaimLabel, Severity } from "./types";

export const SEVERITY_COLOR: Record<Severity, string> = {
  info: "#8DA4BC",
  low: "#20D99A",
  medium: "#FFBF47",
  high: "#FF8A3D",
  critical: "#FF5268",
};

export const SEVERITY_BG: Record<Severity, string> = {
  info: "bg-muted/15 text-muted",
  low: "bg-success/15 text-success",
  medium: "bg-warning/15 text-warning",
  high: "bg-[#FF8A3D]/15 text-[#FF8A3D]",
  critical: "bg-critical/15 text-critical",
};

export const CLAIM_LABEL_META: Record<
  ClaimLabel,
  { label: string; className: string }
> = {
  supported: { label: "Supported by evidence", className: "bg-success/15 text-success" },
  contradicted: { label: "Contradicted", className: "bg-critical/15 text-critical" },
  misleading: { label: "Misleading / missing context", className: "bg-warning/15 text-warning" },
  disputed: { label: "Disputed", className: "bg-[#FF8A3D]/15 text-[#FF8A3D]" },
  unverified: { label: "Unverified", className: "bg-muted/15 text-muted" },
  insufficient_evidence: {
    label: "Insufficient evidence",
    className: "bg-blue/15 text-blue",
  },
};

export const NODE_COLOR: Record<string, string> = {
  cyan: "#20D9F2",
  blue: "#338BFF",
  amber: "#FFBF47",
  red: "#FF5268",
};

export interface NavItem {
  path: string;
  label: string;
  icon: string; // lucide icon name
}

export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Overview", icon: "LayoutDashboard" },
  { path: "/map", label: "Global Network Map", icon: "Globe" },
  { path: "/traffic", label: "Network Traffic", icon: "Activity" },
  { path: "/threats", label: "Security Threats", icon: "ShieldAlert" },
  { path: "/news", label: "News Intelligence", icon: "Newspaper" },
  { path: "/claims", label: "Claim Verification", icon: "BadgeCheck" },
  { path: "/spam", label: "Spam & Phishing", icon: "MailWarning" },
  { path: "/reports", label: "Reports", icon: "FileBarChart" },
  { path: "/sources", label: "Data Sources", icon: "Database" },
  { path: "/health", label: "System Health", icon: "HeartPulse" },
  { path: "/budget", label: "Budget & Usage", icon: "Gauge" },
  { path: "/settings", label: "Settings", icon: "Settings" },
];
