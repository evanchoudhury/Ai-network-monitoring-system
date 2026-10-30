import { useState } from "react";
import { ExternalLink, Layers } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Article, Story } from "../lib/types";
import { AsyncBoundary, Badge, SectionCard } from "../components/ui";
import { PageHeader } from "../components/shared";
import { timeAgo } from "../lib/format";
import { useAuth } from "../auth";

export default function NewsPage() {
  const { isAdmin } = useAuth();
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const tq = topic ? `?topic=${topic}` : "";

  const articles = useApi<{ total: number; items: Article[] }>(
    () => api.get(`/news/articles${tq}`),
    [topic]
  );
  const stories = useApi<Story[]>(() => api.get<Story[]>("/news/stories"), []);

  async function ingestNow() {
    setBusy(true);
    try {
      await api.post("/news/ingest");
      await api.post("/news/analyze-recent?limit=30");
      articles.refetch();
      stories.refetch();
    } finally {
      setBusy(false);
    }
  }

  const topics = ["", "politics", "health", "technology", "business", "science", "world", "general"];

  return (
    <div>
      <PageHeader
        title="News Intelligence"
        subtitle="Collected articles grouped into stories by distinct-publisher diversity."
        actions={
          isAdmin ? (
            <button className="btn-primary" onClick={ingestNow} disabled={busy}>
              {busy ? "Ingesting…" : "Ingest sources now"}
            </button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex flex-wrap gap-1.5">
            {topics.map((t) => (
              <button key={t || "all"} onClick={() => setTopic(t)}
                className={`chip border ${topic === t ? "border-cyan/50 bg-cyan/10 text-cyan" : "border-border bg-elevated text-muted"}`}>
                {t || "all"}
              </button>
            ))}
          </div>
          <SectionCard title="Latest Articles" bodyClassName="p-0">
            <AsyncBoundary state={articles} isEmpty={(d) => d.items.length === 0}
              emptyProps={{
                title: "No articles yet",
                hint: isAdmin ? "Click “Ingest sources now” to fetch from configured RSS feeds."
                  : "No articles collected. An operator can ingest sources.",
              }}>
              {(d) => (
                <div className="divide-y divide-border/60">
                  {d.items.map((a) => (
                    <article key={a.id} className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h4 className="font-medium text-text">{a.headline}</h4>
                          {a.summary && <p className="mt-1 line-clamp-2 text-sm text-muted">{a.summary}</p>}
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted">
                            {a.publisher && <span className="text-text">{a.publisher}</span>}
                            {a.topic && <Badge className="bg-blue/15 text-blue">{a.topic}</Badge>}
                            <span>· {timeAgo(a.published_at ?? a.ingested_at)}</span>
                            {a.story_id && (
                              <span className="inline-flex items-center gap-1">
                                <Layers className="h-3 w-3" /> story #{a.story_id}
                              </span>
                            )}
                          </div>
                        </div>
                        <a href={a.url} target="_blank" rel="noopener noreferrer"
                          className="shrink-0 text-muted hover:text-cyan" title="Open original source">
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </AsyncBoundary>
          </SectionCard>
        </div>

        <SectionCard title="Related Stories" bodyClassName="p-0">
          <AsyncBoundary state={stories} isEmpty={(d) => d.length === 0}
            emptyProps={{ title: "No stories yet" }}>
            {(d) => (
              <div className="divide-y divide-border/60">
                {d.map((s) => (
                  <div key={s.id} className="p-3">
                    <h5 className="line-clamp-2 text-sm font-medium text-text">{s.title}</h5>
                    <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted">
                      <span>{s.article_count} article(s)</span>
                      <span className="inline-flex items-center gap-1 text-cyan">
                        {s.source_diversity} source(s)
                      </span>
                      {s.topic && <Badge className="bg-blue/15 text-blue">{s.topic}</Badge>}
                    </div>
                  </div>
                ))}
                <p className="p-3 text-[11px] text-muted">
                  “Sources” counts distinct publishers — syndicated duplicates are not
                  counted as independent corroboration.
                </p>
              </div>
            )}
          </AsyncBoundary>
        </SectionCard>
      </div>
    </div>
  );
}
