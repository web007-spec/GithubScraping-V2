import { fetchPublic } from "@/lib/public-api";
import { apiFetch } from "@/lib/api";
import type {
  GoogleDocsCrawlRun,
  GoogleDocsImportResult,
  GoogleDocsListResponse,
  GoogleDocsSearchResponse,
  GoogleDocsStats,
  GoogleDocument,
} from "@/lib/google-docs-types";

export async function fetchPublicDocsStats(): Promise<GoogleDocsStats> {
  return fetchPublic<GoogleDocsStats>("/public/google-docs/stats");
}

export async function fetchPublicDocsList(params: {
  q?: string;
  sort?: string;
  order?: string;
  page?: number;
  page_size?: number;
}): Promise<GoogleDocsListResponse> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);
  search.set("page", String(params.page || 1));
  search.set("page_size", String(params.page_size || 24));
  return fetchPublic<GoogleDocsListResponse>(`/public/google-docs?${search.toString()}`);
}

export async function fetchPublicDoc(id: string): Promise<GoogleDocument> {
  return fetchPublic<GoogleDocument>(`/public/google-docs/${encodeURIComponent(id)}`);
}

export function publicDocPreviewUrl(docId: string): string {
  return `/public/google-docs/${encodeURIComponent(docId)}/preview-image`;
}

export async function fetchPublicDocsSearch(params: {
  q: string;
  page?: number;
  page_size?: number;
  ai?: boolean;
}): Promise<GoogleDocsSearchResponse> {
  const search = new URLSearchParams({ q: params.q });
  search.set("page", String(params.page || 1));
  search.set("page_size", String(params.page_size || 20));
  if (params.ai !== false) search.set("ai", "true");
  return fetchPublic<GoogleDocsSearchResponse>(`/public/google-docs/search?${search.toString()}`);
}

export async function adminImportArchiveCsv(): Promise<GoogleDocsImportResult> {
  return apiFetch<GoogleDocsImportResult>("/google-docs/archive/import-csv", {
    method: "POST",
    body: JSON.stringify({ only_parsed: true }),
  });
}

export async function adminImportCsv(): Promise<GoogleDocsImportResult> {
  return adminImportArchiveCsv();
}

export async function adminStartCrawl(body: {
  mode: string;
  query?: string;
  target?: number;
  max_results?: number;
  workers?: number;
  resume?: boolean;
  auto_import?: boolean;
}): Promise<GoogleDocsCrawlRun> {
  return apiFetch<GoogleDocsCrawlRun>("/google-docs/crawl/start", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function adminActiveCrawl(): Promise<GoogleDocsCrawlRun | null> {
  return apiFetch<GoogleDocsCrawlRun | null>("/google-docs/crawl/active");
}

export async function adminCrawlStatus(runId: string): Promise<GoogleDocsCrawlRun> {
  return apiFetch<GoogleDocsCrawlRun>(`/google-docs/crawl/status/${encodeURIComponent(runId)}`);
}

export async function adminStopCrawl(runId: string): Promise<GoogleDocsCrawlRun> {
  return apiFetch<GoogleDocsCrawlRun>(`/google-docs/crawl/stop/${encodeURIComponent(runId)}`, {
    method: "POST",
  });
}

export async function adminListCrawlRuns(): Promise<GoogleDocsCrawlRun[]> {
  return apiFetch<GoogleDocsCrawlRun[]>("/google-docs/crawl/runs?limit=10");
}
