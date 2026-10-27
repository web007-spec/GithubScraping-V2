import { useMongoStorage } from "./database-storage";

const STORAGE_KEY = "outreach_console_auth";

export type StoredAuthSession = {
  access_token: string;
  expires_at: number;
  user?: {
    id: string;
    email?: string;
    role?: string;
    user_metadata?: Record<string, unknown>;
  };
};

export function isLocalAuthMode(): boolean {
  return useMongoStorage;
}

export function readAuthSession(): StoredAuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredAuthSession;
    if (!parsed?.access_token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeAuthSession(session: StoredAuthSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearAuthSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function sessionIsValid(session: StoredAuthSession | null): boolean {
  if (!session?.access_token) return false;
  const now = Math.floor(Date.now() / 1000);
  return (session.expires_at || 0) > now + 30;
}
