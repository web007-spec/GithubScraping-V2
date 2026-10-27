import { API_CONNECTION_ERROR, fetchApi } from "./api-connect";
import { parseApiErrorDetail } from "./api-errors";
import { useMongoStorage } from "./database-storage";

export function getSupabaseConfigError(): string | null {
  if (useMongoStorage) return null;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
  if (!url || url.includes("your-project")) {
    return "NEXT_PUBLIC_SUPABASE_URL is missing or still a placeholder in frontend/.env";
  }
  if (!key || key.length < 20) {
    return "NEXT_PUBLIC_SUPABASE_ANON_KEY is missing in frontend/.env";
  }
  return null;
}

/** Turn Supabase / API errors into plain English for the UI. */
export function formatAuthError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("string should have at least 6 characters") || m.includes("password must be at least 6")) {
    return "Password must be at least 6 characters.";
  }
  if (m.includes("string_too_short") && m.includes("password")) {
    return "Password must be at least 6 characters.";
  }
  if (m.includes("email rate limit")) {
    return "Too many sign-up attempts. Wait a while and try again.";
  }
  if (m.includes("rate limit")) {
    return "Too many attempts. Please wait a few minutes and try again.";
  }
  if (m.includes("invalid login") || m.includes("invalid credentials") || m.includes("wrong email")) {
    return "Wrong email or password.";
  }
  if (m.includes("already registered") || m.includes("sign in instead")) {
    return "This email is already registered. Go to Sign in and use the same email and password.";
  }
  if (m.includes("ip address") || m.includes("same ip") || m.includes("this device")) {
    const match = message.match(/\(([^)]+@[^)]+)\)/);
    if (match?.[1]) {
      return `An account for ${match[1]} was already created from this device. Sign in with that email instead.`;
    }
    return "An account was already created from this device. Sign in with that email instead.";
  }
  if (m.includes("fetch") || m.includes("failed to fetch") || m.includes("cannot reach the api")) {
    return API_CONNECTION_ERROR;
  }
  return message;
}

export { parseApiErrorDetail };

export async function registerViaServer(
  email: string,
  password: string,
  registrationSecret?: string
): Promise<{ ok: boolean; message: string; email: string }> {
  const res = await fetchApi("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      registration_secret: registrationSecret || null,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatAuthError(parseApiErrorDetail(data.detail, res.statusText)));
  }
  return data;
}

export async function grantAdminAccess(
  accessToken: string,
  registrationSecret?: string
): Promise<{ ok: boolean; message: string }> {
  const res = await fetchApi("/auth/grant-admin", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(registrationSecret ? { "X-Registration-Secret": registrationSecret } : {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatAuthError(parseApiErrorDetail(data.detail, res.statusText)));
  }
  return data;
}

export async function refreshSession() {
  if (useMongoStorage) return;
  const { createClient } = await import("./supabase");
  const supabase = createClient();
  await supabase.auth.refreshSession();
}
