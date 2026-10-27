import { createClient } from "./supabase";
import {
  clearAuthSession,
  isLocalAuthMode,
  readAuthSession,
  sessionIsValid,
  writeAuthSession,
} from "./auth-token";
import { API_CONNECTION_ERROR, fetchApi } from "./api-connect";
import { parseApiErrorDetail } from "./api-errors";
import { formatAuthError } from "./auth";

/** Refresh if the access token expires within this many seconds. */
const REFRESH_MARGIN_SEC = 120;

function isNetworkError(err: unknown): boolean {
  if (err instanceof TypeError && err.message === "Failed to fetch") return true;
  if (err instanceof Error && /failed to fetch|network|fetch/i.test(err.message)) {
    return true;
  }
  return false;
}

export async function getAccessToken(): Promise<string | null> {
  if (isLocalAuthMode()) {
    const session = readAuthSession();
    return sessionIsValid(session) ? session!.access_token : null;
  }

  const supabase = createClient();

  try {
    const { data, error } = await supabase.auth.getSession();
    if (error) {
      console.warn("getSession error:", error.message);
      return null;
    }

    const session = data.session;
    if (!session?.access_token) return null;

    const now = Math.floor(Date.now() / 1000);
    const expiresAt = session.expires_at ?? 0;

    if (expiresAt - now > REFRESH_MARGIN_SEC) {
      return session.access_token;
    }

    return await refreshAccessTokenSafe(supabase, session.access_token, expiresAt);
  } catch (err) {
    if (isNetworkError(err)) {
      try {
        const { data } = await supabase.auth.getSession();
        return data.session?.access_token ?? null;
      } catch {
        return null;
      }
    }
    throw err;
  }
}

async function refreshAccessTokenSafe(
  supabase: ReturnType<typeof createClient>,
  fallbackToken: string,
  expiresAt: number
): Promise<string | null> {
  try {
    const { data, error } = await supabase.auth.refreshSession();
    if (!error && data.session?.access_token) {
      return data.session.access_token;
    }
  } catch (err) {
    if (!isNetworkError(err)) {
      console.warn("refreshSession error:", err);
    }
  }

  const now = Math.floor(Date.now() / 1000);
  if (expiresAt > now) {
    return fallbackToken;
  }
  return null;
}

/** Call only after API returns 401. */
export async function refreshAccessToken(): Promise<string | null> {
  if (isLocalAuthMode()) {
    clearAuthSession();
    return null;
  }

  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session?.access_token) return null;
  return refreshAccessTokenSafe(
    supabase,
    session.access_token,
    session.expires_at ?? 0
  );
}

export async function loginWithApi(email: string, password: string) {
  let res: Response;
  try {
    res = await fetchApi("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new Error(formatAuthError(API_CONNECTION_ERROR));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatAuthError(parseApiErrorDetail(data.detail, res.statusText)));
  }
  const expiresAt = Math.floor(Date.now() / 1000) + Number(data.expires_in || 604800);
  writeAuthSession({
    access_token: data.access_token,
    expires_at: expiresAt,
    user: data.user,
  });
  return data;
}

export function signOutLocalAuth(): void {
  clearAuthSession();
}

export async function fetchCurrentUser() {
  const token = await getAccessToken();
  if (!token) return null;
  const res = await fetchApi("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => null);
  if (!res || !res.ok) return null;
  return res.json() as Promise<{
    id: string;
    email?: string;
    role?: string;
    user_metadata?: Record<string, unknown>;
  }>;
}

export async function updateUserProfile(patch: { display_name?: string; avatar_url?: string }) {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetchApi("/auth/profile", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(patch),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatAuthError(parseApiErrorDetail(data.detail, "Could not update profile")));
  }
  return data as {
    id: string;
    email?: string;
    role?: string;
    user_metadata?: Record<string, unknown>;
  };
}

export async function uploadUserAvatar(file: File) {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const form = new FormData();
  form.append("file", file);
  const res = await fetchApi("/auth/avatar", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatAuthError(parseApiErrorDetail(data.detail, "Could not upload avatar")));
  }
  return data as { avatar_url?: string; user_metadata?: Record<string, unknown> };
}

export async function changeUserPassword(currentPassword: string, newPassword: string) {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetchApi("/auth/password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatAuthError(parseApiErrorDetail(data.detail, "Could not change password")));
  }
  return data as { ok: boolean; message?: string };
}
