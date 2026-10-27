export type UsersListFilters = {
  search?: string;
  country?: string;
  followersMin?: string;
  followersMax?: string;
  createdAfter?: string;
  createdBefore?: string;
  hasEmail?: "yes" | "no" | "";
  hasBio?: "yes" | "no" | "";
};

export type UsersListState = {
  page: number;
  pageSize: number;
  sortBy: string;
  sortOrder: "asc" | "desc";
  filters: UsersListFilters;
  displayMode?: "grid" | "cards";
  focusLogin?: string;
  scrollTop?: number;
  pageLogins?: string[];
};

const STORAGE_KEY = "githubUsersListState.v1";

export function saveUsersListState(state: UsersListState) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota errors */
  }
}

export function loadUsersListState(): UsersListState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as UsersListState;
  } catch {
    return null;
  }
}

export function markUsersListFocus(login: string) {
  const current = loadUsersListState();
  saveUsersListState({
    page: current?.page ?? 1,
    pageSize: current?.pageSize ?? 50,
    sortBy: current?.sortBy ?? "last_scraped_at",
    sortOrder: current?.sortOrder ?? "desc",
    filters: current?.filters ?? { hasEmail: "yes" },
    displayMode: current?.displayMode,
    focusLogin: login,
    pageLogins: current?.pageLogins,
  });
}
