/**
 * Web 测试相关的 API 客户端函数
 */
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW10TVNRPT06YjBlNzVmMmE=

import { apiClient } from "./client";

// ==================== 类型定义 ====================

export interface WebTest {
  id: string;
  identifier: string;
  name: string;
  description?: string;
  base_url?: string;
  script_path: string;
  script_format: string;
  script_language: string;
  test_config?: Record<string, unknown>;
  target_pages?: string[];
  test_flows?: Record<string, unknown>[];
  total_pages: number;
  total_flows: number;
  folder_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface WebTestRun {
  id: string;
  identifier: string;
  status: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  duration_ms?: number;
  error_message?: string;
  created_at: string;
}

export interface WebPage {
  id: string;
  display_name: string;
  url: string;
  page_title?: string;
  description?: string;
  page_type: string;
  elements?: Record<string, unknown>[];
  navigation?: Record<string, unknown>;
  tags?: string[];
  tag_group?: string;
  folder_id?: string;
  total_test_cases: number;
  total_test_runs: number;
  last_run_status?: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateWebTestRequest {
  name: string;
  base_url: string;
  script_path: string;
  script_format?: string;
  script_language?: string;
  description?: string;
  test_config?: Record<string, unknown>;
  folder_id?: string;
  target_pages?: string[];
  test_flows?: Record<string, unknown>[];
}

// ==================== Web Test API 函数 ====================
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW10TVNRPT06YjBlNzVmMmE=

export async function listWebTests(
  projectIdentifier: string,
  params?: {
    page?: number;
    page_size?: number;
    search?: string;
    script_format?: string;
  }
): Promise<{ items: WebTest[]; total: number; page: number; page_size: number }> {
  const response = await apiClient.get<{ success: boolean; data: { items: WebTest[]; total: number; page: number; page_size: number } }>(
    `/projects/${projectIdentifier}/web-tests`,
    { params }
  );
  return response.data;
}

export async function getFolderWebTests(
  projectIdentifier: string,
  folderId: string | null,
  params?: {
    page?: number;
    page_size?: number;
  }
): Promise<{ items: WebTest[]; total: number; page: number; page_size: number }> {
  const url = folderId
    ? `/projects/${projectIdentifier}/web-tests/folder/${folderId}`
    : `/projects/${projectIdentifier}/web-tests`;

  const response = await apiClient.get<{ success: boolean; data: { items: WebTest[]; total: number; page: number; page_size: number } }>(
    url, { params }
  );
  return response.data;
}

export async function getWebTest(
  projectIdentifier: string,
  webTestId: string
): Promise<WebTest> {
  const response = await apiClient.get<{ data: WebTest }>(
    `/projects/${projectIdentifier}/web-tests/${webTestId}`
  );
  return response.data;
}

export async function createWebTest(
  projectIdentifier: string,
  data: CreateWebTestRequest
): Promise<WebTest> {
  const formData = new FormData();
  formData.append("name", data.name);
  formData.append("base_url", data.base_url);
  formData.append("script_path", data.script_path);
  formData.append("script_format", data.script_format || "playwright");
  formData.append("script_language", data.script_language || "typescript");

  if (data.description) {
    formData.append("description", data.description);
  }
  if (data.test_config) {
    formData.append("test_config", JSON.stringify(data.test_config));
  }
  if (data.folder_id) {
    formData.append("folder_id", data.folder_id);
  }
  if (data.target_pages) {
    formData.append("target_pages", JSON.stringify(data.target_pages));
  }
  if (data.test_flows) {
    formData.append("test_flows", JSON.stringify(data.test_flows));
  }

  const response = await fetch(`/api/v2/projects/${projectIdentifier}/web-tests`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to create web test");
  }

  const result = await response.json();
  return result.data;
}

export async function updateWebTest(
  projectIdentifier: string,
  webTestId: string,
  data: {
    name?: string;
    description?: string;
    test_config?: Record<string, unknown>;
  }
): Promise<WebTest> {
  const response = await apiClient.patch<{ data: WebTest }>(
    `/projects/${projectIdentifier}/web-tests/${webTestId}`,
    data
  );
  return response.data;
}

export async function deleteWebTest(
  projectIdentifier: string,
  webTestId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectIdentifier}/web-tests/${webTestId}`
  );
}

export async function getWebTestScript(
  projectIdentifier: string,
  webTestId: string
): Promise<string> {
  const response = await fetch(
    `/api/v2/projects/${projectIdentifier}/web-tests/${webTestId}/script`
  );

  if (!response.ok) {
    throw new Error("Failed to get script");
  }

  return await response.text();
}

export async function updateWebTestScript(
  projectIdentifier: string,
  webTestId: string,
  scriptContent: string
): Promise<void> {
  const formData = new FormData();
  formData.append("script_content", scriptContent);

  await apiClient.put(
    `/projects/${projectIdentifier}/web-tests/${webTestId}/script`,
    formData as unknown as Record<string, unknown>
  );
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW10TVNRPT06YjBlNzVmMmE=

export async function runWebTest(
  projectIdentifier: string,
  webTestId: string,
  executionConfig?: Record<string, unknown>
): Promise<{ run_id: string; status: string }> {
  const response = await apiClient.post<{ data: { run_id: string; status: string } }>(
    `/projects/${projectIdentifier}/web-tests/${webTestId}/run`,
    { execution_config: executionConfig }
  );
  return response.data;
}

export async function getWebTestRuns(
  projectIdentifier: string,
  webTestId: string,
  params?: {
    page?: number;
    page_size?: number;
  }
): Promise<{ items: WebTestRun[]; total: number; page: number; page_size: number }> {
  const response = await apiClient.get<{ success: boolean; data: { items: WebTestRun[]; total: number; page: number; page_size: number } }>(
    `/projects/${projectIdentifier}/web-tests/${webTestId}/runs`,
    { params }
  );
  return response.data;
}

// ==================== Web Page API 函数 ====================

export async function listWebPages(
  projectIdentifier: string,
  params?: {
    page?: number;
    page_size?: number;
    folder_id?: string;
    search?: string;
  }
): Promise<{ items: WebPage[]; total: number; page: number; page_size: number }> {
  return apiClient.get(
    `/projects/${projectIdentifier}/web-pages`,
    { params }
  );
}

export async function getWebPage(
  pageId: string
): Promise<WebPage> {
  const response = await apiClient.get<{ data: WebPage }>(
    `/projects/web-pages/${pageId}`
  );
  return response.data;
}

export async function createWebPage(
  projectIdentifier: string,
  data: {
    display_name: string;
    url: string;
    folder_id?: string;
    page_title?: string;
    description?: string;
    page_type?: string;
    elements?: Record<string, unknown>[];
    navigation?: Record<string, unknown>;
    tags?: string[];
    tag_group?: string;
  }
): Promise<WebPage> {
  const response = await apiClient.post<{ data: WebPage }>(
    `/projects/${projectIdentifier}/web-pages`,
    data
  );
  return response.data;
}

export async function updateWebPage(
  pageId: string,
  data: {
    display_name?: string;
    url?: string;
    description?: string;
    elements?: Record<string, unknown>[];
    navigation?: Record<string, unknown>;
  }
): Promise<WebPage> {
  const response = await apiClient.patch<{ data: WebPage }>(
    `/projects/web-pages/${pageId}`,
    data
  );
  return response.data;
}

export async function deleteWebPage(
  pageId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/web-pages/${pageId}`
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW10TVNRPT06YjBlNzVmMmE=
