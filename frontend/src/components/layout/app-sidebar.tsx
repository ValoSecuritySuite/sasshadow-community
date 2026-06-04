"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useSidebar } from "@/hooks/use-sidebar";
import { useEditionContext } from "@/contexts/edition-context";
import { navigation, type NavItem } from "@/config/navigation";

function NavLink({
  item,
  collapsed,
  isCommunity,
}: {
  item: NavItem;
  collapsed: boolean;
  isCommunity: boolean;
}) {
  const pathname = usePathname();
  const isActive =
    pathname === item.href || pathname.startsWith(`${item.href}/`);
  const Icon = item.icon;
  const enterpriseLocked = isCommunity && item.enterpriseOnly;

  const link = (
    <Link
      href={item.href}
      title={
        enterpriseLocked
          ? `${item.title} requires SaaSShadow Enterprise (not in Community Edition)`
          : item.title
      }
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        isActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/70",
        enterpriseLocked && "border border-transparent hover:border-amber-500/25",
        collapsed && "justify-center px-2",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.title}</span>}
      {!collapsed && enterpriseLocked && (
        <span className="ml-auto shrink-0 rounded-full bg-amber-500/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300">
          Enterprise
        </span>
      )}
      {!collapsed && item.badge && !enterpriseLocked && (
        <span className="ml-auto rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
          {item.badge}
        </span>
      )}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right" className="flex max-w-xs flex-col gap-1">
          <span>{item.title}</span>
          {enterpriseLocked ? (
            <span className="text-[11px] text-amber-600 dark:text-amber-400">
              Enterprise only (not in Community Edition)
            </span>
          ) : null}
        </TooltipContent>
      </Tooltip>
    );
  }

  return link;
}

function SidebarContent({ collapsed }: { collapsed: boolean }) {
  const { isCommunity } = useEditionContext();

  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          "flex h-14 items-center border-b border-sidebar-border px-4",
          collapsed && "justify-center px-2",
        )}
      >
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
            <Shield className="h-4 w-4 text-primary-foreground" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight text-sidebar-foreground">
                SaaSShadow
              </span>
              <span className="text-[10px] font-medium uppercase tracking-widest text-sidebar-foreground/50">
                {isCommunity ? "Community Edition" : "Enterprise"}
              </span>
            </div>
          )}
        </Link>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {navigation.map((group) => (
          <div key={group.label} className="mb-3">
            {!collapsed && (
              <p className="mb-1.5 flex items-center gap-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">
                <span>{group.label}</span>
                {isCommunity && group.enterpriseOnly ? (
                  <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-bold normal-case tracking-normal text-amber-700 dark:text-amber-300">
                    Enterprise
                  </span>
                ) : null}
              </p>
            )}
            {collapsed && group.label !== navigation[0].label && (
              <Separator className="mx-auto my-2 w-6 bg-sidebar-border" />
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  collapsed={collapsed}
                  isCommunity={isCommunity}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        {!collapsed && isCommunity ? (
          <p className="px-3 pb-2 text-[10px] leading-snug text-sidebar-foreground/45">
            Items marked Enterprise are visible but not available in Community
            Edition.
          </p>
        ) : null}
        <div
          className={cn(
            "flex items-center gap-2 rounded-md px-3 py-2",
            collapsed && "justify-center px-2",
          )}
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
            S
          </div>
          {!collapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="truncate text-xs font-medium text-sidebar-foreground">
                Security Team
              </span>
              <span className="truncate text-[10px] text-sidebar-foreground/50">
                admin@company.io
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function AppSidebar() {
  const { state, open, toggleSidebar, openMobile, setOpenMobile, isMobile } =
    useSidebar();
  const collapsed = state === "collapsed";

  if (isMobile) {
    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile}>
        <SheetContent side="left" className="w-[var(--sidebar-width-mobile)] p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarContent collapsed={false} />
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside
      className={cn(
        "relative hidden border-r border-sidebar-border bg-sidebar transition-[width] duration-200 ease-in-out md:block",
        open ? "w-[var(--sidebar-width)]" : "w-[var(--sidebar-width-collapsed)]",
      )}
    >
      <SidebarContent collapsed={collapsed} />
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleSidebar}
        className="absolute -right-3 top-[1.1rem] z-40 h-6 w-6 rounded-full border bg-background shadow-sm"
      >
        <ChevronLeft
          className={cn(
            "h-3 w-3 transition-transform duration-200",
            collapsed && "rotate-180",
          )}
        />
        <span className="sr-only">Toggle sidebar</span>
      </Button>
    </aside>
  );
}
