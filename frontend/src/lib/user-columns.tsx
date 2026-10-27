import type { ReactNode } from "react";
import { GitHubUser } from "./types";

export type UserColumnDef = {
  key: string;
  label: string;
  render: (u: GitHubUser) => ReactNode;
  className?: string;
};

function cell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export const USER_TABLE_COLUMNS: UserColumnDef[] = [
  {
    key: "login",
    label: "Login",
    className: "font-medium whitespace-nowrap",
    render: (u) =>
      u.github_url ? (
        <a href={u.github_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
          {u.login}
        </a>
      ) : (
        u.login
      ),
  },
  { key: "name", label: "Name", render: (u) => cell(u.name) },
  { key: "email", label: "Email", render: (u) => cell(u.email) },
  {
    key: "email_source",
    label: "Email source",
    render: (u) => cell(u.email_source),
  },
  {
    key: "all_emails",
    label: "All emails",
    className: "max-w-[200px] break-words text-xs",
    render: (u) =>
      u.all_emails?.length ? u.all_emails.join(", ") : "—",
  },
  {
    key: "bio",
    label: "Bio",
    className: "max-w-[240px] whitespace-pre-wrap break-words text-xs",
    render: (u) => cell(u.bio),
  },
  {
    key: "description",
    label: "Description",
    className: "max-w-[280px] whitespace-pre-wrap break-words text-xs",
    render: (u) => cell(u.description),
  },
  { key: "location", label: "Location", render: (u) => cell(u.location) },
  { key: "company", label: "Company", render: (u) => cell(u.company) },
  { key: "country", label: "Country", render: (u) => cell(u.country) },
  {
    key: "blog",
    label: "Blog",
    render: (u) =>
      u.blog ? (
        <a
          href={u.blog.startsWith("http") ? u.blog : `https://${u.blog}`}
          target="_blank"
          rel="noreferrer"
          className="text-accent"
        >
          {u.blog}
        </a>
      ) : (
        "—"
      ),
  },
  {
    key: "twitter_username",
    label: "Twitter",
    render: (u) =>
      u.twitter_username ? (
        <a
          href={`https://twitter.com/${u.twitter_username.replace(/^@/, "")}`}
          target="_blank"
          rel="noreferrer"
          className="text-accent"
        >
          @{u.twitter_username.replace(/^@/, "")}
        </a>
      ) : (
        "—"
      ),
  },
  {
    key: "social_links",
    label: "Social links",
    className: "max-w-[180px] text-xs",
    render: (u) =>
      u.social_links?.length ? (
        <ul className="list-disc pl-4">
          {u.social_links.map((s, i) => (
            <li key={i}>
              {s.url ? (
                <a href={s.url} target="_blank" rel="noreferrer" className="text-accent">
                  {s.provider || s.url}
                </a>
              ) : (
                s.provider || "—"
              )}
            </li>
          ))}
        </ul>
      ) : (
        "—"
      ),
  },
  { key: "followers", label: "Followers", render: (u) => cell(u.followers) },
  { key: "following", label: "Following", render: (u) => cell(u.following) },
  { key: "public_repos", label: "Repos", render: (u) => cell(u.public_repos) },
  { key: "public_gists", label: "Gists", render: (u) => cell(u.public_gists) },
  {
    key: "created_at",
    label: "GitHub joined",
    className: "whitespace-nowrap text-xs",
    render: (u) => formatDate(u.created_at),
  },
  {
    key: "updated_at",
    label: "GitHub updated",
    className: "whitespace-nowrap text-xs",
    render: (u) => formatDate(u.updated_at),
  },
  {
    key: "last_scraped_at",
    label: "Last scraped",
    className: "whitespace-nowrap text-xs",
    render: (u) => formatDate(u.last_scraped_at),
  },
  {
    key: "github_url",
    label: "Profile URL",
    className: "max-w-[160px] truncate text-xs",
    render: (u) =>
      u.github_url ? (
        <a href={u.github_url} target="_blank" rel="noreferrer" className="text-accent">
          {u.github_url}
        </a>
      ) : (
        "—"
      ),
  },
  {
    key: "avatar_url",
    label: "Avatar",
    render: (u) =>
      u.avatar_url ? (
        <img src={u.avatar_url} alt="" className="h-8 w-8 rounded-full" />
      ) : (
        "—"
      ),
  },
  { key: "id", label: "GitHub ID", render: (u) => cell(u.id) },
];
