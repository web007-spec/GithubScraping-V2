import { getApiBaseUrlCandidates } from "./api-url";

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export const API_CONNECTION_ERROR =
  "Cannot reach the API. On the server PC, run .\\start-project.ps1 from the project root. " +
  "Other users must open the server's address (e.g. http://YOUR-SERVER-IP:3001), not localhost. " +
  "Allow inbound TCP ports 3001 and 8000 in Windows Firewall.";

/** Fetch from the API, trying direct URL then /backend proxy (or vice versa on localhost). */
export async function fetchApi(path: string, options: RequestInit = {}, bases?: string[]): Promise<Response> {
  const candidates = bases?.length ? bases : getApiBaseUrlCandidates();
  let lastError: unknown;

  for (const base of candidates) {
    try {
      return await fetch(`${base.replace(/\/$/, "")}${path}`, options);
    } catch (error) {
      if (isAbortError(error)) throw error;
      lastError = error;
    }
  }

  if (lastError instanceof Error && lastError.message === API_CONNECTION_ERROR) {
    throw lastError;
  }

  throw new Error(API_CONNECTION_ERROR);
}
