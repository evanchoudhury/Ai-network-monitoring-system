import { useState } from "react";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import clsx from "clsx";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Source } from "../lib/types";
import { AsyncBoundary, Badge, SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { timeAgo } from "../lib/format";
import { useAuth } from "../auth";

export default function SourcesPage() {
  const { isAdmin } = useAuth();
  const sources = useApi<Source[]>(() => api.get<Source[]>("/sources"), []);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", authorized: false });
  const [msg, setMsg] = useState<string | null>(null);

  async function ingest() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<{ results: { source: string; status: string; new?: number; error?: string }[] }>(
        "/news/ingest"
      );
      const ok = r.results.filter((x) => x.status === "ok").length;
      setMsg(`Ingested ${ok}/${r.results.length} source(s). ${r.results.filter((x) => x.status === "error").length} failed.`);
      sources.refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function addSource() {
    if (!form.authorized) {
      setMsg("You must confirm authorization before adding a source.");
      return;
    }
    try {
      await api.post("/sources", {
        name: form.name,
        source_type: "rss",
        url: form.url,
        authorized: true,
        enabled: true,
      });
      setForm({ name: "", url: "", authorized: false });
      setMsg("Source added.");
      sources.refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to add source");
    }
  }

  async function remove(id: number) {
    await api.del(`/sources/${id}`);
    sources.refetch();
  }

  return (
    <div>
      <PageHeader
        title="Data Sources"
        subtitle="Only explicitly authorized sources are ingested. Feed terms and robots policies must be respected."
        actions={
          isAdmin ? (
            <button className="btn-primary" onClick={ingest} disabled={busy}>
              <RefreshCw className={clsx("h-4 w-4", busy && "animate-spin")} /> Ingest now
            </button>
          ) : undefined
        }
      />
      {msg && <div className="mb-3 rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-muted">{msg}</div>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SectionCard className="lg:col-span-2" title="Configured sources" bodyClassName="p-0">
          <AsyncBoundary state={sources} isEmpty={(d) => d.length === 0}
            emptyProps={{ title: "No sources configured" }}>
            {(d) => (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted">
                      <th className="px-4 py-2 font-medium">Name</th>
                      <th className="px-4 py-2 font-medium">Type</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Last ingest</th>
                      {isAdmin && <th className="px-4 py-2"></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {d.map((s) => (
                      <tr key={s.id} className="border-b border-border/50">
                        <td className="px-4 py-2">
                          <div className="font-medium text-text">{s.name}</div>
                          {s.url && <div className="max-w-[260px] truncate text-[11px] text-muted">{s.url}</div>}
                        </td>
                        <td className="px-4 py-2"><Badge className="bg-blue/15 text-blue">{s.source_type}</Badge></td>
                        <td className="px-4 py-2">
                          <Badge className={
                            s.last_status === "ok" ? "bg-success/15 text-success"
                              : s.last_status === "error" ? "bg-critical/15 text-critical"
                                : "bg-muted/15 text-muted"
                          }>
                            {s.last_status ?? "never run"}
                          </Badge>
                          {s.last_error && <div className="mt-0.5 max-w-[220px] truncate text-[10px] text-critical">{s.last_error}</div>}
                        </td>
                        <td className="px-4 py-2 text-muted">{timeAgo(s.last_ingested_at)}</td>
                        {isAdmin && (
                          <td className="px-4 py-2 text-right">
                            <button className="text-muted hover:text-critical" onClick={() => remove(s.id)} title="Delete">
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </AsyncBoundary>
        </SectionCard>

        <SectionCard title="Add RSS source">
          {!isAdmin ? (
            <p className="text-sm text-muted">Sign in as an operator (Settings) to add sources.</p>
          ) : (
            <div className="space-y-3">
              <input className="input" placeholder="Source name"
                value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input className="input" placeholder="https://example.com/rss.xml"
                value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
              <label className="flex items-start gap-2 text-xs text-muted">
                <input type="checkbox" className="mt-0.5 accent-cyan" checked={form.authorized}
                  onChange={(e) => setForm({ ...form, authorized: e.target.checked })} />
                <span>I confirm I am authorized to ingest this source and will respect its terms and robots policy.</span>
              </label>
              <button className="btn-primary w-full justify-center" onClick={addSource}
                disabled={!form.name || !form.url}>
                <Plus className="h-4 w-4" /> Add source
              </button>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
