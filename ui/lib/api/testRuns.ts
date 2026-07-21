import { apiClient } from "./client";
import type {
  PaginatedResponse,
  SuccessResponse,
  MessageResponse,
  TestRunCreate,
  TestRunPatchUpdate,
  TestRunFullReplace,
  TestRunInfo,
  TestRunListInfo,
  TestRunMinifiedInfo,
  TestRunTestCaseInfo,
  TestRunTestCaseMinifiedInfo,
  TestRunListParams,
  TestRunTestCasesParams,
  TestRunAssignRequest,
  AddTestCasesRequest,
  RemoveTestCasesRequest,
  CloseTestRunRequest,
  TestRunScriptJobInfo,
  TestRunScriptJobCreate,
  TestRunScheduleInfo,
  TestRunScheduleCreate,
  TestRunScheduleUpdate,
  TestRunExecutionSnapshotInfo,
  ScriptType,
} from "./types";

// 路径前缀
function basePath(projectIdentifier: string): string {
  return `/projects/${projectIdentifier}/test-runs`;
}

// =========================================================
// 列表 / 详情 / 创建
// =========================================================

// 获取测试运行列表
export function listTestRuns(
  projectIdentifier: string,
  params?: TestRunListParams
) {
  return apiClient.get<PaginatedResponse<TestRunListInfo>>(
    basePath(projectIdentifier),
    { params: params as Record<string, string | number | boolean | undefined> }
  );
}

// 获取测试运行详情（默认完整字段）
export function getTestRun(
  projectIdentifier: string,
  testRunIdentifier: string
) {
  return apiClient.get<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}`
  );
}

// 获取测试运行精简详情（minify=true）
export function getTestRunMinified(
  projectIdentifier: string,
  testRunIdentifier: string
) {
  return apiClient.get<SuccessResponse<TestRunMinifiedInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}`,
    { params: { minify: true } }
  );
}

// 创建测试运行
export function createTestRun(
  projectIdentifier: string,
  data: TestRunCreate
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    basePath(projectIdentifier),
    data
  );
}

// =========================================================
// 更新（PATCH 部分 / POST 全量）
// =========================================================

// 部分更新测试运行 (PATCH /update)
export function patchTestRun(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: TestRunPatchUpdate
) {
  return apiClient.patch<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/update`,
    data
  );
}
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1VWM1FRPT06NDNlYmFiODc=

// 全量替换测试运行 (POST /update)
export function replaceTestRun(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: TestRunFullReplace
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/update`,
    data
  );
}

// =========================================================
// 关闭 / 删除
// =========================================================

// 关闭测试运行
export function closeTestRun(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: CloseTestRunRequest = {}
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/close`,
    data
  );
}
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1VWM1FRPT06NDNlYmFiODc=

// 删除测试运行
export function deleteTestRun(
  projectIdentifier: string,
  testRunIdentifier: string
) {
  return apiClient.post<MessageResponse>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/delete`
  );
}

// =========================================================
// 分配负责人
// =========================================================

// 批量分配测试用例负责人
export function assignTestRun(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: TestRunAssignRequest
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/assign`,
    data
  );
}

// =========================================================
// 测试用例子资源
// =========================================================

// 获取测试运行中的测试用例 (默认完整字段)
export function listTestRunTestCases(
  projectIdentifier: string,
  testRunIdentifier: string,
  params?: TestRunTestCasesParams
) {
  return apiClient.get<PaginatedResponse<TestRunTestCaseInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/test-cases`,
    { params: params as Record<string, string | number | boolean | undefined> }
  );
}

// 获取精简测试用例列表 (minify=true)
export function listTestRunTestCasesMinified(
  projectIdentifier: string,
  testRunIdentifier: string,
  params?: Omit<TestRunTestCasesParams, "minify" | "fetch_steps">
) {
  return apiClient.get<PaginatedResponse<TestRunTestCaseMinifiedInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/test-cases`,
    {
      params: {
        ...(params as Record<string, string | number | boolean | undefined>),
        minify: true,
      },
    }
  );
}

// 获取附带前 30 条步骤的测试用例 (fetch_steps=true, 禁用分页)
export function listTestRunTestCasesWithSteps(
  projectIdentifier: string,
  testRunIdentifier: string,
  params?: Omit<TestRunTestCasesParams, "minify" | "fetch_steps">
) {
  return apiClient.get<PaginatedResponse<TestRunTestCaseInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/test-cases`,
    {
      params: {
        ...(params as Record<string, string | number | boolean | undefined>),
        fetch_steps: true,
      },
    }
  );
}

// 添加测试用例到测试运行
export function addTestCasesToRun(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: AddTestCasesRequest
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/test-cases`,
    data
  );
}

// 从测试运行移除测试用例
export function removeTestCasesFromRun(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: RemoveTestCasesRequest
) {
  return apiClient.delete<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/test-cases`,
    { data }
  );
}

