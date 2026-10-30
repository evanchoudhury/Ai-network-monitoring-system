import { ReactNode, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  BadgeCheck,
  Bell,
  Database,
  FileBarChart,
  Gauge,
  Globe,
  HeartPulse,
  LayoutDashboard,
  MailWarning,
  Menu,
  Monitor,
  Newspaper,
  Settings,
  Shield,
  ShieldAlert,
  X,
} from "lucide-react";
import clsx from "clsx";
import { NAV_ITEMS } from "../lib/constants";
import type { SystemStatus } from "../lib/types";
import { timeAgo } from "../lib/format";

const ICONS: Record<string, typeof Activity> = {
  LayoutDashboard,
  Globe,
  Activity,
  ShieldAlert,
  Newspaper,
  BadgeCheck,
  MailWarning,
  FileBarChart,
  Database,
  HeartPulse,
  Gauge,
  Settings,
};

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-cyan/20 to-blue/10 ring-1 ring-cyan/40">
        <Shield className="h-5 w-5 text-cyan" strokeWidth={2.2} />
      </div>
      <div className="leading-tight">
        <div className="font-semibold tracking-wide text-text">
          SENTINEL <span className="text-cyan">AI</span>
        </div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-muted">
          Network &amp; Truth Intelligence
        </div>
      </div>
    </div>
  );
}

/** Real connection/freshness indicator. The app is always LIVE; the dot colour
 *  reflects whether a configured source is actually fresh. It never animates as
 *  "live" unless data is genuinely being received. */
export function ConnectionStatus({ status }: { status?: SystemStatus }) {
  if (!status) return null;
  const net = status.network;
  const news = status.news;

  // Determine the overall indicator from configured sources only.
  let color: string, ring: string, label: string, animate: boolean, tip: string;
  if (!net.configured && !news.configured) {
    color = "bg-muted"; ring = "ring-muted/40"; label = "NO SOURCE"; animate = false;
    tip = "No live data source configured. See Data Sources / System Health.";
  } else if (net.state === "fresh" || news.state === "fresh" || news.state === "degraded") {
    color = "bg-success"; ring = "ring-success/40"; label = "LIVE"; animate = true;
    tip = `Live. ${net.detail} ${news.configured ? "News: " + news.detail : ""}`.trim();
  } else if (net.state === "stale" || news.state === "stale") {
    color = "bg-warning"; ring = "ring-warning/40"; label = "LIVE · STALE"; animate = false;
    tip = `Data is stale. ${net.state === "stale" ? net.detail : news.detail}`;
  } else {
    color = "bg-critical"; ring = "ring-critical/40"; label = "DISCONNECTED"; animate = false;
    tip = net.configured ? net.detail : news.detail;
  }
  const last = net.last_update ?? news.last_update ?? null;
  return (
    <div
      title={tip}
      className={clsx(
        "inline-flex items-center gap-2 rounded-lg border border-border bg-elevated px-3 py-1.5 ring-1",
        ring
      )}
    >
      <span className={clsx("h-2 w-2 rounded-full", color, animate && "animate-pulseGlow")} />
      <span className="text-xs font-semibold tracking-wider text-text">{label}</span>
      {last && <span className="hidden text-[10px] text-muted sm:inline">· {timeAgo(last)}</span>}
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5 px-3">
      {NAV_ITEMS.map((item) => {
        const Icon = ICONS[item.icon] ?? Activity;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-150",
                isActive
                  ? "font-semibold text-text"
                  : "text-muted hover:translate-x-0.5 hover:bg-elevated/70 hover:text-text"
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <>
                    <span
                      className="absolute inset-0 rounded-lg ring-1 ring-cyan/25"
                      style={{ background: "linear-gradient(90deg, rgba(32,217,242,0.14), rgba(51,139,255,0.06))" }}
                    />
                    <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-cyan shadow-[0_0_10px_rgba(32,217,242,0.8)]" />
                  </>
                )}
                <Icon className={clsx("relative h-[18px] w-[18px]", isActive && "text-cyan")} />
                <span className="relative">{item.label}</span>
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

export function Layout({
  children,
  status,
  alertCount,
  rightControls,
}: {
  children: ReactNode;
  status?: SystemStatus;
  alertCount?: number;
  rightControls?: ReactNode;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();
  const current = NAV_ITEMS.find(
    (n) => n.path === location.pathname || (n.path !== "/" && location.pathname.startsWith(n.path))
  );

  return (
    <div className="flex min-h-screen bg-bg text-text">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-sidebar py-5 lg:flex">
        <div className="px-5 pb-5">
          <Logo />
        </div>
        <div className="flex-1 overflow-y-auto">
          <SidebarContent />
        </div>
        <div className="mt-4 px-5 text-[11px] text-muted">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
            <span>v1.0.0 · open source</span>
          </div>
        </div>
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-72 max-w-[85%] border-r border-border bg-sidebar py-5 animate-fadeIn">
            <div className="flex items-center justify-between px-5 pb-5">
              <Logo />
              <button onClick={() => setDrawerOpen(false)} className="text-muted hover:text-text">
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarContent onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-bg/85 px-4 py-3 backdrop-blur">
          <button
            className="text-muted hover:text-text lg:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden items-center gap-2 text-sm text-muted sm:flex">
            <Monitor className="h-4 w-4" />
            <span className="font-medium text-text">{current?.label ?? "Sentinel AI"}</span>
          </div>
          <div className="flex-1" />
          {rightControls}
          <ConnectionStatus status={status} />
          <div className="relative">
            <button className="btn px-2 py-1.5" aria-label="Alerts">
              <Bell className="h-4 w-4" />
            </button>
            {alertCount != null && alertCount > 0 && (
              <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-critical px-1 text-[10px] font-bold text-white">
                {alertCount > 99 ? "99+" : alertCount}
              </span>
            )}
          </div>
        </header>

        <main className="flex-1 px-4 py-5 pb-24 lg:pb-5">{children}</main>

        {/* Mobile bottom nav (primary screens) */}
        <nav className="fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-border bg-sidebar/95 py-2 backdrop-blur lg:hidden">
          {NAV_ITEMS.slice(0, 5).map((item) => {
            const Icon = ICONS[item.icon] ?? Activity;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  clsx(
                    "flex flex-col items-center gap-0.5 px-2 py-1 text-[10px]",
                    isActive ? "text-cyan" : "text-muted"
                  )
                }
              >
                <Icon className="h-5 w-5" />
                <span>{item.label.split(" ")[0]}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
