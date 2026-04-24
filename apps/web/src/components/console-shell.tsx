"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { client } from "@/lib/api/client";
import type { Session } from "@/lib/api/types";
import { Badge, Button, Card, cx } from "@/components/ui";

const ConsoleSessionContext = createContext<Session | null>(null);

export function useConsoleSession() {
  return useContext(ConsoleSessionContext);
}

type NavItem = {
  href: string;
  label: string;
  summary: string;
  focus: string;
};

type NavGroup = {
  title: string;
  description: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    title: "Config",
    description: "Author the control-plane documents that drive runtime behavior.",
    items: [
      {
        href: "/config/api-ontology",
        label: "API Ontology",
        summary: "Define event routing, workflow relationships, and package structure.",
        focus: "Draft, validate, approve, and publish package changes.",
      },
      {
        href: "/config/memory-ontology",
        label: "Memory Ontology",
        summary: "Model memory types, identity strategies, and supersession rules.",
        focus: "Tune durable memory definitions and retrieval behavior.",
      },
      {
        href: "/config/policy-profile",
        label: "Policy Profile",
        summary: "Set sensitivity ceilings, inference rules, and forget behavior.",
        focus: "Adjust operator policy without changing code.",
      },
    ],
  },
  {
    title: "Runtime",
    description: "Exercise the runtime before and after publication.",
    items: [
      {
        href: "/validation",
        label: "Validation",
        summary: "Review document health, warnings, and publish blockers.",
        focus: "Run validation and interpret failing checks quickly.",
      },
      {
        href: "/simulation",
        label: "Simulation",
        summary: "Replay a sample event and inspect decision outcomes safely.",
        focus: "Compose a sample event before you publish.",
      },
      {
        href: "/publication",
        label: "Publication",
        summary: "Promote reviewed snapshots and inspect release notes.",
        focus: "Track active and historical releases by snapshot.",
      },
      {
        href: "/rollback",
        label: "Rollback",
        summary: "Revert future behavior to an earlier snapshot without redeploy.",
        focus: "Operate rollback with explicit consequence framing.",
      },
    ],
  },
  {
    title: "Inspect",
    description: "Trace the runtime after decisions are made.",
    items: [
      {
        href: "/decision-explorer",
        label: "Decision Explorer",
        summary: "Inspect evidence, reason codes, and snapshot lineage.",
        focus: "Trace why a runtime decision happened.",
      },
      {
        href: "/memory-browser",
        label: "Memory Browser",
        summary: "Search structured memories and verify retrieval visibility.",
        focus: "Query user records and inspect active memory state.",
      },
      {
        href: "/audit-log",
        label: "Audit Log",
        summary: "Review operator actions and system lifecycle transitions.",
        focus: "Filter operational history and publication activity.",
      },
    ],
  },
];

function ShellLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={cx(
        "group console-link flex min-h-11 items-center justify-between gap-3 rounded-xl border px-3 py-2.5",
        active
          ? "border-cyan-300/28 bg-cyan-400/10 text-white shadow-[inset_3px_0_0_rgba(34,211,238,0.85)]"
          : "border-transparent text-slate-400 hover:border-white/8 hover:bg-white/5 hover:text-slate-100",
      )}
    >
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold sm:text-[15px]">{item.label}</div>
        <div className={cx("mt-1 hidden truncate text-xs leading-5 lg:block", active ? "text-cyan-100/70" : "text-slate-500 group-hover:text-slate-400")}>
          {item.focus}
        </div>
      </div>
      <span className={cx("h-2 w-2 rounded-full", active ? "bg-[color:var(--color-accent)]" : "bg-transparent")} />
    </Link>
  );
}

function resolvePathTitle(pathname: string) {
  return pathname
    .replace(/^\/+/, "")
    .split("/")
    .filter(Boolean)
    .map((segment) => segment.replaceAll("-", " "))
    .join(" / ") || "Dashboard";
}

function summarizeApiBase(apiBase: string) {
  if (!apiBase) {
    return { host: "Not configured", value: "Set NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL." };
  }

  try {
    const url = new URL(apiBase);
    return { host: url.host, value: url.toString() };
  } catch {
    return { host: apiBase, value: apiBase };
  }
}

