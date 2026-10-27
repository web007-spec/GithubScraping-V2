"use client";

import { useEffect, useState } from "react";
import LoadingState, { LoadingDots } from "@/components/LoadingState";
import { apiFetch } from "@/lib/api";
import { Schedule } from "@/lib/types";

export default function SchedulesPage() {
  const [jobs, setJobs] = useState<Schedule[]>([]);
  const [name, setName] = useState("Weekly scrape");
  const [cron, setCron] = useState("0 2 * * 1");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setJobs(await apiFetch<Schedule[]>("/schedule"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      await apiFetch("/schedule", {
        method: "POST",
        body: JSON.stringify({
          name,
          cron_expression: cron,
          active: true,
          config: {
            countries: ["US", "India", "UK"],
            max_per_location: 100,
            follower_buckets: ["10..99", "100..999"],
            date_buckets: ["2020-01-01..2022-12-31", "2023-01-01..2025-12-31"],
          },
        }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  async function toggle(id: string, active: boolean) {
    setBusyJobId(id);
    try {
      await apiFetch(`/schedule/${id}/toggle?active=${active}`, { method: "PATCH" });
      await load();
    } finally {
      setBusyJobId(null);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title">Schedules</h1>
        <p className="page-subtitle">Automate recurring scrape jobs with a saved baseline configuration.</p>
      </div>

      <form onSubmit={create} className="card mb-8 max-w-lg">
        <h2 className="mb-4 font-medium">Create schedule</h2>
        <input className="input mb-3" value={name} onChange={(e) => setName(e.target.value)} />
        <label className="mb-1 block text-sm text-github-light">Cron (e.g. 0 2 * * 1 = Mon 2am)</label>
        <input className="input mb-4" value={cron} onChange={(e) => setCron(e.target.value)} />
        <p className="mb-4 text-xs text-github-light">
          Default config: US, India, UK — max 100/location. Edit in API/DB for custom buckets.
        </p>
        <button type="submit" className="btn-primary" disabled={creating}>
          {creating ? <LoadingDots label="Creating" /> : "Create"}
        </button>
        {error && <p className="alert-error mt-4">{error}</p>}
      </form>

      <div className="space-y-4">
        {loading && (
          <LoadingState
            variant="inline"
            title="Loading schedules"
            detail="Reading saved automation jobs and next run times."
          />
        )}
        {!loading && jobs.length === 0 && !error && (
          <div className="card-muted text-sm text-github-light">No schedules created yet.</div>
        )}
        {jobs.map((j) => (
          <div key={j.id} className="card">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="font-medium">{j.name}</p>
                <p className="text-sm text-github-light">{j.cron_expression}</p>
                <p className="text-sm">
                  Next: {j.next_run_at ? new Date(j.next_run_at).toLocaleString() : "—"}
                </p>
              </div>
              <button
                onClick={() => toggle(j.id, !j.active)}
                className="btn-secondary h-fit"
                disabled={busyJobId === j.id}
              >
                {busyJobId === j.id ? (
                  <LoadingDots label="Updating" />
                ) : j.active ? (
                  "Disable"
                ) : (
                  "Enable"
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
