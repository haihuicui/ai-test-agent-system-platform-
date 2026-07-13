"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpGM1ZRPT06MTUwOTM3ZTA=

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import useSWR from "swr";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { getProjects } from "@/lib/api/projects";
import type { ProjectInfo } from "@/lib/api/types";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpGM1ZRPT06MTUwOTM3ZTA=

interface MainLayoutProps {
  children: React.ReactNode;
  title?: string;
  headerContent?: React.ReactNode;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpGM1ZRPT06MTUwOTM3ZTA=

const PROJECTS_SWR_KEY = ["projects", "list", { page_size: 100 }] as const;

async function fetchProjects(): Promise<ProjectInfo[]> {
  const response = await getProjects({ page_size: 100 });
  return response.success && response.data ? response.data : [];
}

export function MainLayout({ children, title, headerContent }: MainLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();

  // 从 URL 中提取项目 ID
  const projectIdFromUrl = React.useMemo(() => {
    const match = pathname.match(/\/projects\/([^/]+)/);
    return match ? match[1] : null;
  }, [pathname]);

  // 使用 SWR 缓存项目列表，避免每次路由切换都重新请求
  const { data: projects = [] } = useSWR<ProjectInfo[]>(
    PROJECTS_SWR_KEY,
    fetchProjects,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 5 * 60 * 1000, // 5 分钟
    }
  );

  const currentProject = React.useMemo(() => {
    if (!projectIdFromUrl || !projects.length) return null;
    return projects.find((p) => p.identifier === projectIdFromUrl) || null;
  }, [projects, projectIdFromUrl]);

  // 处理项目切换
  const handleProjectChange = React.useCallback(
    (project: ProjectInfo) => {
      // 导航到新项目的测试用例页面
      router.push(`/projects/${project.identifier}/test-cases`);
    },
    [router]
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        projects={projects}
        currentProject={currentProject}
        onProjectChange={handleProjectChange}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header title={title}>{headerContent}</Header>
        <main className="flex-1 overflow-auto bg-muted/30 p-6">{children}</main>
      </div>
    </div>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpGM1ZRPT06MTUwOTM3ZTA=

