import { apiClient } from "./client";
import type {
  EnvironmentInfo,
  EnvironmentCreate,
  EnvironmentUpdate,
  SuccessResponse,
  MessageResponse,
} from "./types";

export function listEnvironments(projectId: string) {
  return apiClient.get<SuccessResponse<EnvironmentInfo[]>>(
    `/projects/${projectId}/environments`
  );
}

export function createEnvironment(
  projectId: string,
  data: EnvironmentCreate
) {
  return apiClient.post<SuccessResponse<EnvironmentInfo>>(
    `/projects/${projectId}/environments`,
    data
  );
}

export function updateEnvironment(
  projectId: string,
  envId: string,
  data: EnvironmentUpdate
) {
  return apiClient.patch<SuccessResponse<EnvironmentInfo>>(
    `/projects/${projectId}/environments/${envId}`,
    data
  );
}

export function testEnvironmentConnection(projectId: string, envId: string) {
  return apiClient.post<SuccessResponse<{ success: boolean; token_length?: number; token_preview?: string; cache_ttl_seconds?: number; error?: string }>>(
    `/projects/${projectId}/environments/${envId}/test-connection`
  );
}

export function deleteEnvironment(projectId: string, envId: string) {
  return apiClient.delete<SuccessResponse<MessageResponse>>(
    `/projects/${projectId}/environments/${envId}`
  );
}
