import { ReactNode } from "react";
import clsx from "clsx";
import type { Alert } from "../lib/types";
import { SEVERITY_COLOR } from "../lib/constants";
import { SeverityBadge } from "./ui";
import { timeAgo } from "../lib/format";

export function PageHeader({
  title,
  subtitle,
  actions,
  demo,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  demo?: boolean;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-text">
          {title}
          {demo && (
            <span className="chip border border-warning/40 bg-warning/10 text-[10px] uppercase tracking-wider text-warning">
              Demo Data
            </span>
          )}
        </h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function TimeRangeSelect({
  value,
  onChange,
  options = [
    { label: "1h", value: 1 },
    { label: "6h", value: 6 },
    { label: "24h", value: 24 },
    { label: "7d", value: 168 },
  ],
}: {
  value: number;
  onChange: (v: number) => void;
  options?: { label: string; value: number }[];
}) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-elevated p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            value === o.value ? "bg-blue/20 text-cyan" : "text-muted hover:text-text"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function AlertRow({
  alert,
  onAck,
  compact,
}: {
  alert: Alert;
  onAck?: (id: number) => void;
  compact?: boolean;
}) {
  return (
    <div
      className={clsx(
        "flex items-start gap-3 border-b border-border/60 py-2.5 last:border-0",
        alert.acknowledged && "opacity-55"
      )}
    >
      <span
        className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
        style={{ background: SEVERITY_COLOR[alert.severity] }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-text">{alert.title}</span>
        </div>
        {!compact && <p className="mt-0.5 line-clamp-2 text-xs text-muted">{alert.explanation}</p>}
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted">
          <SeverityBadge severity={alert.severity} />
          <span className="font-mono">{alert.category}</span>
          {alert.source && <span>· {alert.source}</span>}
          <span>· {timeAgo(alert.created_at)}</span>
        </div>
      </div>
      {onAck && !alert.acknowledged && (
        <button className="btn shrink-0 px-2 py-1 text-xs" onClick={() => onAck(alert.id)}>
          Ack
        </button>
      )}
      {alert.acknowledged && (
        <span className="shrink-0 text-[11px] text-success">✓ Acked</span>
      )}
    </div>
  );
}
