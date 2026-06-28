/**
 * Android 测试相关的 API 客户端函数
 */
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWtkMVNRPT06MzllNGNiNjY=

import { apiClient } from "./client";

// ==================== 类型定义 ====================

export interface AndroidFunction {
  id: string;
  identifier: string;
  display_name: string;
  name: string;
  description: string | null;
  app_package: string | null;
  app_activity: string | null;
  device_udid: string | null;
  business_module: string | null;
  script_format: string;
  script_language: string;
  test_config: any;
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

export interface AndroidSubFunction {
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

export interface CreateAndroidFunctionRequest {
  display_name: string;
  name: string;
  folder_id?: string;
  description?: string;
  app_package?: string;
  app_activity?: string;
  device_udid?: string;
  business_module?: string;
  script_format?: string;
  script_language?: string;
  test_config?: any;
  pages?: any;
  tags?: any;
  custom_config?: any;
  sort_order?: number;
}

export interface UpdateAndroidFunctionRequest {
  display_name?: string;
  name?: string;
  description?: string;
  app_package?: string;
  app_activity?: string;
  device_udid?: string;
  business_module?: string;
  script_format?: string;
  script_language?: string;
  test_config?: any;
  pages?: any;
  tags?: any;
  custom_config?: any;
  sort_order?: number;
}

export interface CreateAndroidSubFunctionRequest {
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

export interface UpdateAndroidSubFunctionRequest {
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

export interface AndroidFunctionListResponse {
  items: AndroidFunction[];
  total: number;
  offset: number;
  limit: number;
}

export interface AndroidSubFunctionListResponse {
  items: AndroidSubFunction[];
  total: number;
  offset: number;
  limit: number;
}
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWtkMVNRPT06MzllNGNiNjY=

export interface AndroidDevice {
  udid: string;
  name: string;
  model: string;
  version: string;
  status: "connected" | "disconnected" | "busy" | "offline";
  screen_resolution?: string;
  dpi?: number;
}

// ==================== Android 功能 API 函数 ====================

/**
 * 获取项目的 Android 功能列表
 */
export async function listAndroidFunctions(
  projectIdentifier: string,
  params?: {
    p?: number;
    page_size?: number;
    folder_id?: string;
    search?: string;
  }
): Promise<AndroidFunctionListResponse> {
  const response = await apiClient.get<{ data: AndroidFunctionListResponse }>(
    `/projects/${projectIdentifier}/android-functions`,
    { params }
  );
  return response.data;
}

/**
 * 获取 Android 功能详情
 */
export async function getAndroidFunction(
  projectIdentifier: string,
  functionId: string
): Promise<AndroidFunction> {
  const response = await apiClient.get<{ data: AndroidFunction }>(
    `/projects/${projectIdentifier}/android-functions/${functionId}`
  );
  return response.data;
}

/**
 * 创建 Android 功能
 */
export async function createAndroidFunction(
  projectIdentifier: string,
  data: CreateAndroidFunctionRequest
): Promise<AndroidFunction> {
  const response = await apiClient.post<{ data: AndroidFunction }>(
    `/projects/${projectIdentifier}/android-functions`,
    data
  );
  return response.data;
}

/**
 * 更新 Android 功能
 */
export async function updateAndroidFunction(
  projectIdentifier: string,
  functionId: string,
  data: UpdateAndroidFunctionRequest
): Promise<AndroidFunction> {
  const response = await apiClient.patch<{ data: AndroidFunction }>(
    `/projects/${projectIdentifier}/android-functions/${functionId}`,
    data
  );
  return response.data;
}

/**
 * 删除 Android 功能
 */
export async function deleteAndroidFunction(
  projectIdentifier: string,
  functionId: string
): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete<{ data: { success: boolean; message: string } }>(
    `/projects/${projectIdentifier}/android-functions/${functionId}`
  );
  return response.data;
}

// ==================== Android 子功能 API 函数 ====================
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWtkMVNRPT06MzllNGNiNjY=

/**
 * 获取项目的 Android 子功能列表
 */
export async function listAndroidSubFunctions(
  projectIdentifier: string,
  params?: {
    p?: number;
    page_size?: number;
    function_id?: string;
    folder_id?: string;
    search?: string;
  }
): Promise<AndroidSubFunctionListResponse> {
  const response = await apiClient.get<{ data: AndroidSubFunctionListResponse }>(
    `/projects/${projectIdentifier}/android-functions/sub-functions`,
    { params }
  );
  return response.data;
}

/**
 * 获取 Android 子功能详情
 */
export async function getAndroidSubFunction(
  projectIdentifier: string,
  subFunctionId: string
): Promise<AndroidSubFunction> {
  const response = await apiClient.get<{ data: AndroidSubFunction }>(
    `/projects/${projectIdentifier}/android-functions/sub-functions/${subFunctionId}`
  );
  return response.data;
}

/**
 * 创建 Android 子功能
 */
export async function createAndroidSubFunction(
  projectIdentifier: string,
  data: CreateAndroidSubFunctionRequest
): Promise<AndroidSubFunction> {
  const response = await apiClient.post<{ data: AndroidSubFunction }>(
    `/projects/${projectIdentifier}/android-functions/sub-functions`,
    data
  );
  return response.data;
}

/**
 * 更新 Android 子功能
 */
export async function updateAndroidSubFunction(
  projectIdentifier: string,
  subFunctionId: string,
  data: UpdateAndroidSubFunctionRequest
): Promise<AndroidSubFunction> {
  const response = await apiClient.patch<{ data: AndroidSubFunction }>(
    `/projects/${projectIdentifier}/android-functions/sub-functions/${subFunctionId}`,
    data
  );
  return response.data;
}

/**
 * 删除 Android 子功能
 */
export async function deleteAndroidSubFunction(
  projectIdentifier: string,
  subFunctionId: string
): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete<{ data: { success: boolean; message: string } }>(
    `/projects/${projectIdentifier}/android-functions/sub-functions/${subFunctionId}`
  );
  return response.data;
}

// ==================== 设备管理 API 函数 ====================

/**
 * 获取已连接的 Android 设备列表
 */
export async function listAndroidDevices(
  projectIdentifier: string
): Promise<AndroidDevice[]> {
  const response = await apiClient.get<{ data: AndroidDevice[] }>(
    `/projects/${projectIdentifier}/android-devices`
  );
  return response.data;
}

/**
 * 刷新设备列表（扫描 ADB 设备）
 */
export async function refreshAndroidDevices(
  projectIdentifier: string
): Promise<AndroidDevice[]> {
  const response = await apiClient.post<{ data: AndroidDevice[] }>(
    `/projects/${projectIdentifier}/android-devices/refresh`
  );
  return response.data;
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWtkMVNRPT06MzllNGNiNjY=
