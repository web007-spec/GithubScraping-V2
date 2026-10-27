"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import LoadingState from "@/components/LoadingState";
import { apiFetch } from "@/lib/api";
import { loadUsersListState, markUsersListFocus, type UsersListFilters } from "@/lib/users-list-state";
import type { GitHubUser, SocialLink } from "@/lib/types";

type ProfileResponse = {
  user: GitHubUser;
};

type UsersResponse = {
  items: GitHubUser[];
  has_more?: boolean;
  page_size?: number;
};

type NeighborState = {
  prevLogin?: string;
  nextLogin?: string;
  loading: boolean;
};

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function displayText(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "Not available";
  return String(value);
}

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return date.toLocaleString();
}

function formatShortDate(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function normalizeUrl(raw?: string | null) {
  if (!raw) return "";
  const trimmed = raw.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

function twitterUrl(username?: string | null) {
  if (!username) return "";
  const clean = username.trim().replace(/^@/, "");
  return clean ? `https://x.com/${encodeURIComponent(clean)}` : "";
}

function initials(user: GitHubUser) {
  const source = user.name || user.login || "?";
  return source
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function uniqueEmails(user: GitHubUser) {
  return Array.from(
    new Set([user.email, ...(user.all_emails || [])].filter((email): email is string => !!email))
  );
}

function profileLinks(user: GitHubUser) {
  const links: { label: string; href: string; detail?: string }[] = [];
  const githubUrl = normalizeUrl(user.github_url || (user.login ? `github.com/${user.login}` : ""));
  const blogUrl = normalizeUrl(user.blog);
  const xUrl = twitterUrl(user.twitter_username);

  if (githubUrl) links.push({ label: "GitHub", href: githubUrl, detail: user.login });
  if (blogUrl) links.push({ label: "Website", href: blogUrl, detail: user.blog || undefined });
  if (xUrl) links.push({ label: "X", href: xUrl, detail: `@${user.twitter_username?.replace(/^@/, "")}` });

  (user.social_links || []).forEach((link: SocialLink) => {
    const href = normalizeUrl(link.url);
    if (!href) return;
    links.push({
      label: link.provider || link.display_name || "Social",
      href,
      detail: link.display_name || link.url,
    });
  });

  return links;
}

function profileCompleteness(user: GitHubUser, emailCount: number, linkCount: number) {
  const checks = [
    !!user.name,
    !!user.company,
    !!user.location || !!user.country,
    !!(user.bio || user.description),
    emailCount > 0,
    linkCount > 0,
    Number(user.followers || 0) > 0,
    !!user.last_scraped_at,
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}

function reachLabel(user: GitHubUser) {
  const followers = Number(user.followers || 0);
  const repos = Number(user.public_repos || 0);
  if (followers >= 1000 || repos >= 80) return "High reach";
  if (followers >= 250 || repos >= 30) return "Active builder";
  if (followers >= 50 || repos >= 10) return "Visible developer";
  return "Emerging profile";
}

function buildSmartInsights(user: GitHubUser, emailCount: number, linkCount: number, score: number) {
  const market = [user.location, user.country].filter(Boolean).join(", ");
  const insights = [
    `${reachLabel(user)} with ${formatNumber(user.followers)} followers and ${formatNumber(user.public_repos)} public repositories.`,
    emailCount > 0
      ? `${emailCount} email${emailCount === 1 ? "" : "s"} available for direct outreach.`
      : "No stored email yet, so review links before outreach.",
    market ? `Market signal: ${market}.` : "Market signal is incomplete.",
    linkCount > 0
      ? `${linkCount} profile link${linkCount === 1 ? "" : "s"} available for verification.`
      : "No external profile links are stored.",
  ];

  if (score >= 75) insights.unshift("This is a strong profile for review and outreach.");
  if (score < 45) insights.unshift("This profile needs more enrichment before confident outreach.");
  return insights;
}

function buildOutreachDraft(user: GitHubUser, primaryEmail: string) {
  const name = user.name || user.login || "there";
  const market = user.country || user.location;
  const company = user.company ? ` I noticed your profile references ${user.company}.` : "";
  const lines = [
    `Hi ${name},`,
    "",
    `I found your GitHub profile while reviewing developers${market ? ` in ${market}` : ""}.${company}`,
    "Your public work and GitHub activity stood out, and I wanted to reach out with a relevant opportunity.",
    "",
    "Would you be open to a quick conversation?",
  ];
  if (primaryEmail) {
    lines.push("", `Preferred email: ${primaryEmail}`);
  }
  lines.push("", "Best regards");
  return lines.join("\n");
}

function primitiveProfileData(profileData?: Record<string, unknown>) {
  if (!profileData) return [];
  return Object.entries(profileData)
    .filter(([, value]) => {
      const kind = typeof value;
      return value !== null && ["string", "number", "boolean"].includes(kind);
    })
    .slice(0, 8)
    .map(([key, value]) => ({ key, value: String(value) }));
}

function buildUsersQuery(
  page: number,
  pageSize: number,
  sortBy: string,
  sortOrder: string,
  filters: UsersListFilters
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  });
  if (filters.search) params.set("search", filters.search);
  if (filters.country) params.set("country", filters.country);
  if (filters.followersMin) params.set("followers_min", filters.followersMin);
  if (filters.followersMax) params.set("followers_max", filters.followersMax);
  if (filters.createdAfter) params.set("created_after", filters.createdAfter);
  if (filters.createdBefore) params.set("created_before", filters.createdBefore);
  if (filters.hasEmail === "yes") params.set("has_email", "true");
  if (filters.hasEmail === "no") params.set("has_email", "false");
  if (filters.hasBio === "yes") params.set("has_bio", "true");
  if (filters.hasBio === "no") params.set("has_bio", "false");
  return params;
}

export default function UserProfilePage() {
  const router = useRouter();
  const params = useParams<{ login?: string | string[] }>();
  const rawLogin = Array.isArray(params.login) ? params.login[0] : params.login || "";
  const login = safeDecode(rawLogin);
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  const [neighbors, setNeighbors] = useState<NeighborState>({ loading: true });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    apiFetch<ProfileResponse>(`/users/profile/${encodeURIComponent(login)}`)
      .then((data) => {
        if (!cancelled) setUser(data.user);
      })
      .catch((e) => {
        if (!cancelled) {
          setUser(null);
          setError(e instanceof Error ? e.message : "Profile could not be loaded");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [login]);

  const emails = useMemo(() => (user ? uniqueEmails(user) : []), [user]);
  const links = useMemo(() => (user ? profileLinks(user) : []), [user]);
  const profileData = useMemo(() => (user ? primitiveProfileData(user.profile_data) : []), [user]);

  useEffect(() => {
    if (login) markUsersListFocus(login);
  }, [login]);

  useEffect(() => {
    let cancelled = false;

    async function resolveNeighbors() {
      setNeighbors({ loading: true });
      const saved = loadUsersListState();
      if (!saved) {
        if (!cancelled) setNeighbors({ loading: false });
        return;
      }
      const savedState = saved;

      const pageLogins = savedState.pageLogins || [];
      let index = pageLogins.findIndex((item) => item.toLowerCase() === login.toLowerCase());
      let currentPageLogins = pageLogins;
      const filters = savedState.filters || { hasEmail: "yes" };

      async function fetchPage(page: number) {
        const params = buildUsersQuery(
          page,
          savedState.pageSize || 50,
          savedState.sortBy || "last_scraped_at",
          savedState.sortOrder || "desc",
          filters
        );
        const data = await apiFetch<UsersResponse>(`/users?${params}`);
        return {
          logins: (data.items || []).map((item) => item.login).filter(Boolean),
          hasMore: !!data.has_more,
        };
      }

      try {
        if (index === -1) {
          const current = await fetchPage(savedState.page || 1);
          currentPageLogins = current.logins;
          index = currentPageLogins.findIndex((item) => item.toLowerCase() === login.toLowerCase());
        }

        let prevLogin = index > 0 ? currentPageLogins[index - 1] : undefined;
        let nextLogin =
          index >= 0 && index < currentPageLogins.length - 1 ? currentPageLogins[index + 1] : undefined;

        if (!prevLogin && index === 0 && (savedState.page || 1) > 1) {
          const prevPage = await fetchPage((savedState.page || 1) - 1);
          prevLogin = prevPage.logins[prevPage.logins.length - 1];
        }

        if (!nextLogin && index === currentPageLogins.length - 1) {
          const nextPage = await fetchPage((savedState.page || 1) + 1);
          nextLogin = nextPage.logins[0];
        }

        if (!cancelled) setNeighbors({ prevLogin, nextLogin, loading: false });
      } catch {
        if (!cancelled) setNeighbors({ loading: false });
      }
    }

    if (login) void resolveNeighbors();
    return () => {
      cancelled = true;
    };
  }, [login]);

  async function copyValue(label: string, value?: string) {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      window.setTimeout(() => setCopied(""), 1400);
    } catch {
      setCopied("");
    }
  }

  function openNeighbor(nextLogin?: string) {
    if (!nextLogin) return;
    markUsersListFocus(nextLogin);
    router.push(`/users/${encodeURIComponent(nextLogin)}`);
  }

  if (loading) {
    return (
      <LoadingState
        variant="page"
        title="Loading profile"
        detail="Preparing contact, activity, and enrichment details."
      />
    );
  }

  if (error || !user) {
    return (
      <div className="profile-page">
        <section className="profile-empty-state">
          <span>Profile unavailable</span>
          <h1>{login || "User profile"}</h1>
          <p>{error || "Profile was not found."}</p>
          <Link href="/users" className="btn-secondary" onClick={() => markUsersListFocus(login)}>
            Back to users
          </Link>
        </section>
      </div>
    );
  }

  const avatarUrl = user.avatar_url || (user.login ? `https://github.com/${user.login}.png` : "");
  const primaryEmail = emails[0] || "";
  const title = user.name || user.login;
  const githubHref = normalizeUrl(user.github_url || (user.login ? `github.com/${user.login}` : ""));
  const score = profileCompleteness(user, emails.length, links.length);
  const qualityTone = score >= 75 ? "Strong" : score >= 45 ? "Usable" : "Light";
  const insights = buildSmartInsights(user, emails.length, links.length, score);
  const outreachDraft = buildOutreachDraft(user, primaryEmail);
  const smartTags = [
    reachLabel(user),
    primaryEmail ? "Email ready" : "Needs email",
    user.country || user.location || "Market unknown",
  ];
  const heroFacts = [
    { label: "Primary email", value: primaryEmail || "Not available" },
    { label: "Company", value: displayText(user.company) },
    { label: "Market", value: user.country || user.location || "Not available" },
    { label: "Joined GitHub", value: formatShortDate(user.created_at) },
  ];
  const subtitleParts = [
    user.login ? `@${user.login}` : "",
    user.country,
    user.location,
  ].filter(Boolean);
  const nextAction = primaryEmail
    ? "Send a direct outreach email"
    : links.length > 0
      ? "Verify profile links for contact details"
      : "Enrich this profile before outreach";

  return (
    <div className="profile-page space-y-6">
      <div className="profile-breadcrumb">
        <Link href="/users">Users</Link>
        <span>/</span>
        <strong>{user.login}</strong>
      </div>

      <section className="profile-hero">
        <div className="profile-avatar" aria-hidden="true">
          {avatarUrl ? (
            <img src={avatarUrl} alt="" />
          ) : (
            <span className="profile-avatar__fallback">{initials(user)}</span>
          )}
        </div>

        <div className="profile-hero__main">
          <span className="profile-eyebrow">Developer profile</span>
          <h1 className="profile-title">{title}</h1>
          <p className="profile-subtitle">{subtitleParts.join(" / ") || "GitHub user"}</p>
          <div className="profile-chip-row">
            <span className="profile-chip">{displayText(user.company)}</span>
            <span className="profile-chip">{displayText(user.email_source || "Email status unknown")}</span>
            <span className="profile-chip">Scraped {formatDate(user.last_scraped_at)}</span>
          </div>
          <div className="profile-hero-facts">
            {heroFacts.map((fact, index) => (
              <div key={`${fact.label}-${index}`}>
                <span>{fact.label}</span>
                <strong>{fact.value}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="profile-actions">
          <button
            type="button"
            className="btn-secondary"
            disabled={neighbors.loading || !neighbors.prevLogin}
            onClick={() => openNeighbor(neighbors.prevLogin)}
          >
            Previous user
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={neighbors.loading || !neighbors.nextLogin}
            onClick={() => openNeighbor(neighbors.nextLogin)}
          >
            Next user
          </button>
          <Link href="/users" className="btn-secondary" onClick={() => markUsersListFocus(login)}>
            Back to users
          </Link>
          {user.country && (
            <Link href={`/users?country=${encodeURIComponent(user.country)}`} className="btn-secondary">
              Country list
            </Link>
          )}
          {primaryEmail && (
            <a
              className="btn-primary"
              href={`mailto:${primaryEmail}?subject=${encodeURIComponent(`Hello ${title}`)}`}
            >
              Email
            </a>
          )}
          {githubHref && (
            <a className="btn-secondary" href={githubHref} target="_blank" rel="noreferrer">
              Open GitHub
            </a>
          )}
        </div>
      </section>

      <section className="profile-overview-band" aria-label="Profile overview">
        <div>
          <span>Profile status</span>
          <strong>{qualityTone}</strong>
          <p>{score}/100 profile completeness</p>
        </div>
        <div>
          <span>Contact readiness</span>
          <strong>{primaryEmail ? "Ready" : "Incomplete"}</strong>
          <p>{emails.length ? `${emails.length} saved email${emails.length === 1 ? "" : "s"}` : "No email saved yet"}</p>
        </div>
        <div>
          <span>Next action</span>
          <strong>{nextAction}</strong>
          <p>{reachLabel(user)} in {user.country || user.location || "an unknown market"}</p>
        </div>
      </section>

      <section className="profile-command-bar" aria-label="Profile actions">
        <button type="button" className="profile-command" onClick={() => copyValue("Login", user.login)}>
          <span>Copy login</span>
          <strong>{copied === "Login" ? "Copied" : user.login}</strong>
        </button>
        <button
          type="button"
          className="profile-command"
          disabled={!primaryEmail}
          onClick={() => copyValue("Email", primaryEmail)}
        >
          <span>Copy email</span>
          <strong>{copied === "Email" ? "Copied" : primaryEmail || "No email"}</strong>
        </button>
        <button
          type="button"
          className="profile-command"
          disabled={!user.location && !user.country}
          onClick={() => copyValue("Location", [user.location, user.country].filter(Boolean).join(", "))}
        >
          <span>Copy market</span>
          <strong>{copied === "Location" ? "Copied" : displayText(user.country || user.location)}</strong>
        </button>
      </section>

      {copied && (
        <p className="profile-copy-status" aria-live="polite">
          {copied} copied to clipboard.
        </p>
      )}

      <section className="profile-smart-grid" aria-label="Smart profile summary">
        <article className="profile-card profile-card--smart">
          <div className="profile-section-head">
            <span>Smart Summary</span>
            <strong>{qualityTone} match</strong>
          </div>
          <div className="profile-smart-tags">
            {smartTags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
          <ul className="profile-insight-list">
            {insights.map((insight, index) => (
              <li key={`${insight}-${index}`}>{insight}</li>
            ))}
          </ul>
        </article>

        <article className="profile-card profile-card--smart">
          <div className="profile-section-head">
            <span>Outreach Draft</span>
            <strong>{primaryEmail ? "Ready" : "Review"}</strong>
          </div>
          <pre className="profile-outreach">{outreachDraft}</pre>
          <div className="profile-outreach-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => copyValue("Outreach", outreachDraft)}
            >
              {copied === "Outreach" ? "Copied" : "Copy draft"}
            </button>
            {primaryEmail && (
              <a
                className="btn-secondary"
                href={`mailto:${primaryEmail}?subject=${encodeURIComponent(`Hello ${title}`)}&body=${encodeURIComponent(outreachDraft)}`}
              >
                Open email
              </a>
            )}
          </div>
        </article>
      </section>

      <section className="profile-stat-grid" aria-label="GitHub activity">
        <div className="profile-stat">
          <span>Followers</span>
          <strong>{formatNumber(user.followers)}</strong>
        </div>
        <div className="profile-stat">
          <span>Following</span>
          <strong>{formatNumber(user.following)}</strong>
        </div>
        <div className="profile-stat">
          <span>Repositories</span>
          <strong>{formatNumber(user.public_repos)}</strong>
        </div>
        <div className="profile-stat">
          <span>Gists</span>
          <strong>{formatNumber(user.public_gists)}</strong>
        </div>
      </section>

      <section className="profile-grid">
        <article className="profile-card profile-card--wide">
          <div className="profile-section-head">
            <span>About</span>
            <strong>{displayText(user.country)}</strong>
          </div>
          <p className="profile-bio">
            {user.bio || user.description || "No public bio or stored description is available."}
          </p>
        </article>

        <article className="profile-card">
          <div className="profile-section-head">
            <span>Lead Quality</span>
            <strong>{qualityTone}</strong>
          </div>
          <div className="profile-score">
            <div className="profile-score__ring" style={{ "--score": `${score}%` } as CSSProperties}>
              <strong>{score}</strong>
              <span>/100</span>
            </div>
            <div>
              <p>
                {primaryEmail
                  ? "This profile is ready for direct outreach."
                  : "This profile needs an email before direct outreach."}
              </p>
              <div className="profile-score__meter">
                <span style={{ width: `${score}%` }} />
              </div>
            </div>
          </div>
        </article>

        <article className="profile-card">
          <div className="profile-section-head">
            <span>Contact</span>
            <strong>{emails.length} email{emails.length === 1 ? "" : "s"}</strong>
          </div>
          {emails.length > 0 ? (
            <div className="profile-link-list">
              {emails.map((email) => (
                <a key={email} href={`mailto:${email}`}>
                  <span>{email}</span>
                  <small>Send email</small>
                </a>
              ))}
            </div>
          ) : (
            <p className="profile-empty">No email is stored for this user.</p>
          )}
        </article>

        <article className="profile-card">
          <div className="profile-section-head">
            <span>Profile Links</span>
            <strong>{links.length}</strong>
          </div>
          {links.length > 0 ? (
            <div className="profile-link-list">
              {links.map((link) => (
                <a key={`${link.label}-${link.href}`} href={link.href} target="_blank" rel="noreferrer">
                  <span>{link.label}</span>
                  <small>{link.detail || link.href}</small>
                </a>
              ))}
            </div>
          ) : (
            <p className="profile-empty">No external links are stored.</p>
          )}
        </article>

        <article className="profile-card">
          <div className="profile-section-head">
            <span>Details</span>
            <strong>ID {user.id}</strong>
          </div>
          <dl className="profile-list">
            <div className="profile-list-row">
              <dt>Login</dt>
              <dd>{displayText(user.login)}</dd>
            </div>
            <div className="profile-list-row">
              <dt>Name</dt>
              <dd>{displayText(user.name)}</dd>
            </div>
            <div className="profile-list-row">
              <dt>Company</dt>
              <dd>{displayText(user.company)}</dd>
            </div>
            <div className="profile-list-row">
              <dt>Location</dt>
              <dd>{displayText(user.location)}</dd>
            </div>
          </dl>
        </article>

        <article className="profile-card">
          <div className="profile-section-head">
            <span>Timeline</span>
            <strong>Activity</strong>
          </div>
          <dl className="profile-list">
            <div className="profile-list-row">
              <dt>Created</dt>
              <dd>{formatDate(user.created_at)}</dd>
            </div>
            <div className="profile-list-row">
              <dt>Updated</dt>
              <dd>{formatDate(user.updated_at)}</dd>
            </div>
            <div className="profile-list-row">
              <dt>Last scraped</dt>
              <dd>{formatDate(user.last_scraped_at)}</dd>
            </div>
          </dl>
        </article>

        <article className="profile-card profile-card--wide">
          <div className="profile-section-head">
            <span>Stored Enrichment</span>
            <strong>{profileData.length ? `${profileData.length} fields` : "Empty"}</strong>
          </div>
          {profileData.length > 0 ? (
            <dl className="profile-field-grid">
              {profileData.map((item) => (
                <div key={item.key}>
                  <dt>{item.key.replace(/_/g, " ")}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="profile-empty">No compact enrichment fields are stored for this profile.</p>
          )}
        </article>
      </section>
    </div>
  );
}
