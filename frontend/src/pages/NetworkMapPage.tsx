import { useMemo, useState } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { MapData } from "../lib/types";
import { AsyncBoundary, SectionCard } from "../components/ui";
import { PageHeader, TimeRangeSelect } from "../components/shared";
import { NetworkMap } from "../components/NetworkMap";

const COLOR_FILTERS = [
  { key: "cyan", label: "Normal" },
  { key: "blue", label: "High traffic" },
  { key: "amber", label: "Anomaly" },
  { key: "red", label: "Alert" },
] as const;

export default function NetworkMapPage() {
  const [hours, setHours] = useState(24);
  const [animate, setAnimate] = useState(true);
  const [showConnections, setShowConnections] = useState(true);
  const [onlySuspicious, setOnlySuspicious] = useState(false);
  const [active, setActive] = useState<Set<string>>(new Set(COLOR_FILTERS.map((c) => c.key)));

  const map = useApi<MapData>(() => api.get<MapData>(`/map?hours=${hours}`), [hours]);

  const filtered = useMemo(() => {
    if (!map.data) return null;
    const nodes = map.data.nodes.filter((n) => active.has(n.color));
    const visibleIds = new Set(nodes.map((n) => n.id));
    let conns = showConnections
      ? map.data.connections.filter(
          (c) => visibleIds.has(c.src.id) && visibleIds.has(c.dst.id)
        )
      : [];
    if (onlySuspicious) conns = conns.filter((c) => c.suspicious);
    return { nodes, conns };
  }, [map.data, active, showConnections, onlySuspicious]);

  function toggle(key: string) {
    setActive((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  return (
    <div>
      <PageHeader
        title="Global Network Map"
        subtitle="Only locations and connections backed by configured, authorized sources are plotted."
        demo={map.data?.contains_demo_data}
        actions={<TimeRangeSelect value={hours} onChange={setHours} />}
      />

      <AsyncBoundary state={map} isEmpty={(d) => d.nodes.length === 0}
        emptyProps={{
          title: "No located nodes",
          hint: "No services with geographic coordinates have reported data in this window. Add a service location under Data Sources, or generate demo data.",
        }}
      >
        {(d) => (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <SectionCard className="lg:col-span-3" bodyClassName="p-2">
              <NetworkMap
                nodes={filtered?.nodes ?? d.nodes}
                connections={filtered?.conns ?? d.connections}
                animate={animate}
                onToggleAnimate={() => setAnimate((a) => !a)}
                height={560}
              />
            </SectionCard>

            <div className="space-y-4">
              <SectionCard title="Filters">
                <div className="space-y-3 text-sm">
                  <div>
                    <div className="mb-1.5 text-xs text-muted">Node severity</div>
                    <div className="flex flex-col gap-1.5">
                      {COLOR_FILTERS.map((c) => (
                        <label key={c.key} className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={active.has(c.key)}
                            onChange={() => toggle(c.key)}
                            className="accent-cyan"
                          />
                          <span>{c.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <label className="flex items-center gap-2 border-t border-border pt-3">
                    <input type="checkbox" checked={showConnections}
                      onChange={(e) => setShowConnections(e.target.checked)} className="accent-cyan" />
                    <span>Show connection lines</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={onlySuspicious}
                      onChange={(e) => setOnlySuspicious(e.target.checked)} className="accent-cyan" />
                    <span>Only suspicious connections</span>
                  </label>
                </div>
              </SectionCard>

              <SectionCard title="Coverage">
                <dl className="space-y-2 text-sm">
                  <Stat label="Monitored nodes" value={d.counts.nodes} />
                  <Stat label="Countries" value={d.counts.countries} />
                  <Stat label="Connections" value={d.counts.connections} />
                  <Stat label="Suspicious" value={d.counts.suspicious} />
                  <Stat label="Unlocated services" value={d.counts.unlocated} />
                </dl>
                {d.unlocated.length > 0 && (
                  <p className="mt-3 rounded-lg border border-border bg-bg/60 p-2 text-[11px] text-muted">
                    {d.unlocated.length} service(s) have no location and are not plotted.
                    Locations are never fabricated.
                  </p>
                )}
              </SectionCard>
            </div>
          </div>
        )}
      </AsyncBoundary>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className="font-mono font-semibold text-text">{value}</dd>
    </div>
  );
}
