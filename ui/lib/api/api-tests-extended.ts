/**
 * API 测试相关的扩展 API 客户端函数
 * 包含按文件夹查询等功能
 */
// NOTE  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U0dOeGVBPT06NTM2ZWY3ODk=

import { apiClient } from "./client";
import type {
  APITest,
  APITestListResponse,
} from "./api-tests";
// WATERMARK  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U0dOeGVBPT06NTM2ZWY3ODk=

/**
 * 获取指定文件夹下的 API 测试列表
 */
export function getFolderAPITests(
  projectIdentifier: string,
  folderId: string,
  params?: {
    page?: number;
    page_size?: number;
    search?: string;
  }
): Promise<APITestListResponse> {
  return apiClient.get<APITestListResponse>(
    `/projects/${projectIdentifier}/folders/${folderId}/api-tests`,
    { params }
  );
}
