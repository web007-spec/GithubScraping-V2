"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DriveCategoryPicker from "@/components/drive/DriveCategoryPicker";
import {
  adminActiveDriveCrawl,
  adminDriveCrawlStatus,
  adminStartDriveCrawl,
  adminStopDriveCrawl,
  fetchDriveCategories,
} from "@/lib/google-drive-api";
import type { DriveCategory, DriveCrawlRun } from "@/lib/google-drive-types";

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
  showHistory?: boolean;
};

export default function DriveCrawlForm({ showHistory = false }: Props) {
  const [categories, setCategories] = useState<DriveCategory[]>([]);
  const [selected, setSelected] = useState<string[]>(["templates"]);
  const [mode, setMode] = useState("batch_search");
  const [query, setQuery] = useState("resume template");
  const [target, setTarget] = useState(200);
  const [maxResults, setMaxResults] = useState(50);
  const [maxDepth, setMaxDepth] = useState(3);
  const [maxFiles, setMaxFiles] = useState(500);
  const [workers, setWorkers] = useState(6);
  const [activeRun, setActiveRun] = useState<DriveCrawlRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const jobPanelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    void fetchDriveCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const refreshActive = useCallback(async () => {
    try {
      const active = await adminActiveDriveCrawl();
      setActiveRun(active);
      if (!active) setError("");
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
    if (!activeRun || !ACTIVE.has(activeRun.status)) {
      if (activeRun?.status === "failed" && activeRun.last_error) setError(activeRun.last_error);
      return;
    }
    const runId = activeRun.id;
    const timer = window.setInterval(async () => {
      try {
        const latest = await adminDriveCrawlStatus(runId);
        setActiveRun(latest);
        if (latest.status === "failed" && latest.last_error) {
          setError(latest.last_error);
          setMessage("");
        }
      } catch {
        /* ignore */
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeRun]);

  const canStart = useMemo(() => {
    if (selected.length === 0) return false;
    if (mode === "search") return Boolean(query.trim()) && target >= 10 && target <= 50_000;
    if (mode === "batch_search") return target >= 10 && target <= 50_000;
    return true;
  }, [mode, query, selected.length, target]);

  async function handleStart() {
    if (!canStart) {
      setError(
        selected.length === 0
          ? "Select at least one content category."
          : "Check your discovery settings and try again."
      );
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const run = await adminStartDriveCrawl({
        mode,
        query: mode === "search" ? query.trim() : undefined,
        target: mode === "from_discovered" ? undefined : clamp(target, 10, 50_000),
        max_results: mode === "from_discovered" ? undefined : clamp(maxResults, 5, 100),
        categories: selected,
        max_depth: clamp(maxDepth, 1, 8),
        max_files: clamp(maxFiles, 1, 10_000),
        workers: clamp(workers, 1, 32),
        resume: true,
      });
      setActiveRun(run);
      setMessage("Crawl started — discovering public Docs and Drive links, then indexing by category.");
      requestAnimationFrame(() => jobPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start crawl");
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    if (!activeRun) return;
    setBusy(true);
    try {
      const run = await adminStopDriveCrawl(activeRun.id);
      setActiveRun(run);
      setMessage("Stop requested.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop crawl");
    } finally {
      setBusy(false);
    }
  }

  const crawlActive = Boolean(activeRun && ACTIVE.has(activeRun.status));
  const indexed = activeRun?.files_indexed || 0;
  const goal = Math.max(activeRun?.discovered_count || 1, maxFiles, 1);
  const progress =
    discoveredProgress(activeRun, indexed, goal, crawlActive);

  return (
    <div className="docs-crawl-layout">
      <section className="docs-crawl-panel card">
        <div className="docs-crawl__top">
          <div>
            <h2>Crawl settings</h2>
            <p>
              Discover public Google Docs and Drive files via web search, then index content matching your categories.
            </p>
          </div>
          <div className="docs-crawl__buttons">
            <button
              type="button"
              className="btn-primary"
              onClick={() => void handleStart()}
              disabled={busy || crawlActive || !canStart}
            >
              {busy ? "Starting…" : crawlActive ? "Running…" : "Start crawl"}
            </button>
            {crawlActive ? (
              <button type="button" className="btn-secondary" onClick={() => void handleStop()} disabled={busy}>
                Stop
              </button>
            ) : null}
          </div>
        </div>

        {message ? <p className="docs-crawl__msg docs-crawl__msg--ok">{message}</p> : null}
        {error ? <p className="docs-crawl__msg docs-crawl__msg--err">{error}</p> : null}
        {!canStart && selected.length === 0 ? (
          <p className="docs-crawl__msg docs-crawl__msg--err">Select at least one content category to enable Start crawl.</p>
        ) : null}

        <div className="docs-crawl__fields">
          <label>
            <span>Mode</span>
            <select className="input py-2 text-sm" value={mode} onChange={(e) => setMode(e.target.value)} disabled={crawlActive}>
              <option value="batch_search">Batch search — recommended</option>
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
                <span>Results per query</span>
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
                <span>Discovery goal</span>
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
                <span>Discovery goal</span>
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
                <span>Results per query</span>
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
              Crawls URLs from <code>discovered_urls.txt</code>. Run batch search first to populate that file.
            </p>
          ) : null}

          <label>
            <span>Max folder depth</span>
            <input
              className="input py-2 text-sm"
              type="number"
              min={1}
              max={8}
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              disabled={crawlActive}
            />
          </label>
          <label>
            <span>Max files</span>
            <input
              className="input py-2 text-sm"
              type="number"
              min={1}
              max={10000}
              value={maxFiles}
              onChange={(e) => setMaxFiles(Number(e.target.value))}
              disabled={crawlActive}
            />
          </label>
          <label>
            <span>Workers</span>
            <input
              className="input py-2 text-sm"
              type="number"
              min={1}
              max={32}
              value={workers}
              onChange={(e) => setWorkers(Number(e.target.value))}
              disabled={crawlActive}
            />
          </label>
        </div>

        <DriveCategoryPicker categories={categories} selected={selected} onChange={setSelected} />
      </section>

      {activeRun ? (
        <section ref={jobPanelRef} className="docs-crawl-panel docs-crawl-panel--job card">
          <div className="docs-crawl__job-head">
            <div>
              <span className="docs-crawl__job-title">{statusLabel(activeRun.mode)}</span>
              <span className="docs-crawl__job-sub">
                Run {activeRun.id.slice(0, 8)} ·{" "}
                {activeRun.started_at ? new Date(activeRun.started_at).toLocaleString() : "Starting…"}
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
              <dt>Folders</dt>
              <dd>{formatNumber(activeRun.folders_crawled)}</dd>
            </div>
            <div>
              <dt>Files found</dt>
              <dd>{formatNumber(activeRun.files_discovered)}</dd>
            </div>
            <div>
              <dt>Indexed</dt>
              <dd>{formatNumber(activeRun.files_indexed)}</dd>
            </div>
            <div>
              <dt>Failed</dt>
              <dd>{formatNumber(activeRun.failed_count)}</dd>
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
        <section ref={jobPanelRef} className="docs-crawl-panel docs-crawl-panel--idle card">
          <strong>No active crawl</strong>
          <p>Configure categories and start a crawl. Progress appears here automatically.</p>
        </section>
      )}
    </div>
  );
}

function discoveredProgress(
  activeRun: DriveCrawlRun | null,
  indexed: number,
  goal: number,
  crawlActive: boolean
): number {
  if (!activeRun) return 0;
  if (activeRun.status === "completed") return 100;
  if (indexed > 0) return Math.min(99, Math.round((indexed / goal) * 100));
  return crawlActive ? 8 : 0;
}
