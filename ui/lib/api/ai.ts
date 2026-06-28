import { apiClient } from "./client";
import type { TestCaseInfo } from "./types";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1daRWJRPT06NjExNjM5NDI=

// AI生成测试用例的请求参数
export interface AIGenerateTestCasesRequest {
  prompt: string;
  folder_id?: string | null;
  count?: number;
  template?: "test_case" | "test_case_bdd";
}

// AI生成测试用例的响应
export interface AIGenerateTestCasesResponse {
  success: boolean;
  test_cases: TestCaseInfo[];
  message?: string;
}

// 从文档/图片生成测试用例的请求参数
export interface AIGenerateFromDocumentRequest {
  file: File;
  folder_id?: string | null;
  additional_prompt?: string;
  template?: "test_case" | "test_case_bdd";
}

// AI辅助填充测试用例字段的请求参数
export interface AIAssistFieldRequest {
  field: "description" | "preconditions" | "steps" | "feature" | "scenario" | "background";
  context: {
    title?: string;
    description?: string;
    preconditions?: string;
    existing_steps?: Array<{ step: string; result?: string }>;
  };
  prompt?: string;
}
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1daRWJRPT06NjExNjM5NDI=

// AI辅助填充字段的响应
export interface AIAssistFieldResponse {
  success: boolean;
  content: string | Array<{ step: string; result: string }>;
  message?: string;
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1daRWJRPT06NjExNjM5NDI=

// 从提示词生成测试用例
export function generateTestCasesFromPrompt(
  projectId: string,
  data: AIGenerateTestCasesRequest
) {
  return apiClient.post<AIGenerateTestCasesResponse>(
    `/projects/${projectId}/ai/generate-test-cases`,
    data
  );
}

// 从文档/图片生成测试用例
export async function generateTestCasesFromDocument(
  projectId: string,
  data: AIGenerateFromDocumentRequest
) {
  const formData = new FormData();
  formData.append("file", data.file);
  if (data.folder_id) {
    formData.append("folder_id", data.folder_id);
  }
  if (data.additional_prompt) {
    formData.append("additional_prompt", data.additional_prompt);
  }
  if (data.template) {
    formData.append("template", data.template);
  }

  const response = await fetch(
    `/api/v2/projects/${projectId}/ai/generate-from-document`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to generate test cases from document");
  }

  return response.json() as Promise<AIGenerateTestCasesResponse>;
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1daRWJRPT06NjExNjM5NDI=

// AI辅助填充测试用例字段
export function aiAssistField(
  projectId: string,
  data: AIAssistFieldRequest
) {
  return apiClient.post<AIAssistFieldResponse>(
    `/projects/${projectId}/ai/assist-field`,
    data
  );
}

