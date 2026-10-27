"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { fetchPublic } from "@/lib/public-api";
import { useAdminSession } from "@/lib/use-admin-session";

type SetupStatus = {
  ok: boolean;
  storage?: "mongodb" | "supabase";
  missing_tables?: string[];
  missing?: string[];
  can_auto_setup?: boolean;
  sql_file?: string | null;
};

export default function DocsSetupBanner({ onReady }: { onReady?: () => void }) {
  const { isAdmin } = useAdminSession();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const projectRef = (process.env.NEXT_PUBLIC_SUPABASE_URL || "")
    .replace("https://", "")
    .split(".")[0];

  const sqlEditorUrl = projectRef
    ? `https://supabase.com/dashboard/project/${projectRef}/sql/new`
    : "https://supabase.com/dashboard";

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await fetchPublic<SetupStatus>("/public/google-docs/setup-status");
      if (isAdmin && data.storage === "supabase" && !data.ok) {
        try {
          const adminStatus = await apiFetch<SetupStatus>("/google-docs/setup-schema/status");
          setStatus(adminStatus);
          if (adminStatus.ok) onReady?.();
          return;
        } catch {
          /* keep public status */
        }
      }
      setStatus(data);
      if (data.ok) onReady?.();
    } catch {
      setStatus({ ok: false, storage: "mongodb", missing: ["connection"] });
    }
  }, [isAdmin, onReady]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAutoSetup() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await apiFetch<{ ok: boolean; created_tables?: string[] }>(
        "/google-docs/setup-schema",
        { method: "POST" }
      );
      setMessage(
        result.created_tables?.length
          ? `Created: ${result.created_tables.join(", ")}`
          : "Database ready."
      );
      await load();
      onReady?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup failed");
    } finally {
      setBusy(false);
    }
  }

  if (status?.ok) return null;

  const isMongo = status?.storage === "mongodb";

  return (
    <div className="docs-alert docs-alert--warn" role="status">
      <div className="docs-alert__body">
        <strong>{isMongo ? "MongoDB connection required" : "Database tables required"}</strong>
        <p>
          {isMongo ? (
            <>
              Start MongoDB (e.g. run <code>net start MongoDB</code> as Administrator), ensure{" "}
              <code>MONGODB_URI</code> is set in <code>backend/github_Scraping/.env</code>, then
              restart the API. Collections are created automatically.
            </>
          ) : (
            <>
              Run <code>schema/google_docs_setup.sql</code> in Supabase, or switch to MongoDB with{" "}
              <code>MONGODB_URI</code>.
            </>
          )}
        </p>
        {message ? <p className="docs-alert__ok">{message}</p> : null}
        {error ? <p className="docs-alert__err">{error}</p> : null}
      </div>
      <div className="docs-alert__actions">
        {isAdmin && status?.can_auto_setup ? (
          <button type="button" className="btn-primary btn-sm" onClick={() => void handleAutoSetup()} disabled={busy}>
            {busy ? "Setting up…" : "Auto-create tables"}
          </button>
        ) : null}
        {!isMongo ? (
          <a className="btn-secondary btn-sm" href={sqlEditorUrl} target="_blank" rel="noopener noreferrer">
            SQL Editor
          </a>
        ) : null}
        <button type="button" className="btn-ghost btn-sm" onClick={() => void load()}>
          Refresh
        </button>
      </div>
    </div>
  );
}
