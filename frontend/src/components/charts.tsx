import {
  Area,
  AreaChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricPoint } from "../lib/types";
import { formatTime } from "../lib/format";

const AXIS = { stroke: "#1D3349", fontSize: 11, tick: { fill: "#8DA4BC" } };

function tsLabel(ts: string) {
  return formatTime(ts);
}

// Compact numeric axis labels (e.g. 1.8M, 420K) so large byte values fit.
function compact(n: number): string {
  if (n == null || !isFinite(n)) return "";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(1)}G`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  if (abs < 1 && abs > 0) return n.toFixed(2);
  return `${n}`;
}

const tooltipStyle = {
  contentStyle: {
    background: "rgba(13, 25, 40, 0.96)",
    border: "1px solid #1D3349",
    borderRadius: 10,
    fontSize: 12,
    color: "#ECF5FF",
    boxShadow: "0 10px 30px -10px rgba(0,0,0,0.7)",
    backdropFilter: "blur(6px)",
    padding: "8px 12px",
  },
  labelStyle: { color: "#8DA4BC", marginBottom: 4, fontSize: 11 },
  cursor: { stroke: "#20D9F2", strokeOpacity: 0.25, strokeWidth: 1 },
};

export function TrafficChart({
  inbound,
  outbound,
  height = 230,
}: {
  inbound: MetricPoint[];
  outbound: MetricPoint[];
  height?: number;
}) {
  // Merge by timestamp index for a two-series area chart.
  const data = inbound.map((p, i) => ({
    ts: p.timestamp,
    inbound: p.value,
    outbound: outbound[i]?.value ?? null,
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <defs>
          <linearGradient id="gIn" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#338BFF" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#338BFF" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gOut" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#20D9F2" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#20D9F2" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#13263b" vertical={false} />
        <XAxis dataKey="ts" tickFormatter={tsLabel} {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={52} tickFormatter={compact} />
        <Tooltip {...tooltipStyle} labelFormatter={tsLabel} />
        <Area
          type="monotone"
          dataKey="inbound"
          stroke="#338BFF"
          fill="url(#gIn)"
          strokeWidth={1.8}
          name="Inbound"
          connectNulls
        />
        <Area
          type="monotone"
          dataKey="outbound"
          stroke="#20D9F2"
          fill="url(#gOut)"
          strokeWidth={1.8}
          name="Outbound"
          connectNulls
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function MetricLineChart({
  points,
  color = "#20D9F2",
  height = 220,
  label = "value",
}: {
  points: MetricPoint[];
  color?: string;
  height?: number;
  label?: string;
}) {
  const data = points.map((p) => ({ ts: p.timestamp, value: p.value }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke="#13263b" vertical={false} />
        <XAxis dataKey="ts" tickFormatter={tsLabel} {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={52} tickFormatter={compact} />
        <Tooltip {...tooltipStyle} labelFormatter={tsLabel} />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.8}
          dot={false}
          name={label}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function AnomalyTimelineChart({
  points,
  anomalies,
  height = 220,
}: {
  points: MetricPoint[];
  anomalies: { window_end: string | null; observed_value: number }[];
  height?: number;
}) {
  const anomalyTs = new Set(
    anomalies.filter((a) => a.window_end).map((a) => new Date(a.window_end as string).getTime())
  );
  const data = points.map((p) => {
    const t = new Date(p.timestamp).getTime();
    return { ts: t, value: p.value, anomaly: anomalyTs.has(t) ? p.value : null };
  });
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke="#13263b" vertical={false} />
        <XAxis
          dataKey="ts"
          type="number"
          domain={["dataMin", "dataMax"]}
          tickFormatter={(t) => formatTime(new Date(t).toISOString())}
          {...AXIS}
          minTickGap={40}
        />
        <YAxis {...AXIS} width={52} tickFormatter={compact} />
        <Tooltip
          {...tooltipStyle}
          labelFormatter={(t) => formatTime(new Date(Number(t)).toISOString())}
        />
        <Line type="monotone" dataKey="value" stroke="#13D6C1" strokeWidth={1.5} dot={false} name="Traffic" connectNulls />
        <Scatter dataKey="anomaly" fill="#FF5268" name="Anomaly" />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function Sparkline({ values, color = "#20D9F2" }: { values: number[]; color?: string }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={40}>
      <LineChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.6} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
