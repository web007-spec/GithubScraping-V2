"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import DocPreviewImage from "@/components/DocPreviewImage";
import { displayDocTitle } from "@/components/docs/DocsCard";
import LoadingState from "@/components/LoadingState";
import { fetchPublicDoc } from "@/lib/google-docs-api";
import type { GoogleDocument } from "@/lib/google-docs-types";

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleString();
}

export default function ExploreDocDetailPage() {
  const params = useParams<{ id: string }>();
  const docId = decodeURIComponent(params.id || "");
  const [doc, setDoc] = useState<GoogleDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!docId) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchPublicDoc(docId);
      setDoc(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <LoadingState
        variant="inline"
        title="Loading document"
        detail="Fetching document details and preview."
      />
    );
  }

  if (error || !doc) {
    return (
      <div className="docs-detail docs-detail--error card">
        <h1>Document not found</h1>
        <p>{error || "This explored link is not in the archive yet."}</p>
        <Link href="/explore/docs" className="btn-secondary">
          Back to explorer
        </Link>
      </div>
    );
  }

  const title = displayDocTitle(doc);
  const previewUrl = doc.preview_image_url || doc.preview_url;
  const archive = doc.archive_data;
  const links = archive?.links?.filter((link) => link.href) ?? [];
  const paragraphs = archive?.paragraphs?.filter(Boolean) ?? [];

  return (
    <div className="docs-detail">
      <div className="docs-detail__toolbar">
        <Link href="/explore/docs" className="btn-ghost">
          ← Back to explorer
        </Link>
        <a className="btn-primary" href={doc.url} target="_blank" rel="noopener noreferrer">
          Open in Google Docs
        </a>
      </div>

      <div className="docs-detail__layout">
        <aside className="docs-detail__preview card">
          <DocPreviewImage
            docId={doc.google_doc_id}
            directUrl={previewUrl}
            title={title}
            className="docs-detail__preview-img"
            publicPreview
          />
          <p className="docs-detail__preview-caption">First-page preview thumbnail</p>
        </aside>

        <section className="docs-detail__content card">
          <p className="docs-detail__eyebrow">Google Docs archive</p>
          <h1>{title}</h1>
          <p className="docs-detail__url">
            <a href={doc.url} target="_blank" rel="noopener noreferrer">
              {doc.url}
            </a>
          </p>

          <div className="docs-detail__sharing card">
            <h2>Shared by</h2>
            {doc.shared_by_email ? (
              <>
                <p className="docs-detail__sharing-email">
                  <a href={`mailto:${doc.shared_by_email}`}>{doc.shared_by_email}</a>
                </p>
                {doc.shared_by_name ? (
                  <p className="docs-detail__muted">{doc.shared_by_name}</p>
                ) : null}
              </>
            ) : (
              <p className="docs-detail__muted">
                Google does not expose the publisher&apos;s account email for this public document.
                No contact email was found in the document content.
              </p>
            )}
            <p className="docs-detail__muted">
              {doc.shared_at
                ? `Document shared / updated ${formatDate(doc.shared_at)}`
                : "Sharing date not available from Google"}
            </p>
          </div>

          <div className="docs-detail__stats">
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
            <div>
              <span>Language</span>
              <strong>{doc.language?.toUpperCase() || "—"}</strong>
            </div>
            <div>
              <span>Content archived</span>
              <strong>{formatDate(doc.content_archived_at || doc.crawled_at)}</strong>
            </div>
            {doc.shared_at ? (
              <div>
                <span>Document shared</span>
                <strong>{formatDate(doc.shared_at)}</strong>
              </div>
            ) : null}
            {doc.document_modified_at && doc.document_modified_at !== doc.shared_at ? (
              <div>
                <span>Last modified</span>
                <strong>{formatDate(doc.document_modified_at)}</strong>
              </div>
            ) : null}
          </div>

          {doc.headings ? (
            <div className="docs-detail__section">
              <h2>Headings</h2>
              <div className="docs-card__chips">
                {doc.headings
                  .split("|")
                  .map((part) => part.trim())
                  .filter(Boolean)
                  .map((chip, index) => (
                    <span key={`${chip}-${index}`} className="docs-card__chip">
                      {chip}
                    </span>
                  ))}
              </div>
            </div>
          ) : null}

          {links.length > 0 ? (
            <div className="docs-detail__section">
              <h2>Links in document ({links.length})</h2>
              <ul className="docs-detail__links">
                {links.slice(0, 50).map((link) => (
                  <li key={`${link.href}-${link.text}`}>
                    <a href={link.href} target="_blank" rel="noopener noreferrer">
                      {link.text || link.href}
                    </a>
                  </li>
                ))}
              </ul>
              {links.length > 50 ? (
                <p className="docs-detail__muted">Showing first 50 links.</p>
              ) : null}
            </div>
          ) : null}

          {paragraphs.length > 0 ? (
            <div className="docs-detail__section">
              <h2>Archived content</h2>
              <div className="docs-detail__body">
                {paragraphs.slice(0, 12).map((para, index) => (
                  <p key={index}>{para}</p>
                ))}
              </div>
              {paragraphs.length > 12 ? (
                <p className="docs-detail__muted">
                  Showing first 12 paragraphs of {paragraphs.length}. Open the document for the full
                  text.
                </p>
              ) : null}
            </div>
          ) : (
            <div className="docs-detail__section">
              <h2>Excerpt</h2>
              <p>{doc.excerpt || "No excerpt stored."}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
