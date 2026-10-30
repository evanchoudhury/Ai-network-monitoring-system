import { CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { HealthReport } from "../lib/types";
import { AsyncBoundary, FreshnessBadge, SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { formatDateTime } from "../lib/format";

const STATUS_ICON = {
  ok: <CheckCircle2 className="h-4 w-4 text-success" />,
  degraded: <AlertCircle className="h-4 w-4 text-warning" />,
  down: <XCircle className="h-4 w-4 text-critical" />,
};

const LABELS: Record<string, string> = {
  database: "Database",
  collectors: "Data collectors",
  news_sources: "News sources",
  ai_provider: "AI provider",
};

export default function HealthPage() {
  const health = useApi<HealthReport>(() => api.get<HealthReport>("/health"), [], { pollMs: 15000 });

  return (
    <div>
      <PageHeader title="System Health" subtitle="Live status of every major component, with last successful update and recent errors." />
      <AsyncBoundary state={health}>
        {(h) => (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="card flex items-center gap-3 px-4 py-3">
                {STATUS_ICON[h.overall]}
                <div>
                  <div className="text-xs text-muted">Overall status</div>
                  <div className="font-semibold capitalize text-text">{h.overall}</div>
                </div>
              </div>
              <div className="card px-4 py-3">
                <div className="text-xs text-muted">Operating mode</div>
                <div className="font-semibold uppercase text-cyan">LIVE</div>
              </div>
            </div>

            {/* Per-subsystem data-source freshness */}
            <SectionCard title="Data Sources" bodyClassName="p-0">
              <div className="divide-y divide-border/60">
                {([h.status.network, h.status.news, h.status.claims, h.status.spam, h.status.workers]).map((s) => (
                  <div key={s.subsystem} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <div className="font-medium capitalize text-text">{s.subsystem}</div>
                      <div className="text-xs text-muted">{s.detail}</div>
                      {s.instructions && <div className="mt-0.5 text-[11px] text-muted">{s.instructions}</div>}
                    </div>
                    <FreshnessBadge status={s} />
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Components" bodyClassName="p-0">
              <div className="divide-y divide-border/60">
                {h.components.map((c) => (
                  <div key={c.component} className="flex items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-3">
                      {STATUS_ICON[c.status as keyof typeof STATUS_ICON] ?? STATUS_ICON.degraded}
                      <div>
                        <div className="font-medium text-text">{LABELS[c.component] ?? c.component}</div>
                        <div className="text-xs text-muted">{c.detail}</div>
                      </div>
                    </div>
                    <div className="text-right text-xs text-muted">
                      {c.latency_ms != null && <span className="font-mono">{c.latency_ms.toFixed(1)} ms</span>}
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Recent Errors" bodyClassName="p-0">
              {h.last_errors.length === 0 ? (
                <p className="p-4 text-sm text-muted">No recent errors recorded.</p>
              ) : (
                <div className="divide-y divide-border/60">
                  {h.last_errors.map((e, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-2 text-sm">
                      <div>
                        <span className="font-medium text-text">{LABELS[e.component] ?? e.component}</span>
                        <span className="ml-2 text-xs text-muted">{e.detail}</span>
                      </div>
                      <span className="text-xs text-muted">{formatDateTime(e.at)}</span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        )}
      </AsyncBoundary>
    </div>
  );
}
