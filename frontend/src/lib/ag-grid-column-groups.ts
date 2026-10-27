import type { ColDef } from "ag-grid-community";
import { GITHUB_USER_COLUMN_DEFS } from "./ag-grid-columns";

export type ColumnGroupMeta = {
  id: string;
  label: string;
  colIds: string[];
};

function resolveColId(def: ColDef): string {
  return String(def.colId ?? def.field ?? "");
}

/** Grouping for the custom Columns panel (similar to AG Grid tool panel sections). */
export const GITHUB_USER_COLUMN_GROUPS: ColumnGroupMeta[] = [
  {
    id: "identity",
    label: "Identity",
    colIds: ["profileAction", "login", "name", "avatar_url", "id", "github_url"],
  },
  {
    id: "contact",
    label: "Contact & outreach",
    colIds: ["email", "email_source", "all_emails", "outreachAction"],
  },
  {
    id: "profile",
    label: "Profile",
    colIds: [
      "bio",
      "description",
      "location",
      "company",
      "country",
      "blog",
      "twitter_username",
      "social_links",
    ],
  },
  {
    id: "stats",
    label: "GitHub stats",
    colIds: [
      "followers",
      "following",
      "public_repos",
      "public_gists",
      "created_at",
      "updated_at",
      "last_scraped_at",
    ],
  },
];

export function getAllGridColumnIds(): string[] {
  const ids = new Set<string>();
  for (const g of GITHUB_USER_COLUMN_GROUPS) {
    g.colIds.forEach((id) => ids.add(id));
  }
  for (const def of GITHUB_USER_COLUMN_DEFS) {
    const id = resolveColId(def);
    if (id) ids.add(id);
  }
  return [...ids];
}

export function getColumnHeaderLabel(colId: string): string {
  if (colId === "profileAction") return "Profile";
  if (colId === "outreachAction") return "Send";
  const def = GITHUB_USER_COLUMN_DEFS.find((c) => resolveColId(c) === colId);
  return def?.headerName ?? colId;
}
