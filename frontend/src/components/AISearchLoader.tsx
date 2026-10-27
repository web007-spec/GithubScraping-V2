"use client";

type AISearchLoaderProps = {
  query?: string;
  detail?: string;
  className?: string;
};

export default function AISearchLoader({
  query,
  detail = "Ranking matches from the database…",
  className = "",
}: AISearchLoaderProps) {
  const classes = ["ai-search-loader", className].filter(Boolean).join(" ");

  return (
    <div className={classes} role="status" aria-live="polite" aria-busy="true">
      <div className="ai-search-loader__orb" aria-hidden="true">
        <span className="ai-search-loader__ring" />
        <span className="ai-search-loader__core" />
        <span className="ai-search-loader__spark ai-search-loader__spark--1" />
        <span className="ai-search-loader__spark ai-search-loader__spark--2" />
        <span className="ai-search-loader__spark ai-search-loader__spark--3" />
      </div>
      <div className="ai-search-loader__copy">
        <strong>{query ? `AI Search: “${query}”` : "AI Search"}</strong>
        <span>{detail}</span>
        <div className="ai-search-loader__track" aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
