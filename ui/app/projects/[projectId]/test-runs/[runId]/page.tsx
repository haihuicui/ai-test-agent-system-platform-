"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import {
  PlayCircle,
  Play,
  Square,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Lock,
  RefreshCw,
  ArrowLeft,
  Loader2,
  Zap,
  CalendarClock,
  Bot,
  FileCode,
  FileText,
  Globe,
  MoreHorizontal,
  Trash2,
  Pencil,
  Logs,
  Eye,
  BarChart3,
  History,
  CheckSquare,
  Square as SquareIcon,
  MapPin,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  getTestRun,
  executeTestRun,
  cancelTestRun,
  getScriptJobs,
  getJobReportUrl,
  retryJob,
  getJobLogs,
  batchRetryJobs,
  getScriptHistory,
  getScriptBenchmark,
  getJobReportPreview,
  mapJobsToTestCases,
  subscribeToTestRunEvents,
  type TestRunInfo,
  type TestRunScriptJobInfo,
  type TestRunState,
  type ExecutionMode,
  type TriggerType,
  type ScriptType,
  type JobStatus,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZCR1lnPT06Zjc3ZTQ2ZTk=

const RUN_STATE_BADGE: Record<
  TestRunState,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  new_run: { label: "新建", variant: "secondary" },
  in_progress: { label: "进行中", variant: "default" },
  under_review: { label: "评审中", variant: "outline" },
  rejected: { label: "已拒绝", variant: "destructive" },
  approved: { label: "已批准", variant: "default" },
  done: { label: "已完成", variant: "default" },
  closed: { label: "已关闭", variant: "secondary" },
};

const EXECUTION_MODE_BADGE: Record<ExecutionMode, { label: string }> = {
  sequential: { label: "顺序执行" },
  parallel: { label: "并行执行" },
};
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZCR1lnPT06Zjc3ZTQ2ZTk=

const TRIGGER_TYPE_BADGE: Record<TriggerType, { label: string }> = {
  manual: { label: "手动触发" },
  scheduled: { label: "定时触发" },
  api: { label: "API 触发" },
};

const SCRIPT_TYPE_ICON: Record<ScriptType, React.ReactNode> = {
  api_test: <FileCode className="h-4 w-4" />,
  scenario: <FileText className="h-4 w-4" />,
  web_test: <Globe className="h-4 w-4" />,
  test_case: <FileText className="h-4 w-4" />,
};
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZCR1lnPT06Zjc3ZTQ2ZTk=

const SCRIPT_TYPE_LABEL: Record<ScriptType, string> = {
  api_test: "API 测试",
  scenario: "场景测试",
  web_test: "Web 测试",
  test_case: "测试用例",
};

const JOB_STATUS_BADGE: Record<
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

