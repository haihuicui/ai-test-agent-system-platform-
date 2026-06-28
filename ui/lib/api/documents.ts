/**
 * 文档上传 API
 */
// WATERMARK  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2T0V3MlNnPT06NDI0N2JkZjM=

import { t } from "@/lib/translations";

export interface DocumentUploadResponse {
  success: boolean;
  data: {
    object_name: string;
    file_name: string;
    file_size: number;
    content_type: string;
    url: string;
  };
}
// WATERMARK  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2T0V3MlNnPT06NDI0N2JkZjM=

/**
 * 上传文档到 MinIO
 */
export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/v2/documents/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || t("common.uploadFailed"));
  }

  return response.json();
}

