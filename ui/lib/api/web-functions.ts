/**
 * Web 功能和子功能相关的 API 客户端函数
 */

import { apiClient } from "./client";

// ==================== 类型定义 ====================

export interface WebFunction {
  id: string;
  identifier: string;
  display_name: string;
  name: string;
  description: string | null;
  base_url: string | null;
  business_module: string | null;
  navigation: any;
  pages: any;
  tags: any;
  custom_config: any;
  folder_id: string | null;
  total_sub_functions: number;
  total_test_cases: number;
  total_test_runs: number;
  last_run_status: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string | null;
}

export interface WebSubFunction {
  id: string;
  identifier: string;
  function_id: string;
  display_name: string;
  name: string;
  description: string | null;
  test_type: string;
  target_pages: any;
  test_scenario: string | null;
  test_data: any;
  expected_results: any;
  priority: string;
  tags: any;
  custom_config: any;
  folder_id: string | null;
  total_test_cases: number;
  total_test_runs: number;
  last_run_status: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string | null;
}
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkV4QmJBPT06ZmY2MDg0Zjc=

export interface CreateWebFunctionRequest {
  display_name: string;
  name: string;
  business_module: string;
  folder_id?: string;
  description?: string;
  base_url?: string;
  navigation?: any;
  pages?: any;
  tags?: any;
  custom_config?: any;
  sort_order?: number;
}

export interface UpdateWebFunctionRequest {
  display_name?: string;
  name?: string;
  description?: string;
  base_url?: string;
  business_module?: string;
  navigation?: any;
  pages?: any;
  tags?: any;
  custom_config?: any;
  sort_order?: number;
}

export interface CreateWebSubFunctionRequest {
  function_id: string;
  display_name: string;
  name: string;
  folder_id?: string;
  description?: string;
  test_type?: string;
  target_pages?: any;
  test_scenario?: string;
  test_data?: any;
  expected_results?: any;
  priority?: string;
  tags?: any;
  custom_config?: any;
  sort_order?: number;
}

export interface UpdateWebSubFunctionRequest {
  display_name?: string;
  name?: string;
  description?: string;
  test_type?: string;
  target_pages?: any;
  test_scenario?: string;
  test_data?: any;
  expected_results?: any;
  priority?: string;
  tags?: any;
  custom_config?: any;
  sort_order?: number;
}

export interface WebFunctionListResponse {
  items: WebFunction[];
  total: number;
  offset: number;
  limit: number;
}

export interface WebSubFunctionListResponse {
  items: WebSubFunction[];
  total: number;
  offset: number;
  limit: number;
}

// ==================== Web 功能 API 函数 ====================
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkV4QmJBPT06ZmY2MDg0Zjc=

/**
 * 获取项目的 Web 功能列表
 */
export async function listWebFunctions(
  projectIdentifier: string,
  params?: {
    p?: number;
    page_size?: number;
    folder_id?: string;
    search?: string;
  }
): Promise<WebFunctionListResponse> {
  const response = await apiClient.get<{ data: WebFunctionListResponse }>(
    `/projects/${projectIdentifier}/web-functions`,
    { params }
  );
  return response.data;
}

/**
 * 获取 Web 功能详情
 */
export async function getWebFunction(
  projectIdentifier: string,
  functionId: string
): Promise<WebFunction> {
  const response = await apiClient.get<{ data: WebFunction }>(
    `/projects/${projectIdentifier}/web-functions/${functionId}`
  );
  return response.data;
}

/**
 * 创建 Web 功能
 */
export async function createWebFunction(
  projectIdentifier: string,
  data: CreateWebFunctionRequest
): Promise<WebFunction> {
  const response = await apiClient.post<{ data: WebFunction }>(
    `/projects/${projectIdentifier}/web-functions`,
    data
  );
  return response.data;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkV4QmJBPT06ZmY2MDg0Zjc=

/**
 * 更新 Web 功能
 */
export async function updateWebFunction(
  projectIdentifier: string,
  functionId: string,
  data: UpdateWebFunctionRequest
): Promise<WebFunction> {
  const response = await apiClient.patch<{ data: WebFunction }>(
    `/projects/${projectIdentifier}/web-functions/${functionId}`,
    data
  );
  return response.data;
}

/**
 * 删除 Web 功能
 */
export async function deleteWebFunction(
  projectIdentifier: string,
  functionId: string
): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete<{ data: { success: boolean; message: string } }>(
    `/projects/${projectIdentifier}/web-functions/${functionId}`
  );
  return response.data;
}

