import { apiClient } from "./client";
import type {
  TestCaseInfo,
  TestCaseCreate,
  TestCaseUpdate,
  PaginationInfo,
  Priority,
  TestCaseState,
  ExportFormat,
} from "./types";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VsVk5BPT06OGYxNGFiZTU=

interface TestCaseResponse {
  success: boolean;
  test_case: TestCaseInfo;
}

interface TestCaseListResponse {
  success: boolean;
  data?: TestCaseInfo[];
  test_cases?: TestCaseInfo[];
  info?: PaginationInfo;
}

interface TestCaseDeleteResponse {
  success: boolean;
  message: string;
}

export interface TestCaseQueryParams {
  p?: number;
  page_size?: number;
  folder_id?: string;
  search?: string;
  priority?: Priority | string;
  status?: TestCaseState | string;
  owner?: string;
  tags?: string;
  minify?: boolean;
}

// 获取项目下的测试用例列表
export function getTestCases(
  projectId: string,
  params?: TestCaseQueryParams
) {
  return apiClient.get<TestCaseListResponse>(
    `/projects/${projectId}/test-cases`,
    { params: params as Record<string, string | number | boolean | undefined> }
  );
}
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VsVk5BPT06OGYxNGFiZTU=

// 获取文件夹下的测试用例
export function getFolderTestCases(
  projectId: string,
  folderId: string,
  params?: TestCaseQueryParams
) {
  return apiClient.get<TestCaseListResponse>(
    `/projects/${projectId}/folders/${folderId}/test-cases`,
    { params: params as Record<string, string | number | boolean | undefined> }
  );
}

// 获取测试用例详情
export function getTestCase(projectId: string, testCaseId: string) {
  return apiClient.get<TestCaseResponse>(
    `/projects/${projectId}/test-cases/${testCaseId}`
  );
}

// 创建测试用例
export function createTestCase(
  projectId: string,
  folderId: string | null,
  data: TestCaseCreate
) {
  const url = folderId
    ? `/projects/${projectId}/folders/${folderId}/test-cases`
    : `/projects/${projectId}/test-cases`;
  return apiClient.post<TestCaseResponse>(url, data);
}

// 更新测试用例
export function updateTestCase(
  projectId: string,
  testCaseId: string,
  data: TestCaseUpdate
) {
  return apiClient.patch<TestCaseResponse>(
    `/projects/${projectId}/test-cases/${testCaseId}`,
    data
  );
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VsVk5BPT06OGYxNGFiZTU=

// 删除测试用例
export function deleteTestCase(projectId: string, testCaseId: string) {
  return apiClient.delete<TestCaseDeleteResponse>(
    `/projects/${projectId}/test-cases/${testCaseId}`
  );
}

// 移动测试用例到其他文件夹
export function moveTestCase(
  projectId: string,
  testCaseId: string,
  folderId: string | null
) {
  return apiClient.patch<TestCaseResponse>(
    `/projects/${projectId}/test-cases/${testCaseId}/move`,
    { folder_id: folderId }
  );
}

interface BulkOperationResponse {
  success: boolean;
  message: string;
  affected_count: number;
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VsVk5BPT06OGYxNGFiZTU=

// 批量删除测试用例
export function bulkDeleteTestCases(
  projectId: string,
  testCaseIds: string[]
) {
  return apiClient.delete<BulkOperationResponse>(
    `/projects/${projectId}/test-cases`,
    {
      data: {
        test_case_ids: testCaseIds,
      },
    }
  );
}

// 批量更新测试用例
export function bulkUpdateTestCases(
  projectId: string,
  testCaseIds: string[],
  updateData: Partial<TestCaseUpdate>
) {
  return apiClient.patch<BulkOperationResponse>(
    `/projects/${projectId}/test-cases`,
    {
      test_case_ids: testCaseIds,
      update_data: updateData,
    }
  );
}

export interface ExportExcelRequest {
  test_case_ids?: string[];
  folder_id?: string;
}

export interface ExportExcelResponse {
  success: boolean;
  export_id: string;
  status: string;
  status_url: string;
}

export interface ExportTestCasesRequest {
  format: ExportFormat;
  test_case_ids?: string[];
  folder_id?: string;
}

export interface ExportTestCasesResponse {
  success: boolean;
  export_id: string;
  status: string;
  status_url: string;
  format: ExportFormat;
}

export interface ExportStatusResponse {
  success: boolean;
  export_id: string;
  status: string;
  download_url?: string;
  error_message?: string;
}

export function exportTestCases(
  projectId: string,
  data: ExportTestCasesRequest
) {
  return apiClient.post<ExportTestCasesResponse>(
    `/projects/${projectId}/test-cases/export`,
    data
  );
}

// 旧 Excel 导出接口，作为统一导出接口的兼容包装保留
export function exportTestCasesToExcel(
  projectId: string,
  data: ExportExcelRequest
) {
  return exportTestCases(projectId, { format: "excel", ...data });
}

export function getExportStatus(exportId: string) {
  return apiClient.get<ExportStatusResponse>(`/exports/${exportId}/status`);
}

export function getExportDownloadUrl(exportId: string) {
  return `/api/v2/exports/${exportId}/download`;
}

export async function downloadTestCasesExport(
  projectId: string,
  data: ExportTestCasesRequest,
  options?: {
    onCompleted?: () => void;
    onFailed?: (errorMessage: string) => void;
  }
) {
  const { export_id: exportId } = await exportTestCases(projectId, data);

  const maxAttempts = 30;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    const status = await getExportStatus(exportId);

    if (status.status === "completed") {
      window.location.href = getExportDownloadUrl(exportId);
      options?.onCompleted?.();
      return;
    }
    if (status.status === "failed") {
      const message = status.error_message || "导出失败";
      options?.onFailed?.(message);
      return;
    }
  }

  options?.onFailed?.("导出超时，请稍后重试");
}

// 旧 Excel 导出轮询函数，作为兼容包装保留
export async function downloadTestCasesExcel(
  projectId: string,
  data: ExportExcelRequest,
  options?: {
    onCompleted?: () => void;
    onFailed?: (errorMessage: string) => void;
  }
) {
  return downloadTestCasesExport(
    projectId,
    { format: "excel", ...data },
    options
  );
}

