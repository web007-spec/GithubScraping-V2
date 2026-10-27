"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { DriveCard, DriveCardSkeleton } from "@/components/drive/DriveCard";
import { fetchDriveFiles, fetchDriveStats } from "@/lib/google-drive-api";
import type { DriveFile } from "@/lib/google-drive-types";

const PAGE_SIZE = 24;

const SORT_OPTIONS = [
  { value: "indexed_at", label: "Recently indexed" },
  { value: "name", label: "Title" },
  { value: "word_count", label: "Word count" },
  { value: "created_at", label: "Date added" },
];

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function fileKey(file: DriveFile) {
  return String(file.id || file.file_id);
}

export default function DriveExplorer() {
  const [items, setItems] = useState<DriveFile[]>([]);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("indexed_at");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [stats, setStats] = useState<{
    total?: number;
    indexed?: number;
    with_text?: number;
    with_content?: number;
  } | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const scrollSentinelRef = useRef<HTMLDivElement>(null);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchDriveStats();
      if (data.ok) setStats(data);
    } catch {
      /* optional */
    }
  }, []);

  const loadPage = useCallback(
    async (targetOffset: number, append: boolean) => {
      const data = await fetchDriveFiles({
        q,
        sort,
        order,
        limit: PAGE_SIZE,
        offset: targetOffset,
      });
      setTotal(data.total);
      setHasMore(targetOffset + data.items.length < data.total);
      setItems((prev) => (append ? [...prev, ...data.items] : data.items));
    },
    [order, q, sort]
  );

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setOffset(0);
    const timer = window.setTimeout(() => {
      loadPage(0, false)
        .catch((e) => {
          if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load files");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, q ? 350 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [q, sort, order, loadPage]);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || !hasMore) return;
    const nextOffset = offset + PAGE_SIZE;
    setLoadingMore(true);
    setError("");
    try {
      await loadPage(nextOffset, true);
      setOffset(nextOffset);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more files");
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, loadPage, loading, loadingMore, offset]);

  useEffect(() => {
    const node = scrollSentinelRef.current;
    if (!node || loading || items.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) void loadMore();
      },
      { rootMargin: "480px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [items.length, loadMore, loading]);

  return (
    <div className="docs-page">
      <header className="docs-hero docs-hero--compact">
        <div className="docs-hero__content">
          <p className="docs-hero__eyebrow">Google Drive workspace</p>
          <h1 className="docs-hero__title">Files</h1>
          <p className="docs-hero__copy">
            Browse indexed public Google Drive files. Start a crawl to discover folders automatically — no manual URLs
            needed.
          </p>
          <div className="docs-hero__actions">
            <Link href="/explore/drive/crawl/new" className="btn-primary">
              New crawl
            </Link>
            <Link href="/explore/drive/crawl/runs" className="btn-secondary">
              Crawl runs
            </Link>
          </div>
        </div>
      </header>

      {stats ? (
        <section className="docs-page__stats">
          <article className="docs-stat-card">
            <span>Total indexed</span>
            <strong>{formatNumber(stats.total)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>Indexed files</span>
            <strong>{formatNumber(stats.indexed)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>With full content</span>
            <strong>{formatNumber(stats.with_content ?? stats.with_text)}</strong>
          </article>
          <article className="docs-stat-card">
            <span>Showing</span>
            <strong>{formatNumber(items.length)}</strong>
            {total != null ? <em>of {formatNumber(total)}</em> : null}
          </article>
        </section>
      ) : null}

      <section className="docs-toolbar card">
        <p className="docs-toolbar__hint">
          {q ? `Search results for “${q}”` : "All indexed files · scroll to load more"}
        </p>
        <div className="docs-toolbar__controls">
          <label className="docs-toolbar__field docs-toolbar__field--wide">
            <span>Search</span>
            <input
              className="input py-2 text-sm"
              placeholder="Filename or content…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </label>
          <label className="docs-toolbar__field">
            <span>Sort by</span>
            <select className="input py-2 text-sm" value={sort} onChange={(e) => setSort(e.target.value)}>
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

      {loading && items.length === 0 ? (
        <div className="docs-card-grid">
          {Array.from({ length: 8 }).map((_, index) => (
            <DriveCardSkeleton key={index} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="docs-empty-state card">
          <strong>No indexed files yet</strong>
          <p>Run a crawl to automatically discover public Drive folders and index matching files.</p>
          <Link href="/explore/drive/crawl/new" className="btn-primary">
            Start a crawl
          </Link>
        </div>
      ) : (
        <>
          <div className={`docs-card-grid${loading ? " docs-card-grid--loading" : ""}`}>
            {items.map((file) => (
              <div key={fileKey(file)} className="docs-card-anchor">
                <DriveCard file={file} />
              </div>
            ))}
            {loadingMore ? Array.from({ length: 3 }).map((_, i) => <DriveCardSkeleton key={`more-${i}`} />) : null}
          </div>
          <div className="docs-scroll-sentinel" ref={scrollSentinelRef} aria-hidden={!hasMore && !loadingMore}>
            {loadingMore ? (
              <span>
                <span className="users-grid-loading__spinner" /> Loading more files
              </span>
            ) : hasMore ? (
              <span>Scroll for more</span>
            ) : items.length > PAGE_SIZE ? (
              <span>All files loaded</span>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
