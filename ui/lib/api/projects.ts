import { apiClient } from "./client";
import type {
  PaginatedResponse,
  SuccessResponse,
  MessageResponse,
  ProjectInfo,
  ProjectCreate,
  ProjectUpdate,
} from "./types";

// 获取项目列表
export function getProjects(params?: { p?: number; page_size?: number }) {
  return apiClient.get<PaginatedResponse<ProjectInfo>>("/projects", {
    params,
  });
}

// 获取单个项目详情
export function getProject(identifier: string) {
  return apiClient.get<SuccessResponse<ProjectInfo>>(
    `/projects/${identifier}`
  );
}
// WATERMARK  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TjNCaFlRPT06NTk2ZDA4YTE=

// 创建项目
export function createProject(data: ProjectCreate) {
  return apiClient.post<SuccessResponse<ProjectInfo>>("/projects", data);
}

// 更新项目
export function updateProject(identifier: string, data: ProjectUpdate) {
  return apiClient.patch<SuccessResponse<ProjectInfo>>(
    `/projects/${identifier}`,
    data
  );
}

// 删除项目
export function deleteProject(identifier: string) {
  return apiClient.delete<MessageResponse>(`/projects/${identifier}`);
}
// FIXME  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TjNCaFlRPT06NTk2ZDA4YTE=

