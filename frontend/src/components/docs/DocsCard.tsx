"use client";

import Link from "next/link";
import DocPreviewImage from "@/components/DocPreviewImage";
import type { GoogleDocument } from "@/lib/google-docs-types";

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

export function displayDocTitle(doc: GoogleDocument) {
  const title = (doc.title || "").trim();
  if (title) return title;
  const excerpt = (doc.excerpt || "").trim();
  if (excerpt) return excerpt.slice(0, 72) + (excerpt.length > 72 ? "…" : "");
  return "Untitled Google Doc";
}

function headingChips(headings?: string | null) {
  if (!headings) return [];
  return headings
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 3);
}

export function DocsCard({
  doc,
  detailBasePath = "/explore/docs",
  snippet,
  relevanceScore,
  rankingReason,
}: {
  doc: GoogleDocument;
  detailBasePath?: string;
  snippet?: string;
  relevanceScore?: number;
  rankingReason?: string;
}) {
  const title = displayDocTitle(doc);
  const chips = headingChips(doc.headings);
  const previewUrl = doc.preview_image_url || doc.preview_url;

  return (
    <article className="docs-card">
      <Link
        href={doc.url}
        target="_blank"
        rel="noopener noreferrer"
        className="docs-card__preview-link"
        aria-label={`Open ${title} in Google Docs`}
      >
        <div className="docs-card__preview">
          <DocPreviewImage
            docId={doc.google_doc_id}
            directUrl={previewUrl}
            title={title}
            className="docs-card__preview-img"
            publicPreview
          />
          <span className="docs-card__preview-badge">Google Doc</span>
        </div>
      </Link>

      <div className="docs-card__body">
        <div className="docs-card__meta-row">
          <span>{doc.language?.toUpperCase() || "—"}</span>
          <span>{formatDate(doc.shared_at || doc.crawled_at || doc.created_at)}</span>
        </div>

        {doc.shared_by_email ? (
          <p className="docs-card__shared-by">
            <span>Shared by</span>{" "}
            <a href={`mailto:${doc.shared_by_email}`}>{doc.shared_by_email}</a>
          </p>
        ) : (
          <p className="docs-card__shared-by docs-card__shared-by--missing">
            <span>Shared by</span> <em>Email not available</em>
          </p>
        )}

        <h2 className="docs-card__title">
          <Link href={doc.url} target="_blank" rel="noopener noreferrer">
            {title}
          </Link>
        </h2>

        <p className="docs-card__excerpt">
          {rankingReason || snippet || doc.excerpt || "No preview text stored for this document yet."}
        </p>

        {typeof relevanceScore === "number" ? (
          <div className="docs-card__relevance">
            <span>{relevanceScore}% match</span>
          </div>
        ) : null}

        {chips.length > 0 ? (
          <div className="docs-card__chips">
            {chips.map((chip, index) => (
              <span key={`${chip}-${index}`} className="docs-card__chip">
                {chip}
              </span>
            ))}
          </div>
        ) : null}

        <div className="docs-card__stats">
          <div>
            <span>Words</span>
            <strong>{formatNumber(doc.word_count)}</strong>
          </div>
          <div>
            <span>Characters</span>
            <strong>{formatNumber(doc.character_count)}</strong>
          </div>
          <div>
            <span>Images</span>
            <strong>{formatNumber(doc.images_count)}</strong>
          </div>
        </div>

        <div className="docs-card__actions">
          <a className="btn-primary" href={doc.url} target="_blank" rel="noopener noreferrer">
            Open document
          </a>
          <Link
            className="btn-secondary"
            href={`${detailBasePath}/${encodeURIComponent(doc.google_doc_id)}`}
          >
            View details
          </Link>
        </div>
      </div>
    </article>
  );
}

export function DocsCardSkeleton() {
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
          <div><span /><strong /></div>
          <div><span /><strong /></div>
          <div><span /><strong /></div>
        </div>
      </div>
    </article>
  );
}
