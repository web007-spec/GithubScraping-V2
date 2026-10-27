import Link from "next/link";

export default function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="mesh-bg flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[440px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400 to-violet-500 text-sm font-extrabold text-white shadow-lg shadow-sky-500/25">
            OC
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">
            Outreach Console
          </p>
          <h1 className="page-title mt-2">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        <div className="card shadow-elevated">{children}</div>
        {footer && <div className="mt-6 text-center text-sm text-github-light">{footer}</div>}
      </div>
    </div>
  );
}

export function AuthTabs({ active }: { active: "login" | "register" }) {
  return (
    <div className="mb-6 flex rounded-xl bg-surface-subtle p-1">
      <Link
        href="/login"
        className={
          active === "login"
            ? "flex-1 rounded-lg bg-surface py-2.5 text-center text-sm font-semibold text-github shadow-sm"
            : "flex-1 rounded-lg py-2.5 text-center text-sm font-medium text-github-light transition hover:text-github"
        }
      >
        Sign in
      </Link>
      <Link
        href="/register"
        className={
          active === "register"
            ? "flex-1 rounded-lg bg-surface py-2.5 text-center text-sm font-semibold text-github shadow-sm"
            : "flex-1 rounded-lg py-2.5 text-center text-sm font-medium text-github-light transition hover:text-github"
        }
      >
        Register
      </Link>
    </div>
  );
}
