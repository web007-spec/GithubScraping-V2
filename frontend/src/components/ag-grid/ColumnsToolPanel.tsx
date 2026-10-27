"use client";

import { useMemo, useState } from "react";
import {
  GITHUB_USER_COLUMN_GROUPS,
  getColumnHeaderLabel,
} from "@/lib/ag-grid-column-groups";

type ColumnsToolPanelProps = {
  visibleColIds: Set<string>;
  onToggleColumn: (colId: string, visible: boolean) => void;
  onShowAll: () => void;
  onHideAll: () => void;
  summaryByCountry: boolean;
  onSummaryByCountryChange: (value: boolean) => void;
};

export default function ColumnsToolPanel({
  visibleColIds,
  onToggleColumn,
  onShowAll,
  onHideAll,
  summaryByCountry,
  onSummaryByCountryChange,
}: ColumnsToolPanelProps) {
  const [search, setSearch] = useState("");

  const filteredGroups = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return GITHUB_USER_COLUMN_GROUPS;
    return GITHUB_USER_COLUMN_GROUPS.map((g) => ({
      ...g,
      colIds: g.colIds.filter((id) => {
        const label = getColumnHeaderLabel(id).toLowerCase();
        return label.includes(q) || id.toLowerCase().includes(q);
      }),
    })).filter((g) => g.colIds.length > 0);
  }, [search]);

  return (
    <aside className="ag-columns-panel" aria-label="Columns">
      <div className="ag-columns-panel__head">
        <span className="ag-columns-panel__title">Columns</span>
      </div>

      <div className="ag-columns-panel__section">
        <label className="ag-columns-panel__toggle">
          <input
            type="checkbox"
            checked={summaryByCountry}
            onChange={(e) => onSummaryByCountryChange(e.target.checked)}
          />
          <span>Summary by country</span>
        </label>
      </div>

      <div className="ag-columns-panel__search-wrap">
        <input
          type="search"
          className="ag-columns-panel__search"
          placeholder="Search columns…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search columns"
        />
      </div>

      <div className="ag-columns-panel__actions">
        <button type="button" className="ag-columns-panel__link" onClick={onShowAll}>
          Show all
        </button>
        <button type="button" className="ag-columns-panel__link" onClick={onHideAll}>
          Hide all
        </button>
      </div>

      <div className="ag-columns-panel__list">
        {filteredGroups.map((group) => (
          <div key={group.id} className="ag-columns-panel__group">
            <div className="ag-columns-panel__group-label">{group.label}</div>
            <ul className="ag-columns-panel__items">
              {group.colIds.map((colId) => (
                <li key={colId}>
                  <label className="ag-columns-panel__item">
                    <input
                      type="checkbox"
                      checked={visibleColIds.has(colId)}
                      onChange={(e) => onToggleColumn(colId, e.target.checked)}
                    />
                    <span>{getColumnHeaderLabel(colId)}</span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}
