/**
 * 附件 API
 */
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDBGamRnPT06YmU0MDk5ZjU=

import { apiClient } from "./client";

export interface AttachmentInfo {
  id: string;
  name: string;
  size: number;
  content_type?: string;
  created_by?: string;
  created_at: string;
  url?: string;
}
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDBGamRnPT06YmU0MDk5ZjU=

export interface AttachmentUploadResponse {
  id: string;
  name: string;
  size: number;
  content_type?: string;
  created_by?: string;
  created_at: string;
  url?: string;
}

/**
 * 上传测试用例附件
 */
export async function uploadTestCaseAttachment(
  projectIdentifier: string,
  testCaseIdentifier: string,
  file: File
): Promise<AttachmentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // 直接使用 fetch，因为 apiClient 会将 body 转换为 JSON
  const response = await fetch(
    `/api/v2/projects/${projectIdentifier}/test-cases/${testCaseIdentifier}/attachments`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 获取测试用例附件列表
 */
export async function getTestCaseAttachments(
  projectIdentifier: string,
  testCaseIdentifier: string
): Promise<AttachmentInfo[]> {
  const response = await apiClient.get<{ attachments: AttachmentInfo[] }>(
    `/api/v2/projects/${projectIdentifier}/test-cases/${testCaseIdentifier}/attachments`
  );

  return response.attachments;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDBGamRnPT06YmU0MDk5ZjU=

/**
 * 删除测试用例附件
 */
export async function deleteTestCaseAttachment(
  projectIdentifier: string,
  testCaseIdentifier: string,
  attachmentId: string
): Promise<void> {
  await apiClient.delete(
    `/api/v2/projects/${projectIdentifier}/test-cases/${testCaseIdentifier}/attachments/${attachmentId}`
  );
}

/**
 * 获取附件下载链接
 */
export async function getAttachmentDownloadUrl(
  projectIdentifier: string,
  attachmentId: string
): Promise<string> {
  const response = await apiClient.get<{ url: string }>(
    `/api/v2/projects/${projectIdentifier}/attachments/${attachmentId}`
  );

  return response.url;
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDBGamRnPT06YmU0MDk5ZjU=

