/**
 * 场景测试 API 调用函数
 */
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkTk13PT06ZmQ0NzU4YmU=

import { Scenario, ScenarioStep, ScenarioRun, StepResult } from '@/types/scenario';

const API_BASE = '/api/v2/scenarios';

// ==================== 场景管理 ====================

/**
 * 列出场景
 */
export async function listScenarios(
  projectId: string,
  params?: {
    status?: string;
    page?: number;
    page_size?: number;
  }
): Promise<{ total: number; items: Scenario[] }> {
  const searchParams = new URLSearchParams({
    project_id: projectId,
    ...(params?.status && { status: params.status }),
    ...(params?.page && { page: String(params.page) }),
    ...(params?.page_size && { page_size: String(params.page_size) }),
  });

  const response = await fetch(`${API_BASE}?${searchParams}`);
  if (!response.ok) {
    throw new Error('Failed to list scenarios');
  }
  return response.json();
}

/**
 * 获取场景详情
 */
export async function getScenario(scenarioId: string): Promise<Scenario> {
  const response = await fetch(`${API_BASE}/${scenarioId}`);
  if (!response.ok) {
    throw new Error('Failed to get scenario');
  }
  return response.json();
}

/**
 * 创建场景
 */
export async function createScenario(
  projectId: string,
  data: {
    name: string;
    description?: string;
    folder_id?: string;
    global_variables?: Record<string, any>;
    retry_count?: number;
    timeout_seconds?: number;
    parallel_execution?: boolean;
  }
): Promise<Scenario> {
  const response = await fetch(`${API_BASE}?project_id=${projectId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    console.error('Create scenario error:', error);
    throw new Error(error.detail || 'Failed to create scenario');
  }
  return response.json();
}

/**
 * 更新场景
 */
export async function updateScenario(
  scenarioId: string,
  data: {
    name?: string;
    description?: string;
    global_variables?: Record<string, any>;
    retry_count?: number;
    timeout_seconds?: number;
    status?: string;
  }
): Promise<Scenario> {
  const response = await fetch(`${API_BASE}/${scenarioId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to update scenario');
  }
  return response.json();
}

/**
 * 删除场景
 */
export async function deleteScenario(scenarioId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${scenarioId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to delete scenario');
  }
}

// ==================== 步骤管理 ====================

/**
 * 列出步骤
 */
export async function listScenarioSteps(scenarioId: string): Promise<ScenarioStep[]> {
  const response = await fetch(`${API_BASE}/${scenarioId}/steps`);
  if (!response.ok) {
    throw new Error('Failed to list scenario steps');
  }
  return response.json();
}
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkTk13PT06ZmQ0NzU4YmU=

/**
 * 获取单个步骤详情
 */
export async function getScenarioStep(stepId: string): Promise<ScenarioStep> {
  const response = await fetch(`${API_BASE}/steps/${stepId}`);
  if (!response.ok) {
    throw new Error('Failed to get scenario step');
  }
  return response.json();
}

/**
 * 添加步骤
 */
export async function addScenarioStep(
  scenarioId: string,
  data: {
    endpoint_id?: string;
    name: string;
    description?: string;
    step_order?: number;
    request_override?: Record<string, any>;
    headers_override?: Record<string, any>;
    extractors?: Array<{ name: string; path: string; type?: string }>;
    assertions?: Array<{ type: string; expected: any; path?: string; operator?: string }>;
    condition_expression?: string;
    continue_on_failure?: boolean;
    delay_ms?: number;
    retry_count?: number;
  }
): Promise<ScenarioStep> {
  const response = await fetch(`${API_BASE}/${scenarioId}/steps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to add scenario step');
  }
  return response.json();
}

/**
 * 更新步骤
 */
export async function updateScenarioStep(
  scenarioId: string,
  stepId: string,
  data: {
    name?: string;
    description?: string;
    request_override?: Record<string, any>;
    headers_override?: Record<string, any>;
    extractors?: Array<{ name: string; path: string; type?: string }>;
    assertions?: Array<{ type: string; expected: any; path?: string; operator?: string }>;
    condition_expression?: string;
    continue_on_failure?: boolean;
    delay_ms?: number;
    retry_count?: number;
  }
): Promise<ScenarioStep> {
  const response = await fetch(`${API_BASE}/${scenarioId}/steps/${stepId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to update scenario step');
  }
  return response.json();
}

/**
 * 删除步骤
 */
export async function deleteScenarioStep(scenarioId: string, stepId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${scenarioId}/steps/${stepId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to delete scenario step');
  }
}

/**
 * 重新排序步骤
 */
export async function reorderScenarioSteps(
  scenarioId: string,
  stepOrders: Record<string, number>
): Promise<void> {
  const response = await fetch(`${API_BASE}/${scenarioId}/steps/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(stepOrders),
  });

  if (!response.ok) {
    throw new Error('Failed to reorder scenario steps');
  }
}

// ==================== 数据映射 ====================
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkTk13PT06ZmQ0NzU4YmU=

/**
 * 添加数据映射
 */
export async function addDataMapping(
  scenarioId: string,
  stepId: string,
  data: {
    source_type: string;
    source_step_id?: string;
    source_path?: string;
    target_path: string;
    transform_expression?: string;
    description?: string;
  }
): Promise<ScenarioStep> {
  const response = await fetch(
    `${API_BASE}/${scenarioId}/steps/${stepId}/mappings`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to add data mapping');
  }
  return response.json();
}

/**
 * 删除数据映射
 */
export async function deleteDataMapping(
  scenarioId: string,
  stepId: string,
  mappingId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/${scenarioId}/steps/${stepId}/mappings/${mappingId}`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    throw new Error('Failed to delete data mapping');
  }
}

// ==================== 场景执行 ====================

/**
 * 执行场景
 */
export async function executeScenario(
  scenarioId: string,
  data: {
    variables?: Record<string, any>;
    base_url?: string;
    async_mode?: boolean;
    environment_id?: string;
    custom_requirements?: string;
  }
): Promise<{
  run_id: string;
  status: string;
  message: string;
  result?: ScenarioRun;
}> {
  const response = await fetch(`${API_BASE}/${scenarioId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to execute scenario');
  }
  return response.json();
}

// ==================== 执行记录 ====================
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkTk13PT06ZmQ0NzU4YmU=

/**
 * 列出执行记录
 */
export async function listScenarioRuns(
  scenarioId: string,
  page = 1,
  pageSize = 20
): Promise<{ total: number; items: ScenarioRun[] }> {
  const response = await fetch(
    `${API_BASE}/${scenarioId}/runs?page=${page}&page_size=${pageSize}`
  );
  if (!response.ok) {
    throw new Error('Failed to list scenario runs');
  }
  const runs = await response.json();
  return {
    total: runs.total || runs.length,
    items: runs.items || runs,
  };
}

/**
 * 获取执行记录详情
 */
export async function getScenarioRun(
  scenarioId: string,
  runId: string
): Promise<ScenarioRun> {
  const response = await fetch(`${API_BASE}/${scenarioId}/runs/${runId}`);
  if (!response.ok) {
    throw new Error('Failed to get scenario run');
  }
  return response.json();
}

/**
 * 获取步骤执行结果
 */
export async function getStepResults(
  scenarioId: string,
  runId: string
): Promise<StepResult[]> {
  const response = await fetch(
    `${API_BASE}/${scenarioId}/runs/${runId}/results`
  );
  if (!response.ok) {
    throw new Error('Failed to get step results');
  }
  return response.json();
}
