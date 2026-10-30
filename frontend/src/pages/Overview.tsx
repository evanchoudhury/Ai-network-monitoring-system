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
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Anomaly, MapData, MetricPoint, Overview } from "../lib/types";
import { AsyncBoundary, EmptyState, SectionCard, StatusBanner } from "../components/ui";
import { KpiCard } from "../components/KpiCard";
import { PageHeader, AlertRow } from "../components/shared";
import { AnomalyTimelineChart, TrafficChart } from "../components/charts";
import { NetworkMap } from "../components/NetworkMap";
import { formatBytes, formatMs, formatNumber, formatUsd, timeAgo } from "../lib/format";

export default function OverviewPage() {
  const [animate, setAnimate] = useState(true);
  // Auto-refresh every 30s (bounded polling — no excessive traffic).
  const ov = useApi<Overview>(() => api.get<Overview>("/overview"), [], { pollMs: 30000 });
  const traffic = useApi<{ inbound: MetricPoint[]; outbound: MetricPoint[] }>(
    () => api.get("/metrics/traffic?hours=24"),
    [],
    { pollMs: 30000 }
  );
  const mapData = useApi<MapData>(() => api.get<MapData>("/map?hours=24"), [], { pollMs: 60000 });
  const anomalyHist = useApi<MetricPoint[]>(
    async () => (await api.get<{ points: MetricPoint[] }>("/metrics/history?metric=request_rate&hours=24")).points,
    [],
    { pollMs: 60000 }
  );
  const anomalies = useApi<Anomaly[]>(() => api.get<Anomaly[]>("/anomalies?hours=24"), [], { pollMs: 60000 });

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Unified network, threat, and truth-intelligence posture — live data only."
        actions={
          <button className="btn" onClick={() => { ov.refetch(); traffic.refetch(); mapData.refetch(); anomalies.refetch(); }}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        }
      />

      <AsyncBoundary state={ov}>
        {(o) => {
          const hasTraffic = (traffic.data?.inbound.length ?? 0) > 0;
          return (
            <div className="space-y-5">
              {/* Honest banner when no network source is configured/connected */}
              <StatusBanner status={o.status.network} />

              <div className="flex items-center justify-between text-xs text-muted">
                <span>
                  Auto-refreshing · last updated {timeAgo(o.generated_at)}
                </span>
                <span>{o.status.operational ? "Receiving live data" : "Awaiting live data"}</span>
              </div>

              {/* KPI row — null values render as "—" (No data), never fake 0 */}
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
                  <SectionCard title="Network Traffic (24h)" bodyClassName="px-1">
                    {hasTraffic ? (
                      <TrafficChart inbound={traffic.data!.inbound} outbound={traffic.data!.outbound} />
                    ) : (
                      <EmptyState title="No data available"
                        hint={o.status.network.configured
                          ? o.status.network.detail
                          : "Connect a metrics source to see traffic."} />
                    )}
                  </SectionCard>
                  <SectionCard title="Network Anomaly Timeline" bodyClassName="px-1">
                    {(anomalyHist.data?.length ?? 0) > 0 ? (
                      <AnomalyTimelineChart
                        points={anomalyHist.data!}
                        anomalies={(anomalies.data ?? []).map((a) => ({
                          window_end: a.window_end, observed_value: a.observed_value,
                        }))}
                      />
                    ) : (
                      <EmptyState title="No data available"
                        hint="Anomaly detection runs on collected metrics." />
                    )}
                  </SectionCard>
                </div>

                <SectionCard
                  className="xl:col-span-2"
                  title="Global Network Activity"
                  action={<Link to="/map" className="text-xs text-cyan hover:underline">Open full map →</Link>}
                  bodyClassName="p-2"
                >
                  {mapData.data ? (
                    (mapData.data.nodes.length > 0 || mapData.data.connections.length > 0) ? (
                      <NetworkMap
                        nodes={mapData.data.nodes}
                        connections={mapData.data.connections}
                        animate={animate}
                        onToggleAnimate={() => setAnimate((a) => !a)}
                        height={430}
                      />
                    ) : (
                      <div className="flex h-[430px] items-center justify-center p-6 text-center">
                        <EmptyState title="No connection data"
                          hint={mapData.data.empty_reason ?? undefined} />
                      </div>
                    )
                  ) : (
                    <div className="h-[430px]" />
                  )}
                  {mapData.data && mapData.data.nodes.length > 0 && (
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
                    <p className="py-6 text-center text-sm text-muted">
                      No alerts recorded. {o.status.network.configured
                        ? "Detectors are operating on collected data."
                        : "Monitoring is incomplete — no metrics source configured."}
                    </p>
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
          );
        }}
      </AsyncBoundary>
    </div>
  );
}

function Mini({ label, value, accent = "#ECF5FF" }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg/50 py-1.5">
      <div className="font-mono text-base font-semibold" style={{ color: accent }}>{value}</div>
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
