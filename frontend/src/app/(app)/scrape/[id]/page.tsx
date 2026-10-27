"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { apiFetch, ScrapeRun } from "@/lib/api";
import { useMongoStorage } from "@/lib/database-storage";

const ACTIVE_STATUSES = ["pending", "running", "stopping"];
const POLL_INTERVAL_MS = useMongoStorage ? 5000 : 30000;
const TERMINAL_STATUSES = ["completed", "failed", "stopped"];

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function progressTone(status: string) {
  if (status === "running") return "live-progress-band--running";
  if (status === "pending") return "live-progress-band--pending";
  if (status === "stopping") return "live-progress-band--stopping";
  if (status === "completed") return "live-progress-band--completed";
  if (status === "failed") return "live-progress-band--failed";
  if (status === "stopped") return "live-progress-band--stopped";
  return "live-progress-band--idle";
}

function statusLabel(status: string) {
  if (status === "pending") return "Preparing";
  if (status === "running") return "Scraping";
  if (status === "stopping") return "Stopping";
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  if (status === "stopped") return "Stopped";
  return status || "Idle";
}

export default function LiveProgressPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<ScrapeRun | null>(null);
  const [error, setError] = useState("");
  const [stopping, setStopping] = useState(false);
  const [viewCountry, setViewCountry] = useState("");
  const realtimeConnected = useRef(false);

  useEffect(() => {
    if (!id) return;
    let active = true;
    apiFetch<ScrapeRun>(`/scrape/status/${id}`)
      .then((data) => {
        if (active) setRun(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });

    if (useMongoStorage) {
      const poll = window.setInterval(() => {
        if (!active) return;
        apiFetch<ScrapeRun>(`/scrape/status/${id}`)
          .then((data) => {
            if (active) setRun(data);
          })
          .catch(() => {});
      }, POLL_INTERVAL_MS);
      return () => {
        active = false;
        window.clearInterval(poll);
      };
    }

    const supabase = createClient();
    const channel = supabase
      .channel(`run-${id}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "scraping_runs",
          filter: `id=eq.${id}`,
        },
        (payload) => {
          if (active) setRun(payload.new as ScrapeRun);
        }
      )
      .subscribe((status) => {
        realtimeConnected.current = status === "SUBSCRIBED";
      });

    const poll = window.setInterval(() => {
      if (!active || realtimeConnected.current) return;
      setRun((current) => {
        if (current && !ACTIVE_STATUSES.includes(current.status)) {
          window.clearInterval(poll);
          return current;
        }
        apiFetch<ScrapeRun>(`/scrape/status/${id}`)
          .then((data) => {
            if (active) setRun(data);
          })
          .catch(() => {});
        return current;
      });
    }, POLL_INTERVAL_MS);

    return () => {
      active = false;
      supabase.removeChannel(channel);
      window.clearInterval(poll);
    };
  }, [id]);

  async function stopRun() {
    if (stopping) return;
    setStopping(true);
    setError("");
    try {
      await apiFetch<ScrapeRun>(`/scrape/stop/${id}`, { method: "POST" });
      for (let i = 0; i < 24; i++) {
        const updated = await apiFetch<ScrapeRun>(`/scrape/status/${id}`);
        setRun(updated);
        if (!["pending", "running", "stopping"].includes(updated.status)) {
          return;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop");
    } finally {
      setStopping(false);
    }
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!run) return <p>Loading run…</p>;

  const scrapeCountries = (run.config?.countries as string[] | undefined) || [];
  const completedCountries = run.countries_completed || [];
  const countryChoices = [
    ...new Set([...completedCountries, ...scrapeCountries, run.current_country].filter(Boolean)),
  ] as string[];
  const totalCountries = scrapeCountries.length || 1;
  const done = completedCountries.length;
  const actualPct = clampPercent((done / totalCountries) * 100);
  const activeCountryIndex = run.current_country ? scrapeCountries.indexOf(run.current_country) : -1;
  const currentStepPct =
    activeCountryIndex >= 0 ? clampPercent(((activeCountryIndex + 0.5) / totalCountries) * 100) : actualPct;
  const bandPct =
    run.status === "completed"
      ? 100
      : run.status === "pending"
        ? Math.max(actualPct, 6)
        : run.status === "running"
          ? Math.max(actualPct, currentStepPct, 8)
          : run.status === "stopping"
            ? Math.max(actualPct, currentStepPct, 10)
            : actualPct;
  const selectedCountry = viewCountry || run.current_country || countryChoices[0] || "";
  const progressDetail = TERMINAL_STATUSES.includes(run.status)
    ? `${done} of ${totalCountries} countries finished`
    : run.current_country
      ? `Working on ${run.current_country}`
      : run.status === "pending"
        ? "Waiting for the scraper worker"
        : `${done} of ${totalCountries} countries finished`;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Live progress</h1>
        {["running", "pending", "stopping"].includes(run.status) && (
          <button
            onClick={stopRun}
            disabled={stopping}
            className="btn-primary bg-red-600 hover:bg-red-700 disabled:opacity-50"
          >
            {stopping || run.status === "stopping" ? "Stopping…" : "Stop scrape"}
          </button>
        )}
      </div>

      <div className="card mb-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm">
          <span className={`live-progress-status ${progressTone(run.status)}`}>
            <span className="live-progress-status__dot" />
            {statusLabel(run.status)}
          </span>
          <span className="text-github-light">{actualPct}% countries</span>
        </div>
        <div
          className={`live-progress-band ${progressTone(run.status)}`}
          aria-label={`${statusLabel(run.status)}: ${actualPct}% countries`}
        >
          <div
            className="live-progress-band__fill"
            style={{ width: `${bandPct}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-github-light">{progressDetail}</p>
        <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
          <p>
            <span className="text-github-light">Current country:</span>{" "}
            {run.current_country || "—"}
          </p>
          <p>
            <span className="text-github-light">Users found:</span> {run.total_users_found}
          </p>
          <p>
            <span className="text-github-light">Rate limit left:</span>{" "}
            {run.rate_limit_remaining ?? "—"}
          </p>
          <p>
            <span className="text-github-light">ETA (sec):</span>{" "}
            {run.estimated_seconds_remaining ?? "—"}
          </p>
        </div>
        {run.last_error && (
          <p className="mt-4 text-sm text-red-600">Error: {run.last_error}</p>
        )}
      </div>

      {countryChoices.length > 0 && (
        <div className="card mb-6">
          <h2 className="mb-3 font-medium">View results by country</h2>
          <div className="flex flex-wrap items-center gap-3">
            <select
              className="input max-w-[240px]"
              value={selectedCountry}
              onChange={(e) => setViewCountry(e.target.value)}
            >
              {countryChoices.map((c) => (
                <option key={c} value={c}>
                  {c}
                  {completedCountries.includes(c) ? " ✓" : run.current_country === c ? " (active)" : ""}
                </option>
              ))}
            </select>
            {selectedCountry && (
              <Link
                href={`/users?country=${encodeURIComponent(selectedCountry)}`}
                className="btn-secondary"
              >
                View users from {selectedCountry}
              </Link>
            )}
          </div>
          {completedCountries.length > 0 && (
            <p className="mt-2 text-sm text-github-light">
              Completed: {completedCountries.join(", ")}
            </p>
          )}
        </div>
      )}

      <div className="card">
        <h2 className="mb-4 font-medium">Logs</h2>
        <div className="max-h-96 overflow-y-auto font-mono text-xs">
          {(run.log_lines || []).slice(-100).map((line, i) => (
            <div key={i} className="border-b border-gray-100 py-1">
              <span className="text-github-light">{line.ts}</span> {line.message}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
