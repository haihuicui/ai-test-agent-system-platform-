import * as React from "react";
import {
  FileCode,
  FileText,
  Globe,
  Play,
  CalendarClock,
} from "lucide-react";
import type {
  TestRunState,
  ExecutionMode,
  TriggerType,
  ScriptType,
  JobStatus,
  TestRunListInfo,
  TestRunInfo,
} from "@/lib/api";

export const RUN_STATE_BADGE: Record<
  TestRunState,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  new_run: { label: "新建", variant: "secondary" },
  in_progress: { label: "进行中", variant: "default" },
  under_review: { label: "评审中", variant: "outline" },
  rejected: { label: "已拒绝", variant: "destructive" },
  approved: { label: "已批准", variant: "default" },
  done: { label: "已完成", variant: "default" },
  done_with_failures: { label: "已完成（含失败）", variant: "destructive" },
  closed: { label: "已关闭", variant: "secondary" },
};

export const RUN_STATE_OPTIONS: { value: TestRunState; label: string }[] = [
  { value: "new_run", label: "新建" },
  { value: "in_progress", label: "进行中" },
  { value: "under_review", label: "评审中" },
  { value: "rejected", label: "已拒绝" },
  { value: "approved", label: "已批准" },
  { value: "done", label: "已完成" },
  { value: "done_with_failures", label: "已完成（含失败）" },
  { value: "closed", label: "已关闭" },
];

export const EXECUTION_MODE_BADGE: Record<ExecutionMode, { label: string }> = {
  sequential: { label: "顺序执行" },
  parallel: { label: "并行执行" },
};

export const TRIGGER_TYPE_BADGE: Record<TriggerType, { label: string }> = {
  manual: { label: "手动触发" },
  scheduled: { label: "定时触发" },
  api: { label: "API 触发" },
};

export const SCRIPT_TYPE_ICON: Record<ScriptType, React.ReactNode> = {
  api_test: <FileCode className="h-4 w-4" />,
  scenario: <FileText className="h-4 w-4" />,
  web_test: <Globe className="h-4 w-4" />,
  test_case: <FileText className="h-4 w-4" />,
};

export const SCRIPT_TYPE_LABEL: Record<ScriptType, string> = {
  api_test: "API 测试",
  scenario: "场景测试",
  web_test: "Web 测试",
  test_case: "测试用例",
};

export const JOB_STATUS_BADGE: Record<
  JobStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  pending: { label: "待执行", variant: "secondary" },
  running: { label: "执行中", variant: "default" },
  completed: { label: "已完成", variant: "default" },
  failed: { label: "失败", variant: "destructive" },
  skipped: { label: "已跳过", variant: "outline" },
  cancelled: { label: "已取消", variant: "outline" },
};

export function formatDuration(ms?: number | null): string {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

export function progressDoneRatio(
  run: TestRunListInfo | TestRunInfo
): number {
  const total = run.test_cases_count;
  if (!total) return 0;
  const p = run.overall_progress;
  const finished = p.passed + p.failed + p.blocked + p.skipped + p.retest;
  return Math.round((finished / total) * 100);
}

export const TRIGGER_TYPE_ICON: Record<TriggerType, React.ReactNode> = {
  manual: <Play className="h-3.5 w-3.5" />,
  scheduled: <CalendarClock className="h-3.5 w-3.5" />,
  api: <Play className="h-3.5 w-3.5" />,
};
