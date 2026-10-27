"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { displayDriveTitle } from "@/components/drive/DriveCard";
import LoadingState from "@/components/LoadingState";
import { fetchDriveFile } from "@/lib/google-drive-api";
import type { DriveFile } from "@/lib/google-drive-types";

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleString();
}

export default function ExploreDriveDetailPage() {
  const params = useParams<{ id: string }>();
  const fileId = decodeURIComponent(params.id || "");
  const [file, setFile] = useState<DriveFile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!fileId) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchDriveFile(fileId);
      setFile(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load file");
    } finally {
      setLoading(false);
    }
  }, [fileId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <LoadingState variant="inline" title="Loading file" detail="Fetching indexed Drive file details." />
    );
  }

  if (error || !file) {
    return (
      <div className="docs-detail docs-detail--error card">
        <h1>File not found</h1>
        <p>{error || "This file is not in the archive yet."}</p>
        <Link href="/explore/drive" className="btn-secondary">
          Back to explorer
        </Link>
      </div>
    );
  }

  const title = displayDriveTitle(file);
  const openUrl = file.public_url || `https://drive.google.com/file/d/${file.file_id}/view`;
  const previewText = (file.raw_text || file.excerpt || "").trim();

  return (
    <div className="docs-detail">
      <div className="docs-detail__toolbar">
        <Link href="/explore/drive" className="btn-ghost">
          ← Back to explorer
        </Link>
        <a className="btn-primary" href={openUrl} target="_blank" rel="noopener noreferrer">
          Open file
        </a>
      </div>

      <header className="docs-detail__header card">
        <p className="docs-detail__eyebrow">{file.mime_type || file.extension || "Drive file"}</p>
        <h1>{title}</h1>
        <p className="docs-detail__meta">
          Indexed {formatDate(file.indexed_at || file.created_at)} · {formatNumber(file.word_count)} words ·{" "}
          {formatNumber(file.character_count)} characters
        </p>
        {file.categories?.length ? (
          <div className="docs-card__chips">
            {file.categories.map((category) => (
              <span key={category} className="docs-card__chip">
                {category.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        ) : null}
      </header>

      <section className="docs-detail__content card">
        <h2>Extracted content</h2>
        {previewText ? (
          <pre className="docs-detail__text">{previewText.slice(0, 12000)}</pre>
        ) : (
          <p className="text-github-muted">No extracted text is stored for this file.</p>
        )}
      </section>
    </div>
  );
}
