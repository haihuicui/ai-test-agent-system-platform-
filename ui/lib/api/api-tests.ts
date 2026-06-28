/**
 * API 测试相关的 API 客户端函数
 */

import { apiClient } from "./client";
import { ApiError } from "./client";
import { t } from "@/lib/translations";

// ==================== 类型定义 ====================

export interface APITest {
  id: string;
  identifier: string;
  name: string;
  description?: string;
  schema_url?: string;
  schema_path?: string;
  schema_type: string;
  script_path: string;
  script_format: string;
  script_language: string;
  test_config?: Record<string, unknown>;
  total_endpoints: number;
  total_scenarios: number;
  test_case_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface APITestRun {
  id: string;
  identifier: string;
  status: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  duration_ms?: number;
  progress?: number;
  error_message?: string;
  report_path?: string;
  created_at: string;
  updated_at?: string;
}

export interface APITestResult {
  id: string;
  scenario_name: string;
  endpoint: string;
  method: string;
  status: string;
  duration_ms?: number;
  retry_count: number;
  error_message?: string;
  created_at: string;
}
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVVd05nPT06N2MwYzNhYjc=

export interface APITestListResponse {
  items: APITest[];
  total: number;
  page: number;
  page_size: number;
}
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVVd05nPT06N2MwYzNhYjc=

export interface APITestRunListResponse {
  items: APITestRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface APITestResultListResponse {
  items: APITestResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateAPITestRequest {
  name: string;
  schema_path: string;
  script_path: string;
  script_format?: string;
  script_language?: string;
  schema_url?: string;
  description?: string;
  test_config?: Record<string, unknown>;
  total_endpoints?: number;
  total_scenarios?: number;
  generation_params?: Record<string, unknown>;
  test_case_id?: string;
}

// ==================== API 函数 ====================

/**
 * 获取 API 测试列表
 */
export async function listAPITests(
  projectIdentifier: string,
  params?: {
    page?: number;
    page_size?: number;
    search?: string;
    script_format?: string;
  }
): Promise<APITestListResponse> {
  const response = await apiClient.get<{ success: boolean; data: APITestListResponse }>(
    `/projects/${projectIdentifier}/api-tests`,
    { params }
  );
  return response.data;
}

/**
 * 获取文件夹下的 API 测试列表
 */
export async function getFolderAPITests(
  projectIdentifier: string,
  folderId: string | null,
  params?: {
    page?: number;
    page_size?: number;
    search?: string;
  }
): Promise<APITestListResponse> {
  const queryParams = params ? new URLSearchParams() : undefined;
  if (params?.page) queryParams?.set('page', String(params.page));
  if (params?.page_size) queryParams?.set('page_size', String(params.page_size));
  if (params?.search) queryParams?.set('search', params.search);

  const url = folderId
    ? `/projects/${projectIdentifier}/folders/${folderId}/api-tests`
    : `/projects/${projectIdentifier}/api-tests`;

  const response = await apiClient.get<{ success: boolean; data: APITestListResponse }>(
    url,
    queryParams ? { params: Object.fromEntries(queryParams) } : undefined
  );
  return response.data;
}

/**
 * 获取 API 测试详情
 */
export async function getAPITest(
  projectIdentifier: string,
  apiTestId: string
): Promise<APITest> {
  const response = await apiClient.get<{ data: APITest }>(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}`
  );
  return response.data;
}

/**
 * 创建 API 测试
 */
export async function createAPITest(
  projectIdentifier: string,
  data: CreateAPITestRequest
): Promise<APITest> {
  const formData = new FormData();
  formData.append("name", data.name);
  formData.append("schema_path", data.schema_path);
  formData.append("script_path", data.script_path);
  formData.append("script_format", data.script_format || "playwright");
  formData.append("script_language", data.script_language || "typescript");

  if (data.schema_url) {
    formData.append("schema_url", data.schema_url);
  }
  if (data.description) {
    formData.append("description", data.description);
  }
  if (data.test_config) {
    formData.append("test_config", JSON.stringify(data.test_config));
  }
  if (data.generation_params) {
    formData.append("generation_params", JSON.stringify(data.generation_params));
  }
  if (data.test_case_id) {
    formData.append("test_case_id", data.test_case_id);
  }

  const response = await fetch(`/api/v2/projects/${projectIdentifier}/api-tests`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(error.detail || t("apiTests.createFailed"), response.status, error);
  }

  const result = await response.json();
  return result.data;
}

/**
 * 更新 API 测试
 */
export async function updateAPITest(
  projectIdentifier: string,
  apiTestId: string,
  data: {
    name?: string;
    description?: string;
    test_config?: Record<string, unknown>;
    test_case_id?: string;
  }
): Promise<APITest> {
  const response = await apiClient.patch<{ data: APITest }>(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}`,
    data
  );
  return response.data;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVVd05nPT06N2MwYzNhYjc=

/**
 * 删除 API 测试
 */
export async function deleteAPITest(
  projectIdentifier: string,
  apiTestId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}`
  );
}

/**
 * 获取测试脚本
 */
export async function getTestScript(
  projectIdentifier: string,
  apiTestId: string
): Promise<string> {
  const response = await fetch(
    `/api/v2/projects/${projectIdentifier}/api-tests/${apiTestId}/script`
  );

  if (!response.ok) {
    throw new ApiError(t("apiTests.getScriptFailed"), response.status);
  }

  return await response.text();
}

/**
 * 更新测试脚本
 */
export async function updateTestScript(
  projectIdentifier: string,
  apiTestId: string,
  scriptContent: string
): Promise<void> {
  const formData = new FormData();
  formData.append("script_content", scriptContent);

  await apiClient.put(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}/script`,
    formData as unknown as Record<string, unknown>
  );
}

/**
 * 执行 API 测试
 */
export async function runAPITest(
  projectIdentifier: string,
  apiTestId: string,
  executionConfig?: Record<string, unknown>
): Promise<{ run_id: string; status: string }> {
  const response = await apiClient.post<{ data: { run_id: string; status: string } }>(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}/run`,
    { execution_config: executionConfig }
  );
  return response.data;
}

/**
 * 获取测试运行历史
 */
export async function getTestRuns(
  projectIdentifier: string,
  apiTestId: string,
  params?: {
    page?: number;
    page_size?: number;
  }
): Promise<APITestRunListResponse> {
  const response = await apiClient.get<{ success: boolean; data: APITestRunListResponse }>(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}/runs`,
    { params }
  );
  return response.data;
}

