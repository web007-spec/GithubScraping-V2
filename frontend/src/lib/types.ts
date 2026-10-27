export type SocialLink = {

  provider?: string;

  url?: string;

  display_name?: string;

};



export type GitHubUser = {

  id: number;

  login: string;

  name?: string;

  location?: string;

  company?: string;

  email?: string;

  email_source?: string;

  bio?: string;

  description?: string;

  blog?: string;

  twitter_username?: string;

  github_url?: string;

  avatar_url?: string;

  public_repos?: number;

  public_gists?: number;

  followers?: number;

  following?: number;

  created_at?: string;

  updated_at?: string;

  country?: string;

  last_scraped_at?: string;

  all_emails?: string[];

  social_links?: SocialLink[];

  profile_data?: Record<string, unknown>;

};



export type Token = {

  id: string;

  label: string;

  is_active: boolean;

  rate_limit_remaining?: number;

  rate_limit_reset_at?: string;

  notes?: string;

  token_preview?: string;

};



export type Schedule = {

  id: string;

  name: string;

  cron_expression: string;

  config: Record<string, unknown>;

  active: boolean;

  last_run_at?: string;

  next_run_at?: string;

};