function SidebarContent({
  session,
  initials,
  pathname,
  apiBase,
  onClose,
  onSignOut,
}: {
  session: Session;
  initials: string;
  pathname: string;
  apiBase: string;
  onClose?: () => void;
  onSignOut: () => void | Promise<void>;
}) {
  const boundary = summarizeApiBase(apiBase);
  const activeGroup = navGroups.find((group) => group.items.some((item) => item.href === pathname));

  return (
    <div className="flex min-h-full flex-col gap-6">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-cyan-300/24 bg-cyan-400/10 shadow-[var(--shadow-inset-edge)]">
              <div className="h-5 w-5 rounded-md border border-cyan-200/70 bg-cyan-200/10" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold tracking-tight text-white">MemoryEngine</h1>
              <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Operator console</p>
            </div>
          </div>
          {onClose ? (
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          ) : null}
        </div>

        <div className="panel-inset space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="label">Signed in</div>
              <div className="mt-1 text-sm font-semibold text-white">{session.user.displayName}</div>
              <div className="mt-1 truncate text-xs leading-5 text-slate-400" title={session.user.email}>
                {session.user.email}
              </div>
            </div>
            <div className="numeric flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--color-line-subtle)] bg-white/5 text-sm font-semibold text-slate-100">
              {initials}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="accent">{session.user.role}</Badge>
            {activeGroup ? <Badge>{activeGroup.title}</Badge> : null}
          </div>
        </div>
      </div>

      <nav className="space-y-4">
        {navGroups.map((group) => (
            <div key={group.title} className="space-y-2">
              <div className="space-y-1 px-1">
                <div className="label">{group.title}</div>
                <p className="hidden text-xs leading-5 text-slate-500 2xl:block">{group.description}</p>
              </div>
            <div className="space-y-2">
              {group.items.map((item) => (
                <ShellLink key={item.href} item={item} active={pathname === item.href} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="space-y-3">
        <div className="panel-inset space-y-2 p-4 text-xs text-slate-300">
          <div className="label">Live backend</div>
          <div className="text-sm font-semibold text-white">{boundary.host}</div>
          <div className="break-all leading-5 text-slate-400">{boundary.value}</div>
        </div>
        <Button variant="secondary" onClick={onSignOut} className="w-full">
          Sign out
        </Button>
      </div>
    </div>
  );
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const apiBase = process.env.NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL || "";

  const loadSession = () => {
    let active = true;
    setReady(false);
    setError(null);
    client.auth
      .me()
      .then((value) => {
        if (!active) {
          return;
        }
        setSession(value);
        setReady(true);
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        setSession(null);
        setError(requestError instanceof Error ? requestError.message : "Unable to reach the backend.");
        setReady(true);
      });

    return () => {
      active = false;
    };
  };

  useEffect(() => {
    const cancel = loadSession();
    return cancel;
  }, []);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    const desktopSidebarMedia = window.matchMedia("(min-width: 1280px)");
    const syncNavMode = (event?: MediaQueryListEvent) => {
      if (event?.matches ?? desktopSidebarMedia.matches) {
        setMobileNavOpen(false);
      }
    };

    syncNavMode();
    desktopSidebarMedia.addEventListener("change", syncNavMode);
    return () => {
      desktopSidebarMedia.removeEventListener("change", syncNavMode);
    };
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) {
      return;
    }
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [mobileNavOpen]);

  const initials = useMemo(() => {
    const display = session?.user.displayName ?? "Demo User";
    return display
      .split(" ")
      .map((part) => part.slice(0, 1))
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }, [session]);

  const currentNav = useMemo(() => {
    for (const group of navGroups) {
      const item = group.items.find((entry) => entry.href === pathname);
      if (item) {
        return { ...item, groupTitle: group.title, groupDescription: group.description };
      }
    }
    return null;
  }, [pathname]);
  const boundary = useMemo(() => summarizeApiBase(apiBase), [apiBase]);

  const signOut = async () => {
    try {
      await client.auth.logout();
    } finally {
      setSession(null);
      router.push("/login");
    }
  };

  if (!ready) {
    return (
      <div className="grid min-h-[100dvh] place-items-center px-6">
        <Card className="w-full max-w-md space-y-5">
          <div className="flex items-center justify-between gap-4">
            <Badge tone="accent">Loading console</Badge>
            <div className="h-2 w-20 overflow-hidden rounded-full bg-white/8">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-cyan-300/70" />
            </div>
          </div>
          <div className="text-lg font-semibold text-white">Checking session state</div>
          <div className="space-y-2">
            <div className="h-3 rounded-full bg-white/8" />
            <div className="h-3 w-4/5 rounded-full bg-white/6" />
          </div>
          <p className="text-sm text-slate-400">Contacting the configured API boundary and resolving the current operator session.</p>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid min-h-[100dvh] place-items-center px-6">
        <Card className="w-full max-w-xl space-y-4">
          <Badge tone="danger">Backend unavailable</Badge>
          <div className="text-2xl font-semibold text-white">Operator console cannot start</div>
          <p className="text-sm leading-6 text-slate-300">{error}</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void loadSession()}>Retry</Button>
            <Badge tone="danger">Live backend only</Badge>
          </div>
          {apiBase ? <div className="break-all text-xs text-slate-400">{apiBase}</div> : null}
        </Card>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="grid min-h-[100dvh] place-items-center px-6">
        <Card className="w-full max-w-lg space-y-4">
          <Badge tone="accent">Authentication required</Badge>
          <div className="text-2xl font-semibold text-white">Operator console locked</div>
          <p className="text-sm leading-6 text-slate-300">
            Sign in against the live backend to continue. This console does not use an embedded session fallback.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => router.push("/login")}>Go to login</Button>
            {apiBase ? <Badge tone="accent">{apiBase}</Badge> : null}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <ConsoleSessionContext.Provider value={session}>
      <div className="relative min-h-[100dvh] px-3 py-3 sm:px-4 sm:py-4 lg:px-6">
        <div className="console-noise" />
        <a
          href="#main-content"
          className="focus-ring fixed left-4 top-4 z-50 -translate-y-20 rounded-xl border border-cyan-300/30 bg-[color:var(--color-canvas-inset)] px-4 py-2 text-sm font-semibold text-cyan-100 transition focus:translate-y-0"
        >
          Skip to content
        </a>
        <div className="relative mx-auto grid min-h-[calc(100dvh-1.5rem)] max-w-[1720px] items-start gap-4 xl:grid-cols-[286px_minmax(0,1fr)] 2xl:grid-cols-[302px_minmax(0,1fr)]">
          <div
            className={cx(
              "fixed inset-0 z-40 bg-slate-950/70 backdrop-blur-sm transition xl:hidden",
              mobileNavOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
            )}
            onClick={() => setMobileNavOpen(false)}
            aria-hidden={!mobileNavOpen}
          />

          <aside
            className={cx(
              "panel-sidebar fixed inset-x-4 top-4 z-50 max-h-[calc(100dvh-2rem)] overflow-y-auto p-5 transition xl:hidden",
              mobileNavOpen ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-4 opacity-0",
            )}
            aria-hidden={!mobileNavOpen}
          >
            <SidebarContent
              session={session}
              initials={initials}
              pathname={pathname}
              apiBase={apiBase}
              onClose={() => setMobileNavOpen(false)}
              onSignOut={signOut}
            />
          </aside>

          <aside className="panel-sidebar hidden self-start xl:sticky xl:top-4 xl:flex xl:max-h-[calc(100dvh-2rem)] xl:flex-col xl:gap-5 xl:overflow-y-auto xl:p-5">
            <SidebarContent session={session} initials={initials} pathname={pathname} apiBase={apiBase} onSignOut={signOut} />
          </aside>

          <main id="main-content" className="min-w-0 space-y-4">
            <header className="surface-topbar rounded-2xl px-4 py-3 sm:px-5 sm:py-4">
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="accent">{currentNav?.groupTitle ?? "Control plane"}</Badge>
                    <span className="hidden text-xs text-slate-500 sm:inline">/</span>
                    <Badge>{session.user.role}</Badge>
                  </div>
                  <h1 className="mt-2 break-words text-2xl font-semibold tracking-tight text-white text-balance sm:text-3xl">
                    {pathname === "/login" ? "Login" : currentNav?.label ?? resolvePathTitle(pathname)}
                  </h1>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-300">{currentNav?.focus ?? currentNav?.summary ?? "Operate the control plane."}</p>
                </div>
                <div className="flex items-center justify-between gap-2 lg:justify-end">
                  <div className="hidden min-w-0 text-right xl:block">
                    <div className="label">API boundary</div>
                    <div className="mt-1 max-w-64 truncate text-sm font-semibold text-white">{boundary.host}</div>
                  </div>
                  <div className="numeric hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--color-line-subtle)] bg-white/5 text-sm font-semibold text-slate-100 sm:flex">
                    {initials}
                  </div>
                  <div className="flex shrink-0 items-center gap-2 xl:hidden">
                    <Button variant="secondary" onClick={() => setMobileNavOpen(true)}>
                      Menu
                    </Button>
                  </div>
                </div>
              </div>
            </header>

            <div className="space-y-4 pb-6">{children}</div>
          </main>
        </div>
      </div>
    </ConsoleSessionContext.Provider>
  );
}
