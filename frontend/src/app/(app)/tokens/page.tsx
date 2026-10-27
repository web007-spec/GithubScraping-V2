"use client";

import { useEffect, useState } from "react";
import LoadingState, { LoadingDots } from "@/components/LoadingState";
import { apiFetch } from "@/lib/api";
import { Token } from "@/lib/types";

export default function TokensPage() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [token, setToken] = useState("");
  const [label, setLabel] = useState("default");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyTokenId, setBusyTokenId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setTokens(await apiFetch<Token[]>("/tokens"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tokens");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function addToken(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await apiFetch("/tokens", {
        method: "POST",
        body: JSON.stringify({ token, label, is_active: true }),
      });
      setToken("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(id: string, is_active: boolean) {
    setBusyTokenId(id);
    try {
      await apiFetch(`/tokens/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
      });
      await load();
    } finally {
      setBusyTokenId(null);
    }
  }

  async function refresh(id: string) {
    setBusyTokenId(id);
    try {
      await apiFetch(`/tokens/${id}/refresh-rate-limit`, { method: "POST" });
      await load();
    } finally {
      setBusyTokenId(null);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title">GitHub Tokens</h1>
        <p className="page-subtitle">Manage encrypted API tokens used by scraper runs.</p>
      </div>

      <form onSubmit={addToken} className="card mb-8 max-w-lg">
        <h2 className="mb-4 font-medium">Add token</h2>
        <input
          className="input mb-3"
          placeholder="ghp_…"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          required
          type="password"
        />
        <input
          className="input mb-4"
          placeholder="Label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? <LoadingDots label="Saving" /> : "Save encrypted token"}
        </button>
        {error && <p className="alert-error mt-4">{error}</p>}
      </form>

      <div className="space-y-4">
        {loading && (
          <LoadingState
            variant="inline"
            title="Loading tokens"
            detail="Checking encrypted token labels and rate-limit status."
          />
        )}
        {!loading && tokens.length === 0 && !error && (
          <div className="card-muted text-sm text-github-light">No tokens saved yet.</div>
        )}
        {tokens.map((t) => (
          <div key={t.id} className="card flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="font-medium">
                {t.label}{" "}
                {t.is_active && (
                  <span className="ml-2 rounded-md border border-emerald-500/30 bg-emerald-950/40 px-2 py-0.5 text-xs text-emerald-200">
                    active
                  </span>
                )}
              </p>
              <p className="text-sm text-github-light">
                Preview: {t.token_preview || "—"} · Rate limit: {t.rate_limit_remaining ?? "?"}
                {t.rate_limit_reset_at && (
                  <> · resets {new Date(t.rate_limit_reset_at).toLocaleString()}</>
                )}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => refresh(t.id)}
                className="btn-secondary"
                disabled={busyTokenId === t.id}
              >
                {busyTokenId === t.id ? <LoadingDots label="Working" /> : "Refresh limits"}
              </button>
              <button
                onClick={() => toggle(t.id, !t.is_active)}
                className="btn-secondary"
                disabled={busyTokenId === t.id}
              >
                {busyTokenId === t.id ? (
                  <LoadingDots label="Updating" />
                ) : t.is_active ? (
                  "Deactivate"
                ) : (
                  "Activate"
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
