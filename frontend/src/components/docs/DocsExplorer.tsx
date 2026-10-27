"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import AISearchLoader from "@/components/AISearchLoader";
import { DocsCard, DocsCardSkeleton } from "@/components/docs/DocsCard";
import { useDocsBrowseFilter } from "@/lib/docs-browse-context";
import { fetchPublicDocsList, fetchPublicDocsSearch, fetchPublicDocsStats } from "@/lib/google-docs-api";
import type { GoogleDocsStats, GoogleDocument, GoogleDocumentSearchHit } from "@/lib/google-docs-types";

const PAGE_SIZE = 24;

const SORT_OPTIONS = [
  { value: "crawled_at", label: "Recently indexed" },
  { value: "title", label: "Title" },
  { value: "word_count", label: "Word count" },
  { value: "created_at", label: "Date added" },
];

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function docKey(doc: GoogleDocument) {
  return String(doc.id || doc.google_doc_id);
}

function DocsExplorerContent() {
  const { filter: navFilter } = useDocsBrowseFilter();
  const [docs, setDocs] = useState<GoogleDocument[]>([]);
  const [searchResults, setSearchResults] = useState<GoogleDocumentSearchHit[]>([]);
  const [searchMeta, setSearchMeta] = useState<{ mode?: string; total?: number | null }>({});
  const [searching, setSearching] = useState(false);
  const [stats, setStats] = useState<GoogleDocsStats | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [sort, setSort] = useState("crawled_at");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const scrollSentinelRef = useRef<HTMLDivElement>(null);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchPublicDocsStats();
      setStats(data);
    } catch {
      /* optional */
    }
  }, []);

  const loadPage = useCallback(
    async (targetPage: number, append: boolean) => {
      const data = await fetchPublicDocsList({
        sort,
        order,
        page: targetPage,
        page_size: PAGE_SIZE,
      });
      setTotal(data.total);
      setHasMore(Boolean(data.has_more));
      setDocs((prev) => (append ? [...prev, ...data.items] : data.items));
    },
    [sort, order]
  );

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setPage(1);
    loadPage(1, false)
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load documents");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sort, order, loadPage]);

  const searchQuery = navFilter.trim();

  useEffect(() => {
    if (!searchQuery) {
      setSearchResults([]);
      setSearchMeta({});
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    setError("");
    const timer = window.setTimeout(() => {
      fetchPublicDocsSearch({ q: searchQuery, page_size: 48, ai: true })
        .then((data) => {
          if (cancelled) return;
          setSearchResults(data.items || []);
          setSearchMeta({ mode: data.mode, total: data.total });
        })
        .catch((e) => {
          if (!cancelled) setError(e instanceof Error ? e.message : "AI search failed");
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [searchQuery]);

  const visibleDocs = searchQuery ? searchResults : docs;
  const isAiSearch = Boolean(searchQuery);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || !hasMore) return;
    const nextPage = page + 1;
    setLoadingMore(true);
    setError("");
    try {
      await loadPage(nextPage, true);
      setPage(nextPage);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more documents");
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, loadPage, loading, loadingMore, page]);

  useEffect(() => {
    const node = scrollSentinelRef.current;
    if (!node || loading || docs.length === 0 || isAiSearch) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) void loadMore();
      },
      { rootMargin: "480px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [docs.length, isAiSearch, loadMore, loading]);

  return (
    <div className="docs-page">
      <div className="docs-page__head">
        <h1 className="page-title">Documents</h1>
        <p className="page-subtitle">
          Browse archived public Google Docs. Use the search field above for AI search across the full
          database, or use header AI Search for GitHub users and docs together.
        </p>
      </div>

      {stats ? (
        <section className="docs-page__stats">
          <article className="docs-stat-card">
            <span>Total indexed</span>
            <strong>{formatNumber(stats.total)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>Parsed documents</span>
            <strong>{formatNumber(stats.parsed)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>With full content</span>
            <strong>{formatNumber(stats.with_content)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>With embedded images</span>
            <strong>{formatNumber(stats.with_images)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>Showing</span>
            <strong>{formatNumber(visibleDocs.length)}</strong>
            {total != null ? <em>of {formatNumber(total)}</em> : null}
          </article>
        </section>
      ) : null}

      <section className="docs-toolbar card">
        <p className="docs-toolbar__hint">
          {searchQuery
            ? searching
              ? `AI search in progress for “${searchQuery}”`
              : `AI search: ${formatNumber(visibleDocs.length)} match${visibleDocs.length === 1 ? "" : "es"}${searchMeta.total != null ? ` of ${formatNumber(searchMeta.total)}` : ""}${searchMeta.mode === "ai" ? " · OpenAI ranked" : searchMeta.mode === "ranked" ? " · relevance ranked" : ""}`
            : "All indexed documents · scroll to load more"}
        </p>
        <div className="docs-toolbar__controls">
          <label className="docs-toolbar__field">
            <span>Sort by</span>
            <select
              className="input py-2 text-sm"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="docs-toolbar__field">
            <span>Order</span>
            <select
              className="input py-2 text-sm"
              value={order}
              onChange={(e) => setOrder(e.target.value as "desc" | "asc")}
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
        </div>
      </section>

      {error ? <p className="docs-page__error">{error}</p> : null}

      {searching ? (
        <AISearchLoader query={searchQuery} detail="Querying MongoDB and ranking exact matches…" />
      ) : null}

      {!searching && loading && docs.length === 0 && !isAiSearch ? (
        <div className="docs-card-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <DocsCardSkeleton key={i} />
          ))}
        </div>
      ) : !searching && visibleDocs.length === 0 ? (
        <div className="docs-empty-state card">
          <strong>{isAiSearch ? "No matching documents" : "No documents to display yet"}</strong>
          <p>
            {isAiSearch
              ? "Try different keywords or a more specific phrase."
              : "Documents appear here after an administrator runs a crawl."}
          </p>
          {!isAiSearch ? (
            <Link href="/explore/docs/crawl/new" className="btn-primary">
              Go to New Crawl
            </Link>
          ) : null}
        </div>
      ) : !searching ? (
        <>
          <div className={`docs-card-grid${loading ? " docs-card-grid--loading" : ""}`}>
            {visibleDocs.map((doc) => {
              const hit = doc as GoogleDocumentSearchHit;
              return (
              <div key={docKey(doc)} className="docs-card-anchor">
                <DocsCard
                  doc={doc}
                  snippet={hit.snippet}
                  relevanceScore={hit.relevance_score}
                  rankingReason={hit.ranking_reason}
                />
              </div>
              );
            })}
            {!isAiSearch && loadingMore
              ? Array.from({ length: 3 }).map((_, i) => <DocsCardSkeleton key={`more-${i}`} />)
              : null}
          </div>
          {!isAiSearch ? (
            <div
              className="docs-scroll-sentinel"
              ref={scrollSentinelRef}
              aria-hidden={!hasMore && !loadingMore}
            >
              {loadingMore ? (
                <span>
                  <span className="users-grid-loading__spinner" /> Loading more documents
                </span>
              ) : hasMore ? (
                <span>Scroll for more</span>
              ) : docs.length > PAGE_SIZE ? (
                <span>All documents loaded</span>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default function DocsExplorer() {
  return (
    <Suspense fallback={<p className="text-github-muted">Loading documents…</p>}>
      <DocsExplorerContent />
    </Suspense>
  );
}
