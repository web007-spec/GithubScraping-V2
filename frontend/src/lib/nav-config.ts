export type HubModuleId = "hub" | "github" | "docs" | "drive";

export type NavLink = {
  href: string;
  label: string;
  description?: string;
};

export type HubModule = {
  id: HubModuleId;
  label: string;
  shortLabel: string;
  href: string;
  accent: string;
  description: string;
  enabled?: boolean;
  disabledReason?: string;
  subLinks?: NavLink[];
};

export const PLATFORM_NAME = "Outreach Console";
export const PLATFORM_TAGLINE = "GitHub scraping · Google Drive";

export function isModuleEnabled(module: HubModule): boolean {
  return module.enabled !== false;
}

export function enabledHubModules(): HubModule[] {
  return HUB_MODULES.filter(isModuleEnabled);
}

export const HUB_MODULES: HubModule[] = [
  {
    id: "hub",
    label: "Home",
    shortLabel: "Home",
    href: "/",
    accent: "#38bdf8",
    description: "Unified overview and quick access to every workspace.",
  },
  {
    id: "github",
    label: "GitHub Scraping",
    shortLabel: "GitHub",
    href: "/github",
    accent: "#22c55e",
    description: "Discover GitHub users, run scrapes, and manage outreach data.",
    subLinks: [
      { href: "/github", label: "Dashboard", description: "Runs, stats, and country coverage" },
      { href: "/scrape/new", label: "New Scrape", description: "Start a targeted scrape run" },
      { href: "/users", label: "Users", description: "Browse and filter the user archive" },
      { href: "/tokens", label: "Tokens", description: "GitHub API token capacity" },
      { href: "/schedules", label: "Schedules", description: "Automated scrape jobs" },
      { href: "/logs", label: "Run logs", description: "History and errors" },
    ],
  },
  {
    id: "docs",
    label: "Google Docs Scraping",
    shortLabel: "Docs",
    href: "/explore/docs",
    accent: "#a78bfa",
    description: "Legacy Google Docs archive (deprecated — use Drive).",
    enabled: false,
    disabledReason: "Hidden — use Google Drive",
    subLinks: [
      { href: "/explore/docs", label: "Documents", description: "Browse indexed documentation" },
      { href: "/explore/docs/crawl/new", label: "New Crawl", description: "Discover and archive Google Docs" },
      { href: "/explore/docs/crawl/runs", label: "Crawl runs", description: "Crawl history and status" },
    ],
  },
  {
    id: "drive",
    label: "Google Drive",
    shortLabel: "Drive",
    href: "/explore/drive",
    accent: "#f59e0b",
    description: "Discover and index public Google Drive folders automatically by content type.",
    subLinks: [
      { href: "/explore/drive", label: "Files", description: "Browse indexed public Drive files" },
      { href: "/explore/drive/crawl/new", label: "New Crawl", description: "Auto-discover folders and index by category" },
      { href: "/explore/drive/crawl/runs", label: "Crawl Runs", description: "History of Drive discovery jobs" },
    ],
  },
];

const GITHUB_PREFIXES = ["/github", "/scrape", "/users", "/tokens", "/schedules", "/logs"];

export function resolveActiveModule(pathname: string): HubModuleId {
  if (pathname === "/") return "hub";
  if (pathname.startsWith("/search")) return "hub";
  if (pathname.startsWith("/explore/drive")) return "drive";
  if (pathname.startsWith("/explore/docs") || pathname.startsWith("/docs")) return "docs";
  if (GITHUB_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    return "github";
  }
  return "hub";
}

export function isNavLinkActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/github") return pathname === "/github";
  if (href === "/explore/drive") {
    if (pathname === "/explore/drive") return true;
    if (pathname.startsWith("/explore/drive/crawl")) return false;
    return pathname.startsWith("/explore/drive/");
  }
  if (href === "/explore/docs") {
    if (pathname === "/explore/docs") return true;
    if (pathname.startsWith("/explore/docs/crawl")) return false;
    return pathname.startsWith("/explore/docs/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