// 执行测试运行
export function executeTestRun(
  projectIdentifier: string,
  testRunIdentifier: string
) {
  return apiClient.post<SuccessResponse<{
    test_run_id: string;
    status: string;
    total: number;
    passed: number;
    failed: number;
  }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/execute`
  );
}

// 取消测试运行
export function cancelTestRun(
  projectIdentifier: string,
  testRunIdentifier: string
) {
  return apiClient.post<SuccessResponse<{ cancelled: boolean }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/cancel`
  );
}

// SSE 实时状态订阅
export function subscribeToTestRunEvents(
  projectIdentifier: string,
  testRunIdentifier: string,
  onMessage: (data: unknown) => void,
  onError?: (error: Event) => void
): EventSource {
  const url = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v2/projects/${projectIdentifier}/test-runs/${testRunIdentifier}/events`;
  const es = new EventSource(url);
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      onMessage(event.data);
    }
  };
  if (onError) {
    es.onerror = onError;
  }
  return es;
}

// =========================================================
// 执行快照子资源
// =========================================================

// 获取测试运行的执行快照列表
export function listExecutionSnapshots(
  projectIdentifier: string,
  testRunIdentifier: string,
  params?: { page?: number; page_size?: number }
) {
  return apiClient.get<SuccessResponse<{
    items: TestRunExecutionSnapshotInfo[];
    total: number;
    page: number;
    page_size: number;
  }>>(`${basePath(projectIdentifier)}/${testRunIdentifier}/snapshots`, {
    params: params as Record<string, string | number | undefined>,
  });
}

// 获取执行快照详情（含作业列表）
export function getExecutionSnapshot(
  projectIdentifier: string,
  testRunIdentifier: string,
  snapshotId: string
) {
  return apiClient.get<SuccessResponse<TestRunExecutionSnapshotInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/snapshots/${snapshotId}`
  );
}

// 获取快照作业日志
export function getSnapshotJobLogs(
  projectIdentifier: string,
  testRunIdentifier: string,
  snapshotId: string,
  snapshotJobId: string
) {
  return apiClient.get<SuccessResponse<{ stdout: string; stderr: string }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/snapshots/${snapshotId}/jobs/${snapshotJobId}/logs`
  );
}

// 获取快照作业报告浏览 URL
export function getSnapshotJobReportUrl(
  projectIdentifier: string,
  testRunIdentifier: string,
  snapshotId: string,
  snapshotJobId: string
) {
  return apiClient.get<SuccessResponse<{ url: string; expires_in: number }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/snapshots/${snapshotId}/jobs/${snapshotJobId}/report-url`
  );
}

// =========================================================
// 脚本作业子资源
// =========================================================

// 获取测试运行的脚本作业列表
export function getScriptJobs(
  projectIdentifier: string,
  testRunIdentifier: string,
  params?: {
    script_type?: ScriptType;
    page?: number;
    page_size?: number;
  }
) {
  return apiClient.get<SuccessResponse<{
    items: TestRunScriptJobInfo[];
    total: number;
    page: number;
    page_size: number;
  }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs`,
    { params: params as Record<string, string | number | undefined> }
  );
}

// 添加脚本作业到测试运行
export function addScriptJobs(
  projectIdentifier: string,
  testRunIdentifier: string,
  data: TestRunScriptJobCreate[]
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs`,
    data
  );
}

// 从测试运行移除脚本作业
export function removeScriptJob(
  projectIdentifier: string,
  testRunIdentifier: string,
  jobId: string
) {
  return apiClient.delete<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/${jobId}`
  );
}

// 获取脚本作业报告预签名 URL
export function getJobReportUrl(
  projectIdentifier: string,
  testRunIdentifier: string,
  jobId: string
) {
  return apiClient.get<SuccessResponse<{ url: string; expires_in: number }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/${jobId}/report-url`
  );
}

// 重试脚本作业
export function retryJob(
  projectIdentifier: string,
  testRunIdentifier: string,
  jobId: string
) {
  return apiClient.post<SuccessResponse<TestRunScriptJobInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/${jobId}/retry`
  );
}

// 获取脚本作业日志
export function getJobLogs(
  projectIdentifier: string,
  testRunIdentifier: string,
  jobId: string
) {
  return apiClient.get<SuccessResponse<{ stdout: string; stderr: string }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/${jobId}/logs`
  );
}

