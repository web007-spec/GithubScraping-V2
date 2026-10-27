"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import AISearchLoader from "@/components/AISearchLoader";
import { DocsCard, displayDocTitle } from "@/components/docs/DocsCard";
import type { GoogleDocument } from "@/lib/google-docs-types";
import { fetchGlobalAiSearch, type GlobalSearchHit } from "@/lib/global-search-api";

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function SearchResultsContent() {
  const searchParams = useSearchParams();
  const query = (searchParams.get("q") || "").trim();
  const [items, setItems] = useState<GlobalSearchHit[]>([]);
  const [meta, setMeta] = useState<{ mode?: string; total?: number | null; cached?: boolean }>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!query) {
      setItems([]);
      setMeta({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchGlobalAiSearch({ q: query, page_size: 30 })
      .then((data) => {
        if (cancelled) return;
        setItems(data.items || []);
        setMeta({ mode: data.mode, total: data.total, cached: data.cached });
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Search failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query]);

  const users = useMemo(() => items.filter((item) => item.type === "user"), [items]);
  const docs = useMemo(() => items.filter((item) => item.type === "doc"), [items]);

  if (!query) {
    return (
      <div className="search-page__empty card">
        <strong>Global AI Search</strong>
        <p>
          Use the <strong>AI Search</strong> bar in the header to find GitHub users and Google Docs by
          meaning or keywords. One smart query searches both archives.
        </p>
      </div>
    );
  }

  return (
    <div className="search-page">
      <header className="search-page__hero">
        <p className="search-page__eyebrow">Global AI search</p>
        <h1>Results for “{query}”</h1>
        <p className="search-page__meta">
          {loading
            ? "Searching GitHub users and Google Docs…"
            : meta.mode === "ai"
              ? `OpenAI-ranked across both archives${meta.cached ? " · cached" : ""}`
              : meta.mode === "ranked"
                ? "Relevance-ranked from database (exact + keyword matches)"
                : "Keyword matches"}
          {meta.total != null ? ` · ${formatNumber(meta.total)} hits` : ""}
        </p>
      </header>

      {error ? <p className="docs-page__error">{error}</p> : null}

      {loading ? (
        <AISearchLoader query={query} detail="Scanning archives and ranking the best matches…" />
      ) : items.length === 0 ? (
        <div className="search-page__empty card">
          <strong>No matches</strong>
          <p>Try different keywords or a broader phrase.</p>
        </div>
      ) : (
        <div className="search-page__sections">
          {users.length > 0 ? (
            <section className="search-page__section card">
              <div className="search-page__section-head">
                <h2>GitHub users</h2>
                <span>{users.length}</span>
              </div>
              <ul className="search-user-list">
                {users.map((user) => (
                  <li key={user.id}>
                    <Link href={`/users/${encodeURIComponent(user.login || user.id)}`}>
                      <strong>{user.name || user.login}</strong>
                      <span>@{user.login}</span>
                      {user.location ? <em>{user.location}</em> : null}
                      {user.relevance_score != null ? (
                        <small>{user.relevance_score}% match</small>
                      ) : null}
                      {user.snippet ? <p>{user.snippet}</p> : null}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {docs.length > 0 ? (
            <section className="search-page__section">
              <div className="search-page__section-head">
                <h2>Google Docs</h2>
                <span>{docs.length}</span>
              </div>
              <div className="docs-card-grid">
                {docs.map((hit) => (
                  <DocsCard
                    key={hit.id}
                    doc={hit as GoogleDocument}
                    snippet={hit.snippet}
                    relevanceScore={hit.relevance_score}
                    rankingReason={hit.ranking_reason}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="text-github-muted">Loading search…</p>}>
      <SearchResultsContent />
    </Suspense>
  );
}
