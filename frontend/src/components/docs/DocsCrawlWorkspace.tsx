"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DocsCrawlForm from "@/components/docs/DocsCrawlForm";
import DocsSetupBanner from "@/components/docs/DocsSetupBanner";
import { fetchPublic } from "@/lib/public-api";
import { useAdminSession } from "@/lib/use-admin-session";

type SetupStatus = {
  ok: boolean;
};

export default function DocsCrawlWorkspace() {
  const { isAdmin, checking } = useAdminSession();
  const [dbReady, setDbReady] = useState(false);

  const onDbReady = useCallback(() => {
    setDbReady(true);
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    fetchPublic<SetupStatus>("/public/google-docs/setup-status")
      .then((data) => {
        if (data.ok) setDbReady(true);
      })
      .catch(() => {});
  }, [isAdmin]);

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
          <p>Starting crawls and importing archives requires an administrator account.</p>
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
          <p className="docs-hero__eyebrow">Google Docs workspace</p>
          <h1 className="docs-hero__title">New Crawl</h1>
          <p className="docs-hero__copy">
            Discover public Google Docs, archive content, and sync them into the document library.
          </p>
          <div className="docs-hero__actions">
            <Link href="/explore/docs/crawl/runs" className="btn-secondary">
              Crawl runs
            </Link>
            <Link href="/explore/docs" className="btn-secondary">
              Browse documents
            </Link>
          </div>
        </div>
      </header>

      <DocsSetupBanner onReady={onDbReady} />
      <DocsCrawlForm dbReady={dbReady} showHistory />
    </div>
  );
}
