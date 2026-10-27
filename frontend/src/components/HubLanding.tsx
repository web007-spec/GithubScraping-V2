"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LoadingState from "@/components/LoadingState";
import { fetchDriveStats } from "@/lib/google-drive-api";
import { enabledHubModules, PLATFORM_NAME, PLATFORM_TAGLINE } from "@/lib/nav-config";
import { apiFetch } from "@/lib/api";

type GitHubSnapshot = {
  total_users: number;
  active_runs: number;
  active_tokens: number;
};

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

export default function HubLanding() {
  const [loading, setLoading] = useState(true);
  const [github, setGithub] = useState<GitHubSnapshot | null>(null);
  const [driveIndexed, setDriveIndexed] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const [githubRes, driveRes] = await Promise.allSettled([
          apiFetch<GitHubSnapshot>("/scrape/dashboard"),
          fetchDriveStats(),
        ]);

        if (cancelled) return;

        if (githubRes.status === "fulfilled") {
          setGithub({
            total_users: githubRes.value.total_users,
            active_runs: githubRes.value.active_runs,
            active_tokens: githubRes.value.active_tokens,
          });
        }

        if (driveRes.status === "fulfilled") {
          setDriveIndexed(driveRes.value.indexed ?? driveRes.value.total ?? 0);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load hub overview");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const modules = enabledHubModules().filter((m) => m.id !== "hub");

  if (loading) {
    return (
      <LoadingState
        variant="page"
        title="Loading workspace"
        detail="Gathering GitHub and Drive status."
      />
    );
  }

  return (
    <div className="hub-page">
      <section className="hub-hero">
        <div className="hub-hero__copy">
          <p className="hub-hero__eyebrow">{PLATFORM_TAGLINE}</p>
          <h1 className="hub-hero__title">{PLATFORM_NAME}</h1>
          <p className="hub-hero__lead">
            One integrated console for GitHub user scraping and public Google Drive indexing.
          </p>
        </div>
        <div className="hub-hero__stats">
          <article>
            <span>GitHub users</span>
            <strong>{formatNumber(github?.total_users)}</strong>
          </article>
          <article>
            <span>Drive files</span>
            <strong>{driveIndexed != null ? formatNumber(driveIndexed) : "—"}</strong>
          </article>
          <article>
            <span>Active scrapes</span>
            <strong>{formatNumber(github?.active_runs)}</strong>
          </article>
          <article>
            <span>Active tokens</span>
            <strong>{formatNumber(github?.active_tokens)}</strong>
          </article>
        </div>
      </section>

      {error ? <p className="alert-info">{error}</p> : null}

      <section className="hub-modules-grid">
        {modules.map((module) => {
          const stat =
            module.id === "github"
              ? `${formatNumber(github?.total_users)} users · ${formatNumber(github?.active_tokens)} tokens`
              : `${formatNumber(driveIndexed)} public files indexed`;

          return (
            <Link key={module.id} href={module.href} className={`hub-module-card hub-module-card--${module.id}`}>
              <div className="hub-module-card__head">
                <span className="hub-module-card__mark" style={{ background: module.accent }} />
                <div>
                  <h2>{module.label}</h2>
                  <p>{module.description}</p>
                </div>
              </div>
              <p className="hub-module-card__stat">{stat}</p>
              <span className="hub-module-card__cta">Open workspace →</span>
            </Link>
          );
        })}
      </section>

      <section className="hub-quick card">
        <h2>Quick actions</h2>
        <div className="hub-quick__grid">
          <Link href="/scrape/new" className="hub-quick__item">
            <strong>Start GitHub scrape</strong>
            <span>Launch a new country or keyword run</span>
          </Link>
          <Link href="/explore/drive/crawl/new" className="hub-quick__item">
            <strong>Crawl public Drive</strong>
            <span>Select categories and index public folders</span>
          </Link>
          <Link href="/explore/drive" className="hub-quick__item">
            <strong>Browse Drive files</strong>
            <span>Search the indexed public Drive archive</span>
          </Link>
          <Link href="/users" className="hub-quick__item">
            <strong>Review user archive</strong>
            <span>Filter and export scraped profiles</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
