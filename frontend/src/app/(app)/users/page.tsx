"use client";

import dynamic from "next/dynamic";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import LoadingState from "@/components/LoadingState";
import { apiFetch } from "@/lib/api";
import { getApiBaseUrl } from "@/lib/api-url";
import {
  loadUsersListState,
  markUsersListFocus,
  saveUsersListState,
  type UsersListFilters,
} from "@/lib/users-list-state";
import { GitHubUser } from "@/lib/types";

type CountryOption = { country: string; count: number };

function visibleCountries(countries: CountryOption[]) {
  return countries.filter((item) => !item.country.toLowerCase().includes("korea"));
}

const UsersDataGrid = dynamic(() => import("@/components/UsersDataGrid"), {
  ssr: false,
  loading: () => <UsersGridSkeleton />,
});

type ServerFilters = UsersListFilters;
type DisplayMode = "grid" | "cards";

type UsersResponse = {
  items: GitHubUser[];
  total: number | null;
  has_more?: boolean;
  page_size?: number;
  limited_by_active_scrape?: boolean;
};

const PAGE_SIZE_OPTIONS = [
  { value: 50, label: "50" },
  { value: 100, label: "100" },
  { value: 200, label: "200" },
];

const USERS_PAGE_CACHE_MS = 8000;

function formatNumber(value?: number | null) {
  return Number(value || 0).toLocaleString();
}

function profileHref(user: GitHubUser) {
  return `/users/${encodeURIComponent(user.login)}`;
}

function userInitials(user: GitHubUser) {
  const source = user.name || user.login || "?";
  return (
    source
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "?"
  );
}

