import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import { AsyncBoundary, SectionCard } from "../components/ui";
import { PageHeader, TimeRangeSelect } from "../components/shared";
import { formatDateTime } from "../lib/format";

interface ReportSummary {
  window_hours: number;
  mode: { mode: string };
  metrics_ingested: number;
  anomalies: number;
  alerts: number;
  articles: number;
  claims: number;
  spam_assessments: number;
  generated_at: string;
}

export default function ReportsPage() {
  const [hours, setHours] = useState(24);
  const report = useApi<ReportSummary>(() => api.get(`/reports/summary?hours=${hours}`), [hours]);

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Historical activity summaries across all subsystems."
        actions={
          <TimeRangeSelect value={hours} onChange={setHours}
            options={[
              { label: "24h", value: 24 },
              { label: "7d", value: 168 },
              { label: "30d", value: 720 },
            ]} />
        }
      />
      <AsyncBoundary state={report}>
        {(r) => (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Tile label="Metrics ingested" value={r.metrics_ingested} />
              <Tile label="Anomalies" value={r.anomalies} />
              <Tile label="Alerts" value={r.alerts} />
              <Tile label="Articles" value={r.articles} />
              <Tile label="Claims" value={r.claims} />
              <Tile label="Spam checks" value={r.spam_assessments} />
            </div>
            <SectionCard title="Report metadata">
              <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
                <Row label="Window" value={`${r.window_hours} hours`} />
                <Row label="Mode" value={r.mode.mode.toUpperCase()} />
                <Row label="Generated" value={formatDateTime(r.generated_at)} />
              </dl>
              <p className="mt-3 text-xs text-muted">
                Counts reflect records created within the selected window. Metric and article
                retention policies may remove older data — see Budget &amp; Usage.
              </p>
            </SectionCard>
          </div>
        )}
      </AsyncBoundary>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="card p-4 text-center">
      <div className="font-mono text-2xl font-semibold text-text">{value}</div>
      <div className="mt-1 text-xs text-muted">{label}</div>
    </div>
  );
}
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg/50 p-2">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="font-mono text-sm text-text">{value}</div>
    </div>
  );
}
