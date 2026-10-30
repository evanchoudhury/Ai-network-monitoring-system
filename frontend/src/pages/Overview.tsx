import { useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  BadgeCheck,
  FileText,
  Gauge,
  MailWarning,
  Radar,
  ShieldAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Anomaly, MapData, MetricPoint, Overview } from "../lib/types";
import { AsyncBoundary, SectionCard } from "../components/ui";
import { KpiCard } from "../components/KpiCard";
import { PageHeader, AlertRow } from "../components/shared";
import { AnomalyTimelineChart, TrafficChart } from "../components/charts";
import { NetworkMap } from "../components/NetworkMap";
import { formatBytes, formatMs, formatNumber, formatUsd } from "../lib/format";
import { useAuth } from "../auth";

export default function OverviewPage() {
  const { isAdmin } = useAuth();
  const [animate, setAnimate] = useState(true);
  const ov = useApi<Overview>(() => api.get<Overview>("/overview"), [], { pollMs: 30000 });
  const traffic = useApi<{ inbound: MetricPoint[]; outbound: MetricPoint[] }>(
    () => api.get("/metrics/traffic?hours=24"),
    []
  );
  const mapData = useApi<MapData>(() => api.get<MapData>("/map?hours=24"), []);
  const anomalyHist = useApi<MetricPoint[]>(
    async () => (await api.get<{ points: MetricPoint[] }>("/metrics/history?metric=request_rate&hours=24")).points,
    []
  );
  const anomalies = useApi<Anomaly[]>(() => api.get<Anomaly[]>("/anomalies?hours=24"), []);

  async function generateDemo() {
    await api.post("/admin/demo/generate");
    ov.refetch();
    traffic.refetch();
    mapData.refetch();
    anomalyHist.refetch();
    anomalies.refetch();
  }

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Unified network, threat, and truth-intelligence posture."
        demo={ov.data?.mode.mode === "demo"}
        actions={
          ov.data?.mode.mode === "empty" && isAdmin ? (
            <button className="btn-primary" onClick={generateDemo}>
              Generate demo data
            </button>
          ) : undefined
        }
      />

      <AsyncBoundary
        state={ov}
        emptyProps={{
          title: "No data collected yet",
          hint: isAdmin
            ? "Generate demo data to explore the dashboard, or connect a live source under Data Sources."
            : "Sign in as an operator (Settings) to generate demo data or connect a live source.",
        }}
      >
        {(o) => (
          <div className="space-y-5">
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
              <KpiCard label="Inbound Traffic (24h)" value={formatBytes(o.kpis.incoming_bytes_24h)}
                icon={<ArrowDownToLine className="h-5 w-5" />} accent="#338BFF" />
              <KpiCard label="Outbound Traffic (24h)" value={formatBytes(o.kpis.outgoing_bytes_24h)}
                icon={<ArrowUpFromLine className="h-5 w-5" />} accent="#20D9F2" />
              <KpiCard label="Requests / sec" value={formatNumber(o.kpis.requests_per_second)}
                icon={<Activity className="h-5 w-5" />} accent="#13D6C1" />
              <KpiCard label="Active Alerts" value={o.kpis.active_alerts}
                icon={<ShieldAlert className="h-5 w-5" />} accent="#FF5268" />
              <KpiCard label="Claims Under Review" value={o.kpis.claims_awaiting_review}
                icon={<FileText className="h-5 w-5" />} accent="#338BFF" />
              <KpiCard label="Avg Latency p95" value={formatMs(o.kpis.avg_latency_p95_ms)}
                icon={<Gauge className="h-5 w-5" />} accent="#FFBF47" />
              <KpiCard label="Anomalies (24h)" value={o.kpis.anomalies_24h}
                icon={<Radar className="h-5 w-5" />} accent="#FFBF47" />
              <KpiCard label="Articles Collected" value={formatNumber(o.kpis.articles_collected)}
                icon={<FileText className="h-5 w-5" />} accent="#20D9F2" />
              <KpiCard label="Spam Detections" value={o.kpis.spam_detections}
                icon={<MailWarning className="h-5 w-5" />} accent="#FF5268" />
              <KpiCard label="Monitored Services" value={o.kpis.monitored_services}
                icon={<BadgeCheck className="h-5 w-5" />} accent="#20D99A" />
            </div>

            {/* Charts + map */}
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              <div className="space-y-4 xl:col-span-1">
                <SectionCard title="Real-Time Network Traffic" bodyClassName="px-1">
                  {traffic.data ? (
                    <TrafficChart inbound={traffic.data.inbound} outbound={traffic.data.outbound} />
                  ) : (
                    <div className="h-[230px]" />
                  )}
                </SectionCard>
                <SectionCard title="Network Anomaly Timeline" bodyClassName="px-1">
                  {anomalyHist.data ? (
                    <AnomalyTimelineChart
                      points={anomalyHist.data}
                      anomalies={(anomalies.data ?? []).map((a) => ({
                        window_end: a.window_end,
                        observed_value: a.observed_value,
                      }))}
                    />
                  ) : (
                    <div className="h-[220px]" />
                  )}
                </SectionCard>
              </div>

              <SectionCard
                className="xl:col-span-2"
                title="Global Network Activity"
                action={
                  mapData.data?.contains_demo_data ? (
                    <span className="chip border border-warning/40 bg-warning/10 text-[10px] uppercase tracking-wider text-warning">
                      Demo Data
                    </span>
                  ) : (
                    <Link to="/map" className="text-xs text-cyan hover:underline">
                      Open full map →
                    </Link>
                  )
                }
                bodyClassName="p-2"
              >
                {mapData.data ? (
                  <NetworkMap
                    nodes={mapData.data.nodes}
                    connections={mapData.data.connections}
                    animate={animate}
                    onToggleAnimate={() => setAnimate((a) => !a)}
                    height={430}
                  />
                ) : (
                  <div className="h-[430px]" />
                )}
                {mapData.data && (
                  <div className="mt-2 grid grid-cols-4 gap-2 px-2 text-center">
                    <Mini label="Monitored" value={mapData.data.counts.nodes} />
                    <Mini label="Countries" value={mapData.data.counts.countries} />
                    <Mini label="Connections" value={mapData.data.counts.connections} />
                    <Mini label="Suspicious" value={mapData.data.counts.suspicious} accent="#FF5268" />
                  </div>
                )}
              </SectionCard>
            </div>

            {/* Lower row: alerts + AI usage */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <SectionCard
                className="lg:col-span-2"
                title="Recent Alerts"
                action={<Link to="/threats" className="text-xs text-cyan hover:underline">View all →</Link>}
                bodyClassName="py-1"
              >
                {o.recent_alerts.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted">No alerts recorded.</p>
                ) : (
                  o.recent_alerts.map((a) => <AlertRow key={a.id} alert={a} compact />)
                )}
              </SectionCard>

              <SectionCard title="AI Usage & Estimated Cost">
                <div className="space-y-3">
                  <UsageRow label="Model requests today" value={formatNumber(o.ai_usage.day_requests)} />
                  <UsageRow label="Tokens today" value={formatNumber(o.ai_usage.day_tokens)} />
                  <UsageRow label="Est. cost today" value={formatUsd(o.ai_usage.estimated_day_cost_usd)} />
                  <UsageRow label="Est. cost this month" value={formatUsd(o.ai_usage.estimated_month_cost_usd)} />
                  <p className="rounded-lg border border-border bg-bg/60 p-2 text-[11px] leading-relaxed text-muted">
                    {o.ai_usage.note}
                  </p>
                </div>
              </SectionCard>
            </div>
          </div>
        )}
      </AsyncBoundary>
    </div>
  );
}

function Mini({ label, value, accent = "#ECF5FF" }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg/50 py-1.5">
      <div className="font-mono text-base font-semibold" style={{ color: accent }}>
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
    </div>
  );
}

function UsageRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/50 pb-2 text-sm last:border-0">
      <span className="text-muted">{label}</span>
      <span className="font-mono font-semibold text-text">{value}</span>
    </div>
  );
}
