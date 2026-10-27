import { createClient } from "./supabase";
import { API_CONNECTION_ERROR, fetchApi, isAbortError } from "./api-connect";
import { getApiBaseUrlCandidates } from "./api-url";
import { getAccessToken, refreshAccessToken } from "./auth-session";
import { parseApiErrorDetail } from "./api-errors";

export class ApiAuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiAuthError";
  }
}

const GET_CACHE_TTL_MS = 10000;
const getCache = new Map<string, { expires: number; value: unknown }>();
const pendingGets = new Map<string, Promise<unknown>>();

function getCacheTtlMs(_path: string): number {
  return GET_CACHE_TTL_MS;
}

export function invalidateApiCache(prefix?: string) {
  if (!prefix) {
    getCache.clear();
    pendingGets.clear();
    return;
  }
  for (const key of getCache.keys()) {
    if (key.startsWith(prefix)) getCache.delete(key);
  }
  for (const key of pendingGets.keys()) {
    if (key.startsWith(prefix)) pendingGets.delete(key);
  }
}

function cloneJson<T>(value: T): T {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}

function isCacheableGet(path: string, options: RequestInit): boolean {
  const method = String(options.method || "GET").toUpperCase();
  if (method !== "GET") return false;
  if (path.startsWith("/users?")) return false;
  if (path.startsWith("/scrape/status")) return false;
  if (path.startsWith("/scrape/runs")) return false;
  return true;
}

async function redirectToLogin(message?: string) {
  try {
    const supabase = createClient();
    await supabase.auth.signOut();
  } catch {
    /* ignore sign-out network errors */
  }
  if (typeof window !== "undefined") {
    const q = message ? `?error=${encodeURIComponent(message)}` : "";
    window.location.href = `/login${q}`;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retried = false,
  baseUrl?: string
): Promise<T> {
  const method = String(options.method || "GET").toUpperCase();
  if (method !== "GET") {
    getCache.clear();
    pendingGets.clear();
  }

  const token = await getAccessToken();
  if (!token) {
    await redirectToLogin("Session expired. Please sign in again.");
    throw new ApiAuthError("Not authenticated");
  }

  const cacheKey = path;
  const cacheable = isCacheableGet(path, options);
  if (cacheable) {
    const cached = getCache.get(cacheKey);
    if (cached && cached.expires > Date.now()) {
      return cloneJson(cached.value) as T;
    }
    const pending = pendingGets.get(cacheKey);
    if (pending) {
      return cloneJson((await pending) as T);
    }
  }

  const runRequest = async (): Promise<T> => {
    let res: Response;
    const bases = baseUrl ? [baseUrl.replace(/\/$/, "")] : getApiBaseUrlCandidates();
    try {
      res = await fetchApi(path, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...(options.headers || {}),
        },
      }, bases);
    } catch (error) {
      if (isAbortError(error)) throw error;
      throw new Error(error instanceof Error ? error.message : API_CONNECTION_ERROR);
    }

    if (res.status === 401 && !retried) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return apiFetch<T>(path, options, true);
      }
      await redirectToLogin("Session expired. Please sign in again.");
      throw new ApiAuthError("Session expired");
    }

    if (res.status === 403) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(parseApiErrorDetail(err.detail, "Admin access required"));
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const detail = parseApiErrorDetail(err.detail, res.statusText);
      if (res.status >= 500) {
        throw new Error(
          detail.includes("column") || detail.includes("42703")
            ? `${detail} - Run schema/github_users_enrichment.sql in the Supabase SQL Editor.`
            : detail.includes("google_documents")
              ? `${detail} - Run schema/google_documents.sql in the Supabase SQL Editor.`
              : `Server error (${res.status}): ${detail}`
        );
      }
      throw new Error(detail || res.statusText);
    }

    if (res.headers.get("content-type")?.includes("application/json")) {
      const json = await res.json();
      if (cacheable) {
        getCache.set(cacheKey, {
          expires: Date.now() + getCacheTtlMs(path),
          value: json,
        });
      }
      return json;
    }
    return res as unknown as T;
  };

  if (cacheable) {
    const promise = runRequest();
    pendingGets.set(cacheKey, promise);
    try {
      return cloneJson(await promise);
    } finally {
      pendingGets.delete(cacheKey);
    }
  }
  return runRequest();
}

export type ScrapeRun = {
  id: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  total_users_found: number;
  current_country?: string;
  countries_completed: string[];
  config: Record<string, unknown>;
  log_lines: { ts: string; message: string }[];
  rate_limit_remaining?: number;
  rate_limit_reset_at?: string;
  estimated_seconds_remaining?: number;
  last_error?: string;
};

export type ScrapeConfig = {
  countries: string[];
  max_per_location?: number | null;
  follower_buckets: string[];
  date_buckets: string[];
};
