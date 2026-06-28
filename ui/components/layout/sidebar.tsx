"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1hWS1NRPT06OTM0NTlmNWQ=

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FolderKanban,
  FileText,
  PlayCircle,
  ClipboardList,
  BarChart3,
  ChevronDown,
  Settings,
  Home,
  Database,
  Globe,
  Layers,
  Shield,
  Smartphone,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ProjectInfo } from "@/lib/api/types";
import { useLanguage } from "@/providers/LanguageProvider";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1hWS1NRPT06OTM0NTlmNWQ=

interface SidebarProps {
  projects: ProjectInfo[];
  currentProject?: ProjectInfo | null;
  onProjectChange?: (project: ProjectInfo) => void;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1hWS1NRPT06OTM0NTlmNWQ=

export function Sidebar({
  projects,
  currentProject,
  onProjectChange,
}: SidebarProps) {
  const pathname = usePathname();
  const { t } = useLanguage();

  const navItems = [
    {
      title: t("nav.testCases"),
      href: "/test-cases",
      icon: FileText,
    },
    {
      title: t("nav.apiTests"),
      href: "/api-tests",
      icon: Database,
    },
    {
      title: t("nav.webTests"),
      href: "/web-tests",
      icon: Globe,
    },
    {
      title: t("nav.androidTests"),
      href: "/android-tests",
      icon: Smartphone,
    },
    {
      title: t("nav.pentest"),
      href: "/pentest",
      icon: Shield,
    },
    {
      title: t("nav.testRuns"),
      href: "/test-runs",
      icon: PlayCircle,
    },
    // {
    //   title: t("nav.testPlans"),
    //   href: "/test-plans",
    //   icon: ClipboardList,
    // },
    // {
    //   title: t("nav.reports"),
    //   href: "/reports",
    //   icon: BarChart3,
    // },
    {
      title: t("nav.fullstackAnalysis"),
      href: "/fullstack-analysis",
      icon: Layers,
    },
  ];

  const getNavHref = (baseHref: string) => {
    if (!currentProject) return "#";
    return `/projects/${currentProject.identifier}${baseHref}`;
  };

  const isActive = (href: string) => {
    if (!currentProject) return false;
    const fullHref = getNavHref(href);
    return pathname.startsWith(fullHref);
  };

  return (
    <div className="flex h-full w-60 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/projects" className="flex items-center gap-2">
          <img src="/logo.svg" alt="logo" className="h-6 w-6" />
          <span className="font-semibold">{t("meta.title")}</span>
        </Link>
      </div>

      {/* Project Selector */}
      <div className="border-b p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className="w-full justify-between"
              disabled={projects.length === 0}
            >
              <span className="truncate">
                {currentProject?.name || t("nav.selectProject")}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-52">
            {projects.map((project) => (
              <DropdownMenuItem
                key={project.identifier}
                onClick={() => onProjectChange?.(project)}
                className={cn(
                  currentProject?.identifier === project.identifier &&
                    "bg-accent"
                )}
              >
                <span className="truncate">{project.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-2">
        <nav className="flex flex-col gap-1">
          <Link href="/projects">
            <Button
              variant={pathname === "/projects" ? "secondary" : "ghost"}
              className="w-full justify-start"
            >
              <Home className="mr-2 h-4 w-4" />
              {t("nav.allProjects")}
            </Button>
          </Link>

          {currentProject && (
            <>
              <div className="my-2 px-2 text-xs font-medium text-muted-foreground">
                {t("nav.projectNavigation")}
              </div>
              {navItems.map((item) => (
                <Link key={item.href} href={getNavHref(item.href)}>
                  <Button
                    variant={isActive(item.href) ? "secondary" : "ghost"}
                    className="w-full justify-start"
                  >
                    <item.icon className="mr-2 h-4 w-4" />
                    {item.title}
                  </Button>
                </Link>
              ))}
            </>
          )}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t p-3">
        <Button variant="ghost" className="w-full justify-start">
          <Settings className="mr-2 h-4 w-4" />
          {t("nav.settings")}
        </Button>
      </div>
    </div>
  );
}

// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1hWS1NRPT06OTM0NTlmNWQ=
