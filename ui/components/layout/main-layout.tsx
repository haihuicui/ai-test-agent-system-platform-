"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpGM1ZRPT06MTUwOTM3ZTA=

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
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

export function MainLayout({ children, title, headerContent }: MainLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [projects, setProjects] = React.useState<ProjectInfo[]>([]);
  const [currentProject, setCurrentProject] = React.useState<ProjectInfo | null>(
    null
  );
  const [loading, setLoading] = React.useState(true);

  // 从 URL 中提取项目 ID
  const projectIdFromUrl = React.useMemo(() => {
    const match = pathname.match(/\/projects\/([^/]+)/);
    return match ? match[1] : null;
  }, [pathname]);

  // 加载项目列表
  React.useEffect(() => {
    const loadProjects = async () => {
      try {
        const response = await getProjects({ page_size: 100 });
        if (response.success && response.data) {
          setProjects(response.data);

          // 如果 URL 中有项目 ID，设置当前项目
          if (projectIdFromUrl) {
            const project = response.data.find(
              (p) => p.identifier === projectIdFromUrl
            );
            if (project) {
              setCurrentProject(project);
            }
          }
        }
      } catch (error) {
        console.error("Failed to load projects:", error);
      } finally {
        setLoading(false);
      }
    };

    loadProjects();
  }, [projectIdFromUrl]);

  // 处理项目切换
  const handleProjectChange = (project: ProjectInfo) => {
    setCurrentProject(project);
    // 导航到新项目的测试用例页面
    router.push(`/projects/${project.identifier}/test-cases`);
  };

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

