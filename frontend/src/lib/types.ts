// Shared API response types for Sentinel AI.

export type Mode = "live" | "live_stale" | "demo" | "empty";

export interface ModeInfo {
  mode: Mode;
  live_metrics_24h: number;
  has_demo_data: boolean;
  last_live_metric_at: string | null;
}

export interface Overview {
  mode: ModeInfo;
  generated_at: string;
  kpis: {
    incoming_bytes_24h: number;
    outgoing_bytes_24h: number;
    requests_per_second: number;
    avg_latency_p95_ms: number | null;
    error_rate: number | null;
    active_alerts: number;
    anomalies_24h: number;
    articles_collected: number;
    claims_awaiting_review: number;
    spam_detections: number;
    monitored_services: number;
  };
  ai_usage: {
    day_requests: number;
    day_tokens: number;
    estimated_day_cost_usd: number;
    estimated_month_cost_usd: number;
    note: string;
  };
  recent_alerts: Alert[];
}

export interface Alert {
  id: number;
  created_at: string;
  severity: Severity;
  category: string;
  source: string | null;
  title: string;
  explanation: string;
  evidence: Record<string, unknown> | null;
  related: Record<string, unknown> | null;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface MetricPoint {
  timestamp: string;
  value: number;
  service_id: number | null;
  is_demo: boolean;
}

export interface MapNode {
  id: number;
  name: string;
  country: string | null;
  city: string | null;
  color: "cyan" | "blue" | "amber" | "red";
  kind: string;
  request_rate: number | null;
  error_rate: number | null;
  latency_p95_ms: number | null;
  available: boolean | null;
  is_demo: boolean;
  last_seen: string | null;
  lat: number;
  lon: number;
}

export interface MapConnection {
  id: number;
  src: { id: number; name: string; lat: number; lon: number };
  dst: { id: number; name: string; lat: number; lon: number };
  bytes: number | null;
  count: number;
  suspicious: boolean;
  is_demo: boolean;
  style: "normal" | "attack";
}

export interface MapData {
  nodes: MapNode[];
  connections: MapConnection[];
  unlocated: MapNode[];
  legend: Record<string, string>;
  counts: {
    nodes: number;
    connections: number;
    countries: number;
    suspicious: number;
    unlocated: number;
  };
  contains_demo_data: boolean;
  window_hours: number;
  mode: ModeInfo;
}

export interface Anomaly {
  id: number;
  service_id: number | null;
  metric: string;
  observed_value: number;
  baseline_mean: number | null;
  baseline_std: number | null;
  zscore: number | null;
  method: string;
  severity: Severity;
  explanation: string;
  confirmed_attack: boolean;
  is_demo: boolean;
  window_start: string | null;
  window_end: string | null;
  detected_at: string;
}

export interface Article {
  id: number;
  headline: string;
  publisher: string | null;
  url: string;
  topic: string | null;
  language: string | null;
  summary: string | null;
  story_id: number | null;
  published_at: string | null;
  ingested_at: string;
}

export interface Story {
  id: number;
  title: string;
  topic: string | null;
  article_count: number;
  source_diversity: number;
  first_seen: string;
  last_updated: string;
}

export type ClaimLabel =
  | "supported"
  | "contradicted"
  | "misleading"
  | "disputed"
  | "unverified"
  | "insufficient_evidence";

export interface Evidence {
  url: string;
  title: string | null;
  publisher: string | null;
  snippet: string | null;
  stance: "support" | "contradict" | "context";
  relevance: number;
  provider: string;
  evidence_timestamp: string | null;
  retrieved_at: string;
}

export interface Claim {
  id: number;
  article_id: number;
  text: string;
  entities: Record<string, string[]> | null;
  status: ClaimLabel;
  needs_review: boolean;
  created_at: string;
  assessment: {
    label: ClaimLabel;
    explanation: string;
    limitations: string;
    supporting_count: number;
    contradicting_count: number;
    model_version: string;
    reviewed_by: string | null;
    created_at: string;
  } | null;
  evidence?: Evidence[];
}

export interface SpamResult {
  category: "clean" | "low_risk" | "suspicious" | "high_risk" | "phishing";
  score: number;
  score_is_calibrated: boolean;
  indicators: { name: string; weight: number; detail: string }[];
  urls: { url: string; host: string; flags: string[] }[];
  explanation: string;
  recommendation: string;
  model_version: string;
}

export interface SpamRecord extends SpamResult {
  id: number;
  created_at: string;
  preview: string;
  source: string;
}

export interface Source {
  id: number;
  name: string;
  source_type: string;
  url: string | null;
  enabled: boolean;
  authorized: boolean;
  last_status: string | null;
  last_error: string | null;
  last_ingested_at: string | null;
  config: Record<string, unknown> | null;
}

export interface HealthReport {
  overall: "ok" | "degraded" | "down";
  mode: ModeInfo;
  components: { component: string; status: string; detail: string | null; latency_ms: number | null }[];
  last_errors: { component: string; status: string; detail: string | null; at: string }[];
  generated_at: string;
}

export interface Budget {
  within_budget: boolean;
  day_requests: number;
  day_tokens: number;
  estimated_day_cost_usd: number;
  estimated_month_cost_usd: number;
  limits: Record<string, number>;
  notes: string[];
  resource_controls: Record<string, number | boolean>;
  disclaimer: string;
}

export interface ServiceInfo {
  id: number;
  name: string;
  description: string | null;
  country: string | null;
  city: string | null;
  lat: number | null;
  lon: number | null;
  authorized: boolean;
  is_demo: boolean;
  latest: Record<string, unknown> | null;
}
