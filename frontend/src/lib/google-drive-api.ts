import { apiFetch } from "@/lib/api";
import { fetchPublic } from "@/lib/public-api";
import type { DriveCategory, DriveCrawlRun, DriveFile } from "@/lib/google-drive-types";

export async function fetchDriveCategories(): Promise<DriveCategory[]> {
  const data = await fetchPublic<{ categories: DriveCategory[] }>("/public/google-drive/categories");
  return data.categories || [];
}

export async function fetchDriveStats() {
  return fetchPublic<{ ok: boolean; total?: number; indexed?: number; with_text?: number; with_content?: number }>(
    "/public/google-drive/stats"
  );
}

export async function fetchDriveFiles(params: {
  q?: string;
  mime_type?: string;
  extension?: string;
  category?: string;
  sort?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.mime_type) qs.set("mime_type", params.mime_type);
  if (params.extension) qs.set("extension", params.extension);
  if (params.category) qs.set("category", params.category);
  if (params.sort) qs.set("sort", params.sort);
  if (params.order) qs.set("order", params.order);
  qs.set("limit", String(params.limit ?? 24));
  qs.set("offset", String(params.offset ?? 0));
  return fetchPublic<{ items: DriveFile[]; total: number }>(`/public/google-drive?${qs}`);
}

export async function fetchDriveFile(fileId: string) {
  return fetchPublic<DriveFile>(`/public/google-drive/${encodeURIComponent(fileId)}`);
}

export async function adminStartDriveCrawl(body: {
  mode: string;
  query?: string;
  target?: number;
  max_results?: number;
  categories: string[];
  max_depth?: number;
  max_files?: number;
  workers?: number;
  resume?: boolean;
  seed_urls?: string[];
}) {
  const data = await apiFetch<{ run: DriveCrawlRun }>("/google-drive/crawl/start", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data.run;
}

export async function adminActiveDriveCrawl() {
  const data = await apiFetch<{ run: DriveCrawlRun | null }>("/google-drive/crawl/active");
  return data.run;
}

export async function adminDriveCrawlStatus(runId: string) {
  const data = await apiFetch<{ run: DriveCrawlRun }>(`/google-drive/crawl/status/${runId}`);
  return data.run;
}

export async function adminStopDriveCrawl(runId: string) {
  const data = await apiFetch<{ run: DriveCrawlRun }>(`/google-drive/crawl/stop/${runId}`, {
    method: "POST",
  });
  return data.run;
}

export async function adminListDriveCrawls(limit = 20) {
  const data = await apiFetch<{ runs: DriveCrawlRun[] }>(`/google-drive/crawl/runs?limit=${limit}`);
  return data.runs;
}
