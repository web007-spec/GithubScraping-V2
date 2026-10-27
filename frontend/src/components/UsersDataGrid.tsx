"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  type ColumnVisibleEvent,
  type GridApi,
  type FilterChangedEvent,
  type GridReadyEvent,
  type SelectionChangedEvent,
  type SortChangedEvent,
} from "ag-grid-community";
import { AgGridProvider } from "ag-grid-react";
import { githubUsersGridTheme } from "@/lib/ag-grid-theme";
import {
  GITHUB_USER_COLUMN_DEFS,
  GITHUB_USER_DEFAULT_COL_DEF,
} from "@/lib/ag-grid-columns";
import { getAllGridColumnIds } from "@/lib/ag-grid-column-groups";
import { buildCountrySummaryRows } from "@/lib/ag-grid-summary";
import { gridCellRenderers } from "@/components/ag-grid/cell-renderers";
import ColumnsToolPanel from "@/components/ag-grid/ColumnsToolPanel";
import type { GitHubUser } from "@/lib/types";
import type { ColDef } from "ag-grid-community";

const modules = [AllCommunityModule];
const COLUMN_STATE_KEY = "githubUsersGrid.columnState.v1";
const DEFAULT_VISIBLE = new Set(getAllGridColumnIds());

type UsersDataGridProps = {
  rowData: GitHubUser[];
  loading?: boolean;
  totalLoaded?: number;
  totalAvailable?: number;
  totalKnown?: boolean;
  hasMore?: boolean;
  countryOptions?: { country: string; count: number }[];
  selectedCountry?: string;
  onCountryChange?: (country: string) => void;
  onServerSortChange?: (sortBy: string, sortOrder: "asc" | "desc") => void;
  onServerFiltersChange?: (filters: {
    search?: string;
    country?: string;
    followersMin?: string;
    followersMax?: string;
    createdAfter?: string;
    createdBefore?: string;
    hasEmail?: "yes" | "no" | "";
    hasBio?: "yes" | "no" | "";
  }) => void;
  focusLogin?: string;
  onFocusHandled?: () => void;
};

