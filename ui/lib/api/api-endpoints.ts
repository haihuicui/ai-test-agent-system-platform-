import { apiClient } from "./client";
import type { APITestResult } from "./api-tests";

// ==================== 类型定义 ====================
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtZMFRRPT06NTVmZGIyMGQ=

export interface APIEndpoint {
  id: string;
  display_name: string;
  path: string;
  method: string;
  summary: string | null;
  description: string | null;
  tag_group: string | null;
  parameters: any[] | null;
  request_body: any | null;
  responses: any | null;
  folder_id: string | null;
  project_id: number;
  sort_order: number;
  total_test_cases: number;
  total_test_runs: number;
  last_run_status: string | null;
  api_test_ids: string[] | null;
  created_at: string;
  updated_at: string | null;
}

export interface APIEndpointListResponse {
  success: boolean;
  data: APIEndpoint[];
}

// ==================== API 函数 ====================
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtZMFRRPT06NTVmZGIyMGQ=

/**
 * 获取项目的 API 端点列表
 */
export async function listAPIEndpoints(
  projectIdentifier: string,
  params?: {
    folder_id?: string;
    tag_group?: string;
  }
): Promise<APIEndpoint[]> {
  return apiClient.get<APIEndpoint[]>(
    `/projects/${projectIdentifier}/api-endpoints`,
    { params }
  );
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtZMFRRPT06NTVmZGIyMGQ=

/**
 * 获取 API 端点详情
 */
export async function getAPIEndpoint(
  endpointId: string
): Promise<APIEndpoint> {
  return apiClient.get<APIEndpoint>(
    `/api-endpoints/${endpointId}`
  );
}

/**
 * 获取 API 端点关联的测试脚本
 */
export async function getEndpointTestScripts(
  endpointId: string
): Promise<{
  endpoint_id: string;
  test_scripts: Array<{
    id: string;
    name: string;
    identifier: string;
    script_format: string;
    script_language: string;
    total_endpoints: number;
    total_scenarios: number;
    created_at: string;
    updated_at: string;
  }>;
}> {
  return apiClient.get<{
    endpoint_id: string;
    test_scripts: Array<any>;
  }>(
    `/api-endpoints/${endpointId}/test-scripts`
  );
}

/**
 * 获取 API 端点的测试执行报告
 */
export async function getEndpointTestRuns(
  endpointId: string,
  limit: number = 10
): Promise<{
  endpoint_id: string;
  test_runs: Array<{
    id: string;
    api_test_id: string;
    status: string;
    total_scenarios: number;
    passed_scenarios: number;
    failed_scenarios: number;
    skipped_scenarios: number;
    duration: number;
    report_path?: string | null;
    report_attachment_id?: string | null;
    created_at: string;
  }>;
  total_runs: number;
  last_run_status: string | null;
}> {
  return apiClient.get<{
    endpoint_id: string;
    test_runs: Array<any>;
    total_runs: number;
    last_run_status: string | null;
  }>(
    `/api-endpoints/${endpointId}/test-runs`,
    { params: { limit } }
  );
}

/**
 * 获取 API 端点某次测试运行的详细结果。
 */
export async function getEndpointRunResults(
  endpointId: string,
  runId: string,
  apiTestId: string,
  params?: {
    page?: number;
    page_size?: number;
  }
): Promise<{
  items: APITestResult[];
  total: number;
  page: number;
  page_size: number;
}> {
  return apiClient.get<{
    items: APITestResult[];
    total: number;
    page: number;
    page_size: number;
  }>(
    `/api-endpoints/${endpointId}/runs/${runId}/results`,
    { params: { ...params, api_test_id: apiTestId } }
  );
}

/**
 * 更新 API 端点
 */
export async function updateAPIEndpoint(
  endpointId: string,
  data: {
    display_name?: string;
    path?: string;
    method?: string;
    summary?: string;
    description?: string;
    tag_group?: string;
    parameters?: any[] | null;
    request_body?: any | null;
    responses?: any | null;
    custom_config?: any;
    total_test_cases?: number;
    total_test_runs?: number;
    last_run_status?: string;
    api_test_ids?: string[];
  }
): Promise<APIEndpoint> {
  return apiClient.patch<APIEndpoint>(
    `/api-endpoints/${endpointId}`,
    data
  );
}

/**
 * 删除 API 端点
 */
export async function deleteAPIEndpoint(
  endpointId: string
): Promise<void> {
  return apiClient.delete(
    `/api-endpoints/${endpointId}`
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtZMFRRPT06NTVmZGIyMGQ=
