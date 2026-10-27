import { fetchApi } from "@/lib/api-connect";
import { getApiBaseUrl } from "@/lib/api-url";

export type PublicExampleRelease = {
  version: string;
  title: string;
  description?: string | null;
  install_instructions?: string | null;
  file_name: string;
  file_size: number;
  download_url: string;
};

/** Unauthenticated API calls (login/register, public browse). */
export async function fetchPublic<T>(path: string): Promise<T> {
  const res = await fetchApi(path, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : res.statusText);
  }
  const text = await res.text();
  if (!text || text === "null") {
    return null as T;
  }
  return JSON.parse(text) as T;
}

export function releaseDownloadHref(downloadPath: string): string {
  return `${getApiBaseUrl()}${downloadPath}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
