"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function GlobalAISearch() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("q") || "";
  const [query, setQuery] = useState(urlQuery);

  useEffect(() => {
    setQuery(urlQuery);
  }, [urlQuery]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  function handleClear() {
    setQuery("");
  }

  return (
    <form className="global-ai-search" onSubmit={handleSubmit} role="search" aria-label="Global AI search">
      <span className="global-ai-search__label">AI Search</span>
      <input
        type="search"
        className="global-ai-search__input"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search GitHub users and Google Docs…"
      />
      {query ? (
        <button type="button" className="global-ai-search__clear" onClick={handleClear} aria-label="Clear">
          ×
        </button>
      ) : null}
      <button type="submit" className="global-ai-search__submit">
        Search
      </button>
    </form>
  );
}
