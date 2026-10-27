"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type DocsBrowseContextValue = {
  filter: string;
  setFilter: (value: string) => void;
};

const DocsBrowseContext = createContext<DocsBrowseContextValue | null>(null);

export function DocsBrowseProvider({ children }: { children: ReactNode }) {
  const [filter, setFilter] = useState("");
  const value = useMemo(() => ({ filter, setFilter }), [filter]);
  return <DocsBrowseContext.Provider value={value}>{children}</DocsBrowseContext.Provider>;
}

export function useDocsBrowseFilter() {
  const ctx = useContext(DocsBrowseContext);
  if (!ctx) {
    throw new Error("useDocsBrowseFilter must be used within DocsBrowseProvider");
  }
  return ctx;
}

export function useOptionalDocsBrowseFilter() {
  return useContext(DocsBrowseContext);
}
