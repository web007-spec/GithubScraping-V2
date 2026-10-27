import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import type { GitHubUser } from "./types";

function formatDate(value: unknown): string {
  if (!value || typeof value !== "string") return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function textOrEmpty(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  return String(value);
}

const dateCol = (field: keyof GitHubUser, headerName: string, width = 168): ColDef<GitHubUser> => ({
  field,
  headerName,
  width,
  filter: "agDateColumnFilter",
  valueFormatter: (p: ValueFormatterParams<GitHubUser>) => formatDate(p.value),
});

const numCol = (field: keyof GitHubUser, headerName: string, width = 110): ColDef<GitHubUser> => ({
  field,
  headerName,
  width,
  filter: "agNumberColumnFilter",
  type: "numericColumn",
});

export const GITHUB_USER_COLUMN_DEFS: ColDef<GitHubUser>[] = [
  {
    colId: "profileAction",
    headerName: "Profile",
    pinned: "left",
    width: 96,
    sortable: false,
    filter: false,
    floatingFilter: false,
    cellRenderer: "profileActionRenderer",
    suppressHeaderMenuButton: true,
  },
  {
    colId: "outreachAction",
    headerName: "Send",
    pinned: "left",
    width: 88,
    sortable: false,
    filter: false,
    floatingFilter: false,
    cellRenderer: "outreachActionRenderer",
    suppressHeaderMenuButton: true,
  },
  {
    field: "login",
    headerName: "Login",
    pinned: "left",
    width: 140,
    cellClass: "font-medium",
    cellRenderer: "loginLinkRenderer",
  },
  { field: "name", headerName: "Name", width: 140 },
  { field: "email", headerName: "Email", width: 200 },
  { field: "email_source", headerName: "Email source", width: 120 },
  {
    field: "all_emails",
    headerName: "All emails",
    width: 200,
    hide: true,
    valueGetter: (p) => p.data?.all_emails?.join(", ") ?? "",
    tooltipField: "all_emails",
  },
  {
    field: "bio",
    headerName: "Bio",
    width: 220,
    flex: 1,
    minWidth: 160,
    hide: true,
    tooltipField: "bio",
  },
  {
    field: "description",
    headerName: "Description",
    width: 240,
    flex: 1,
    minWidth: 160,
    hide: true,
    tooltipField: "description",
  },
  { field: "location", headerName: "Location", width: 140 },
  { field: "company", headerName: "Company", width: 140 },
  { field: "country", headerName: "Country", width: 110 },
  {
    field: "blog",
    headerName: "Blog",
    width: 160,
    cellRenderer: "urlLinkRenderer",
  },
  {
    field: "twitter_username",
    headerName: "Twitter",
    width: 130,
    cellRenderer: "twitterRenderer",
  },
  {
    field: "social_links",
    headerName: "Social links",
    width: 180,
    hide: true,
    valueGetter: (p) =>
      p.data?.social_links
        ?.map((s) => s.url || s.provider || "")
        .filter(Boolean)
        .join(" / ") ?? "",
  },
  numCol("followers", "Followers"),
  numCol("following", "Following"),
  numCol("public_repos", "Repos"),
  numCol("public_gists", "Gists"),
  dateCol("created_at", "GitHub joined"),
  dateCol("updated_at", "GitHub updated"),
  dateCol("last_scraped_at", "Last scraped"),
  {
    field: "github_url",
    headerName: "Profile URL",
    width: 180,
    cellRenderer: "urlLinkRenderer",
  },
  {
    field: "avatar_url",
    headerName: "Avatar",
    width: 72,
    hide: true,
    sortable: false,
    filter: false,
    cellRenderer: "avatarRenderer",
  },
  { field: "id", headerName: "GitHub ID", width: 110, filter: "agNumberColumnFilter" },
];

export const GITHUB_USER_DEFAULT_COL_DEF: ColDef<GitHubUser> = {
  sortable: true,
  resizable: true,
  filter: true,
  floatingFilter: true,
  minWidth: 90,
  suppressHeaderMenuButton: false,
  headerClass: "ag-material-col-header",
  valueFormatter: (p) => textOrEmpty(p.value),
  filterParams: {
    buttons: ["apply", "reset"],
    closeOnApply: true,
  },
};
