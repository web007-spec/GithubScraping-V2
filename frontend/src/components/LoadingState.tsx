"use client";

type LoadingStateProps = {
  title?: string;
  detail?: string;
  variant?: "page" | "card" | "inline";
  className?: string;
};

export function LoadingDots({ label = "Loading" }: { label?: string }) {
  return (
    <span className="loading-dots" aria-live="polite">
      <span>{label}</span>
      <span className="loading-dots__marks" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </span>
  );
}

export default function LoadingState({
  title = "Loading data",
  detail = "Please wait while the latest information is prepared.",
  variant = "card",
  className = "",
}: LoadingStateProps) {
  const classes = ["loading-state", `loading-state--${variant}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} role="status" aria-live="polite" aria-busy="true">
      <div className="loading-state__mark" aria-hidden="true">
        <span className="loading-state__ring" />
        <span className="loading-state__pulse" />
      </div>
      <div className="loading-state__content">
        <strong>{title}</strong>
        <span>{detail}</span>
        <div className="loading-state__bar" aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