/**
 * 获取测试运行详情
 */
export async function getTestRun(
  projectIdentifier: string,
  apiTestId: string,
  runId: string
): Promise<APITestRun> {
  const response = await apiClient.get<{ data: APITestRun }>(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}/runs/${runId}`
  );
  return response.data;
}

/**
 * 获取测试结果
 */
export async function getTestResults(
  projectIdentifier: string,
  apiTestId: string,
  runId: string,
  params?: {
    page?: number;
    page_size?: number;
  }
): Promise<APITestResultListResponse> {
  const response = await apiClient.get<{ success: boolean; data: APITestResultListResponse }>(
    `/projects/${projectIdentifier}/api-tests/${apiTestId}/runs/${runId}/results`,
    { params }
  );
  return response.data;
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVVd05nPT06N2MwYzNhYjc=

/**
 * 上传 Schema 文件
 */
export async function uploadSchema(
  projectIdentifier: string,
  file: File
): Promise<{ schema_path: string; schema_url?: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `/api/v2/projects/${projectIdentifier}/api-tests/upload-schema`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(error.detail || t("apiTests.uploadFailed"), response.status, error);
  }

  const result = await response.json();
  return result.data;
}

/**
 * 从 Schema 生成 API 测试（AI 生成）
 */
export async function generateFromSchema(
  projectIdentifier: string,
  params: {
    schema_url?: string;
    schema_path?: string;
    script_format?: string;
    script_language?: string;
    include_auth?: boolean;
    include_security?: boolean;
    include_error_handling?: boolean;
  }
): Promise<{
  test_plan: string;
  test_script: string;
  statistics: {
    total_endpoints: number;
    total_scenarios: number;
  };
}> {
  const formData = new FormData();
  if (params.schema_url) {
    formData.append("schema_url", params.schema_url);
  }
  if (params.schema_path) {
    formData.append("schema_path", params.schema_path);
  }
  formData.append("script_format", params.script_format || "playwright");
  formData.append("script_language", params.script_language || "typescript");
  formData.append("include_auth", String(params.include_auth ?? true));
  formData.append("include_security", String(params.include_security ?? false));
  formData.append("include_error_handling", String(params.include_error_handling ?? true));

  const response = await fetch(
    `/api/v2/projects/${projectIdentifier}/api-tests/generate-from-schema`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(error.detail || t("apiTests.aiGenerateFailed"), response.status, error);
  }

  const result = await response.json();
  return result.data;
}
