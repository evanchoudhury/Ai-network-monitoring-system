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
import type { ModeInfo } from "../lib/types";
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

export function ModeIndicator({ mode }: { mode?: ModeInfo }) {
  if (!mode) return null;
  const map = {
    live: { label: "LIVE", dot: "bg-success", ring: "ring-success/40", text: "text-success" },
    live_stale: { label: "LIVE · STALE", dot: "bg-warning", ring: "ring-warning/40", text: "text-warning" },
    demo: { label: "DEMO", dot: "bg-cyan", ring: "ring-cyan/40", text: "text-cyan" },
    empty: { label: "NO DATA", dot: "bg-muted", ring: "ring-muted/40", text: "text-muted" },
  }[mode.mode];
  return (
    <div
      title={
        mode.mode === "demo"
          ? "Showing synthetic demonstration data."
          : mode.mode === "live_stale"
            ? `Live source is stale. Last live metric ${timeAgo(mode.last_live_metric_at)}.`
            : mode.mode === "empty"
              ? "No data collected yet. Generate demo data or connect a live source."
              : "Showing live data from configured sources."
      }
      className={clsx(
        "inline-flex items-center gap-2 rounded-lg border border-border bg-elevated px-3 py-1.5 ring-1",
        map.ring
      )}
    >
      <span className={clsx("h-2 w-2 rounded-full animate-pulseGlow", map.dot)} />
      <span className={clsx("text-xs font-semibold tracking-wider", map.text)}>{map.label}</span>
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
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-blue/15 font-semibold text-text ring-1 ring-blue/40 shadow-glow-blue"
                  : "text-muted hover:bg-elevated hover:text-text"
              )
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

export function Layout({
  children,
  mode,
  alertCount,
  rightControls,
}: {
  children: ReactNode;
  mode?: ModeInfo;
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
          <ModeIndicator mode={mode} />
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
