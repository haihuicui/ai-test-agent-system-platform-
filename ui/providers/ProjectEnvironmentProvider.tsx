"use client";

import * as React from "react";
import { listEnvironments } from "@/lib/api/environments";
import type { EnvironmentInfo } from "@/lib/api/types";

interface ProjectEnvironmentContextType {
  environments: EnvironmentInfo[];
  selectedEnvironmentId: string | null;
  setSelectedEnvironmentId: (id: string | null) => void;
  selectedEnvironment: EnvironmentInfo | null;
  loading: boolean;
  refreshEnvironments: () => Promise<void>;
}

const ProjectEnvironmentContext = React.createContext<
  ProjectEnvironmentContextType | undefined
>(undefined);

function getStorageKey(projectId: string) {
  return `project-env-${projectId}`;
}

interface ProjectEnvironmentProviderProps {
  projectId: string;
  children: React.ReactNode;
}

export function ProjectEnvironmentProvider({
  projectId,
  children,
}: ProjectEnvironmentProviderProps) {
  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentIdState] = React.useState<
    string | null
  >(null);
  const [loading, setLoading] = React.useState(false);

  // 加载环境列表
  const loadEnvironments = React.useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await listEnvironments(projectId);
      const envs = res.data || [];
      setEnvironments(envs);

      // 如果没有选中环境，尝试恢复 localStorage 中的选择
      const savedId = localStorage.getItem(getStorageKey(projectId));
      const stillExists = envs.some((e) => e.id === savedId);

      if (savedId && stillExists) {
        setSelectedEnvironmentIdState(savedId);
      } else if (envs.length > 0) {
        // 优先选择默认环境
        const defaultEnv =
          envs.find((e) => e.is_default) || envs[0];
        setSelectedEnvironmentIdState(defaultEnv.id);
      } else {
        setSelectedEnvironmentIdState(null);
      }
    } catch (error) {
      console.error("Failed to load environments:", error);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  React.useEffect(() => {
    loadEnvironments();
  }, [loadEnvironments]);

  const setSelectedEnvironmentId = React.useCallback(
    (id: string | null) => {
      setSelectedEnvironmentIdState(id);
      if (id) {
        localStorage.setItem(getStorageKey(projectId), id);
      } else {
        localStorage.removeItem(getStorageKey(projectId));
      }
    },
    [projectId]
  );

  const selectedEnvironment = React.useMemo(() => {
    return environments.find((e) => e.id === selectedEnvironmentId) || null;
  }, [environments, selectedEnvironmentId]);

  const value = React.useMemo(
    () => ({
      environments,
      selectedEnvironmentId,
      setSelectedEnvironmentId,
      selectedEnvironment,
      loading,
      refreshEnvironments: loadEnvironments,
    }),
    [
      environments,
      selectedEnvironmentId,
      setSelectedEnvironmentId,
      selectedEnvironment,
      loading,
      loadEnvironments,
    ]
  );

  return (
    <ProjectEnvironmentContext.Provider value={value}>
      {children}
    </ProjectEnvironmentContext.Provider>
  );
}

export function useProjectEnvironment() {
  const context = React.useContext(ProjectEnvironmentContext);
  if (!context) {
    throw new Error(
      "useProjectEnvironment must be used within a ProjectEnvironmentProvider"
    );
  }
  return context;
}
