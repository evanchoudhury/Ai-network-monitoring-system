import { ReactNode } from "react";
import clsx from "clsx";
import { Sparkline } from "./charts";

export function KpiCard({
  label,
  value,
  icon,
  accent = "#20D9F2",
  sub,
  spark,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  accent?: string;
  sub?: ReactNode;
  spark?: number[];
}) {
  return (
    <div className="card p-4 transition-colors hover:border-border/80">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className="truncate text-xs font-medium text-muted">{label}</div>
          <div className="kpi-value mt-1">{value}</div>
          {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
        </div>
        <div
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
          style={{ background: `${accent}1A`, color: accent }}
        >
          {icon}
        </div>
      </div>
      {spark && spark.length > 1 && (
        <div className="mt-2 -mb-1">
          <Sparkline values={spark} color={accent} />
        </div>
      )}
    </div>
  );
}

export function StatPill({
  label,
  value,
  className,
}: {
  label: string;
  value: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("rounded-lg border border-border bg-elevated px-3 py-2", className)}>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="font-mono text-sm font-semibold text-text">{value}</div>
    </div>
  );
}