export default function UsersDataGrid({
  rowData,
  loading = false,
  totalLoaded = 0,
  totalAvailable = 0,
  totalKnown = false,
  hasMore = false,
  countryOptions = [],
  selectedCountry = "",
  onCountryChange,
  onServerSortChange,
  onServerFiltersChange,
  focusLogin = "",
  onFocusHandled,
}: UsersDataGridProps) {
  const apiRef = useRef<GridApi<GitHubUser> | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [summaryByCountry, setSummaryByCountry] = useState(false);
  const [selectedCount, setSelectedCount] = useState(0);
  const [visibleColIds, setVisibleColIds] = useState<Set<string>>(DEFAULT_VISIBLE);

  const displayRows = useMemo((): GitHubUser[] => {
    if (!summaryByCountry) return rowData;
    return buildCountrySummaryRows(rowData) as unknown as GitHubUser[];
  }, [rowData, summaryByCountry]);

  const columnDefs = useMemo((): ColDef<GitHubUser>[] => {
    if (!summaryByCountry) return GITHUB_USER_COLUMN_DEFS;
    return GITHUB_USER_COLUMN_DEFS.map((col) => {
      const id = String(col.colId ?? col.field ?? "");
      return id === "outreachAction" || id === "profileAction" ? { ...col, hide: true } : col;
    });
  }, [summaryByCountry]);

  const defaultColDef = useMemo(
    () => ({
      ...GITHUB_USER_DEFAULT_COL_DEF,
      floatingFilter: true,
    }),
    []
  );

  const syncVisibleFromGrid = useCallback(() => {
    const api = apiRef.current;
    if (!api) return;
    const next = new Set<string>();
    api.getColumns()?.forEach((col) => {
      const id = col.getColId();
      if (col.isVisible()) next.add(id);
    });
    setVisibleColIds(next);
  }, []);

  const applyColumnVisibility = useCallback((colId: string, visible: boolean) => {
    apiRef.current?.setColumnsVisible([colId], visible);
    setVisibleColIds((prev) => {
      const next = new Set(prev);
      if (visible) next.add(colId);
      else next.delete(colId);
      return next;
    });
  }, []);

  const onGridReady = useCallback(
    (e: GridReadyEvent<GitHubUser>) => {
      apiRef.current = e.api;
      try {
        const raw = localStorage.getItem(COLUMN_STATE_KEY);
        if (raw) {
          const state = JSON.parse(raw);
          if (Array.isArray(state)) {
            e.api.applyColumnState({ state, applyOrder: true });
          }
        }
      } catch {
        /* ignore */
      }
      syncVisibleFromGrid();
    },
    [syncVisibleFromGrid]
  );

  const onColumnVisible = useCallback(
    (_e: ColumnVisibleEvent) => {
      syncVisibleFromGrid();
    },
    [syncVisibleFromGrid]
  );

  const onSelectionChanged = useCallback((e: SelectionChangedEvent) => {
    setSelectedCount(e.api.getSelectedRows().length);
  }, []);

  const onSortChanged = useCallback(
    (e: SortChangedEvent<GitHubUser>) => {
      const sorted = e.api
        .getColumnState()
        .find((col) => col.sort === "asc" || col.sort === "desc");
      if (!sorted?.colId || !sorted.sort) {
        onServerSortChange?.("last_scraped_at", "desc");
        return;
      }
      const sortMap: Record<string, string> = {
        followers: "followers",
        public_repos: "public_repos",
        created_at: "created_at",
        login: "login",
        last_scraped_at: "last_scraped_at",
      };
      const sortBy = sortMap[sorted.colId];
      if (sortBy) onServerSortChange?.(sortBy, sorted.sort);
    },
    [onServerSortChange]
  );

  const onFilterChanged = useCallback(
    (e: FilterChangedEvent<GitHubUser>) => {
      const model = e.api.getFilterModel() as Record<string, any>;
      const next: {
        search?: string;
        country?: string;
        followersMin?: string;
        followersMax?: string;
        createdAfter?: string;
        createdBefore?: string;
        hasEmail?: "yes" | "no" | "";
        hasBio?: "yes" | "no" | "";
      } = {
        search: "",
        country: "",
        followersMin: "",
        followersMax: "",
        createdAfter: "",
        createdBefore: "",
      };

      for (const field of ["login", "name", "email", "location", "company", "bio"]) {
        const filter = model[field];
        const value = String(filter?.filter || "").trim();
        if (value) {
          next.search = value;
          break;
        }
      }

      const country = String(model.country?.filter || "").trim();
      if (country) next.country = country;

      const followers = model.followers;
      if (followers?.filter != null) {
        if (followers.type === "lessThan" || followers.type === "lessThanOrEqual") {
          next.followersMax = String(followers.filter);
        } else {
          next.followersMin = String(followers.filter);
        }
      }

      const created = model.created_at;
      if (created?.dateFrom) {
        if (created.type === "lessThan" || created.type === "lessThanOrEqual") {
          next.createdBefore = String(created.dateFrom).slice(0, 10);
        } else {
          next.createdAfter = String(created.dateFrom).slice(0, 10);
        }
      }

      const emailFilter = model.email;
      if (emailFilter?.type === "blank") next.hasEmail = "no";
      if (emailFilter?.type === "notBlank") next.hasEmail = "yes";

      const bioFilter = model.bio;
      if (bioFilter?.type === "blank") next.hasBio = "no";
      if (bioFilter?.type === "notBlank") next.hasBio = "yes";

      onServerFiltersChange?.(next);
    },
    [onServerFiltersChange]
  );

  useEffect(() => {
    const api = apiRef.current;
    if (!api) return;
    api.setGridOption("rowData", displayRows);
    if (summaryByCountry) {
      api.setColumnsVisible(["outreachAction", "profileAction"], false);
    }
  }, [displayRows, summaryByCountry]);

  useEffect(() => {
    if (!focusLogin || loading || summaryByCountry) return;
    const api = apiRef.current;
    if (!api) return;

    let rowIndex = -1;
    api.forEachNode((node, index) => {
      if (node.data?.login === focusLogin) rowIndex = index;
    });
    if (rowIndex < 0) return;

    requestAnimationFrame(() => {
      api.ensureIndexVisible(rowIndex, "middle");
      const rowEl = document.querySelector(
        `.ag-material-demo__grid [row-index="${rowIndex}"]`
      ) as HTMLElement | null;
      rowEl?.classList.add("users-grid-row--focused");
      window.setTimeout(() => rowEl?.classList.remove("users-grid-row--focused"), 2400);
      onFocusHandled?.();
    });
  }, [focusLogin, loading, displayRows, summaryByCountry, onFocusHandled]);

  const saveColumnState = useCallback(() => {
    const state = apiRef.current?.getColumnState();
    if (state) {
      localStorage.setItem(COLUMN_STATE_KEY, JSON.stringify(state));
    }
  }, []);

  const resetColumns = useCallback(() => {
    apiRef.current?.resetColumnState();
    apiRef.current?.setColumnsVisible(getAllGridColumnIds(), true);
    localStorage.removeItem(COLUMN_STATE_KEY);
    syncVisibleFromGrid();
  }, [syncVisibleFromGrid]);

  const showAllColumns = useCallback(() => {
    apiRef.current?.setColumnsVisible(getAllGridColumnIds(), true);
    syncVisibleFromGrid();
  }, [syncVisibleFromGrid]);

  const hideAllColumns = useCallback(() => {
    const keep = ["profileAction", "login", "email", "country", "outreachAction"];
    getAllGridColumnIds().forEach((id) => {
      apiRef.current?.setColumnsVisible([id], keep.includes(id));
    });
    syncVisibleFromGrid();
  }, [syncVisibleFromGrid]);

  const statusText = loading
    ? "Loading..."
    : totalKnown
      ? `${totalLoaded.toLocaleString()} / ${totalAvailable.toLocaleString()} rows`
      : `${totalLoaded.toLocaleString()} loaded${hasMore ? " - more available" : ""}`;

  return (
    <AgGridProvider modules={modules}>
      <div className="ag-material-demo">
        <div className="ag-material-demo__toolbar">
          <div className="ag-material-demo__toolbar-left">
            <span className="ag-material-demo__badge">Users</span>
            <select
              className="ag-material-demo__select"
              value={selectedCountry}
              onChange={(e) => onCountryChange?.(e.target.value)}
              aria-label="Filter by country"
            >
              <option value="">All countries</option>
              {countryOptions.map((country) => (
                <option key={country.country} value={country.country}>
                  {country.country} ({country.count.toLocaleString()})
                </option>
              ))}
            </select>
            {summaryByCountry && (
              <span className="ag-material-demo__pill">Summary view</span>
            )}
          </div>
          <div className="ag-material-demo__toolbar-right">
            <span className="ag-material-demo__stat">
              {statusText}
              {selectedCount > 0 ? ` - ${selectedCount} selected` : ""}
            </span>
            <button
              type="button"
              className="ag-material-demo__btn"
              onClick={() => setPanelOpen((v) => !v)}
            >
              {panelOpen ? "Hide columns" : "Columns"}
            </button>
            <button type="button" className="ag-material-demo__btn" onClick={resetColumns}>
              Reset layout
            </button>
          </div>
        </div>

        <div
          className={`ag-material-demo__body${panelOpen ? "" : " ag-material-demo__body--no-panel"}`}
        >
          <div
            className="ag-material-demo__grid"
            style={{ height: "calc(72vh - 64px)", minHeight: 400 }}
          >
            {loading && (
              <div className="users-grid-loading" aria-live="polite" aria-label="Loading users">
                <div className="users-grid-loading__panel">
                  <div className="users-grid-loading__mark">
                    <span className="users-grid-loading__spinner" />
                  </div>
                  <div className="users-grid-loading__copy">
                    <strong>Loading users</strong>
                    <span>Fetching page, preparing columns, painting rows</span>
                  </div>
                  <div className="users-grid-loading__meter">
                    <span />
                  </div>
                </div>
              </div>
            )}
            <AgGridReact<GitHubUser>
              theme={githubUsersGridTheme}
              rowData={displayRows}
              columnDefs={columnDefs}
              defaultColDef={defaultColDef}
              components={gridCellRenderers}
              getRowId={(p) => String(p.data?.id ?? p.data?.login)}
              onGridReady={onGridReady}
              onColumnVisible={onColumnVisible}
              onColumnMoved={saveColumnState}
              onColumnResized={saveColumnState}
              onSelectionChanged={onSelectionChanged}
              onSortChanged={onSortChanged}
              onFilterChanged={onFilterChanged}
              loading={loading}
              animateRows={false}
              pagination={false}
              rowBuffer={8}
              suppressCellFocus={false}
              enableCellTextSelection
              rowSelection={{
                mode: "multiRow",
                checkboxes: !summaryByCountry,
                headerCheckbox: !summaryByCountry,
              }}
              tooltipShowDelay={400}
              overlayNoRowsTemplate='<span style="color:#9aa8bb;font-family:Roboto,sans-serif">No users match your filters</span>'
              overlayLoadingTemplate='<span style="color:#9aa8bb;font-family:Roboto,sans-serif">Loading users...</span>'
            />
          </div>

          {panelOpen && (
            <ColumnsToolPanel
              visibleColIds={visibleColIds}
              onToggleColumn={applyColumnVisibility}
              onShowAll={showAllColumns}
              onHideAll={hideAllColumns}
              summaryByCountry={summaryByCountry}
              onSummaryByCountryChange={setSummaryByCountry}
            />
          )}
        </div>

        <div className="ag-material-demo__statusbar">
          <span>
            Rows: {displayRows.length.toLocaleString()}
            {summaryByCountry ? " (country summaries)" : ""}
          </span>
          <span>Server-paged results</span>
        </div>
      </div>
    </AgGridProvider>
  );
}
