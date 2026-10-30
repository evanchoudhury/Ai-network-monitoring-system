import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { MetricPoint, ServiceInfo } from "../lib/types";
import { AsyncBoundary, SectionCard } from "../components/ui";
import { PageHeader, TimeRangeSelect } from "../components/shared";
import { MetricLineChart, TrafficChart } from "../components/charts";

export default function TrafficPage() {
  const [hours, setHours] = useState(24);
  const [serviceId, setServiceId] = useState<number | null>(null);
  const q = serviceId ? `&service_id=${serviceId}` : "";

  const services = useApi<ServiceInfo[]>(() => api.get<ServiceInfo[]>("/services"), []);
  const traffic = useApi<{ inbound: MetricPoint[]; outbound: MetricPoint[]; contains_demo_data: boolean }>(
    () => api.get(`/metrics/traffic?hours=${hours}${q}`),
    [hours, serviceId]
  );
  const rps = useApi<{ points: MetricPoint[] }>(
    () => api.get(`/metrics/history?metric=request_rate&hours=${hours}${q}`),
    [hours, serviceId]
  );
  const latency = useApi<{ points: MetricPoint[] }>(
    () => api.get(`/metrics/history?metric=latency_p95_ms&hours=${hours}${q}`),
    [hours, serviceId]
  );
  const errRate = useApi<{ points: MetricPoint[] }>(
    () => api.get(`/metrics/history?metric=error_rate&hours=${hours}${q}`),
    [hours, serviceId]
  );

  return (
    <div>
      <PageHeader
        title="Network Traffic"
        subtitle="Inbound/outbound bandwidth, request rate, latency, and error rate over time."
        demo={traffic.data?.contains_demo_data}
        actions={
          <div className="flex items-center gap-2">
            <select
              className="input w-40 py-1.5"
              value={serviceId ?? ""}
              onChange={(e) => setServiceId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">All services</option>
              {services.data?.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <TimeRangeSelect value={hours} onChange={setHours} />
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SectionCard title="Inbound vs Outbound Bandwidth" bodyClassName="px-1">
          <AsyncBoundary state={traffic} isEmpty={(d) => d.inbound.length === 0}
            emptyProps={{ title: "No traffic data", hint: "No metrics in this window." }}>
            {(d) => <TrafficChart inbound={d.inbound} outbound={d.outbound} height={260} />}
          </AsyncBoundary>
        </SectionCard>

        <SectionCard title="Request Rate (req/s)" bodyClassName="px-1">
          <AsyncBoundary state={rps} isEmpty={(d) => d.points.length === 0}
            emptyProps={{ title: "No request-rate data" }}>
            {(d) => <MetricLineChart points={d.points} color="#13D6C1" height={260} label="req/s" />}
          </AsyncBoundary>
        </SectionCard>

        <SectionCard title="Latency p95 (ms)" bodyClassName="px-1">
          <AsyncBoundary state={latency} isEmpty={(d) => d.points.length === 0}
            emptyProps={{ title: "No latency data" }}>
            {(d) => <MetricLineChart points={d.points} color="#FFBF47" height={260} label="ms" />}
          </AsyncBoundary>
        </SectionCard>

        <SectionCard title="Error Rate" bodyClassName="px-1">
          <AsyncBoundary state={errRate} isEmpty={(d) => d.points.length === 0}
            emptyProps={{ title: "No error-rate data" }}>
            {(d) => <MetricLineChart points={d.points} color="#FF5268" height={260} label="error rate" />}
          </AsyncBoundary>
        </SectionCard>
      </div>
    </div>
  );
}
