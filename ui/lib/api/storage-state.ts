import { apiClient } from "./client";
import type { SuccessResponse } from "./types";

export interface LoginSelectors {
  login_url: string;
  username_selector?: string;
  password_selector?: string;
  captcha_selector?: string;
  submit_selector?: string;
  success_selector?: string;
}

export interface StorageStateGenerateRequest {
  username?: string;
  password: string;
  captcha?: string;
  selectors: LoginSelectors;
  headless?: boolean;
  save_attachment?: boolean;
}

export interface StorageStateJobInfo {
  job_id: string;
  project_id: string;
  environment_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
  output_path: string | null;
  attachment_id: string | null;
  error_message: string | null;
  stdout: string | null;
  stderr: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StorageStateLatestInfo {
  job_id: string;
  environment_id: string | null;
  output_path: string;
  attachment_id: string | null;
  generated_at: string;
  object_name: string | null;
}

export function generateStorageState(
  projectId: string,
  envId: string,
  data: StorageStateGenerateRequest
) {
  return apiClient.post<SuccessResponse<StorageStateJobInfo>>(
    `/projects/${projectId}/environments/${envId}/storage-state/generate`,
    data
  );
}

export function getStorageStateJob(
  projectId: string,
  envId: string,
  jobId: string
) {
  return apiClient.get<SuccessResponse<StorageStateJobInfo>>(
    `/projects/${projectId}/environments/${envId}/storage-state/jobs/${jobId}`
  );
}

export function getLatestStorageState(projectId: string, envId: string) {
  return apiClient.get<SuccessResponse<StorageStateLatestInfo | null>>(
    `/projects/${projectId}/environments/${envId}/storage-state/latest`
  );
}