function formatDuration(ms?: number | null): string {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZCR1lnPT06Zjc3ZTQ2ZTk=

function progressDoneRatio(run: TestRunInfo): number {
  const total = run.test_cases_count;
  if (!total) return 0;
  const p = run.overall_progress;
  const finished = p.passed + p.failed + p.blocked + p.skipped + p.retest;
  return Math.round((finished / total) * 100);
}

export default function TestRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const runId = params.runId as string;

  const [testRun, setTestRun] = React.useState<TestRunInfo | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [executing, setExecuting] = React.useState(false);

  const [scriptJobs, setScriptJobs] = React.useState<TestRunScriptJobInfo[]>([]);
  const [jobsLoading, setJobsLoading] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState<ScriptType | "all">("all");
  const [cancelling, setCancelling] = React.useState(false);
  const [retryingJobId, setRetryingJobId] = React.useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = React.useState<string | null>(null);

  // 批量重试状态
  const [selectedJobIds, setSelectedJobIds] = React.useState<Set<string>>(new Set());
  const [batchRetrying, setBatchRetrying] = React.useState(false);

  // 日志弹窗状态
  const [logDialogJob, setLogDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [logDialogData, setLogDialogData] = React.useState<{ stdout: string; stderr: string } | null>(null);
  const [logDialogLoading, setLogDialogLoading] = React.useState(false);

  // 报告预览弹窗状态
  const [reportDialogJob, setReportDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [reportDialogHtml, setReportDialogHtml] = React.useState<string | null>(null);
  const [reportDialogLoading, setReportDialogLoading] = React.useState(false);

  // 历史趋势弹窗状态
  const [historyDialogJob, setHistoryDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [historyDialogData, setHistoryDialogData] = React.useState<unknown>(null);
  const [historyDialogLoading, setHistoryDialogLoading] = React.useState(false);

  // 性能基准弹窗状态
  const [benchmarkDialogJob, setBenchmarkDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [benchmarkDialogData, setBenchmarkDialogData] = React.useState<unknown>(null);
  const [benchmarkDialogLoading, setBenchmarkDialogLoading] = React.useState(false);

  // 映射到用例状态
  const [mappingJobs, setMappingJobs] = React.useState(false);

  // ref 用于 SSE handler 中读取最新状态，避免闭包问题
  const testRunRef = React.useRef<TestRunInfo | null>(null);
  React.useEffect(() => {
    testRunRef.current = testRun;
  }, [testRun]);

  // SSE 实时状态订阅 + 轮询 fallback
  React.useEffect(() => {
    if (!projectId || !runId || !testRun) return;
    if (testRun.run_state !== "in_progress") return;

    let sseBroken = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (pollTimer) return;
      pollTimer = setInterval(() => {
        loadDetailSilent();
        loadScriptJobs();
      }, 3000);
    };

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    const es = subscribeToTestRunEvents(
      projectId,
      runId,
      (data) => {
        if (typeof data !== "object" || data === null) return;
        const payload = data as Record<string, unknown>;

        // SSE 推送了错误事件 → 关闭 SSE，启动轮询
        if (payload.event === "error") {
          sseBroken = true;
          es.close();
          startPolling();
          return;
        }

        // 1. 实时更新脚本作业列表
        if (payload.jobs && Array.isArray(payload.jobs)) {
          setScriptJobs(payload.jobs as TestRunScriptJobInfo[]);
        }

        // 2. 实时更新 overall_progress 和 run_state
        if (payload.overall_progress || payload.run_state) {
          setTestRun((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              run_state: (payload.run_state as TestRunInfo["run_state"]) || prev.run_state,
              overall_progress: (payload.overall_progress as TestRunInfo["overall_progress"]) || prev.overall_progress,
            };
          });
        }

        // 3. run_state 发生实际变化时，重新加载完整详情
        if (payload.run_state && payload.run_state !== testRunRef.current?.run_state) {
          loadDetailSilent();
          loadScriptJobs();
        }

        // 4. 执行完成后关闭 SSE 并刷新详情
        if (payload.event === "completed") {
          loadDetailSilent();
          loadScriptJobs();
          es.close();
          stopPolling();
        }
      },
      () => {
        // onError: SSE 连接断开（网络错误等）→ 启动轮询
        if (!sseBroken) {
          sseBroken = true;
          startPolling();
        }
      }
    );

    return () => {
      es.close();
      stopPolling();
    };
  }, [projectId, runId, testRun?.run_state]);

  // 静默加载详情（不触发全屏 loading）
  const loadDetailSilent = React.useCallback(async () => {
    if (!projectId || !runId) return;
    try {
      const response = await getTestRun(projectId, runId);
      setTestRun(response.data);
    } catch {
      // silent fail
    }
  }, [projectId, runId]);

  const loadDetail = React.useCallback(async () => {
    if (!projectId || !runId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await getTestRun(projectId, runId);
      setTestRun(response.data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载测试运行详情失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId, runId]);

  const loadScriptJobs = React.useCallback(async () => {
    if (!projectId || !runId) return;
    setJobsLoading(true);
    try {
      const response = await getScriptJobs(projectId, runId, { page: 1, page_size: 100 });
      setScriptJobs(response.data.items);
    } catch {
      // Script jobs may not be available for legacy runs
      setScriptJobs([]);
    } finally {
      setJobsLoading(false);
    }
  }, [projectId, runId]);

  React.useEffect(() => {
    loadDetail();
    loadScriptJobs();
  }, [loadDetail, loadScriptJobs]);

  async function handleExecute() {
    if (!testRun) return;
    setExecuting(true);
    try {
      await executeTestRun(projectId, testRun.identifier);
      await loadDetail();
      await loadScriptJobs();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "执行测试运行失败";
      setError(msg);
    } finally {
      setExecuting(false);
    }
  }

  async function handleCancel() {
    if (!testRun) return;
    setCancelling(true);
    try {
      await cancelTestRun(projectId, testRun.identifier);
      await loadDetail();
      await loadScriptJobs();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "取消执行失败";
      setError(msg);
    } finally {
      setCancelling(false);
    }
  }

  async function handleViewReport(job: TestRunScriptJobInfo) {
    if (!testRun) return;
    try {
      const response = await getJobReportUrl(projectId, testRun.identifier, job.id);
      const url = response.data.url;
      if (url) window.open(url, "_blank");
    } catch {
      // 静默失败
    }
  }

  async function handleRetryJob(job: TestRunScriptJobInfo) {
    if (!testRun) return;
    setRetryingJobId(job.id);
    try {
      await retryJob(projectId, testRun.identifier, job.id);
      await loadScriptJobs();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "重试失败";
      setError(msg);
    } finally {
      setRetryingJobId(null);
    }
  }

  function toggleJobSelection(jobId: string) {
    setSelectedJobIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  }

  async function handleBatchRetry() {
    if (!testRun || selectedJobIds.size === 0) return;
    setBatchRetrying(true);
    try {
      await batchRetryJobs(projectId, testRun.identifier, Array.from(selectedJobIds));
      setSelectedJobIds(new Set());
      await loadScriptJobs();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "批量重试失败";
      setError(msg);
    } finally {
      setBatchRetrying(false);
    }
  }

  async function handleViewLogs(job: TestRunScriptJobInfo) {
    if (!testRun) return;
    setLogDialogJob(job);
    setLogDialogLoading(true);
    try {
      const res = await getJobLogs(projectId, testRun.identifier, job.id);
      setLogDialogData(res.data);
    } catch (err) {
      setLogDialogData({ stdout: "", stderr: err instanceof ApiError ? err.message : "加载日志失败" });
    } finally {
      setLogDialogLoading(false);
    }
  }

  async function handlePreviewReport(job: TestRunScriptJobInfo) {
    if (!testRun) return;
    setReportDialogJob(job);
    setReportDialogLoading(true);
    try {
      const html = await getJobReportPreview(projectId, testRun.identifier, job.id);
      setReportDialogHtml(html);
    } catch (err) {
      setReportDialogHtml(`<html><body style="color:red;padding:20px">${err instanceof ApiError ? err.message : "加载报告失败"}</body></html>`);
    } finally {
      setReportDialogLoading(false);
    }
  }

  async function handleViewHistory(job: TestRunScriptJobInfo) {
    if (!testRun) return;
    setHistoryDialogJob(job);
    setHistoryDialogLoading(true);
    try {
      const res = await getScriptHistory(projectId, testRun.identifier, job.script_type, job.script_id, 30);
      setHistoryDialogData(res.data);
    } catch (err) {
      setHistoryDialogData({ error: err instanceof ApiError ? err.message : "加载历史失败" });
    } finally {
      setHistoryDialogLoading(false);
    }
  }

  async function handleViewBenchmark(job: TestRunScriptJobInfo) {
    if (!testRun) return;
    setBenchmarkDialogJob(job);
    setBenchmarkDialogLoading(true);
    try {
      const res = await getScriptBenchmark(projectId, testRun.identifier, job.script_type, job.script_id, 30);
      setBenchmarkDialogData(res.data);
    } catch (err) {
      setBenchmarkDialogData({ error: err instanceof ApiError ? err.message : "加载基准失败" });
    } finally {
      setBenchmarkDialogLoading(false);
    }
  }

  async function handleMapJobsToCases() {
    if (!testRun) return;
    setMappingJobs(true);
    try {
      await mapJobsToTestCases(projectId, testRun.identifier);
      await loadDetail();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "映射失败";
      setError(msg);
    } finally {
      setMappingJobs(false);
    }
  }

  const filteredJobs = React.useMemo(() => {
    if (activeTab === "all") return scriptJobs;
    return scriptJobs.filter((j) => j.script_type === activeTab);
  }, [scriptJobs, activeTab]);

  const jobCounts = React.useMemo(() => {
    const counts: Record<string, number> = { all: scriptJobs.length };
    for (const job of scriptJobs) {
      counts[job.script_type] = (counts[job.script_type] || 0) + 1;
    }
    return counts;
  }, [scriptJobs]);

  if (loading) {
    return (
      <MainLayout title="测试运行详情">
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </MainLayout>
    );
  }

  if (error || !testRun) {
    return (
      <MainLayout title="测试运行详情">
        <div className="flex h-64 flex-col items-center justify-center gap-4">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <p className="text-muted-foreground">{error || "测试运行不存在"}</p>
          <Button variant="outline" onClick={loadDetail}>
            <RefreshCw className="mr-2 h-4 w-4" />
            重试
          </Button>
        </div>
      </MainLayout>
    );
  }

  const p = testRun.overall_progress;
  const progress = progressDoneRatio(testRun);
  const stateInfo = RUN_STATE_BADGE[testRun.run_state];
  const closed = testRun.active_state === "closed";

  return (
    <MainLayout title={`测试运行: ${testRun.name}`}>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => router.push(`/projects/${projectId}/test-runs`)}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回列表
          </Button>
        </div>

        {/* 基本信息卡片 */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <PlayCircle className="h-6 w-6 text-primary" />
                <h1 className="text-xl font-semibold">{testRun.name}</h1>
                <Badge variant="outline" className="font-mono text-xs">
                  {testRun.identifier}
                </Badge>
                <Badge variant={stateInfo.variant}>{stateInfo.label}</Badge>
                {closed && (
                  <Badge variant="secondary">
                    <Lock className="mr-1 h-3 w-3" />
                    已关闭
                  </Badge>
                )}
              </div>
              {testRun.description && (
                <p className="text-sm text-muted-foreground">{testRun.description}</p>
              )}
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                {testRun.execution_mode && (
                  <span className="flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5" />
                    {EXECUTION_MODE_BADGE[testRun.execution_mode].label}
                  </span>
                )}
                {testRun.max_concurrency && testRun.execution_mode === "parallel" && (
                  <span>并发数: {testRun.max_concurrency}</span>
                )}
                {testRun.trigger_type && (
                  <span className="flex items-center gap-1">
                    {testRun.trigger_type === "scheduled" ? (
                      <CalendarClock className="h-3.5 w-3.5" />
                    ) : testRun.trigger_type === "api" ? (
                      <Bot className="h-3.5 w-3.5" />
                    ) : (
                      <Play className="h-3.5 w-3.5" />
                    )}
                    {TRIGGER_TYPE_BADGE[testRun.trigger_type].label}
                  </span>
                )}
                <span>创建于 {new Date(testRun.created_at).toLocaleString()}</span>
                {testRun.assignee && <span>负责人: {testRun.assignee}</span>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {testRun.run_state === "in_progress" ? (
                <Button
                  variant="destructive"
                  onClick={handleCancel}
                  disabled={cancelling}
                >
                  {cancelling ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Square className="mr-2 h-4 w-4" />
                  )}
                  取消执行
                </Button>
              ) : (
                <Button
                  onClick={handleExecute}
                  disabled={executing || closed}
                >
                  {executing ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  执行
                </Button>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem disabled>
                    <Pencil className="mr-2 h-4 w-4" />
                    编辑
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled>
                    <Trash2 className="mr-2 h-4 w-4" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* 进度概览 */}
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border p-4">
              <div className="text-sm text-muted-foreground">通过率</div>
              <div className="mt-1 text-2xl font-bold">{testRun.test_cases_count ? Math.round((p.passed / testRun.test_cases_count) * 100) : 0}%</div>
              <Progress value={progress} className="mt-2" />
            </div>
            <div className="rounded-lg border p-4">
              <div className="text-sm text-muted-foreground">通过</div>
              <div className="mt-1 flex items-center gap-2 text-2xl font-bold text-green-600">
                <CheckCircle2 className="h-5 w-5" />
                {p.passed}
              </div>
            </div>
            <div className="rounded-lg border p-4">
              <div className="text-sm text-muted-foreground">失败</div>
              <div className="mt-1 flex items-center gap-2 text-2xl font-bold text-red-600">
                <XCircle className="h-5 w-5" />
                {p.failed}
              </div>
            </div>
            <div className="rounded-lg border p-4">
              <div className="text-sm text-muted-foreground">未测/进行中</div>
              <div className="mt-1 flex items-center gap-2 text-2xl font-bold text-amber-600">
                <Clock className="h-5 w-5" />
                {p.untested + p.in_progress}
              </div>
            </div>
          </div>

          {/* 详细统计 */}
          <div className="mt-4 flex flex-wrap gap-4 text-sm text-muted-foreground">
            <span>未测: {p.untested}</span>
            <span>重测: {p.retest}</span>
            <span>阻塞: {p.blocked}</span>
            <span>跳过: {p.skipped}</span>
            <span>自定义状态: {testRun.customstatus_count}</span>
            <span>总用例: {testRun.test_cases_count}</span>
          </div>
        </div>

        {/* 脚本作业 */}
        {scriptJobs.length > 0 && (
          <div className="rounded-lg border bg-card">
            <div className="border-b p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="font-medium">脚本作业</h2>
                  <p className="text-sm text-muted-foreground">
                    该测试运行包含 {scriptJobs.length} 个脚本作业
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {selectedJobIds.size > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={batchRetrying}
                      onClick={handleBatchRetry}
                    >
                      {batchRetrying ? (
                        <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-3.5 w-3.5" />
                      )}
                      批量重试 ({selectedJobIds.size})
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={mappingJobs}
                    onClick={handleMapJobsToCases}
                  >
                    {mappingJobs ? (
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <MapPin className="mr-2 h-3.5 w-3.5" />
                    )}
                    同步到用例
                  </Button>
                </div>
              </div>
            </div>
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as ScriptType | "all")}>
              <div className="border-b px-4 pt-2">
                <TabsList>
                  <TabsTrigger value="all">
                    全部 {jobCounts.all > 0 && `(${jobCounts.all})`}
                  </TabsTrigger>
                  {(jobCounts.api_test || 0) > 0 && (
                    <TabsTrigger value="api_test">
                      API {jobCounts.api_test > 0 && `(${jobCounts.api_test})`}
                    </TabsTrigger>
                  )}
                  {(jobCounts.scenario || 0) > 0 && (
                    <TabsTrigger value="scenario">
                      场景 {jobCounts.scenario > 0 && `(${jobCounts.scenario})`}
                    </TabsTrigger>
                  )}
                  {(jobCounts.web_test || 0) > 0 && (
                    <TabsTrigger value="web_test">
                      Web {jobCounts.web_test > 0 && `(${jobCounts.web_test})`}
                    </TabsTrigger>
                  )}
                </TabsList>
              </div>
              <TabsContent value={activeTab} className="p-0">
                {jobsLoading ? (
                  <div className="flex h-32 items-center justify-center">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : filteredJobs.length === 0 ? (
                  <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                    该分类下暂无脚本作业
                  </div>
                ) : (
                  <div className="divide-y">
                    {filteredJobs.map((job) => {
                      const statusBadge = JOB_STATUS_BADGE[job.status];
                      const isExpanded = expandedJobId === job.id;
                      const summary = job.result_summary as Record<string, number> | null | undefined;
                      const total = summary?.total || 0;
                      const passed = summary?.passed || 0;
                      const failed = summary?.failed || 0;
                      const skipped = summary?.skipped || 0;
                      const passedPct = total > 0 ? (passed / total) * 100 : 0;
                      const failedPct = total > 0 ? (failed / total) * 100 : 0;
                      const skippedPct = total > 0 ? (skipped / total) * 100 : 0;
                      const canRetry = ["failed", "skipped", "cancelled"].includes(job.status);

                      return (
                        <div key={job.id} className="p-4 hover:bg-muted/50 transition-colors">
                          {/* 第一行：复选框 + 图标 + 名称 + 类型 + 状态 */}
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex items-start gap-3 min-w-0">
                              {canRetry && (
                                <div className="mt-1 shrink-0">
                                  <Checkbox
                                    checked={selectedJobIds.has(job.id)}
                                    onCheckedChange={() => toggleJobSelection(job.id)}
                                  />
                                </div>
                              )}
                              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                                {SCRIPT_TYPE_ICON[job.script_type]}
                              </div>
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="font-medium truncate">{job.script_name || job.script_identifier || job.script_id}</span>
                                  <Badge variant="outline" className="text-xs shrink-0">
                                    {SCRIPT_TYPE_LABEL[job.script_type]}
                                  </Badge>
                                  <Badge variant={statusBadge.variant} className="text-xs shrink-0">
                                    {statusBadge.label}
                                  </Badge>
                                  {job.retry_count > 0 && (
                                    <Badge variant="outline" className="text-xs shrink-0">
                                      重试 {job.retry_count}/{job.max_retries}
                                    </Badge>
                                  )}
                                </div>
                                {/* 时间线 */}
                                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                  <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    顺序 #{job.execution_order}
                                  </span>
                                  <span>{job.execution_mode === "parallel" ? "并行" : "顺序"}</span>
                                  {job.started_at && (
                                    <span>开始 {new Date(job.started_at).toLocaleString()}</span>
                                  )}
                                  {job.completed_at && (
                                    <span>结束 {new Date(job.completed_at).toLocaleString()}</span>
                                  )}
                                  {job.duration_ms && job.duration_ms > 0 && (
                                    <span className="font-mono text-foreground">{formatDuration(job.duration_ms)}</span>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* 操作按钮 */}
                            <div className="flex shrink-0 flex-wrap items-center gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 gap-1 text-xs"
                                onClick={() => handleViewLogs(job)}
                              >
                                <Logs className="h-3.5 w-3.5" />
                                日志
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 gap-1 text-xs"
                                onClick={() => handleViewHistory(job)}
                              >
                                <History className="h-3.5 w-3.5" />
                                历史
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 gap-1 text-xs"
                                onClick={() => handleViewBenchmark(job)}
                              >
                                <BarChart3 className="h-3.5 w-3.5" />
                                基准
                              </Button>
                              {job.report_path && (
                                <>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 gap-1 text-xs"
                                    onClick={() => handlePreviewReport(job)}
                                  >
                                    <Eye className="h-3.5 w-3.5" />
                                    预览
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 gap-1 text-xs"
                                    onClick={() => handleViewReport(job)}
                                  >
                                    <FileText className="h-3.5 w-3.5" />
                                    报告
                                  </Button>
                                </>
                              )}
                              {canRetry && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 gap-1 text-xs"
                                  disabled={retryingJobId === job.id}
                                  onClick={() => handleRetryJob(job)}
                                >
                                  {retryingJobId === job.id ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  ) : (
                                    <RefreshCw className="h-3.5 w-3.5" />
                                  )}
                                  重试
                                </Button>
                              )}
                            </div>
                          </div>

                          {/* 结果进度条 */}
                          {total > 0 && (
                            <div className="mt-3">
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-muted-foreground">
                                  {String(passed)} 通过 · {String(failed)} 失败 · {String(skipped)} 跳过 · 共 {String(total)}
                                </span>
                                <span className="font-mono">
                                  {Math.round((Number(passed) / Number(total)) * 100)}%
                                </span>
                              </div>
                              <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
                                <div className="bg-green-500 transition-all" style={{ width: `${passedPct}%` }} />
                                <div className="bg-red-500 transition-all" style={{ width: `${failedPct}%` }} />
                                <div className="bg-amber-400 transition-all" style={{ width: `${skippedPct}%` }} />
                              </div>
                            </div>
                          )}

                          {/* 错误信息（可折叠） */}
                          {job.error_message && (
                            <div className="mt-3">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 gap-1 text-xs text-destructive"
                                onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                              >
                                <AlertCircle className="h-3.5 w-3.5" />
                                {isExpanded ? "收起错误" : "查看错误详情"}
                              </Button>
                              {isExpanded && (
                                <div className="relative mt-2">
                                  <pre className="max-h-48 overflow-auto rounded-md border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive whitespace-pre-wrap">
                                    {job.error_message}
                                  </pre>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="absolute right-2 top-2 h-6 text-xs"
                                    onClick={() => navigator.clipboard.writeText(job.error_message || "")}
                                  >
                                    复制
                                  </Button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>
        )}

        {/* 测试用例列表（简略） */}
        {testRun.test_cases && testRun.test_cases.length > 0 && (
          <div className="rounded-lg border bg-card">
            <div className="border-b p-4">
              <h2 className="font-medium">测试用例</h2>
              <p className="text-sm text-muted-foreground">
                共 {testRun.test_cases.length} 个测试用例
              </p>
            </div>
            <div className="divide-y">
              {testRun.test_cases.slice(0, 20).map((tc) => (
                <div key={tc.id} className="flex items-center justify-between p-4 hover:bg-muted/50">
                  <div>
                    <div className="font-medium">{tc.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {tc.identifier} · {tc.latest_status}
                    </div>
                  </div>
                  <Badge variant={tc.latest_status === "passed" ? "default" : tc.latest_status === "failed" ? "destructive" : "secondary"}>
                    {tc.latest_status}
                  </Badge>
                </div>
              ))}
              {testRun.test_cases.length > 20 && (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  还有 {testRun.test_cases.length - 20} 个用例...
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 日志弹窗 */}
      <Dialog open={!!logDialogJob} onOpenChange={(open) => { if (!open) { setLogDialogJob(null); setLogDialogData(null); } }}>
        <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>执行日志</DialogTitle>
            <DialogDescription>
              {logDialogJob?.script_name || logDialogJob?.script_id}
            </DialogDescription>
          </DialogHeader>
          {logDialogLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : logDialogData ? (
            <ScrollArea className="flex-1 border rounded-md">
              <div className="p-4 space-y-4">
                {logDialogData.stdout && (
                  <div>
                    <div className="text-xs font-semibold text-muted-foreground mb-1">标准输出 (stdout)</div>
                    <pre className="text-xs bg-muted p-3 rounded-md overflow-auto whitespace-pre-wrap">{logDialogData.stdout}</pre>
                  </div>
                )}
                {logDialogData.stderr && (
                  <div>
                    <div className="text-xs font-semibold text-destructive mb-1">标准错误 (stderr)</div>
                    <pre className="text-xs bg-destructive/5 text-destructive p-3 rounded-md overflow-auto whitespace-pre-wrap">{logDialogData.stderr}</pre>
                  </div>
                )}
                {!logDialogData.stdout && !logDialogData.stderr && (
                  <div className="text-sm text-muted-foreground text-center py-8">暂无日志</div>
                )}
              </div>
            </ScrollArea>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* 报告预览弹窗 */}
      <Dialog open={!!reportDialogJob} onOpenChange={(open) => { if (!open) { setReportDialogJob(null); setReportDialogHtml(null); } }}>
        <DialogContent className="max-w-6xl max-h-[90vh] flex flex-col p-0">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>报告预览</DialogTitle>
            <DialogDescription>
              {reportDialogJob?.script_name || reportDialogJob?.script_id}
            </DialogDescription>
          </DialogHeader>
          {reportDialogLoading ? (
            <div className="flex h-96 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : reportDialogHtml ? (
            <div className="flex-1 overflow-hidden border-t">
              <iframe
                srcDoc={reportDialogHtml}
                className="w-full h-[70vh]"
                sandbox="allow-scripts allow-same-origin"
                title="报告预览"
              />
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* 历史趋势弹窗 */}
      <Dialog open={!!historyDialogJob} onOpenChange={(open) => { if (!open) { setHistoryDialogJob(null); setHistoryDialogData(null); } }}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>执行历史趋势</DialogTitle>
            <DialogDescription>
              {historyDialogJob?.script_name || historyDialogJob?.script_id}
            </DialogDescription>
          </DialogHeader>
          {historyDialogLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : historyDialogData && typeof historyDialogData === "object" && !("error" in historyDialogData) ? (
            <ScrollArea className="flex-1">
              <div className="p-4 space-y-4">
                <div className="grid grid-cols-4 gap-4">
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold">{(historyDialogData as any).success_rate}%</div>
                    <div className="text-xs text-muted-foreground">成功率</div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold text-green-600">{(historyDialogData as any).passed}</div>
                    <div className="text-xs text-muted-foreground">通过</div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold text-red-600">{(historyDialogData as any).failed}</div>
                    <div className="text-xs text-muted-foreground">失败</div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold text-amber-600">{(historyDialogData as any).total_runs}</div>
                    <div className="text-xs text-muted-foreground">总执行</div>
                  </div>
                </div>
                <div className="rounded-lg border">
                  <div className="border-b px-4 py-2 text-sm font-medium">最近执行记录</div>
                  <div className="divide-y">
                    {(historyDialogData as any).history?.map((h: any) => (
                      <div key={h.job_id} className="flex items-center justify-between px-4 py-2 text-sm">
                        <div className="flex items-center gap-2">
                          <Badge variant={h.status === "completed" ? "default" : h.status === "failed" ? "destructive" : "secondary"} className="text-xs">
                            {h.status}
                          </Badge>
                          <span className="text-muted-foreground">{h.duration_ms ? `${(h.duration_ms / 1000).toFixed(1)}s` : "-"}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">{h.completed_at ? new Date(h.completed_at).toLocaleString() : "-"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </ScrollArea>
          ) : (
            <div className="text-sm text-destructive text-center py-8">
              {(historyDialogData as any)?.error || "暂无历史数据"}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* 性能基准弹窗 */}
      <Dialog open={!!benchmarkDialogJob} onOpenChange={(open) => { if (!open) { setBenchmarkDialogJob(null); setBenchmarkDialogData(null); } }}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>性能基准</DialogTitle>
            <DialogDescription>
              {benchmarkDialogJob?.script_name || benchmarkDialogJob?.script_id}
            </DialogDescription>
          </DialogHeader>
          {benchmarkDialogLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : benchmarkDialogData && typeof benchmarkDialogData === "object" && !("error" in benchmarkDialogData) ? (
            <ScrollArea className="flex-1">
              <div className="p-4 space-y-4">
                <div className="grid grid-cols-4 gap-4">
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold">{formatDuration((benchmarkDialogData as any).avg_duration_ms)}</div>
                    <div className="text-xs text-muted-foreground">平均耗时</div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold text-green-600">{formatDuration((benchmarkDialogData as any).min_duration_ms)}</div>
                    <div className="text-xs text-muted-foreground">最快</div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold text-red-600">{formatDuration((benchmarkDialogData as any).max_duration_ms)}</div>
                    <div className="text-xs text-muted-foreground">最慢</div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-2xl font-bold text-amber-600">{formatDuration((benchmarkDialogData as any).median_duration_ms)}</div>
                    <div className="text-xs text-muted-foreground">中位数</div>
                  </div>
                </div>
                <div className="rounded-lg border">
                  <div className="border-b px-4 py-2 text-sm font-medium">耗时趋势</div>
                  <div className="divide-y">
                    {(benchmarkDialogData as any).runs?.map((r: any) => (
                      <div key={r.job_id} className="flex items-center justify-between px-4 py-2 text-sm">
                        <div className="flex items-center gap-2">
                          <Badge variant={r.status === "completed" ? "default" : r.status === "failed" ? "destructive" : "secondary"} className="text-xs">
                            {r.status}
                          </Badge>
                          <span>{formatDuration(r.duration_ms)}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">{r.date ? new Date(r.date).toLocaleString() : "-"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </ScrollArea>
          ) : (
            <div className="text-sm text-destructive text-center py-8">
              {(benchmarkDialogData as any)?.error || "暂无基准数据"}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
