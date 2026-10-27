"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { LoadingDots } from "@/components/LoadingState";
import { apiFetch } from "@/lib/api";
import {
  COUNTRY_PRESETS,
  DATE_BUCKETS,
  DEFAULT_COUNTRIES,
  FOLLOWER_BUCKETS,
} from "@/lib/countries";

const SORT_OPTIONS = [
  { value: "joined", label: "Join date" },
  { value: "followers", label: "Followers" },
  { value: "repositories", label: "Repositories" },
] as const;

const DEFAULT_SELECTED_COUNTRIES = COUNTRY_PRESETS.find(
  (preset) => preset.id === "developer-hubs"
)?.countries.slice(0, 8) ?? ["US", "India", "UK"];

const IMPACT_PROFILES = {
  low: {
    label: "Low impact",
    description: "Keeps the computer responsive",
    workers: 6,
    maxPerLocation: 50,
  },
  balanced: {
    label: "Balanced",
    description: "Good speed without heavy load",
    workers: 10,
    maxPerLocation: 100,
  },
  fast: {
    label: "Fast",
    description: "Higher CPU/network usage",
    workers: 18,
    maxPerLocation: 200,
  },
} as const;

type ImpactProfile = keyof typeof IMPACT_PROFILES;

export default function NewScrapePage() {
  const router = useRouter();
  const [countries, setCountries] = useState<string[]>([...DEFAULT_SELECTED_COUNTRIES]);
  const [countryQuery, setCountryQuery] = useState("");
  const [impactProfile, setImpactProfile] = useState<ImpactProfile>("low");
  const [maxPerLocation, setMaxPerLocation] = useState<number>(
    IMPACT_PROFILES.low.maxPerLocation
  );
  const [profileWorkers, setProfileWorkers] = useState<number>(
    IMPACT_PROFILES.low.workers
  );
  const [usePresetBuckets, setUsePresetBuckets] = useState(false);
  const [joinDateStart, setJoinDateStart] = useState("2014-01-01");
  const [joinDateEnd, setJoinDateEnd] = useState("2025-12-31");
  const [searchSort, setSearchSort] = useState<"joined" | "followers" | "repositories">("joined");
  const [searchOrder, setSearchOrder] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const bucketPreview = useMemo(() => {
    if (usePresetBuckets) return DATE_BUCKETS.join(", ");
    if (!joinDateStart || !joinDateEnd) return "-";
    if (joinDateStart > joinDateEnd) return "End date must be after start date";
    return `${joinDateStart} -> ${joinDateEnd} (split into search buckets)`;
  }, [usePresetBuckets, joinDateStart, joinDateEnd]);

  const visibleCountries = useMemo(() => {
    const q = countryQuery.trim().toLowerCase();
    if (!q) return DEFAULT_COUNTRIES;
    return DEFAULT_COUNTRIES.filter((country) => country.toLowerCase().includes(q));
  }, [countryQuery]);

  const selectedVisibleCount = useMemo(
    () => visibleCountries.filter((country) => countries.includes(country)).length,
    [countries, visibleCountries]
  );

  function toggleCountry(country: string) {
    setCountries((prev) =>
      prev.includes(country) ? prev.filter((x) => x !== country) : [...prev, country]
    );
  }

  function applyCountryPreset(nextCountries: readonly string[]) {
    setCountries([...nextCountries]);
  }

  function selectVisibleCountries() {
    setCountries((prev) => Array.from(new Set([...prev, ...visibleCountries])));
  }

  function applyImpactProfile(profile: ImpactProfile) {
    setImpactProfile(profile);
    setMaxPerLocation(IMPACT_PROFILES[profile].maxPerLocation);
    setProfileWorkers(IMPACT_PROFILES[profile].workers);
  }

  async function startScrape() {
    if (countries.length === 0) {
      setError("Select at least one country");
      return;
    }
    if (!usePresetBuckets && joinDateStart > joinDateEnd) {
      setError("Join date end must be on or after start");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const config: Record<string, unknown> = {
        countries,
        max_per_location: maxPerLocation || null,
        profile_workers: profileWorkers,
        follower_buckets: FOLLOWER_BUCKETS,
        search_sort: searchSort,
        search_order: searchOrder,
        email_only: true,
        use_email_search_hint: true,
      };

      if (usePresetBuckets) {
        config.date_buckets = DATE_BUCKETS;
      } else {
        config.join_date_start = joinDateStart;
        config.join_date_end = joinDateEnd;
        config.date_buckets = [];
      }

      const run = await apiFetch<{ id: string }>("/scrape/start", {
        method: "POST",
        body: JSON.stringify({ config }),
      });
      router.push(`/scrape/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title">New Scrape</h1>
        <p className="page-subtitle">Start a fast email-focused scrape run by market.</p>
      </div>

      <div className="card mb-6">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="font-medium">Computer impact</h2>
            <p className="mt-1 text-sm text-github-light">
              Low impact is the default so the admin site and your computer stay responsive.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(IMPACT_PROFILES) as ImpactProfile[]).map((profile) => (
              <button
                key={profile}
                type="button"
                onClick={() => applyImpactProfile(profile)}
                className={
                  impactProfile === profile
                    ? "rounded-md bg-accent px-3 py-2 text-xs font-semibold text-slate-950"
                    : "rounded-md border border-surface-border bg-surface-subtle px-3 py-2 text-xs font-medium text-github-light hover:border-accent hover:text-github"
                }
              >
                {IMPACT_PROFILES[profile].label}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium">
              Max users per location: {maxPerLocation}
            </label>
            <input
              type="range"
              min={10}
              max={500}
              step={10}
              value={maxPerLocation}
              onChange={(event) => {
                setMaxPerLocation(Number(event.target.value));
                setImpactProfile("balanced");
              }}
              className="w-full"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">
              Profile workers: {profileWorkers}
            </label>
            <input
              type="range"
              min={1}
              max={24}
              step={1}
              value={profileWorkers}
              onChange={(event) => {
                setProfileWorkers(Number(event.target.value));
                setImpactProfile("balanced");
              }}
              className="w-full"
            />
            <p className="mt-2 text-xs text-github-light">
              {IMPACT_PROFILES[impactProfile].description}
            </p>
          </div>
        </div>
      </div>

      <div className="card mb-6">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="font-medium">Countries</h2>
            <p className="mt-1 text-sm text-github-light">
              {countries.length} selected across developer, client, and high-value markets.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {COUNTRY_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyCountryPreset(preset.countries)}
                className="rounded-md border border-surface-border bg-surface-subtle px-3 py-2 text-xs font-medium text-github-light hover:border-accent hover:text-github"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3 grid gap-3 lg:grid-cols-[minmax(220px,360px)_auto] lg:items-center">
          <input
            className="input"
            value={countryQuery}
            onChange={(event) => setCountryQuery(event.target.value)}
            placeholder="Search country"
          />
          <div className="flex flex-wrap gap-2 text-xs">
            <button
              type="button"
              onClick={selectVisibleCountries}
              className="rounded-md border border-surface-border px-3 py-2 font-medium text-github-light hover:border-accent hover:text-github"
            >
              Select visible ({visibleCountries.length})
            </button>
            <button
              type="button"
              onClick={() => setCountries([])}
              className="rounded-md border border-surface-border px-3 py-2 font-medium text-github-light hover:border-red-400 hover:text-red-200"
            >
              Clear
            </button>
          </div>
        </div>

        <div className="max-h-72 overflow-y-auto rounded-md border border-surface-border bg-surface-muted p-3">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {visibleCountries.map((country) => {
              const selected = countries.includes(country);
              return (
                <button
                  key={country}
                  type="button"
                  onClick={() => toggleCountry(country)}
                  className={
                    selected
                      ? "rounded-md bg-accent px-3 py-2 text-left text-xs font-semibold text-slate-950"
                      : "rounded-md border border-surface-border bg-surface-subtle px-3 py-2 text-left text-xs text-github-light hover:border-slate-500 hover:text-github"
                  }
                >
                  {country}
                </button>
              );
            })}
          </div>
        </div>
        <p className="mt-3 text-xs text-github-light">
          Showing {visibleCountries.length} countries; {selectedVisibleCount} visible selected.
        </p>
      </div>

      <div className="card mb-6">
        <h2 className="mb-4 font-medium">Join date range (GitHub account created)</h2>
        <label className="mb-4 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={usePresetBuckets}
            onChange={(event) => setUsePresetBuckets(event.target.checked)}
          />
          Use preset buckets (2008-2025)
        </label>
        {!usePresetBuckets && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm text-github-light">From</label>
              <input
                type="date"
                className="input"
                value={joinDateStart}
                min="2008-01-01"
                max={joinDateEnd}
                onChange={(event) => setJoinDateStart(event.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-github-light">To</label>
              <input
                type="date"
                className="input"
                value={joinDateEnd}
                min={joinDateStart}
                max="2025-12-31"
                onChange={(event) => setJoinDateEnd(event.target.value)}
              />
            </div>
          </div>
        )}
        <p className="mt-3 text-xs text-github-light">Buckets: {bucketPreview}</p>
      </div>

      <div className="card mb-6">
        <h2 className="mb-4 font-medium">Search order</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm text-github-light">Sort by</label>
            <select
              className="input"
              value={searchSort}
              onChange={(event) =>
                setSearchSort(event.target.value as "joined" | "followers" | "repositories")
              }
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm text-github-light">Direction</label>
            <select
              className="input"
              value={searchOrder}
              onChange={(event) => setSearchOrder(event.target.value as "asc" | "desc")}
            >
              <option value="desc">Decreasing (high to low / newest first)</option>
              <option value="asc">Increasing (low to high / oldest first)</option>
            </select>
          </div>
        </div>
      </div>

      {error && <p className="alert-error mb-4">{error}</p>}

      <button onClick={startScrape} className="btn-primary" disabled={loading}>
        {loading ? <LoadingDots label="Starting" /> : "Start scrape"}
      </button>
    </div>
  );
}
