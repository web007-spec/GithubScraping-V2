"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LoadingState from "@/components/LoadingState";
import { apiFetch, ScrapeRun } from "@/lib/api";

export default function LogsPage() {
  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiFetch<ScrapeRun[]>("/scrape/runs?limit=100")
      .then((data) => {
        if (!cancelled) setRuns(data);
      })
      .catch((e) => {
        if (!cancelled && e?.name !== "ApiAuthError") setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title">Scrape logs</h1>
        <p className="page-subtitle">Recent scrape runs. Open a run for full live logs.</p>
      </div>

      {error && <p className="alert-error mb-4">{error}</p>}

      <div className="space-y-4">
        {loading && (
          <LoadingState
            variant="inline"
            title="Loading scrape logs"
            detail="Reading recent runs, statuses, and country progress."
          />
        )}
        {!loading && runs.length === 0 && !error && (
          <div className="card-muted text-sm text-github-light">No scrape runs yet.</div>
        )}
        {runs.map((run) => (
          <div key={run.id} className="card">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-medium capitalize">{run.status}</p>
                <p className="text-sm text-github-light">
                  {run.started_at ? new Date(run.started_at).toLocaleString() : "Not started"} -{" "}
                  {run.total_users_found} users
                </p>
                {run.last_error && <p className="alert-error mt-3">{run.last_error}</p>}
                <p className="mt-2 text-xs text-github-light">
                  Countries: {(run.countries_completed || []).join(", ") || "-"}
                </p>
              </div>
              <Link href={`/scrape/${run.id}`} className="btn-secondary">
                Details
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