// 批量重试脚本作业
export function batchRetryJobs(
  projectIdentifier: string,
  testRunIdentifier: string,
  jobIds: string[]
) {
  return apiClient.post<SuccessResponse<{ retried: number; jobs: TestRunScriptJobInfo[] }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/batch-retry`,
    { job_ids: jobIds }
  );
}

// 获取脚本执行历史趋势
export function getScriptHistory(
  projectIdentifier: string,
  testRunIdentifier: string,
  scriptType: ScriptType,
  scriptId: string,
  limit?: number
) {
  return apiClient.get<SuccessResponse<{
    script_type: string;
    script_id: string;
    total_runs: number;
    success_rate: number;
    passed: number;
    failed: number;
    skipped: number;
    cancelled: number;
    history: Array<{
      job_id: string;
      test_run_id: string;
      status: string;
      result_summary: Record<string, number> | null;
      duration_ms: number | null;
      started_at: string | null;
      completed_at: string | null;
    }>;
  }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/history`,
    { params: { script_type: scriptType, script_id: scriptId, limit } }
  );
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1VWM1FRPT06NDNlYmFiODc=

// 获取脚本性能基准
export function getScriptBenchmark(
  projectIdentifier: string,
  testRunIdentifier: string,
  scriptType: ScriptType,
  scriptId: string,
  limit?: number
) {
  return apiClient.get<SuccessResponse<{
    script_type: string;
    script_id: string;
    total_runs: number;
    avg_duration_ms: number;
    min_duration_ms: number;
    max_duration_ms: number;
    median_duration_ms: number;
    runs: Array<{
      job_id: string;
      status: string;
      duration_ms: number;
      date: string | null;
    }>;
  }>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/benchmark`,
    { params: { script_type: scriptType, script_id: scriptId, limit } }
  );
}

// 获取脚本作业报告预览 HTML
export function getJobReportPreview(
  projectIdentifier: string,
  testRunIdentifier: string,
  jobId: string
) {
  return apiClient.get<string>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/script-jobs/${jobId}/report-preview`
  );
}

// 将脚本作业结果映射到测试用例
export function mapJobsToTestCases(
  projectIdentifier: string,
  testRunIdentifier: string
) {
  return apiClient.post<SuccessResponse<TestRunInfo>>(
    `${basePath(projectIdentifier)}/${testRunIdentifier}/map-jobs-to-cases`
  );
}

// =========================================================
// 定时调度子资源
// =========================================================

// 获取定时调度列表
export function getSchedules(
  projectIdentifier: string,
  params?: {
    page?: number;
    page_size?: number;
  }
) {
  return apiClient.get<SuccessResponse<{
    items: TestRunScheduleInfo[];
    total: number;
    page: number;
    page_size: number;
  }>>(
    `${basePath(projectIdentifier)}/schedules`,
    { params: params as Record<string, string | number | undefined> }
  );
}

// 获取定时调度详情
export function getSchedule(
  projectIdentifier: string,
  scheduleId: string
) {
  return apiClient.get<SuccessResponse<TestRunScheduleInfo>>(
    `${basePath(projectIdentifier)}/schedules/${scheduleId}`
  );
}

// 创建定时调度
export function createSchedule(
  projectIdentifier: string,
  data: TestRunScheduleCreate
) {
  return apiClient.post<SuccessResponse<TestRunScheduleInfo>>(
    `${basePath(projectIdentifier)}/schedules`,
    data
  );
}

// 更新定时调度
export function updateSchedule(
  projectIdentifier: string,
  scheduleId: string,
  data: TestRunScheduleUpdate
) {
  return apiClient.patch<SuccessResponse<TestRunScheduleInfo>>(
    `${basePath(projectIdentifier)}/schedules/${scheduleId}`,
    data
  );
}

// 删除定时调度
export function deleteSchedule(
  projectIdentifier: string,
  scheduleId: string
) {
  return apiClient.delete<MessageResponse>(
    `${basePath(projectIdentifier)}/schedules/${scheduleId}`
  );
}

// 立即触发一次调度
export function triggerSchedule(
  projectIdentifier: string,
  scheduleId: string
) {
  return apiClient.post<SuccessResponse<{
    status: string;
    reason?: string;
    test_run_id?: string;
    identifier?: string;
    message: string;
  }>>(`${basePath(projectIdentifier)}/schedules/${scheduleId}/trigger`);
}

// 获取调度的执行历史
export function getScheduleRuns(
  projectIdentifier: string,
  scheduleId: string,
  params?: {
    page?: number;
    page_size?: number;
  }
) {
  return apiClient.get<SuccessResponse<{
    items: TestRunListInfo[];
    total: number;
    page: number;
    page_size: number;
  }>>(
    `${basePath(projectIdentifier)}/schedules/${scheduleId}/runs`,
    { params: params as Record<string, string | number | undefined> }
  );
}

// =========================================================
// 工具函数
// =========================================================

// 将逗号分隔字符串转为字符串数组
export function csvToList(value?: string): string[] | undefined {
  if (!value) return undefined;
  const items = value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
  return items.length ? items : undefined;
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1VWM1FRPT06NDNlYmFiODc=

// 将字符串数组转为逗号分隔字符串
export function listToCsv(values?: string[]): string | undefined {
  if (!values || values.length === 0) return undefined;
  return values.join(",");
}
