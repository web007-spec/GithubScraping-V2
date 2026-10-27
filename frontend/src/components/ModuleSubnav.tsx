"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import DocsNavbarSearch from "@/components/docs/DocsNavbarSearch";
import {
  HUB_MODULES,
  isModuleEnabled,
  isNavLinkActive,
  resolveActiveModule,
  type HubModuleId,
} from "@/lib/nav-config";
import { useAdminSession } from "@/lib/use-admin-session";

function moduleLinks(moduleId: HubModuleId) {
  return HUB_MODULES.find((module) => module.id === moduleId)?.subLinks ?? [];
}

export default function ModuleSubnav() {
  const pathname = usePathname();
  const { isAdmin, checking } = useAdminSession();
  const moduleId = resolveActiveModule(pathname);
  const module = HUB_MODULES.find((item) => item.id === moduleId);
  const links = moduleLinks(moduleId);

  if (checking || moduleId === "hub" || !module || !isModuleEnabled(module) || links.length <= 1) {
    return null;
  }

  const showDocsSearch = moduleId === "docs" && pathname === "/explore/docs";

  return (
    <div className="workspace-subnav-wrap">
      <nav className="workspace-subnav" aria-label={`${module.label} pages`}>
        <span className="workspace-subnav__label">{module.label}</span>
        <div className="workspace-subnav__links">
          {links.map((link) => {
            const active = isNavLinkActive(pathname, link.href);
            const adminOnly =
              (moduleId === "docs" || moduleId === "drive") && link.href.includes("/crawl/");
            const href =
              !isAdmin && (moduleId === "docs" || moduleId === "drive") && adminOnly
                ? "/login"
                : link.href;
            return (
              <Link
                key={link.href}
                href={href}
                prefetch={false}
                className={`workspace-subnav__link${active ? " workspace-subnav__link--active" : ""}`}
                style={
                  active
                    ? ({ "--module-accent": module.accent } as React.CSSProperties)
                    : undefined
                }
              >
                {link.label}
              </Link>
            );
          })}
        </div>
        {showDocsSearch ? <DocsNavbarSearch /> : null}
      </nav>
    </div>
  );
}
