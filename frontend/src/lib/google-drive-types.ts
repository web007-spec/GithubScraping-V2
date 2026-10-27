export type DriveSubcategory = {
  id: string;
  label: string;
};

export type DriveCategory = {
  id: string;
  label: string;
  description: string;
  subcategories: DriveSubcategory[];
};

export type DriveFile = {
  id: string;
  file_id: string;
  folder_id?: string | null;
  name?: string | null;
  mime_type?: string | null;
  extension?: string | null;
  size?: number | null;
  public_url?: string | null;
  raw_text?: string | null;
  excerpt?: string | null;
  word_count?: number | null;
  character_count?: number | null;
  language?: string | null;
  categories?: string[];
  status?: string;
  indexed_at?: string | null;
  created_at?: string | null;
};

export type DriveCrawlRun = {
  id: string;
  status: string;
  mode: string;
  config?: {
    mode?: string;
    query?: string;
    target?: number;
    max_results?: number;
    seed_urls?: string[];
    categories?: string[];
    max_depth?: number;
    max_files?: number;
    workers?: number;
    resume?: boolean;
  };
  discovered_count?: number;
  current_phase?: string;
  folders_crawled?: number;
  files_discovered?: number;
  files_downloaded?: number;
  files_indexed?: number;
  failed_count?: number;
  log_lines?: { ts: string; message: string }[];
  last_error?: string | null;
  created_at?: string;
  started_at?: string | null;
  ended_at?: string | null;
};
