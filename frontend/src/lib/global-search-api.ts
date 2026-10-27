import { fetchPublic } from "@/lib/public-api";

export type GlobalSearchUserHit = {
  type: "user";
  id: string;
  login?: string;
  name?: string | null;
  bio?: string | null;
  location?: string | null;
  followers?: number | null;
  avatar_url?: string | null;
  snippet?: string;
  relevance_score?: number;
  ranking_reason?: string;
};

export type GlobalSearchDocHit = {
  type: "doc";
  id: string;
  google_doc_id?: string;
  title?: string | null;
  excerpt?: string | null;
  url?: string;
  preview_image_url?: string | null;
  snippet?: string;
  relevance_score?: number;
  ranking_reason?: string;
};

export type GlobalSearchHit = GlobalSearchUserHit | GlobalSearchDocHit;

export type GlobalSearchResponse = {
  items: GlobalSearchHit[];
  total: number | null;
  query: string;
  mode?: "ai" | "keyword" | "ranked";
  ai_available?: boolean;
  cached?: boolean;
  candidates?: number;
  page?: number;
  page_size?: number;
  ai_error?: string;
};

export async function fetchGlobalAiSearch(params: {
  q: string;
  page?: number;
  page_size?: number;
}): Promise<GlobalSearchResponse> {
  const search = new URLSearchParams({ q: params.q });
  search.set("page", String(params.page || 1));
  search.set("page_size", String(params.page_size || 20));
  return fetchPublic<GlobalSearchResponse>(`/public/search/ai?${search.toString()}`);
}
