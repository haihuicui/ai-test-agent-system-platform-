/**
 * 场景测试类型定义
 */
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZFd1FRPT06MmJjYTMyZjg=

export interface Scenario {
  id: string;
  project_id: string;
  identifier: string;
  name: string;
  description: string | null;
  folder_id: string | null;
  status: 'draft' | 'active' | 'archived';
  global_variables: Record<string, any>;
  retry_count: number;
  timeout_seconds: number;
  parallel_execution: boolean;
  total_steps: number;
  last_run_status: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface ScenarioStep {
  id: string;
  scenario_id: string;
  endpoint_id: string | null;
  step_order: number;
  name: string;
  description: string | null;
  request_override: Record<string, any>;
  headers_override: Record<string, any>;
  extractors: StepExtractor[];
  variable_exports: StepVariableExport[];
  assertions: StepAssertion[];
  condition_expression: string | null;
  continue_on_failure: boolean;
  delay_ms: number;
  retry_count: number;
  data_mappings: DataMapping[];
  created_at: string;
  updated_at: string;
  endpoint?: {
    id: string;
    method: string;
    path: string;
    display_name: string;
  };
}
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZFd1FRPT06MmJjYTMyZjg=

export interface StepExtractor {
  name: string;
  path: string;
  type?: string;
}

export interface StepVariableExport {
  name: string;
  source: 'request' | 'response';
  path: string;
  type?: string;
}

export interface StepAssertion {
  type: 'status' | 'jsonpath' | 'header';
  expected: any;
  path?: string;
  operator?: string;
}

export interface DataMapping {
  id: string;
  source_type: 'previous_response' | 'variable' | 'static';
  source_step_id: string | null;
  source_path: string | null;
  target_path: string;
  transform_expression: string | null;
  description: string | null;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZFd1FRPT06MmJjYTMyZjg=

export interface ScenarioRun {
  id: string;
  scenario_id: string;
  project_id: string;
  identifier: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  runtime_variables: Record<string, any>;
  execution_config: Record<string, any>;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  skipped_steps: number;
  duration_ms: number | null;
  report_path: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  executed_by: string | null;
}

export interface StepResult {
  id: string;
  run_id: string;
  step_id: string;
  endpoint_id: string | null;
  step_name: string | null;
  step_order: number;
  status: 'passed' | 'failed' | 'skipped' | 'error';
  full_url: string | null;
  request_data: Record<string, any> | null;
  response_data: Record<string, any> | null;
  extracted_data: Record<string, any>;
  exported_data: Record<string, any>;
  assertion_results: AssertionResult[];
  duration_ms: number | null;
  error_message: string | null;
  error_stack: string | null;
  created_at: string;
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZFd1FRPT06MmJjYTMyZjg=

export interface AssertionResult {
  assertion: StepAssertion;
  passed: boolean;
  actual: any;
  expected: any;
  message: string;
}
