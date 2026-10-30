import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Budget } from "../lib/types";
import { AsyncBoundary, SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { formatNumber, formatUsd } from "../lib/format";

function Meter({ label, value, limit, unit }: { label: string; value: number; limit: number; unit?: string }) {
  const pct = limit > 0 ? Math.min(100, (value / limit) * 100) : 0;
  const color = pct > 90 ? "#FF5268" : pct > 70 ? "#FFBF47" : "#20D99A";
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-text">
          {unit === "usd" ? formatUsd(value) : formatNumber(value)} /{" "}
          {unit === "usd" ? formatUsd(limit) : formatNumber(limit)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-bg">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

export default function BudgetPage() {
  const budget = useApi<Budget>(() => api.get<Budget>("/budget"), [], { pollMs: 30000 });

  return (
    <div>
      <PageHeader title="Budget & Usage" subtitle="Application-level model usage limits and estimated AI cost." />
      <AsyncBoundary state={budget}>
        {(b) => (
          <div className="space-y-4">
            <div className="rounded-xl border border-warning/30 bg-warning/5 p-3 text-sm text-warning">
              ⚠ {b.disclaimer}
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SectionCard title="Usage vs Limits">
                <div className="space-y-4">
                  <Meter label="Model requests today" value={b.day_requests} limit={b.limits.max_requests_per_day} />
                  <Meter label="Tokens today" value={b.day_tokens} limit={b.limits.max_tokens_per_day} />
                  <Meter label="Estimated cost today" value={b.estimated_day_cost_usd} limit={b.limits.daily_usd} unit="usd" />
                  <Meter label="Estimated cost this month" value={b.estimated_month_cost_usd} limit={b.limits.monthly_usd} unit="usd" />
                </div>
                <div className="mt-4 flex items-center gap-2 text-sm">
                  <span className={b.within_budget ? "text-success" : "text-critical"}>
                    {b.within_budget ? "✓ Within budget" : "✗ Budget threshold reached"}
                  </span>
                </div>
                {b.notes.length > 0 && (
                  <ul className="mt-2 list-disc pl-5 text-xs text-warning">
                    {b.notes.map((n, i) => <li key={i}>{n}</li>)}
                  </ul>
                )}
              </SectionCard>

              <SectionCard title="Resource Controls">
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  {Object.entries(b.resource_controls).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-border bg-bg/50 p-2">
                      <div className="text-[11px] text-muted">{k.replace(/_/g, " ")}</div>
                      <div className="font-mono text-text">{String(v)}</div>
                    </div>
                  ))}
                </dl>
                <p className="mt-3 text-xs text-muted">
                  The core analysis pipeline is deterministic and uses no external AI, so the
                  default estimated AI cost is <span className="font-mono text-text">$0.00</span>.
                  Costs are estimates unless explicitly marked provider-reported.
                </p>
              </SectionCard>
            </div>
          </div>
        )}
      </AsyncBoundary>
    </div>
  );
}
