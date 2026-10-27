"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api-connect";
import { getAccessToken } from "@/lib/auth-session";
import { publicDocPreviewUrl } from "@/lib/google-docs-api";

type Props = {
  docId: string;
  directUrl?: string | null;
  title?: string | null;
  className?: string;
  publicPreview?: boolean;
};

function DocPlaceholder({ title, className }: { title?: string | null; className?: string }) {
  const letter = (title || "Document").trim().charAt(0).toUpperCase() || "D";
  return (
    <div className={`docs-card__preview-fallback ${className || ""}`} aria-hidden="true">
      <span className="docs-card__preview-icon">📄</span>
      <strong>{letter}</strong>
    </div>
  );
}

export default function DocPreviewImage({
  docId,
  directUrl,
  title,
  className,
  publicPreview = false,
}: Props) {
  const [src, setSrc] = useState<string | null>(directUrl || null);
  const [failed, setFailed] = useState(false);
  const [proxyAttempted, setProxyAttempted] = useState(false);

  const loadProxy = useCallback(async () => {
    if (proxyAttempted) return;
    setProxyAttempted(true);
    try {
      const path = publicPreview
        ? publicDocPreviewUrl(docId)
        : `/google-docs/${encodeURIComponent(docId)}/preview-image`;
      const headers: Record<string, string> = {};
      if (!publicPreview) {
        const token = await getAccessToken();
        if (!token) {
          setFailed(true);
          return;
        }
        headers.Authorization = `Bearer ${token}`;
      }
      const response = await fetchApi(path, { headers });
      if (!response.ok) {
        setFailed(true);
        return;
      }
      const blob = await response.blob();
      setSrc(URL.createObjectURL(blob));
    } catch {
      setFailed(true);
    }
  }, [docId, proxyAttempted, publicPreview]);

  useEffect(() => {
    setSrc(directUrl || null);
    setFailed(false);
    setProxyAttempted(false);
  }, [directUrl, docId]);

  useEffect(() => {
    if (!directUrl && !proxyAttempted && !failed) {
      void loadProxy();
    }
  }, [directUrl, failed, loadProxy, proxyAttempted]);

  useEffect(() => {
    return () => {
      if (src && src.startsWith("blob:")) {
        URL.revokeObjectURL(src);
      }
    };
  }, [src]);

  if (failed) {
    return <DocPlaceholder title={title} className={className} />;
  }

  if (!src) {
    return <DocPlaceholder title={title} className={className} />;
  }

  return (
    <img
      className={className}
      src={src}
      alt={title ? `Preview of ${title}` : "Document preview"}
      loading="lazy"
      decoding="async"
      onError={() => {
        if (!proxyAttempted) {
          void loadProxy();
        } else {
          setFailed(true);
        }
      }}
    />
  );
}
