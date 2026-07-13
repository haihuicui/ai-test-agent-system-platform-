import useSWR, { mutate as globalMutate } from "swr";
import { getProjects } from "@/lib/api/projects";
import type { ProjectInfo } from "@/lib/api/types";

export const PROJECTS_SWR_KEY = ["projects", "list", { page_size: 100 }] as const;

async function fetchProjects(): Promise<ProjectInfo[]> {
  const response = await getProjects({ page_size: 100 });
  return response.success && response.data ? response.data : [];
}

export function useProjects() {
  const { data: projects = [], error, isLoading, mutate } = useSWR<ProjectInfo[]>(
    PROJECTS_SWR_KEY,
    fetchProjects,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 5 * 60 * 1000, // 5 分钟
    }
  );

  return {
    projects,
    error,
    isLoading,
    mutate,
    revalidate: () => mutate(),
  };
}

export function invalidateProjects() {
  return globalMutate(PROJECTS_SWR_KEY);
}
