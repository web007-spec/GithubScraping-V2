"use client";

import type { CustomCellRendererProps } from "ag-grid-react";
import { AG_GRID_MATERIAL } from "@/lib/ag-grid-theme";
import { markUsersListFocus } from "@/lib/users-list-state";
import type { GitHubUser } from "@/lib/types";

const linkStyle = { color: AG_GRID_MATERIAL.primary, textDecoration: "none" as const };

function openProfile(login: string) {
  markUsersListFocus(login);
}

export function LoginLinkRenderer(props: CustomCellRendererProps<GitHubUser>) {
  const login = props.value as string;
  if (!login) return null;
  return (
    <a
      href={`/users/${encodeURIComponent(login)}`}
      style={linkStyle}
      onClick={() => openProfile(login)}
    >
      {login}
    </a>
  );
}

export function ProfileActionRenderer(props: CustomCellRendererProps<GitHubUser>) {
  const login = props.data?.login;
  if (!login) return <span className="text-github-light">-</span>;
  return (
    <a
      href={`/users/${encodeURIComponent(login)}`}
      className="ag-profile-open"
      title={`Open ${login} profile`}
      onClick={(e) => {
        e.stopPropagation();
        openProfile(login);
      }}
    >
      Profile
    </a>
  );
}

export function UrlLinkRenderer(props: CustomCellRendererProps<GitHubUser>) {
  const raw = props.value as string;
  if (!raw) return <span className="text-github-light">-</span>;
  const href = raw.startsWith("http") ? raw : `https://${raw}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={{
        ...linkStyle,
        display: "block",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {raw}
    </a>
  );
}

export function TwitterRenderer(props: CustomCellRendererProps<GitHubUser>) {
  const raw = props.data?.twitter_username;
  if (!raw) return <span className="text-github-light">-</span>;
  const handle = raw.replace(/^@/, "");
  return (
    <a
      href={`https://twitter.com/${handle}`}
      target="_blank"
      rel="noreferrer"
      style={linkStyle}
    >
      @{handle}
    </a>
  );
}

export function AvatarRenderer(props: CustomCellRendererProps<GitHubUser>) {
  const url = props.data?.avatar_url;
  if (!url) return <span className="text-github-light">-</span>;
  return <img src={url} alt="" className="h-8 w-8 rounded-full" />;
}

function buildComposeUrl(email: string, subject: string, body: string): string {
  const domain = email.split("@")[1]?.toLowerCase() ?? "";
  if (domain === "gmail.com" || domain === "googlemail.com") {
    const params = new URLSearchParams({ view: "cm", fs: "1", to: email });
    if (subject) params.set("su", subject);
    if (body) params.set("body", body);
    return `https://mail.google.com/mail/?${params.toString()}`;
  }
  if (
    /^(outlook|hotmail|live)\./i.test(domain) ||
    ["outlook.com", "hotmail.com", "live.com"].includes(domain)
  ) {
    const params = new URLSearchParams({ to: email });
    if (subject) params.set("subject", subject);
    if (body) params.set("body", body);
    return `https://outlook.live.com/mail/0/deeplink/compose?${params.toString()}`;
  }
  const params = new URLSearchParams();
  if (subject) params.set("subject", subject);
  if (body) params.set("body", body);
  const q = params.toString();
  return `mailto:${email}${q ? `?${q}` : ""}`;
}

export function OutreachActionRenderer(props: CustomCellRendererProps<GitHubUser>) {
  const email = props.data?.email?.trim();
  if (!email) {
    return <span className="text-github-light">-</span>;
  }
  const who = props.data?.name || props.data?.login || "there";
  const subject = `Following up - ${who}`;
  const body = `Hi ${who},\n\nI hope you are doing well.\n\nBest regards`;
  const href = buildComposeUrl(email, subject, body);
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="ag-outreach-send"
      title={`Compose email to ${email}`}
      onClick={(e) => e.stopPropagation()}
    >
      Send
    </a>
  );
}

export const gridCellRenderers = {
  profileActionRenderer: ProfileActionRenderer,
  loginLinkRenderer: LoginLinkRenderer,
  urlLinkRenderer: UrlLinkRenderer,
  twitterRenderer: TwitterRenderer,
  avatarRenderer: AvatarRenderer,
  outreachActionRenderer: OutreachActionRenderer,
};
