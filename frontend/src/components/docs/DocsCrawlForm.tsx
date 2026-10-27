"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  adminActiveCrawl,
  adminCrawlStatus,
  adminImportCsv,
  adminStartCrawl,
  adminStopCrawl,
} from "@/lib/google-docs-api";
import type { GoogleDocsCrawlRun } from "@/lib/google-docs-types";

const ACTIVE = new Set(["pending", "running", "stopping"]);

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function statusLabel(status: string) {
  return status.replace(/_/g, " ");
}

function clamp(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, Math.round(value)));
}

type Props = {
  dbReady?: boolean;
  onImported?: () => void;
  showHistory?: boolean;
};

export default function DocsCrawlForm({ dbReady = true, onImported, showHistory = false }: Props) {
  const [mode, setMode] = useState("batch_search");
  const [query, setQuery] = useState("resume template");
  const [target, setTarget] = useState(10_000);
  const [maxResults, setMaxResults] = useState(100);
  const [workers, setWorkers] = useState(20);
  const [activeRun, setActiveRun] = useState<GoogleDocsCrawlRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const refreshActive = useCallback(async () => {
    try {
      const active = await adminActiveCrawl();
      setActiveRun(active);
      setError("");
      return active;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load crawl status");
      return null;
    }
  }, []);

  useEffect(() => {
    void refreshActive();
  }, [refreshActive]);

  useEffect(() => {
    if (!activeRun || !ACTIVE.has(activeRun.status)) return;
    const runId = activeRun.id;
    const timer = window.setInterval(async () => {
      try {
        const latest = await adminCrawlStatus(runId);
        setActiveRun(latest);
        if (!ACTIVE.has(latest.status)) {
          onImported?.();
        }
      } catch {
        /* ignore polling errors */
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeRun, onImported]);

  const canStart = useMemo(() => {
    if (mode === "search") return Boolean(query.trim()) && target >= 10 && target <= 50_000;
    if (mode === "batch_search") return target >= 10 && target <= 50_000;
    return true;
  }, [mode, query, target]);

  async function handleStart() {
    if (!canStart) {
      setError(
        mode === "search"
          ? "Enter a search query and set a discovery goal between 10 and 50,000."
          : "Set the discovery goal between 10 and 50,000."
      );
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");
    try {
      const cappedMax = clamp(maxResults, 5, 100);
      const cappedWorkers = clamp(workers, 1, 100);
      const cappedTarget = clamp(target, 10, 50_000);

      const run = await adminStartCrawl({
        mode,
        query: mode === "search" ? query.trim() : undefined,
        target: mode === "from_discovered" ? undefined : cappedTarget,
        max_results: mode === "from_discovered" ? undefined : cappedMax,
        workers: cappedWorkers,
        resume: true,
        auto_import: dbReady,
      });
      setActiveRun(run);
      setMessage(
        dbReady
          ? "Crawl started — documents are saved to the database as they are crawled."
          : "Crawl started — run database setup first."
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start crawl");
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    if (!activeRun) return;
    setBusy(true);
    setError("");
    try {
      const run = await adminStopCrawl(activeRun.id);
      setActiveRun(run);
      setMessage("Stop requested.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop crawl");
    } finally {
      setBusy(false);
    }
  }

  async function handleImport() {
    setImporting(true);
    setError("");
    setMessage("");
    try {
      const result = await adminImportCsv();
      setMessage(`Imported ${formatNumber(result.imported)} documents.`);
      onImported?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const crawlActive = Boolean(activeRun && ACTIVE.has(activeRun.status));
  const progress =
    activeRun && activeRun.discovered_count
      ? Math.min(100, Math.round(((activeRun.parsed_count || 0) / activeRun.discovered_count) * 100))
      : crawlActive
        ? 8
        : 0;

  return (
    <div className="docs-crawl-layout">
      <section className="docs-crawl-panel card">
        <div className="docs-crawl__top">
          <div>
            <h2>Crawl settings</h2>
            <p>
              Discover public Google Docs via web search, then crawl and save to the database. Use{" "}
              <strong>Batch search</strong> with <code>queries.txt</code> to reach tens of thousands of documents.
            </p>
          </div>
          <div className="docs-crawl__buttons">
            <button
              type="button"
              className="btn-primary"
              onClick={() => void handleStart()}
              disabled={busy || crawlActive || !canStart}
            >
              {crawlActive ? "Running…" : "Start crawl"}
            </button>
            {crawlActive ? (
              <button type="button" className="btn-secondary" onClick={() => void handleStop()} disabled={busy}>
                Stop
              </button>
            ) : null}
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void handleImport()}
              disabled={importing || crawlActive || !dbReady}
              title={dbReady ? "Import an old results.csv file into the database" : "Run database setup first"}
            >
              {importing ? "Importing…" : "Import legacy CSV"}
            </button>
          </div>
        </div>

        <div className="docs-crawl__fields">
          <label>
            <span>Mode</span>
            <select className="input py-2 text-sm" value={mode} onChange={(e) => setMode(e.target.value)} disabled={crawlActive}>
              <option value="batch_search">Batch search (queries file) — recommended</option>
              <option value="search">Search query + expand</option>
              <option value="from_discovered">Discovered URLs file only</option>
            </select>
          </label>

          {mode === "search" ? (
            <>
              <label className="docs-crawl__wide">
                <span>Search query</span>
                <input
                  className="input py-2 text-sm"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="resume template"
                  disabled={crawlActive}
                />
              </label>
              <label>
                <span>Results per search query</span>
                <input
                  className="input py-2 text-sm"
                  type="number"
                  min={5}
                  max={100}
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  disabled={crawlActive}
                />
              </label>
              <label>
                <span>Discovery goal (total URLs)</span>
                <input
                  className="input py-2 text-sm"
                  type="number"
                  min={10}
                  max={50000}
                  value={target}
                  onChange={(e) => setTarget(Number(e.target.value))}
                  disabled={crawlActive}
                />
              </label>
            </>
          ) : null}

          {mode === "batch_search" ? (
            <>
              <label>
                <span>Discovery goal (total URLs)</span>
                <input
                  className="input py-2 text-sm"
                  type="number"
                  min={10}
                  max={50000}
                  value={target}
                  onChange={(e) => setTarget(Number(e.target.value))}
                  disabled={crawlActive}
                />
              </label>
              <label>
                <span>Results per search query</span>
                <input
                  className="input py-2 text-sm"
                  type="number"
                  min={5}
                  max={100}
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  disabled={crawlActive}
                />
              </label>
            </>
          ) : null}

          {mode === "from_discovered" ? (
            <p className="docs-crawl__hint">
              Crawls URLs from <code>discovered_urls.txt</code> in the indexer data folder. Use batch search first to
              populate that file.
            </p>
          ) : null}

          <label>
            <span>Workers</span>
            <input
              className="input py-2 text-sm"
              type="number"
              min={1}
              max={100}
              value={workers}
              onChange={(e) => setWorkers(Number(e.target.value))}
              disabled={crawlActive}
            />
          </label>
        </div>

        {message ? <p className="docs-crawl__msg docs-crawl__msg--ok">{message}</p> : null}
        {error ? <p className="docs-crawl__msg docs-crawl__msg--err">{error}</p> : null}
      </section>

      {activeRun ? (
        <section className="docs-crawl-panel docs-crawl-panel--job card">
          <div className="docs-crawl__job-head">
            <div>
              <span className="docs-crawl__job-title">{statusLabel(activeRun.mode)}</span>
              <span className="docs-crawl__job-sub">
                Run {activeRun.id.slice(0, 8)} · {activeRun.started_at ? new Date(activeRun.started_at).toLocaleString() : "Starting…"}
              </span>
            </div>
            <span className={`docs-crawl__badge docs-crawl__badge--${activeRun.status}`}>{activeRun.status}</span>
          </div>

          <div className="docs-crawl__progress">
            <div className="docs-crawl__progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <p className="docs-crawl__progress-label">{crawlActive ? `${progress}% complete` : "Run finished"}</p>

          <dl className="docs-crawl__metrics">
            <div>
              <dt>Discovered</dt>
              <dd>{formatNumber(activeRun.discovered_count)}</dd>
            </div>
            <div>
              <dt>Crawled</dt>
              <dd>{formatNumber(activeRun.crawled_count)}</dd>
            </div>
            <div>
              <dt>Parsed</dt>
              <dd>{formatNumber(activeRun.parsed_count)}</dd>
            </div>
            <div>
              <dt>Failed</dt>
              <dd>{formatNumber(activeRun.failed_count)}</dd>
            </div>
            <div>
              <dt>Synced</dt>
              <dd>{formatNumber(activeRun.imported_count)}</dd>
            </div>
            <div>
              <dt>Phase</dt>
              <dd>{activeRun.current_phase || "—"}</dd>
            </div>
          </dl>

          {activeRun.last_error ? (
            <p className="docs-crawl__msg docs-crawl__msg--err">{activeRun.last_error}</p>
          ) : null}

          {showHistory && activeRun.log_lines && activeRun.log_lines.length > 0 ? (
            <div className="docs-crawl__logs">
              <span className="docs-crawl__history-title">Live log</span>
              <pre>
                {activeRun.log_lines
                  .slice(-12)
                  .map((line) => `${line.ts} ${line.message}`)
                  .join("\n")}
              </pre>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="docs-crawl-panel docs-crawl-panel--idle card">
          <strong>No active crawl</strong>
          <p>Configure settings on the left and start a crawl. Progress and file sync stats appear here.</p>
        </section>
      )}
    </div>
  );
}
