export type GoogleDocument = {
  id: string;
  google_doc_id: string;
  url: string;
  title?: string | null;
  excerpt?: string | null;
  clean_text?: string | null;
  headings?: string | null;
  word_count?: number | null;
  character_count?: number | null;
  language?: string | null;
  preview_url?: string | null;
  preview_image_url?: string | null;
  images_count?: number | null;
  search_text?: string | null;
  archive_data?: GoogleDocumentArchive | null;
  content_archived_at?: string | null;
  shared_by_email?: string | null;
  shared_by_name?: string | null;
  shared_at?: string | null;
  document_modified_at?: string | null;
  status?: string;
  error_message?: string | null;
  crawled_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type GoogleDocsListResponse = {
  items: GoogleDocument[];
  total: number | null;
  page: number;
  page_size: number;
  has_more: boolean;
};

export type GoogleDocsStats = {
  total: number;
  parsed: number;
  with_content?: number;
  with_images: number;
};

export type GoogleDocumentSearchHit = GoogleDocument & {
  snippet?: string;
  relevance_score?: number;
  ranking_reason?: string;
};

export type GoogleDocsSearchResponse = {
  items: GoogleDocumentSearchHit[];
  total: number | null;
  page: number;
  page_size: number;
  query: string;
  mode?: "ai" | "keyword" | "ranked";
  ai_available?: boolean;
  candidates?: number;
  ranked?: number;
  score_threshold?: number;
  ai_error?: string;
};

export type GoogleDocumentArchive = {
  headings?: string[];
  paragraphs?: string[];
  lists?: string[];
  tables?: string[];
  links?: { href: string; text: string }[];
  images?: { src: string; alt: string }[];
};

export type GoogleDocsImportResult = {
  imported: number;
  skipped: number;
  errors: number;
  csv_path: string;
};

export type GoogleDocsCrawlRun = {
  id: string;
  status: string;
  mode: string;
  config: Record<string, unknown>;
  started_at?: string | null;
  ended_at?: string | null;
  discovered_count?: number;
  crawled_count?: number;
  parsed_count?: number;
  failed_count?: number;
  imported_count?: number;
  current_phase?: string;
  log_lines?: { ts: string; message: string }[];
  last_error?: string | null;
  worker_pid?: string | null;
  created_at?: string;
  updated_at?: string;
};
