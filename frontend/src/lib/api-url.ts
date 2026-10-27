const DEFAULT_API_PORT = process.env.NEXT_PUBLIC_API_PORT || "8000";

export function getApiPort(): number {
  const fromDirect = process.env.NEXT_PUBLIC_API_DIRECT_URL?.match(/:(\d+)(?:\/|$)/)?.[1];
  if (fromDirect) return Number(fromDirect) || 8000;
  return Number(DEFAULT_API_PORT) || 8000;
}

/** Direct FastAPI URL (bypasses Next.js proxy). Works for LAN clients on the same host. */
export function getApiDirectUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_DIRECT_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;

  if (typeof window !== "undefined") {
    const { hostname, protocol } = window.location;
    const port = getApiPort();
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `http://127.0.0.1:${port}`;
    }
    return `${protocol}//${hostname}:${port}`;
  }

  return (
    process.env.API_PROXY_TARGET?.replace(/\/$/, "") ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
    `http://127.0.0.1:${getApiPort()}`
  );
}

/** Same-origin Next.js rewrite target (`/backend` → FastAPI on the server). */
export function getApiProxyUrl(): string | null {
  if (typeof window === "undefined") {
    return getApiDirectUrl();
  }
  return `${window.location.origin}/backend`;
}

function uniqueUrls(urls: string[]): string[] {
  return [...new Set(urls.map((url) => url.replace(/\/$/, "")).filter(Boolean))];
}

/**
 * Ordered API bases to try when a request fails.
 * LAN users hit the API directly (port 8000); localhost tries proxy then direct.
 */
export function getApiBaseUrlCandidates(): string[] {
  if (typeof window === "undefined") {
    return uniqueUrls([getApiDirectUrl()]);
  }

  const direct = getApiDirectUrl();
  const proxy = getApiProxyUrl();
  const { hostname } = window.location;

  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return uniqueUrls([proxy || direct, direct]);
  }

  return uniqueUrls([direct, proxy || direct]);
}

/** Primary API base URL (first candidate). */
export function getApiBaseUrl(): string {
  return getApiBaseUrlCandidates()[0];
}

/** Large uploads — always direct to avoid proxy overhead. */
export function getApiUploadBaseUrl(): string {
  return getApiDirectUrl();
}

export function getChatApiBaseUrl(): string {
  return getApiDirectUrl();
}
