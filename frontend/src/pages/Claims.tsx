import { useEffect, useState } from "react";
import { ExternalLink, Scale } from "lucide-react";
import clsx from "clsx";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Claim } from "../lib/types";
import { AsyncBoundary, Badge, SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { CLAIM_LABEL_META } from "../lib/constants";
import { timeAgo } from "../lib/format";

function ClaimCard({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const meta = CLAIM_LABEL_META[claim.status];
  const ev = claim.evidence ?? [];
  const support = ev.filter((e) => e.stance === "support");
  const contra = ev.filter((e) => e.stance === "contradict");

  return (
    <div className="p-4">
      <div className="flex items-start justify-between gap-3">
        <blockquote className="border-l-2 border-border pl-3 text-sm text-text">“{claim.text}”</blockquote>
        <Badge className={clsx("shrink-0", meta.className)}>{meta.label}</Badge>
      </div>

      {claim.assessment && (
        <p className="mt-2 text-sm text-muted">{claim.assessment.explanation}</p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span className="inline-flex items-center gap-1 text-success">
          ▲ {claim.assessment?.supporting_count ?? 0} supporting
        </span>
        <span className="inline-flex items-center gap-1 text-critical">
          ▼ {claim.assessment?.contradicting_count ?? 0} contradicting
        </span>
        <span>· {claim.assessment?.model_version}</span>
        <span>· {timeAgo(claim.created_at)}</span>
        {(support.length > 0 || contra.length > 0) && (
          <button onClick={() => setOpen((o) => !o)} className="text-cyan hover:underline">
            {open ? "Hide evidence" : "Show evidence"}
          </button>
        )}
      </div>

      {open && (
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <EvidenceCol title="Supporting" items={support} accent="text-success" />
          <EvidenceCol title="Contradicting" items={contra} accent="text-critical" />
        </div>
      )}

      {claim.assessment?.limitations && (
        <p className="mt-3 rounded-lg border border-border bg-bg/60 p-2 text-[11px] text-muted">
          <strong className="text-muted">Limitations:</strong> {claim.assessment.limitations}
        </p>
      )}
    </div>
  );
}

function EvidenceCol({
  title,
  items,
  accent,
}: {
  title: string;
  items: Claim["evidence"];
  accent: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-bg/40 p-2">
      <div className={clsx("mb-1 text-xs font-semibold", accent)}>{title} ({items?.length ?? 0})</div>
      {!items || items.length === 0 ? (
        <p className="text-[11px] text-muted">None found in configured sources.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((e, i) => (
            <li key={i} className="text-[11px]">
              <a href={e.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-text hover:text-cyan">
                {e.title ?? e.url} <ExternalLink className="h-3 w-3" />
              </a>
              <div className="text-muted">
                {e.publisher ?? "unknown"} · {e.evidence_timestamp ? timeAgo(e.evidence_timestamp) : "no date"}
                {" "}· rel {e.relevance.toFixed(2)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ClaimsPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Claim[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const sq = status ? `?status=${status}` : "";
  const claims = useApi<{ total: number; items: Claim[] }>(() => api.get(`/claims${sq}`), [status]);

  async function analyze() {
    if (text.trim().length < 20) {
      setErr("Please enter at least 20 characters.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post<{ claims: Claim[] }>("/claims/analyze", {
        text,
        use_factcheck: true,
      });
      setResult(r.claims);
      claims.refetch();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  const labels = ["", "supported", "contradicted", "misleading", "disputed", "unverified", "insufficient_evidence"];

  return (
    <div>
      <PageHeader
        title="Claim Verification"
        subtitle="Evidence-based assessment that abstains when evidence is insufficient — never fabricated certainty."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SectionCard className="lg:col-span-1" title="Analyze a claim">
          <textarea
            className="input h-32 resize-none"
            placeholder="Paste a news sentence or statement to assess against configured evidence sources…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="mt-2 flex items-center gap-2">
            <button className="btn-primary" onClick={analyze} disabled={busy}>
              <Scale className="h-4 w-4" />
              {busy ? "Assessing…" : "Assess claim"}
            </button>
            {err && <span className="text-xs text-critical">{err}</span>}
          </div>
          {result && (
            <div className="mt-3 space-y-2 border-t border-border pt-3">
              {result.length === 0 ? (
                <p className="text-sm text-muted">No check-worthy factual claim was extracted.</p>
              ) : (
                result.map((c) => {
                  const meta = CLAIM_LABEL_META[c.status];
                  return (
                    <div key={c.id} className="rounded-lg border border-border bg-bg/40 p-2">
                      <Badge className={meta.className}>{meta.label}</Badge>
                      <p className="mt-1 text-xs text-muted">{c.assessment?.explanation}</p>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </SectionCard>

        <SectionCard className="lg:col-span-2" title="Assessed Claims" bodyClassName="p-0"
          action={
            <select className="input w-44 py-1 text-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
              {labels.map((l) => (
                <option key={l || "all"} value={l}>{l ? CLAIM_LABEL_META[l as keyof typeof CLAIM_LABEL_META]?.label ?? l : "All labels"}</option>
              ))}
            </select>
          }>
          <AsyncBoundary state={claims} isEmpty={(d) => d.items.length === 0}
            emptyProps={{ title: "No claims yet", hint: "Assess a claim, or ingest news to populate." }}>
            {(d) => (
              <div className="divide-y divide-border/60">
                {d.items.map((c) => <ClaimCardLoader key={c.id} id={c.id} fallback={c} />)}
              </div>
            )}
          </AsyncBoundary>
        </SectionCard>
      </div>
    </div>
  );
}

// Lazily fetch the full claim (with evidence) once on mount.
function ClaimCardLoader({ id, fallback }: { id: number; fallback: Claim }) {
  const [full, setFull] = useState<Claim | null>(null);
  useEffect(() => {
    let active = true;
    api.get<Claim>(`/claims/${id}`)
      .then((c) => active && setFull(c))
      .catch(() => active && setFull(fallback));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  return <ClaimCard claim={full ?? fallback} />;
}
