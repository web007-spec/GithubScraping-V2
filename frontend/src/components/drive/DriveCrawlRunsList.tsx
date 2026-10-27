"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  adminActiveDriveCrawl,
  adminListDriveCrawls,
  adminStopDriveCrawl,
} from "@/lib/google-drive-api";
import type { DriveCrawlRun } from "@/lib/google-drive-types";
import { useAdminSession } from "@/lib/use-admin-session";

const ACTIVE = new Set(["pending", "running", "stopping"]);

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export default function DriveCrawlRunsList() {
  const { isAdmin, checking } = useAdminSession();
  const [runs, setRuns] = useState<DriveCrawlRun[]>([]);
  const [activeRun, setActiveRun] = useState<DriveCrawlRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stoppingId, setStoppingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [active, history] = await Promise.all([adminActiveDriveCrawl(), adminListDriveCrawls()]);
      setActiveRun(active);
      setRuns(history);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load crawl runs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(timer);
  }, [isAdmin, refresh]);

  async function handleStop(id: string) {
    setStoppingId(id);
    try {
      await adminStopDriveCrawl(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop crawl");
    } finally {
      setStoppingId(null);
    }
  }

  if (checking) {
    return <p className="text-github-muted">Loading…</p>;
  }

  if (!isAdmin) {
    return (
      <div className="docs-page">
        <div className="docs-empty-state card">
          <span className="docs-empty-state__icon" aria-hidden="true">
            🔒
          </span>
          <strong>Admin sign-in required</strong>
          <p>Crawl run history is available to administrators only.</p>
          <Link href="/login" className="btn-primary">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="docs-page">
      <header className="docs-hero docs-hero--compact">
        <div className="docs-hero__content">
          <p className="docs-hero__eyebrow">Google Drive workspace</p>
          <h1 className="docs-hero__title">Crawl runs</h1>
          <p className="docs-hero__copy">History of discovery jobs, indexed files, and errors.</p>
          <div className="docs-hero__actions">
            <Link href="/explore/drive/crawl/new" className="btn-primary">
              New crawl
            </Link>
            <button type="button" className="btn-secondary" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
        </div>
      </header>

      {error ? <p className="docs-page__error">{error}</p> : null}

      {loading ? (
        <p className="text-github-muted">Loading runs…</p>
      ) : runs.length === 0 && !activeRun ? (
        <div className="docs-empty-state card">
          <strong>No crawl runs yet</strong>
          <p>Start your first crawl to discover and index public Drive files.</p>
          <Link href="/explore/drive/crawl/new" className="btn-primary">
            New crawl
          </Link>
        </div>
      ) : (
        <div className="docs-runs-table card">
          <table>
            <thead>
              <tr>
                <th>Mode</th>
                <th>Status</th>
                <th>Discovered</th>
                <th>Indexed</th>
                <th>Failed</th>
                <th>Started</th>
                <th>Ended</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {[...(activeRun ? [activeRun] : []), ...runs.filter((run) => !activeRun || run.id !== activeRun.id)].map(
                (run) => {
                  const isActive = ACTIVE.has(run.status);
                  return (
                    <tr key={run.id} className={isActive ? "docs-runs-table__row--active" : undefined}>
                      <td>{run.mode.replace(/_/g, " ")}</td>
                      <td>
                        <span className={`docs-crawl__badge docs-crawl__badge--${run.status}`}>{run.status}</span>
                      </td>
                      <td>{formatNumber(run.discovered_count)}</td>
                      <td>{formatNumber(run.files_indexed)}</td>
                      <td>{formatNumber(run.failed_count)}</td>
                      <td>{formatDate(run.started_at || run.created_at)}</td>
                      <td>{formatDate(run.ended_at)}</td>
                      <td>
                        {isActive ? (
                          <button
                            type="button"
                            className="btn-secondary py-1 text-xs"
                            disabled={stoppingId === run.id}
                            onClick={() => void handleStop(run.id)}
                          >
                            {stoppingId === run.id ? "Stopping…" : "Stop"}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                }
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
