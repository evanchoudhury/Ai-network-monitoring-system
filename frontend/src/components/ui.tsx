import { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, WifiOff } from "lucide-react";
import clsx from "clsx";
import type { Severity } from "../lib/types";
import { SEVERITY_BG } from "../lib/constants";

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

export function DemoTag() {
  return (
    <span
      title="This view contains synthetic demonstration data, not live observations."
      className="chip border border-warning/40 bg-warning/10 font-semibold uppercase tracking-wider text-warning"
    >
      Demo Data
    </span>
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
