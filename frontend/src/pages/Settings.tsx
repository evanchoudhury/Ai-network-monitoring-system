import { useState } from "react";
import { LogIn, LogOut, Database, Trash2 } from "lucide-react";
import { SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { useAuth } from "../auth";
import { api } from "../lib/api";

export default function SettingsPage() {
  const { isAdmin, login, logout } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function doLogin() {
    setErr(null);
    setBusy(true);
    try {
      await login(username, password);
      setPassword("");
      setMsg("Signed in as operator.");
    } catch {
      setErr("Invalid credentials.");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(path: string, label: string) {
    setMsg(null);
    setBusy(true);
    try {
      const r = await api.post<Record<string, unknown>>(path);
      setMsg(`${label}: ${JSON.stringify(r.generated ?? r.deleted ?? r.status ?? r)}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Settings" subtitle="Operator authentication and administrative actions." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Operator Access">
          {isAdmin ? (
            <div className="space-y-3">
              <p className="text-sm text-success">✓ Signed in as operator.</p>
              <button className="btn" onClick={logout}>
                <LogOut className="h-4 w-4" /> Sign out
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted">
                Administrative actions (ingestion, source management, demo data, acknowledgements)
                require operator sign-in.
              </p>
              <input className="input" placeholder="Username" value={username}
                onChange={(e) => setUsername(e.target.value)} />
              <input className="input" type="password" placeholder="Password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doLogin()} />
              {err && <p className="text-xs text-critical">{err}</p>}
              <button className="btn-primary" onClick={doLogin} disabled={busy || !password}>
                <LogIn className="h-4 w-4" /> Sign in
              </button>
              <p className="text-[11px] text-muted">
                Default dev credentials come from <code className="text-text">ADMIN_USERNAME</code> /
                <code className="text-text"> ADMIN_PASSWORD</code> in your environment.
              </p>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Administrative Actions">
          {!isAdmin ? (
            <p className="text-sm text-muted">Sign in to access administrative actions.</p>
          ) : (
            <div className="space-y-3">
              <button className="btn w-full justify-start" disabled={busy}
                onClick={() => runAction("/admin/demo/generate", "Demo data generated")}>
                <Database className="h-4 w-4" /> Generate demo data (clearly flagged)
              </button>
              <button className="btn w-full justify-start" disabled={busy}
                onClick={() => runAction("/admin/retention/run", "Retention applied")}>
                <Trash2 className="h-4 w-4" /> Run data-retention cleanup now
              </button>
              {msg && <p className="break-all rounded-lg border border-border bg-bg/60 p-2 text-xs text-muted">{msg}</p>}
            </div>
          )}
        </SectionCard>

        <SectionCard title="About" className="lg:col-span-2">
          <div className="space-y-2 text-sm text-muted">
            <p>
              <span className="font-semibold text-text">Sentinel AI</span> — Network &amp; Truth
              Intelligence. An open-source platform for authorized network monitoring, anomaly
              detection, news intelligence, evidence-based claim assessment, and spam/phishing analysis.
            </p>
            <ul className="list-disc space-y-1 pl-5 text-xs">
              <li>The platform never determines absolute truth; it abstains when evidence is insufficient.</li>
              <li>Only authorized sources and services are monitored. Suspicious links are never auto-visited.</li>
              <li>Demo data is always clearly labeled and never silently substituted for live data.</li>
              <li>Budget limits cap application-level AI usage, not your total cloud bill.</li>
            </ul>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
