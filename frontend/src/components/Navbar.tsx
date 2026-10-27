"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import GlobalAISearch from "@/components/GlobalAISearch";
import {
  HUB_MODULES,
  PLATFORM_NAME,
  PLATFORM_TAGLINE,
  isModuleEnabled,
  resolveActiveModule,
} from "@/lib/nav-config";
import { createClient } from "@/lib/supabase";
import { fetchCurrentUser, signOutLocalAuth } from "@/lib/auth-session";
import { useMongoStorage } from "@/lib/database-storage";

function displayName(user: { email?: string; user_metadata?: Record<string, unknown> } | null) {
  const metadata = user?.user_metadata || {};
  const name =
    metadata.display_name ||
    metadata.full_name ||
    metadata.name ||
    user?.email?.split("@")[0] ||
    "Account";
  return String(name);
}

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "A"
  );
}

function avatarUrl(user: { user_metadata?: Record<string, unknown> } | null) {
  const value = user?.user_metadata?.avatar_url;
  return typeof value === "string" ? value : "";
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [account, setAccount] = useState<{
    id?: string;
    email?: string;
    user_metadata?: Record<string, unknown>;
    app_metadata?: Record<string, unknown>;
  } | null>(null);

  const activeModuleId = resolveActiveModule(pathname);
  const isAdmin = account?.app_metadata?.role === "admin";

  const mobileOptions = useMemo(() => {
    const items: { href: string; label: string }[] = [{ href: "/", label: "Home" }];
    for (const mod of HUB_MODULES) {
      if (mod.id === "hub" || !isModuleEnabled(mod)) continue;
      items.push({ href: mod.href, label: mod.label });
      for (const sub of mod.subLinks ?? []) {
        if (sub.href !== mod.href) {
          items.push({ href: sub.href, label: `${mod.shortLabel}: ${sub.label}` });
        }
      }
    }
    items.push({ href: "/profile", label: "Profile settings" });
    return items;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadMongoAccount() {
      const user = await fetchCurrentUser();
      if (cancelled || !user) return;
      setAccount({
        id: user.id,
        email: user.email,
        user_metadata: user.user_metadata || {},
        app_metadata: { role: user.role },
      });
    }

    function onProfileUpdated(event: Event) {
      const nextUser = (event as CustomEvent).detail;
      if (nextUser) setAccount(nextUser);
    }

    window.addEventListener("account-profile-updated", onProfileUpdated);

    if (useMongoStorage) {
      void loadMongoAccount();
      return () => {
        cancelled = true;
        window.removeEventListener("account-profile-updated", onProfileUpdated);
      };
    }

    const supabase = createClient();

    supabase.auth.getUser().then(({ data }) => {
      if (!cancelled) setAccount(data.user || null);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setAccount(session?.user || null);
    });

    return () => {
      cancelled = true;
      window.removeEventListener("account-profile-updated", onProfileUpdated);
      listener.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  async function signOut() {
    if (useMongoStorage) {
      signOutLocalAuth();
    } else {
      const supabase = createClient();
      await supabase.auth.signOut();
    }
    setMenuOpen(false);
    router.push("/login");
  }

  function moduleHref(module: (typeof HUB_MODULES)[number]) {
    if (!isAdmin && module.id !== "hub") return "/login";
    return module.href;
  }

  const name = displayName(account);
  const role = String(account?.app_metadata?.role || "guest");
  const avatar = avatarUrl(account);

  return (
    <header className="app-navbar sticky top-0 z-40">
      <div className="app-navbar__inner mx-auto max-w-[1600px] px-4 py-3 sm:px-6">
        <div className="app-navbar__grid app-navbar__grid--search">
          <div className="app-navbar__start">
            <Link href="/" prefetch={false} className="app-navbar__brand">
              <span className="app-brand-mark app-brand-mark--hub">OC</span>
              <span className="app-navbar__brand-copy hidden lg:inline">
                <span className="block text-sm font-extrabold text-github">{PLATFORM_NAME}</span>
                <span className="block text-[11px] font-medium text-github-muted">{PLATFORM_TAGLINE}</span>
              </span>
            </Link>

            <nav className="app-navbar__modules hidden md:flex" aria-label="Workspace modules">
              {HUB_MODULES.filter(isModuleEnabled).map((module) => {
                const active = module.id === activeModuleId;
                const href = moduleHref(module);
                const tabClass = `hub-module-tab${active ? " hub-module-tab--active" : ""}`;

                return (
                  <Link
                    key={module.id}
                    href={href}
                    prefetch={false}
                    className={tabClass}
                    style={
                      active
                        ? ({
                            "--module-accent": module.accent,
                          } as React.CSSProperties)
                        : undefined
                    }
                  >
                    <span>{module.shortLabel}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="app-navbar__search">
            <Suspense fallback={null}>
              <GlobalAISearch />
            </Suspense>
          </div>

          <div className="app-navbar__end">
            <select
              className="input max-w-[160px] py-2 text-xs md:hidden"
              value={pathname}
              onChange={(e) => router.push(e.target.value)}
              aria-label="Navigate"
            >
              {mobileOptions.map((item) => (
                <option key={item.href + item.label} value={item.href}>
                  {item.label}
                </option>
              ))}
            </select>

            {isAdmin ? (
              <div className="app-account-menu" ref={menuRef}>
                <button
                  type="button"
                  className={`app-account-trigger${menuOpen || pathname === "/profile" ? " app-account-trigger--active" : ""}`}
                  onClick={() => setMenuOpen((open) => !open)}
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  aria-label="Account menu"
                >
                  <span className="app-account-avatar">
                    {avatar ? <img src={avatar} alt="" /> : initials(name)}
                  </span>
                  <span className="app-account-trigger__copy hidden sm:inline">
                    <strong>{name}</strong>
                    <small>{role}</small>
                  </span>
                  <span className="app-account-caret" aria-hidden="true" />
                </button>

                {menuOpen && (
                  <div className="app-account-dropdown" role="menu">
                    <div className="app-account-dropdown__head">
                      <span className="app-account-avatar app-account-avatar--large">
                        {avatar ? <img src={avatar} alt="" /> : initials(name)}
                      </span>
                      <div>
                        <strong>{name}</strong>
                        <small>{account?.email || "Signed-in user"}</small>
                      </div>
                    </div>
                    <Link href="/profile" prefetch={false} role="menuitem" onClick={() => setMenuOpen(false)}>
                      Profile settings
                    </Link>
                    <button type="button" role="menuitem" onClick={signOut}>
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link href="/login" className="btn-secondary py-2 text-xs">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
