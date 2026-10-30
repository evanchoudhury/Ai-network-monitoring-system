import { useState } from "react";
import { AlertTriangle, Link2, ShieldCheck } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { SpamRecord, SpamResult } from "../lib/types";
import { AsyncBoundary, Badge, SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { timeAgo } from "../lib/format";

const CAT_META: Record<string, { label: string; className: string }> = {
  clean: { label: "Clean", className: "bg-success/15 text-success" },
  low_risk: { label: "Low Risk", className: "bg-blue/15 text-blue" },
  suspicious: { label: "Suspicious", className: "bg-warning/15 text-warning" },
  high_risk: { label: "High Risk", className: "bg-critical/15 text-critical" },
  phishing: { label: "Phishing", className: "bg-critical/20 text-critical" },
};

export default function SpamPage() {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SpamResult | null>(null);
  const recent = useApi<{ total: number; items: SpamRecord[] }>(() => api.get("/spam"), []);

  async function analyze() {
    setBusy(true);
    try {
      const r = await api.post<SpamResult>("/spam/analyze", { message: msg, store: true });
      setResult(r);
      recent.refetch();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Spam & Phishing Analysis"
        subtitle="Explainable, rule-based scoring. The score is a heuristic — not a calibrated probability. Links are never visited automatically."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Analyze a message">
          <textarea
            className="input h-36 resize-none"
            placeholder="Paste an email or message to analyze for spam/phishing indicators…"
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
          />
          <button className="btn-primary mt-2" onClick={analyze} disabled={busy || !msg.trim()}>
            {busy ? "Analyzing…" : "Analyze message"}
          </button>

          {result && (
            <div className="mt-4 space-y-3 border-t border-border pt-4 animate-fadeIn">
              <div className="flex items-center justify-between">
                <Badge className={CAT_META[result.category].className}>
                  {CAT_META[result.category].label}
                </Badge>
                <span className="font-mono text-sm text-text">
                  score {result.score.toFixed(2)}
                  <span className="ml-1 text-[10px] text-muted">
                    ({result.score_is_calibrated ? "calibrated" : "heuristic"})
                  </span>
                </span>
              </div>
              <p className="text-sm text-muted">{result.explanation}</p>

              {result.indicators.length > 0 && (
                <div>
                  <div className="mb-1 text-xs font-semibold text-muted">Triggered indicators</div>
                  <ul className="space-y-1">
                    {result.indicators.map((ind, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs">
                        <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-warning" />
                        <span className="text-text">{ind.detail}</span>
                        <span className="ml-auto font-mono text-muted">+{ind.weight}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.urls.length > 0 && (
                <div>
                  <div className="mb-1 text-xs font-semibold text-muted">Links (not visited)</div>
                  <ul className="space-y-1">
                    {result.urls.map((u, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs">
                        <Link2 className="h-3 w-3 shrink-0 text-muted" />
                        <span className="truncate font-mono text-text">{u.host || u.url}</span>
                        {u.flags.map((f) => (
                          <Badge key={f} className="bg-critical/15 text-critical">{f}</Badge>
                        ))}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="rounded-lg border border-border bg-bg/60 p-2 text-xs">
                <div className="flex items-center gap-1 font-semibold text-cyan">
                  <ShieldCheck className="h-3.5 w-3.5" /> Recommended action
                </div>
                <p className="mt-1 text-muted">{result.recommendation}</p>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Recent Detections" bodyClassName="p-0">
          <AsyncBoundary state={recent} isEmpty={(d) => d.items.length === 0}
            emptyProps={{ title: "No detections yet", hint: "Analyze a message to populate." }}>
            {(d) => (
              <div className="divide-y divide-border/60">
                {d.items.map((s) => (
                  <div key={s.id} className="p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="line-clamp-2 text-sm text-text">{s.preview}</p>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <Badge className={CAT_META[s.category].className}>{CAT_META[s.category].label}</Badge>
                        <span className="font-mono text-xs text-muted">{s.score.toFixed(2)}</span>
                      </div>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted">
                      <span>{(s.indicators ?? []).length} indicator(s)</span>
                      <span>· {s.source}</span>
                      <span>· {timeAgo(s.created_at)}</span>
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
