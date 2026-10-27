"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import LoadingState, { LoadingDots } from "@/components/LoadingState";
import { apiFetch, ScrapeRun } from "@/lib/api";

type CountryOption = { country: string; count: number };

type Dashboard = {
  total_users: number;
  active_runs: number;
  active_tokens: number;
  countries?: CountryOption[];
  last_run: ScrapeRun | null;
};

const ACTIVE_STATUSES = ["pending", "running", "stopping"];

function visibleCountries(countries: CountryOption[]) {
  return countries.filter((item) => !item.country.toLowerCase().includes("korea"));
}

function formatNumber(value: number | null | undefined) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value?: string) {
  if (!value) return "Not started";
  return new Date(value).toLocaleString();
}

function statusTone(status?: string) {
  if (!status) return "dashboard-status--idle";
  if (status === "running") return "dashboard-status--running";
  if (status === "pending" || status === "stopping") return "dashboard-status--pending";
  if (status === "completed") return "dashboard-status--success";
  if (status === "failed") return "dashboard-status--danger";
  return "dashboard-status--idle";
}

export default function GitHubDashboard() {
  const [stats, setStats] = useState<Dashboard | null>(null);
  const [countries, setCountries] = useState<CountryOption[]>([]);
  const [viewCountry, setViewCountry] = useState("");
  const [error, setError] = useState("");
  const [stoppingRunId, setStoppingRunId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Dashboard>("/scrape/dashboard")
      .then((dashboard) => {
        if (cancelled) return;
        setStats(dashboard);
        setCountries(visibleCountries(dashboard.countries || []));
        setUpdatedAt(new Date());
      })
      .catch((e) => {
        if (!cancelled && e?.name !== "ApiAuthError") setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshDashboard() {
    setRefreshing(true);
    try {
      const dashboard = await apiFetch<Dashboard>("/scrape/dashboard");
      setStats(dashboard);
      setCountries(visibleCountries(dashboard.countries || []));
      setUpdatedAt(new Date());
    } finally {
      setRefreshing(false);
    }
  }

  async function stopRun(id: string) {
    setStoppingRunId(id);
    try {
      await apiFetch<ScrapeRun>(`/scrape/stop/${id}`, { method: "POST" });
    } catch {
      /* may already be stopping */
    }
    for (let i = 0; i < 18; i++) {
      const run = await apiFetch<ScrapeRun>(`/scrape/status/${id}`);
      if (!ACTIVE_STATUSES.includes(run.status)) {
        await refreshDashboard();
        setStoppingRunId(null);
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
    await refreshDashboard();
    setStoppingRunId(null);
  }

  const countryInsights = useMemo(() => {
    const top = countries.slice(0, 6);
    const total = countries.reduce((sum, item) => sum + item.count, 0);
    return { top, total };
  }, [countries]);

  if (error) return <p className="alert-error">{error}</p>;
  if (!stats) {
    return (
      <LoadingState
        variant="page"
        title="Loading dashboard"
        detail="Collecting scrape status, user totals, and country counts."
      />
    );
  }

  const run = stats.last_run;
  const isActive = run && ACTIVE_STATUSES.includes(run.status);
  const runCountries = (run?.config?.countries as string[] | undefined) || [];
  const completedCountries = run?.countries_completed || [];
  const totalRunCountries = runCountries.length || completedCountries.length || 0;
  const runProgress =
    totalRunCountries > 0
      ? Math.min(100, Math.round((completedCountries.length / totalRunCountries) * 100))
      : run?.status === "completed"
        ? 100
        : 0;
  const selectedCountry = viewCountry || countryInsights.top[0]?.country || "";
  const selectedCountryCount =
    countries.find((country) => country.country === selectedCountry)?.count || 0;

  return (
    <div className="dashboard-page space-y-6">
      <section className="dashboard-hero">
        <div className="dashboard-hero__content">
          <span className="dashboard-eyebrow">GitHub scraping</span>
          <h1 className="dashboard-title">GitHub Scraping Workspace</h1>
          <p className="dashboard-copy">
            Monitor scrape health, review country coverage, and manage your GitHub user archive.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/scrape/new" className="btn-primary">
              Start scrape
            </Link>
            <Link href="/users" className="btn-secondary">
              Browse users
            </Link>
            <button className="btn-secondary" onClick={refreshDashboard} disabled={refreshing}>
              {refreshing ? <LoadingDots label="Refreshing" /> : "Refresh"}
            </button>
          </div>
          {updatedAt && (
            <p className="dashboard-updated">Updated {updatedAt.toLocaleTimeString()}</p>
          )}
        </div>
        <div className="dashboard-hero__panel">
          <div className={`dashboard-status ${statusTone(run?.status)}`}>
            <span className="dashboard-status__dot" />
            <span>{run ? run.status : "idle"}</span>
          </div>
          <p className="dashboard-hero__metric">{formatNumber(stats.total_users)}</p>
          <p className="dashboard-hero__label">stored users ready for filtering and outreach</p>
          <div className="dashboard-hero__grid">
            <span>Active runs</span>
            <strong>{stats.active_runs}</strong>
            <span>Active tokens</span>
            <strong>{stats.active_tokens}</strong>
          </div>
        </div>
      </section>

      <section className="dashboard-metrics">
        <div className="dashboard-card dashboard-card--metric">
          <span className="dashboard-card__label">Archive size</span>
          <strong>{formatNumber(stats.total_users)}</strong>
          <span>email-focused records in the database</span>
        </div>
        <div className="dashboard-card dashboard-card--metric">
          <span className="dashboard-card__label">Coverage</span>
          <strong>{countries.length}</strong>
          <span>countries currently visible in the archive</span>
        </div>
        <div className="dashboard-card dashboard-card--metric">
          <span className="dashboard-card__label">Tokens</span>
          <strong>{stats.active_tokens}</strong>
          <span>{stats.active_tokens > 0 ? "available for scraping" : "add a token before large runs"}</span>
        </div>
        <div className="dashboard-card dashboard-card--metric">
          <span className="dashboard-card__label">System mode</span>
          <strong>{stats.active_runs > 0 ? "Live" : "Ready"}</strong>
          <span>{stats.active_runs > 0 ? "lightweight reads enabled" : "ready for the next scrape"}</span>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="dashboard-card">
          <div className="dashboard-section-head">
            <div>
              <h2>Latest Run</h2>
              <p>{run ? `Started ${formatDate(run.started_at)}` : "No scrape has been started yet."}</p>
            </div>
            {run && <span className={`dashboard-status ${statusTone(run.status)}`}>{run.status}</span>}
          </div>

          {run ? (
            <div className="space-y-5">
              <div>
                <div className="mb-2 flex items-center justify-between text-sm text-github-light">
                  <span>{completedCountries.length} of {totalRunCountries || "-"} countries complete</span>
                  <span>{runProgress}%</span>
                </div>
                <div className="dashboard-progress">
                  <span style={{ width: `${runProgress}%` }} />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="dashboard-mini">
                  <span>Users found</span>
                  <strong>{formatNumber(run.total_users_found)}</strong>
                </div>
                <div className="dashboard-mini">
                  <span>Current country</span>
                  <strong>{run.current_country || "-"}</strong>
                </div>
                <div className="dashboard-mini">
                  <span>Rate limit</span>
                  <strong>{run.rate_limit_remaining ?? "-"}</strong>
                </div>
                <div className="dashboard-mini">
                  <span>ETA</span>
                  <strong>{run.estimated_seconds_remaining ? `${run.estimated_seconds_remaining}s` : "-"}</strong>
                </div>
              </div>

              {run.last_error && <p className="alert-error">Last error: {run.last_error}</p>}

              <div className="flex flex-wrap gap-3">
                <Link href={`/scrape/${run.id}`} className="btn-secondary">
                  View live progress
                </Link>
                {isActive && (
                  <button
                    onClick={() => stopRun(run.id)}
                    className="btn-secondary border-red-500/40 text-red-200 hover:bg-red-950/40"
                    disabled={stoppingRunId === run.id}
                  >
                    {stoppingRunId === run.id ? <LoadingDots label="Stopping" /> : "Stop run"}
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="dashboard-empty">
              <strong>No scrape history yet</strong>
              <span>Create a focused scrape run to start building your outreach archive.</span>
              <Link href="/scrape/new" className="btn-primary">Create first run</Link>
            </div>
          )}
        </div>

        <div className="dashboard-card">
          <div className="dashboard-section-head">
            <div>
              <h2>Country Finder</h2>
              <p>Choose a market and jump straight into filtered users.</p>
            </div>
          </div>
          {countries.length > 0 ? (
            <div className="space-y-4">
              <select
                className="input"
                value={selectedCountry}
                onChange={(event) => setViewCountry(event.target.value)}
              >
                {countries.map((country) => (
                  <option key={country.country} value={country.country}>
                    {country.country} ({formatNumber(country.count)} users)
                  </option>
                ))}
              </select>
              <div className="dashboard-selected-country">
                <span>{selectedCountry}</span>
                <strong>{formatNumber(selectedCountryCount)}</strong>
                <small>available records</small>
              </div>
              <Link
                href={`/users?country=${encodeURIComponent(selectedCountry)}`}
                className="btn-primary w-full"
              >
                Open country list
              </Link>
            </div>
          ) : (
            <div className="dashboard-empty">
              <strong>No country data yet</strong>
              <span>Run a scrape to populate country coverage.</span>
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="dashboard-card">
          <div className="dashboard-section-head">
            <div>
              <h2>Top Countries</h2>
              <p>Largest visible markets in the archive.</p>
            </div>
            <Link href="/users" className="dashboard-link">All users</Link>
          </div>
          <div className="space-y-3">
            {countryInsights.top.map((country) => {
              const pct = countryInsights.total
                ? Math.max(4, Math.round((country.count / countryInsights.total) * 100))
                : 0;
              return (
                <Link
                  href={`/users?country=${encodeURIComponent(country.country)}`}
                  key={country.country}
                  className="dashboard-country-row"
                >
                  <div>
                    <strong>{country.country}</strong>
                    <span>{formatNumber(country.count)} users</span>
                  </div>
                  <div className="dashboard-country-row__bar">
                    <span style={{ width: `${pct}%` }} />
                  </div>
                </Link>
              );
            })}
            {countryInsights.top.length === 0 && (
              <p className="text-sm text-github-light">No country records found yet.</p>
            )}
          </div>
        </div>

        <div className="dashboard-card">
          <div className="dashboard-section-head">
            <div>
              <h2>Next Best Actions</h2>
              <p>Shortcuts based on the current workspace state.</p>
            </div>
          </div>
          <div className="dashboard-action-list">
            <Link href="/users" className="dashboard-action">
              <strong>Review fresh users</strong>
              <span>Open the optimized AG Grid table with server-side paging.</span>
            </Link>
            <Link href="/tokens" className="dashboard-action">
              <strong>Check token capacity</strong>
              <span>Refresh token rate limits before large scrapes.</span>
            </Link>
            <Link href="/logs" className="dashboard-action">
              <strong>Audit recent runs</strong>
              <span>Read progress, errors, and completed countries.</span>
            </Link>
            <Link href="/schedules" className="dashboard-action">
              <strong>Manage schedules</strong>
              <span>Automate recurring scrape jobs.</span>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
