"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogoutButton } from "@/app/dashboard/logout-button";

import { ThemeToggle } from "./theme-toggle";

type ShellSession = {
  name: string;
  role: string;
} | null;

type NavItem = { href: string; label: string; icon: React.ReactNode };
type NavGroup = { label: string; items: NavItem[] };

const Icon = {
  Home: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  ),
  Kanban: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="5" height="18" rx="1"/><rect x="10" y="3" width="5" height="11" rx="1"/><rect x="17" y="3" width="5" height="15" rx="1"/>
    </svg>
  ),
  Check: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
    </svg>
  ),
  Clipboard: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
    </svg>
  ),
  Folder: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  Database: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  Cpu: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>
    </svg>
  ),
  Cog: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>
  ),
  Sliders: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>
    </svg>
  ),
  Users: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  List: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
    </svg>
  ),
  Clock: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
    </svg>
  ),
};

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Command",
    items: [
      { href: "/dashboard",  label: "Dashboard",  icon: <Icon.Home /> },
      { href: "/workboard",  label: "Workboard",  icon: <Icon.Kanban /> },
      { href: "/approvals",  label: "Approvals",  icon: <Icon.Check /> },
    ],
  },
  {
    label: "Pipeline",
    items: [
      { href: "/project-logs",   label: "Project Logs",   icon: <Icon.Clipboard /> },
      { href: "/artifacts",      label: "Artifacts",      icon: <Icon.Folder /> },
      { href: "/project-memory", label: "Project Memory", icon: <Icon.Database /> },
    ],
  },
  {
    label: "Agents",
    items: [
      { href: "/agents", label: "Agents", icon: <Icon.Cpu /> },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/settings",   label: "Settings",    icon: <Icon.Sliders /> },
      { href: "/backoffice", label: "Back-office",  icon: <Icon.Cog /> },
      { href: "/users",      label: "Users",        icon: <Icon.Users /> },
      { href: "/audit",      label: "Audit",        icon: <Icon.List /> },
      { href: "/cron",       label: "Cron Jobs",    icon: <Icon.Clock /> },
    ],
  },
];

function isPublicPath(pathname: string) {
  return (
    pathname === "/" ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/reset-password")
  );
}

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function formatPathLabel(pathname: string) {
  if (pathname === "/dashboard") {
    return "Control Center";
  }

  const segments = pathname
    .split("/")
    .filter(Boolean)
    .map((segment) =>
      segment
        .replace(/-/g, " ")
        .replace(/\b\w/g, (character) => character.toUpperCase()),
    );

  return segments.join(" / ");
}

export function AppShell({
  children,
  session,
}: {
  children: React.ReactNode;
  session: ShellSession;
}) {
  const pathname = usePathname();

  if (!session || isPublicPath(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-transparent text-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 px-4 py-4 lg:flex lg:flex-col">
          <div className="material-panel rounded-[2rem] bg-[linear-gradient(180deg,#212b47_0%,#1a2035_100%)] px-5 py-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">
              Multi AI Agent
            </p>
            <h1 className="mt-2 text-xl font-semibold text-white">
              Control Center
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Orchestration, approvals, visibility, and project memory in one place.
            </p>
          </div>

          <nav className="mt-8 flex-1 space-y-6">
            {NAV_GROUPS.map((group) => (
              <div key={group.label}>
                <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {group.label}
                </p>
                <div className="mt-3 space-y-1">
                  {group.items.map((item) => {
                    const active = isActivePath(pathname, item.href);

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`flex items-center gap-2.5 justify-between rounded-2xl px-3 py-2.5 text-sm font-medium transition ${
                          active
                            ? "bg-[linear-gradient(135deg,#4f8cff_0%,#6aa0ff_100%)] text-white shadow-[0_18px_36px_-20px_rgba(79,140,255,0.8)]"
                            : "text-slate-400 hover:bg-white/6 hover:text-white"
                        }`}
                      >
                        <span className={`shrink-0 ${active ? "text-white" : "text-slate-500"}`}>{item.icon}</span>
                        <span className="flex-1">{item.label}</span>
                        {active ? (
                          <span className="h-1.5 w-1.5 rounded-full bg-[#24e08a]" />
                        ) : null}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          <div className="material-panel rounded-[2rem] px-4 py-4 text-sm">
            <p className="font-medium text-white">{session.name}</p>
            <p className="mt-1 text-slate-400">{session.role}</p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 px-5 py-4 lg:px-8">
            <div className="material-panel flex items-center justify-between gap-4 rounded-[1.75rem] px-5 py-4">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                  Pages
                </p>
                <p className="truncate text-sm font-medium text-slate-200">
                  {formatPathLabel(pathname)}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <div className="hidden md:block md:min-w-56">
                  <div className="material-chip flex h-11 items-center rounded-2xl px-4 text-sm text-slate-500">
                    Type here...
                  </div>
                </div>
                <div className="hidden h-11 items-center rounded-2xl border border-[rgba(36,224,138,0.25)] bg-[rgba(36,224,138,0.07)] px-4 text-sm font-medium text-[#24e08a] lg:flex">
                  Runtime OK
                </div>
                <ThemeToggle />
                <LogoutButton />
              </div>
            </div>
          </header>

          <main className="flex-1 px-0 py-0">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