function UsersCardView({
  users,
  loading,
  hasMore,
  loadingMore,
  sentinelRef,
  onLoadMore,
}: {
  users: GitHubUser[];
  loading: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  sentinelRef: RefObject<HTMLDivElement>;
  onLoadMore: () => void;
}) {
  if (loading && users.length === 0) {
    return (
      <div className="users-card-grid">
        {Array.from({ length: 9 }).map((_, index) => (
          <div key={index} className="users-card users-card--skeleton">
            <span />
            <strong />
            <p />
            <p />
          </div>
        ))}
      </div>
    );
  }

  if (!users.length) {
    return (
      <div className="users-card-empty">
        <strong>No users match your filters</strong>
        <span>Adjust search, country, or email filters to reveal more profiles.</span>
      </div>
    );
  }

  return (
    <div className={`users-card-grid${loading ? " users-card-grid--loading" : ""}`}>
      {users.map((user) => {
        const email = user.email || user.all_emails?.[0] || "";
        const avatar = user.avatar_url || (user.login ? `https://github.com/${user.login}.png` : "");
        return (
          <article key={user.id || user.login} className="users-card">
            <div className="users-card__photo-wrap">
              <span className="users-card__avatar">
                {avatar ? <img src={avatar} alt="" loading="lazy" /> : userInitials(user)}
              </span>
            </div>
            <div className="users-card__identity">
              <strong>{user.name || user.login}</strong>
              <span>@{user.login}</span>
            </div>
            <div className="users-card__headline">
              <span>{user.country || user.location || "Unknown market"}</span>
              <span>{email ? "Email ready" : "No email"}</span>
            </div>

            <p className="users-card__bio">
              {user.bio || user.description || "No profile description stored yet."}
            </p>

            <div className="users-card__details">
              <div>
                <span>Company</span>
                <strong>{user.company || "Not available"}</strong>
              </div>
              <div>
                <span>Email</span>
                <strong>{email || "Not available"}</strong>
              </div>
            </div>

            <div className="users-card__stats">
              <div>
                <span>Followers</span>
                <strong>{formatNumber(user.followers)}</strong>
              </div>
              <div>
                <span>Repos</span>
                <strong>{formatNumber(user.public_repos)}</strong>
              </div>
              <div>
                <span>Gists</span>
                <strong>{formatNumber(user.public_gists)}</strong>
              </div>
            </div>

            <div className="users-card__actions">
              <Link
                href={profileHref(user)}
                className="btn-primary"
                onClick={() => markUsersListFocus(user.login)}
              >
                View profile
              </Link>
              {email ? (
                <a className="btn-secondary" href={`mailto:${email}`}>
                  Email
                </a>
              ) : (
                <a
                  className="btn-secondary"
                  href={user.github_url || `https://github.com/${user.login}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  GitHub
                </a>
              )}
            </div>
          </article>
        );
      })}
      <div className="users-card-scroll-sentinel" ref={sentinelRef}>
        {loadingMore ? (
          <span><span className="users-grid-loading__spinner" /> Loading more cards</span>
        ) : hasMore ? (
          <button type="button" onClick={onLoadMore}>
            Load more users
          </button>
        ) : (
          <span>All matching users loaded</span>
        )}
      </div>
    </div>
  );
}
function UsersGridSkeleton() {
  return (
    <div className="ag-material-demo users-grid-skeleton" style={{ height: "72vh", minHeight: 480 }}>
      <div className="ag-material-demo__toolbar">
        <div className="ag-material-demo__toolbar-left">
          <span className="skeleton-pill" />
          <span className="skeleton-control" />
        </div>
        <div className="ag-material-demo__toolbar-right">
          <span className="skeleton-line w-28" />
          <span className="skeleton-button" />
          <span className="skeleton-button" />
        </div>
      </div>
      <div className="skeleton-grid">
        {Array.from({ length: 12 }).map((_, row) => (
          <div key={row} className="skeleton-row">
            {Array.from({ length: 7 }).map((__, col) => (
              <span key={col} className="skeleton-cell" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function buildQueryParams(
  page: number,
  pageSize: number,
  sortBy: string,
  sortOrder: string,
  filters: ServerFilters
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

function UsersPageContent() {
  const searchParams = useSearchParams();
  const restoredRef = useRef(false);
  const savedState = useRef(loadUsersListState());
  const [items, setItems] = useState<GitHubUser[]>([]);
  const [total, setTotal] = useState(0);
  const [totalKnown, setTotalKnown] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(savedState.current?.page ?? 1);
  const [pageSize, setPageSize] = useState(savedState.current?.pageSize ?? 50);
  const [sortBy, setSortBy] = useState(savedState.current?.sortBy ?? "last_scraped_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(
    savedState.current?.sortOrder ?? "desc"
  );
  const [filters, setFilters] = useState<ServerFilters>(
    savedState.current?.filters ?? {
      country: searchParams.get("country") || "",
      hasEmail: "yes",
    }
  );
  const [focusLogin, setFocusLogin] = useState(savedState.current?.focusLogin ?? "");
  const [displayMode, setDisplayMode] = useState<DisplayMode>(
    savedState.current?.displayMode ?? "grid"
  );
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [activeScrapeLimited, setActiveScrapeLimited] = useState(false);
  const [cardPage, setCardPage] = useState(1);
  const [loadingMoreCards, setLoadingMoreCards] = useState(false);
  const requestSeqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const cardSentinelRef = useRef<HTMLDivElement>(null);
  const pageCacheRef = useRef(new Map<string, { expires: number; data: UsersResponse }>());
  const urlCountry = searchParams.get("country");

  useEffect(() => {
    if (urlCountry !== null) {
      setFilters((prev) => {
        if (prev.country === urlCountry) return prev;
        return { ...prev, country: urlCountry };
      });
      setPage(1);
    }
  }, [urlCountry]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ countries: CountryOption[] }>("/users/countries")
      .then((data) => {
        if (!cancelled) setCountryOptions(visibleCountries(data.countries || []));
      })
      .catch(() => {
        if (!cancelled) setCountryOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedFilters(filters);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [filters]);

  const loadUsers = useCallback(async () => {
    const requestId = requestSeqRef.current + 1;
    requestSeqRef.current = requestId;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setLoadError("");
    const effectivePage = displayMode === "cards" ? 1 : page;
    const params = buildQueryParams(effectivePage, pageSize, sortBy, sortOrder, debouncedFilters);
    const cacheKey = params.toString();
    const cached = pageCacheRef.current.get(cacheKey);
    if (cached && cached.expires > Date.now()) {
      const data = cached.data;
      const nextItems = data.items || [];
      const effectivePageSize = data.page_size || pageSize;
      setItems(nextItems);
      setHasMore(!!data.has_more);
      setActiveScrapeLimited(!!data.limited_by_active_scrape);
      setTotalKnown(typeof data.total === "number");
      setTotal(
        typeof data.total === "number"
          ? data.total
          : (effectivePage - 1) * effectivePageSize + nextItems.length + (data.has_more ? 1 : 0)
      );
      if (displayMode === "cards") setCardPage(1);
      setLoading(false);
      return;
    }

    try {
      const data = await apiFetch<UsersResponse>(`/users?${params}`, {
        signal: controller.signal,
      });

      if (requestSeqRef.current !== requestId) return;
      pageCacheRef.current.set(cacheKey, {
        expires: Date.now() + USERS_PAGE_CACHE_MS,
        data,
      });
      const nextItems = data.items || [];
      const effectivePageSize = data.page_size || pageSize;
      setItems(nextItems);
      setHasMore(!!data.has_more);
      setActiveScrapeLimited(!!data.limited_by_active_scrape);
      if (effectivePageSize !== pageSize) {
        setPageSize(effectivePageSize);
      }
      setTotalKnown(typeof data.total === "number");
      setTotal(
        typeof data.total === "number"
          ? data.total
          : (effectivePage - 1) * effectivePageSize + nextItems.length + (data.has_more ? 1 : 0)
      );
      if (displayMode === "cards") setCardPage(1);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      if (requestSeqRef.current !== requestId) return;
      setLoadError(e instanceof Error ? e.message : "Failed to load users");
      setItems([]);
      setTotal(0);
      setTotalKnown(false);
      setHasMore(false);
    } finally {
      if (requestSeqRef.current === requestId) setLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedFilters, displayMode]);

  useEffect(() => {
    loadUsers();
    return () => {
      abortRef.current?.abort();
    };
  }, [loadUsers]);

  const loadMoreCards = useCallback(async () => {
    if (displayMode !== "cards" || loading || loadingMoreCards || !hasMore) return;
    const nextPage = cardPage + 1;
    setLoadingMoreCards(true);
    setLoadError("");
    try {
      const params = buildQueryParams(nextPage, pageSize, sortBy, sortOrder, debouncedFilters);
      const data = await apiFetch<UsersResponse>(`/users?${params}`);
      const nextItems = data.items || [];
      setItems((prev) => {
        const merged = new Map<string | number, GitHubUser>();
        for (const item of prev) merged.set(item.id || item.login, item);
        for (const item of nextItems) merged.set(item.id || item.login, item);
        return Array.from(merged.values());
      });
      setCardPage(nextPage);
      setHasMore(!!data.has_more);
      setActiveScrapeLimited(!!data.limited_by_active_scrape);
      setTotalKnown(typeof data.total === "number");
      setTotal((prev) => (typeof data.total === "number" ? data.total : Math.max(prev, nextPage * pageSize + (data.has_more ? 1 : 0))));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load more users");
    } finally {
      setLoadingMoreCards(false);
    }
  }, [cardPage, debouncedFilters, displayMode, hasMore, loading, loadingMoreCards, pageSize, sortBy, sortOrder]);

  useEffect(() => {
    if (displayMode !== "cards") return;
    const node = cardSentinelRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) void loadMoreCards();
      },
      { rootMargin: "640px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [displayMode, loadMoreCards, items.length]);

  useEffect(() => {
    if (displayMode !== "cards") return;

    function maybeLoadMore() {
      const distanceFromBottom =
        document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
      if (distanceFromBottom < 900) void loadMoreCards();
    }

    window.addEventListener("scroll", maybeLoadMore, { passive: true });
    window.addEventListener("resize", maybeLoadMore);
    window.setTimeout(maybeLoadMore, 100);
    return () => {
      window.removeEventListener("scroll", maybeLoadMore);
      window.removeEventListener("resize", maybeLoadMore);
    };
  }, [displayMode, loadMoreCards, items.length]);

  useEffect(() => {
    if (restoredRef.current) return;
    saveUsersListState({
      page: displayMode === "cards" ? cardPage : page,
      pageSize,
      sortBy,
      sortOrder,
      filters: debouncedFilters,
      displayMode,
      focusLogin: focusLogin || undefined,
      pageLogins: items.map((item) => item.login).filter(Boolean),
    });
  }, [page, pageSize, sortBy, sortOrder, debouncedFilters, displayMode, focusLogin, items, cardPage]);

  const handleGridSortChange = useCallback((nextSortBy: string, nextOrder: "asc" | "desc") => {
    setSortBy(nextSortBy);
    setSortOrder(nextOrder);
    setPage(1);
  }, []);

  const handleGridFiltersChange = useCallback((nextFilters: ServerFilters) => {
    setFilters((prev) => {
      const next = {
        ...prev,
        ...nextFilters,
        hasEmail: nextFilters.hasEmail ?? prev.hasEmail ?? "yes",
      };
      if (JSON.stringify(prev) === JSON.stringify(next)) return prev;
      return next;
    });
    setPage(1);
  }, []);

  async function exportData(format: "csv" | "json") {
    const { getAccessToken } = await import("@/lib/auth-session");
    const token = await getAccessToken();
    const url = `${getApiBaseUrl()}/users/export?format=${format}${
      debouncedFilters.country ? `&country=${encodeURIComponent(debouncedFilters.country)}` : ""
    }`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      setLoadError(err.detail || "Export failed");
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `github_users.${format}`;
    a.click();
  }

  const totalPages = totalKnown ? Math.max(1, Math.ceil(total / pageSize)) : null;

  return (
    <div className="users-material-page">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Users</h1>
          <p className="page-subtitle">
            Filter, sort, select, and send outreach directly from the grid.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="users-display-toggle" role="group" aria-label="Display mode">
            <button
              type="button"
              className={displayMode === "grid" ? "is-active" : ""}
              onClick={() => setDisplayMode("grid")}
            >
              Grid
            </button>
            <button
              type="button"
              className={displayMode === "cards" ? "is-active" : ""}
              onClick={() => {
                setDisplayMode("cards");
                setPage(1);
              }}
            >
              Cards
            </button>
          </div>
          <button onClick={() => exportData("csv")} className="btn-secondary">
            Export CSV
          </button>
          <button onClick={() => exportData("json")} className="btn-secondary">
            Export JSON
          </button>
        </div>
      </div>

      {loadError && <p className="alert-error mb-4">{loadError}</p>}
      {activeScrapeLimited && (
        <p className="alert-info mb-4">
          A scrape is running, so the users page is using lightweight reads and smaller pages.
        </p>
      )}

      {displayMode === "grid" ? (
        <UsersDataGrid
          rowData={items}
          loading={loading}
          totalLoaded={items.length}
          totalAvailable={total}
          totalKnown={totalKnown}
          hasMore={hasMore}
          countryOptions={countryOptions}
          selectedCountry={filters.country || ""}
          focusLogin={focusLogin}
          onFocusHandled={() => {
            restoredRef.current = true;
            setFocusLogin("");
          }}
          onCountryChange={(country) => {
            setFilters((prev) => ({ ...prev, country }));
            setPage(1);
            setFocusLogin("");
          }}
          onServerSortChange={handleGridSortChange}
          onServerFiltersChange={handleGridFiltersChange}
        />
      ) : (
        <UsersCardView
          users={items}
          loading={loading}
          hasMore={hasMore}
          loadingMore={loadingMoreCards}
          sentinelRef={cardSentinelRef}
          onLoadMore={() => void loadMoreCards()}
        />
      )}

      {displayMode === "grid" && (items.length > 0 || page > 1) && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              className="btn-secondary"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <button
              className="btn-secondary"
              disabled={loading || (totalKnown ? page >= (totalPages || 1) : !hasMore)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
          <div className="flex items-center gap-3 text-sm text-github-light">
            <span>
              {totalKnown
                ? `Page ${page} of ${totalPages}`
                : `Page ${page}${hasMore ? " - more rows available" : " - last page"}`}
            </span>
            <select
              className="input w-auto py-2"
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} rows
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

export default function UsersPage() {
  return (
    <Suspense
      fallback={
        <LoadingState
          variant="page"
          title="Loading users"
          detail="Preparing filters, saved layout, and the user grid."
        />
      }
    >
      <UsersPageContent />
    </Suspense>
  );
}
