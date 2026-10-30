import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Alert, Anomaly } from "../lib/types";
import { AsyncBoundary, SectionCard, SeverityBadge } from "../components/ui";
import { PageHeader } from "../components/shared";
import { formatDateTime, timeAgo } from "../lib/format";
import { useAuth } from "../auth";
import clsx from "clsx";

export default function ThreatsPage() {
  const { isAdmin } = useAuth();
  const [filter, setFilter] = useState<"all" | "open" | "acked">("open");
  const ackParam = filter === "all" ? "" : filter === "open" ? "?acknowledged=false" : "?acknowledged=true";

  const alerts = useApi<{ total: number; items: Alert[] }>(
    () => api.get(`/alerts${ackParam}`),
    [filter],
    { pollMs: 20000 }
  );
  const anomalies = useApi<Anomaly[]>(() => api.get<Anomaly[]>("/anomalies?hours=168"), []);

  async function ack(id: number) {
    await api.post(`/alerts/${id}/ack`, { actor: "operator" });
    alerts.refetch();
  }

  return (
    <div>
      <PageHeader
        title="Security Threats"
        subtitle="Persistent alerts with severity, source, evidence, and acknowledgement state."
        actions={
          <div className="inline-flex rounded-lg border border-border bg-elevated p-0.5">
            {(["open", "acked", "all"] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={clsx("rounded-md px-3 py-1 text-xs font-medium capitalize",
                  filter === f ? "bg-blue/20 text-cyan" : "text-muted hover:text-text")}>
                {f}
              </button>
            ))}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SectionCard className="lg:col-span-2" title="Alerts" bodyClassName="p-0">
          <AsyncBoundary state={alerts} isEmpty={(d) => d.items.length === 0}
            emptyProps={{ title: "No alerts", hint: "No alerts match this filter." }}>
            {(d) => (
              <div className="divide-y divide-border/60">
                {d.items.map((a) => (
                  <div key={a.id} className={clsx("p-4", a.acknowledged && "opacity-60")}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <SeverityBadge severity={a.severity} />
                          <span className="font-mono text-[11px] text-muted">{a.category}</span>
                        </div>
                        <h4 className="mt-1 font-medium text-text">{a.title}</h4>
                        <p className="mt-1 text-sm text-muted">{a.explanation}</p>
                        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted">
                          {a.source && <span>Source: {a.source}</span>}
                          <span>· {formatDateTime(a.created_at)} ({timeAgo(a.created_at)})</span>
                        </div>
                        {a.evidence && (
                          <pre className="mt-2 overflow-x-auto rounded-lg border border-border bg-bg/60 p-2 text-[11px] text-muted">
                            {JSON.stringify(a.evidence, null, 2)}
                          </pre>
                        )}
                      </div>
                      <div className="shrink-0">
                        {a.acknowledged ? (
                          <span className="text-[11px] text-success">✓ {a.acknowledged_by ?? "acked"}</span>
                        ) : isAdmin ? (
                          <button className="btn px-2 py-1 text-xs" onClick={() => ack(a.id)}>
                            Acknowledge
                          </button>
                        ) : (
                          <span className="text-[11px] text-muted">sign in to ack</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </AsyncBoundary>
        </SectionCard>

        <SectionCard title="Recent Anomalies" bodyClassName="p-0">
          <AsyncBoundary state={anomalies} isEmpty={(d) => d.length === 0}
            emptyProps={{ title: "No anomalies", hint: "No anomalies detected in the last 7 days." }}>
            {(d) => (
              <div className="divide-y divide-border/60">
                {d.slice(0, 20).map((a) => (
                  <div key={a.id} className="p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm text-text">{a.metric}</span>
                      <SeverityBadge severity={a.severity} />
                    </div>
                    <p className="mt-1 line-clamp-3 text-xs text-muted">{a.explanation}</p>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                      <span>z={a.zscore?.toFixed(1)}</span>
                      <span>{timeAgo(a.window_end ?? a.detected_at)}</span>
                    </div>
                    <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">
                      {a.confirmed_attack ? "Confirmed" : "Anomaly — not a confirmed attack"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </AsyncBoundary>
        </SectionCard>
      </div>
    </div>
  );
}
