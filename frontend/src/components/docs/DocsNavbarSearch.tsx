"use client";

import { useOptionalDocsBrowseFilter } from "@/lib/docs-browse-context";

export default function DocsNavbarSearch() {
  const browse = useOptionalDocsBrowseFilter();
  if (!browse) return null;

  return (
    <div className="workspace-subnav__search">
      <input
        type="search"
        className="docs-navbar-search__input"
        value={browse.filter}
        onChange={(e) => browse.setFilter(e.target.value)}
        placeholder="AI search documents…"
        aria-label="Search documents"
      />
    </div>
  );
}
