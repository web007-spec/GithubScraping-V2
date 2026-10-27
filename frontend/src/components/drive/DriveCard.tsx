"use client";

import { useState } from "react";
import Link from "next/link";
import type { DriveFile } from "@/lib/google-drive-types";

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatSize(bytes?: number | null) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function displayDriveTitle(file: DriveFile) {
  const title = (file.name || "").trim();
  if (title) return title;
  return file.file_id || "Untitled file";
}

function mimeBadge(file: DriveFile) {
  const mime = (file.mime_type || "").toLowerCase();
  const ext = (file.extension || "").toLowerCase();
  if (mime.includes("document")) return "Google Doc";
  if (mime.includes("spreadsheet")) return "Google Sheet";
  if (mime.includes("presentation")) return "Google Slides";
  if (mime.includes("pdf") || ext === "pdf") return "PDF";
  if (mime.includes("csv") || ext === "csv") return "CSV";
  if (mime.includes("html") || ext === "html") return "HTML";
  if (mime.includes("text") || ext === "txt") return "Text";
  if (ext) return ext.toUpperCase();
  return "Drive file";
}

function previewIcon(file: DriveFile) {
  const badge = mimeBadge(file);
  if (badge.includes("Sheet")) return "📊";
  if (badge.includes("Slides")) return "📽️";
  if (badge === "PDF") return "📕";
  return "📄";
}

function driveThumbnailUrl(fileId: string) {
  return `https://drive.google.com/thumbnail?id=${encodeURIComponent(fileId)}&sz=w640-h480`;
}

function categoryLabel(id: string) {
  return id.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function DrivePreview({ file, title }: { file: DriveFile; title: string }) {
  const [failed, setFailed] = useState(false);
  const letter = title.trim().charAt(0).toUpperCase() || "D";

  if (failed || !file.file_id) {
    return (
      <div className="docs-card__preview-fallback" aria-hidden="true">
        <span className="docs-card__preview-icon">{previewIcon(file)}</span>
        <strong>{letter}</strong>
      </div>
    );
  }

  return (
    <img
      src={driveThumbnailUrl(file.file_id)}
      alt=""
      className="docs-card__preview-img"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

export function DriveCard({
  file,
  detailBasePath = "/explore/drive",
}: {
  file: DriveFile;
  detailBasePath?: string;
}) {
  const title = displayDriveTitle(file);
  const openUrl = file.public_url || `https://drive.google.com/file/d/${file.file_id}/view`;
  const chips = (file.categories || []).slice(0, 3).map(categoryLabel);
  const badge = mimeBadge(file);

  return (
    <article className="docs-card">
      <a
        href={openUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="docs-card__preview-link"
        aria-label={`Open ${title}`}
      >
        <div className="docs-card__preview">
          <DrivePreview file={file} title={title} />
          <span className="docs-card__preview-badge">{badge}</span>
        </div>
      </a>

      <div className="docs-card__body">
        <div className="docs-card__meta-row">
          <span>{file.language?.toUpperCase() || file.extension?.toUpperCase() || "—"}</span>
          <span>{formatDate(file.indexed_at || file.created_at)}</span>
        </div>

        <p className="docs-card__shared-by docs-card__shared-by--missing">
          <span>Source</span> <em>Public Drive file</em>
        </p>

        <h2 className="docs-card__title">
          <a href={openUrl} target="_blank" rel="noopener noreferrer">
            {title}
          </a>
        </h2>

        <p className="docs-card__excerpt">{file.excerpt || "No preview text stored for this file yet."}</p>

        {chips.length > 0 ? (
          <div className="docs-card__chips">
            {chips.map((chip) => (
              <span key={chip} className="docs-card__chip">
                {chip}
              </span>
            ))}
          </div>
        ) : null}

        <div className="docs-card__stats">
          <div>
            <span>Words</span>
            <strong>{formatNumber(file.word_count)}</strong>
          </div>
          <div>
            <span>Characters</span>
            <strong>{formatNumber(file.character_count)}</strong>
          </div>
          <div>
            <span>Size</span>
            <strong>{formatSize(file.size)}</strong>
          </div>
        </div>

        <div className="docs-card__actions">
          <a className="btn-primary" href={openUrl} target="_blank" rel="noopener noreferrer">
            Open file
          </a>
          <Link className="btn-secondary" href={`${detailBasePath}/${encodeURIComponent(file.file_id)}`}>
            View details
          </Link>
        </div>
      </div>
    </article>
  );
}

export function DriveCardSkeleton() {
  return (
    <article className="docs-card docs-card--skeleton">
      <div className="docs-card__preview docs-card__preview--skeleton" />
      <div className="docs-card__body">
        <span className="docs-card__skeleton-line docs-card__skeleton-line--short" />
        <strong className="docs-card__skeleton-line docs-card__skeleton-line--title" />
        <p className="docs-card__skeleton-line" />
        <p className="docs-card__skeleton-line" />
        <p className="docs-card__skeleton-line docs-card__skeleton-line--half" />
        <div className="docs-card__stats">
          <div>
            <span />
            <strong />
          </div>
          <div>
            <span />
            <strong />
          </div>
          <div>
            <span />
            <strong />
          </div>
        </div>
      </div>
    </article>
  );
}