// ==================== Web 子功能 API 函数 ====================

/**
 * 获取项目的 Web 子功能列表
 */
export async function listWebSubFunctions(
  projectIdentifier: string,
  params?: {
    p?: number;
    page_size?: number;
    function_id?: string;
    folder_id?: string;
    search?: string;
  }
): Promise<WebSubFunctionListResponse> {
  const response = await apiClient.get<{ data: WebSubFunctionListResponse }>(
    `/projects/${projectIdentifier}/web-functions/sub-functions`,
    { params }
  );
  return response.data;
}

/**
 * 获取 Web 子功能详情
 */
export async function getWebSubFunction(
  projectIdentifier: string,
  subFunctionId: string
): Promise<WebSubFunction> {
  const response = await apiClient.get<{ data: WebSubFunction }>(
    `/projects/${projectIdentifier}/web-functions/sub-functions/${subFunctionId}`
  );
  return response.data;
}

/**
 * 创建 Web 子功能
 */
export async function createWebSubFunction(
  projectIdentifier: string,
  data: CreateWebSubFunctionRequest
): Promise<WebSubFunction> {
  const response = await apiClient.post<{ data: WebSubFunction }>(
    `/projects/${projectIdentifier}/web-functions/sub-functions`,
    data
  );
  return response.data;
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkV4QmJBPT06ZmY2MDg0Zjc=

/**
 * 更新 Web 子功能
 */
export async function updateWebSubFunction(
  projectIdentifier: string,
  subFunctionId: string,
  data: UpdateWebSubFunctionRequest
): Promise<WebSubFunction> {
  const response = await apiClient.patch<{ data: WebSubFunction }>(
    `/projects/${projectIdentifier}/web-functions/sub-functions/${subFunctionId}`,
    data
  );
  return response.data;
}

/**
 * 删除 Web 子功能
 */
export async function deleteWebSubFunction(
  projectIdentifier: string,
  subFunctionId: string
): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete<{ data: { success: boolean; message: string } }>(
    `/projects/${projectIdentifier}/web-functions/sub-functions/${subFunctionId}`
  );
  return response.data;
}

/**
 * 获取文件夹下的 Web 功能
 */
export async function getFolderWebFunctions(
  projectIdentifier: string,
  folderId: string,
  params?: {
    offset?: number;
    limit?: number;
    search?: string;
  }
): Promise<WebFunctionListResponse> {
  const response = await apiClient.get<{ data: WebFunctionListResponse }>(
    `/projects/${projectIdentifier}/web-functions`,
    {
      params: {
        ...params,
        folder_id: folderId,
      },
    }
  );
  return response.data;
}

/**
 * 获取文件夹下的 Web 子功能
 */
export async function getFolderWebSubFunctions(
  projectIdentifier: string,
  folderId: string,
  params?: {
    offset?: number;
    limit?: number;
    search?: string;
  }
): Promise<WebSubFunctionListResponse> {
  const response = await apiClient.get<{ data: WebSubFunctionListResponse }>(
    `/projects/${projectIdentifier}/web-functions/sub-functions`,
    {
      params: {
        ...params,
        folder_id: folderId,
      },
    }
  );
  return response.data;
}

// ==================== Web 功能批量执行 API ====================

export interface BatchRunWebFunctionsRequest {
  function_ids: string[];
}

export interface BatchRunWebFunctionsResponse {
  test_run_id: string;
  identifier: string;
  status: string;
  job_count: number;
  skipped_count: number;
}

/**
 * 批量运行选中的 Web 功能（执行其下所有子功能的测试脚本）
 */
export async function batchRunWebFunctions(
  projectIdentifier: string,
  data: BatchRunWebFunctionsRequest
): Promise<BatchRunWebFunctionsResponse> {
  const response = await apiClient.post<{ data: BatchRunWebFunctionsResponse }>(
    `/projects/${projectIdentifier}/web-functions/batch-run`,
    data
  );
  return response.data;
}
