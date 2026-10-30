import { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, PlugZap, WifiOff } from "lucide-react";
import clsx from "clsx";
import type { Severity, SubsystemStatus } from "../lib/types";
import { SEVERITY_BG } from "../lib/constants";
import { timeAgo } from "../lib/format";

export function Card({
  children,
  className,
  elevated,
}: {
  children: ReactNode;
  className?: string;
  elevated?: boolean;
}) {
  return (
    <div className={clsx(elevated ? "card-elevated" : "card", "animate-fadeIn", className)}>
      {children}
    </div>
  );
}

export function SectionCard({
  title,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Card className={className}>
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="section-title">{title}</h3>
          {action}
        </div>
      )}
      <div className={clsx("p-4", bodyClassName)}>{children}</div>
    </Card>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={clsx("chip uppercase", SEVERITY_BG[severity])}>{severity}</span>
  );
}

export function Badge({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <span className={clsx("chip", className)}>{children}</span>;
}

const STATE_META: Record<string, { label: string; className: string; dot: string }> = {
  fresh: { label: "Fresh", className: "text-success", dot: "bg-success" },
  active: { label: "Active", className: "text-success", dot: "bg-success" },
  degraded: { label: "Degraded", className: "text-warning", dot: "bg-warning" },
  stale: { label: "Stale", className: "text-warning", dot: "bg-warning" },
  disconnected: { label: "Disconnected", className: "text-critical", dot: "bg-critical" },
  failed: { label: "Failed", className: "text-critical", dot: "bg-critical" },
  not_configured: { label: "Not configured", className: "text-muted", dot: "bg-muted" },
  no_source: { label: "No source", className: "text-muted", dot: "bg-muted" },
  disabled: { label: "Disabled", className: "text-muted", dot: "bg-muted" },
};

/** Small freshness pill for a subsystem state. */
export function FreshnessBadge({ status }: { status: SubsystemStatus }) {
  const m = STATE_META[status.state] ?? STATE_META.not_configured;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={clsx("h-2 w-2 rounded-full", m.dot)} />
      <span className={m.className}>{m.label}</span>
      {status.last_update && (
        <span className="text-muted">· {timeAgo(status.last_update)}</span>
      )}
    </span>
  );
}

/** Prominent banner shown when a data source is not configured/connected.
 *  Returns null when the subsystem is configured and not in an error state. */
export function StatusBanner({ status }: { status?: SubsystemStatus }) {
  if (!status) return null;
  const bad = ["not_configured", "no_source", "disconnected", "failed"].includes(status.state);
  if (!bad) return null;
  const critical = status.state === "disconnected" || status.state === "failed";
  return (
    <div
      className={clsx(
        "mb-4 flex items-start gap-3 rounded-xl border p-3 text-sm",
        critical ? "border-critical/40 bg-critical/5" : "border-warning/40 bg-warning/5"
      )}
    >
      <PlugZap className={clsx("mt-0.5 h-5 w-5 shrink-0", critical ? "text-critical" : "text-warning")} />
      <div>
        <div className="font-semibold text-text">{status.detail}</div>
        {status.instructions && (
          <div className="mt-0.5 text-xs text-muted">{status.instructions}</div>
        )}
      </div>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("animate-spin", className)} />;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-muted">
      <Spinner className="h-6 w-6 text-cyan" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({
  title = "No data yet",
  hint,
  action,
}: {
  title?: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted">
      <Inbox className="h-7 w-7 opacity-60" />
      <div className="text-sm font-medium text-text">{title}</div>
      {hint && <div className="max-w-sm text-xs">{hint}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({
  message,
  status,
  onRetry,
}: {
  message: string;
  status?: number | null;
  onRetry?: () => void;
}) {
  const unavailable = status === 0 || status === 503;
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      {unavailable ? (
        <WifiOff className="h-7 w-7 text-warning" />
      ) : (
        <AlertTriangle className="h-7 w-7 text-critical" />
      )}
      <div className="text-sm font-medium text-text">
        {unavailable ? "Service unavailable" : "Something went wrong"}
      </div>
      <div className="max-w-sm text-xs text-muted">{message}</div>
      {onRetry && (
        <button className="btn mt-2" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

/** Wraps an async-state view with standard loading/error/empty handling. */
export function AsyncBoundary<T>({
  state,
  isEmpty,
  children,
  emptyProps,
}: {
  state: { data: T | null; loading: boolean; error: string | null; errorStatus: number | null; refetch: () => void };
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
  emptyProps?: { title?: string; hint?: string; action?: ReactNode };
}) {
  if (state.loading && state.data == null) return <LoadingState />;
  if (state.error && state.data == null)
    return <ErrorState message={state.error} status={state.errorStatus} onRetry={state.refetch} />;
  if (state.data == null) return <EmptyState {...emptyProps} />;
  if (isEmpty && isEmpty(state.data)) return <EmptyState {...emptyProps} />;
  return <>{children(state.data)}</>;
}
