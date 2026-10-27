"use client";

import Link from "next/link";
import DriveCrawlForm from "@/components/drive/DriveCrawlForm";
import { useAdminSession } from "@/lib/use-admin-session";

export default function DriveCrawlWorkspace() {
  const { isAdmin, checking } = useAdminSession();

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
          <p>Starting Drive crawls requires an administrator account.</p>
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
          <h1 className="docs-hero__title">New Crawl</h1>
          <p className="docs-hero__copy">
            Discover public Google Docs and Drive files via web search, then index them by category — no manual URLs.
          </p>
          <div className="docs-hero__actions">
            <Link href="/explore/drive/crawl/runs" className="btn-secondary">
              Crawl runs
            </Link>
            <Link href="/explore/drive" className="btn-secondary">
              Browse files
            </Link>
          </div>
        </div>
      </header>

      <DriveCrawlForm showHistory />
    </div>
  );
}
