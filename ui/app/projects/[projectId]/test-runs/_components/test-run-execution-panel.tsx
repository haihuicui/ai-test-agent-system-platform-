"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  PlayCircle,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Lock,
  Zap,
  CalendarClock,
  Loader2,
  Logs,
  Eye,
  BarChart3,
  History,
  FileText,
  RefreshCw,
  MapPin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getTestRun,
  getScriptJobs,
  getJobLogs,
  getJobReportUrl,
  retryJob,
  getScriptHistory,
  getScriptBenchmark,
  getSnapshotJobLogs,
  getSnapshotJobReportUrl,
  type TestRunInfo,
  type TestRunScriptJobInfo,
  type ScriptType,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import {
  RUN_STATE_BADGE,
  EXECUTION_MODE_BADGE,
  TRIGGER_TYPE_BADGE,
  TRIGGER_TYPE_ICON,
  SCRIPT_TYPE_ICON,
  SCRIPT_TYPE_LABEL,
  JOB_STATUS_BADGE,
  formatDuration,
  progressDoneRatio,
} from "./test-run-shared";

export interface TestRunExecutionPanelProps {
  projectId: string;
  runId: string;
  testRun?: TestRunInfo;
  scriptJobs?: TestRunScriptJobInfo[];
  onTestRunChange?: (run: TestRunInfo) => void;
  onScriptJobsChange?: (jobs: TestRunScriptJobInfo[]) => void;
  showViewFullDetail?: boolean;
  enablePolling?: boolean;
  onError?: (message: string) => void;
  // 脚本作业批量操作（仅在当前运行详情页传入）
  selectedJobIds?: Set<string>;
  onToggleJobSelection?: (jobId: string) => void;
  batchRetrying?: boolean;
  onBatchRetry?: () => void;
  mappingJobs?: boolean;
  onMapJobsToCases?: () => void;
  // 是否隐藏顶部基本信息卡片（用于详情页顶部已有 summary 的场景）
  hideHeader?: boolean;
  // 是否只读（查看历史快照时禁止重试、同步等写操作）
  readOnly?: boolean;
  // 当前展示的是哪个快照的作业（提供此值时使用快照日志/报告接口）
  snapshotId?: string;
}

export function TestRunExecutionPanel({
  projectId,
  runId,
  testRun: externalTestRun,
  scriptJobs: externalScriptJobs,
  onTestRunChange,
  onScriptJobsChange,
  showViewFullDetail = false,
  enablePolling = true,
  onError,
  selectedJobIds,
  onToggleJobSelection,
  batchRetrying,
  onBatchRetry,
  mappingJobs,
  onMapJobsToCases,
  hideHeader = false,
  readOnly = false,
  snapshotId,
}: TestRunExecutionPanelProps) {
  const router = useRouter();
  const isControlled = externalTestRun !== undefined;

  const [internalTestRun, setInternalTestRun] = React.useState<TestRunInfo | null>(null);
  const [runLoading, setRunLoading] = React.useState(!isControlled);
  const [runError, setRunError] = React.useState<string | null>(null);

  const [internalScriptJobs, setInternalScriptJobs] = React.useState<TestRunScriptJobInfo[]>([]);
  const [jobsLoading, setJobsLoading] = React.useState(false);

  const testRun = isControlled ? externalTestRun : internalTestRun;
  const scriptJobs = externalScriptJobs !== undefined ? externalScriptJobs : internalScriptJobs;

  const setTestRun = React.useCallback(
    (run: TestRunInfo | null) => {
      if (!isControlled) setInternalTestRun(run);
      if (run) onTestRunChange?.(run);
    },
    [isControlled, onTestRunChange]
  );

  const setScriptJobsList = React.useCallback(
    (jobs: TestRunScriptJobInfo[]) => {
      if (externalScriptJobs === undefined) setInternalScriptJobs(jobs);
      onScriptJobsChange?.(jobs);
    },
    [externalScriptJobs, onScriptJobsChange]
  );
  const [activeJobTab, setActiveJobTab] = React.useState<ScriptType | "all">("all");
  const [expandedJobId, setExpandedJobId] = React.useState<string | null>(null);
  const [retryingJobId, setRetryingJobId] = React.useState<string | null>(null);

  // 日志弹窗
  const [logDialogJob, setLogDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [logDialogData, setLogDialogData] = React.useState<{ stdout: string; stderr: string } | null>(null);
  const [logDialogLoading, setLogDialogLoading] = React.useState(false);

  // 报告预览弹窗
  const [reportDialogJob, setReportDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [reportDialogUrl, setReportDialogUrl] = React.useState<string | null>(null);
  const [reportDialogError, setReportDialogError] = React.useState<string | null>(null);
  const [reportDialogLoading, setReportDialogLoading] = React.useState(false);

  // 历史趋势弹窗
  const [historyDialogJob, setHistoryDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [historyDialogData, setHistoryDialogData] = React.useState<unknown>(null);
  const [historyDialogLoading, setHistoryDialogLoading] = React.useState(false);

  // 性能基准弹窗
  const [benchmarkDialogJob, setBenchmarkDialogJob] = React.useState<TestRunScriptJobInfo | null>(null);
  const [benchmarkDialogData, setBenchmarkDialogData] = React.useState<unknown>(null);
  const [benchmarkDialogLoading, setBenchmarkDialogLoading] = React.useState(false);

  const loadDetail = React.useCallback(async () => {
    if (!projectId || !runId || isControlled) return;
    try {
      const response = await getTestRun(projectId, runId);
      setTestRun(response.data);
      setRunError(null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载测试运行详情失败";
      setRunError(msg);
      onError?.(msg);
    } finally {
      setRunLoading(false);
    }
  }, [projectId, runId, isControlled, onError, setTestRun]);

  const loadScriptJobs = React.useCallback(async () => {
    if (!projectId || !runId || externalScriptJobs !== undefined) return;
    setJobsLoading(true);
    try {
      const response = await getScriptJobs(projectId, runId, { page: 1, page_size: 100 });
      setScriptJobsList(response.data.items);
    } catch {
      setScriptJobsList([]);
    } finally {
      setJobsLoading(false);
    }
  }, [projectId, runId, externalScriptJobs, setScriptJobsList]);

  React.useEffect(() => {
    if (isControlled) {
      setRunLoading(false);
      return;
    }
    setRunLoading(true);
    setRunError(null);
    loadDetail();
    loadScriptJobs();
  }, [loadDetail, loadScriptJobs, isControlled]);

  // 进行中时轮询刷新（仅在非受控且启用轮询时）
  React.useEffect(() => {
    if (isControlled || !enablePolling || !testRun || testRun.run_state !== "in_progress") return;
    const timer = setInterval(() => {
      loadDetail();
      loadScriptJobs();
    }, 3000);
    return () => clearInterval(timer);
  }, [isControlled, enablePolling, testRun?.run_state, loadDetail, loadScriptJobs]);

  async function handleViewLogs(job: TestRunScriptJobInfo) {
    setLogDialogJob(job);
    setLogDialogLoading(true);
    try {
      const res = snapshotId
        ? await getSnapshotJobLogs(projectId, runId, snapshotId, job.id)
        : await getJobLogs(projectId, runId, job.id);
      setLogDialogData(res.data);
    } catch (err) {
      setLogDialogData({ stdout: "", stderr: err instanceof ApiError ? err.message : "加载日志失败" });
    } finally {
      setLogDialogLoading(false);
    }
  }

  async function handlePreviewReport(job: TestRunScriptJobInfo) {
    setReportDialogJob(job);
    setReportDialogUrl(null);
    setReportDialogError(null);
    setReportDialogLoading(true);
    try {
      const response = snapshotId
        ? await getSnapshotJobReportUrl(projectId, runId, snapshotId, job.id)
        : await getJobReportUrl(projectId, runId, job.id);
      const url = response.data.url;
      setReportDialogUrl(url.endsWith("/") ? url : `${url}/`);
    } catch (err) {
      setReportDialogError(err instanceof ApiError ? err.message : "加载报告失败");
    } finally {
      setReportDialogLoading(false);
    }
  }

  async function handleViewHistory(job: TestRunScriptJobInfo) {
    setHistoryDialogJob(job);
    setHistoryDialogLoading(true);
    try {
      const res = await getScriptHistory(projectId, runId, job.script_type, job.script_id, 30);
      setHistoryDialogData(res.data);
    } catch (err) {
      setHistoryDialogData({ error: err instanceof ApiError ? err.message : "加载历史失败" });
    } finally {
      setHistoryDialogLoading(false);
    }
  }

  async function handleViewBenchmark(job: TestRunScriptJobInfo) {
    setBenchmarkDialogJob(job);
    setBenchmarkDialogLoading(true);
    try {
      const res = await getScriptBenchmark(projectId, runId, job.script_type, job.script_id, 30);
      setBenchmarkDialogData(res.data);
    } catch (err) {
      setBenchmarkDialogData({ error: err instanceof ApiError ? err.message : "加载基准失败" });
    } finally {
      setBenchmarkDialogLoading(false);
    }
  }

  async function handleRetryJob(job: TestRunScriptJobInfo) {
    setRetryingJobId(job.id);
    try {
      await retryJob(projectId, runId, job.id);
      // 重试后需要刷新当前运行状态；在受控模式下 loadDetail/loadScriptJobs 会跳过，因此直接拉取
      if (!isControlled) {
        await loadDetail();
        await loadScriptJobs();
      } else {
        const runRes = await getTestRun(projectId, runId);
        setTestRun(runRes.data);
        const jobsRes = await getScriptJobs(projectId, runId, { page: 1, page_size: 100 });
        setScriptJobsList(jobsRes.data.items);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "重试失败";
      onError?.(msg);
    } finally {
      setRetryingJobId(null);
    }
  }

  const filteredJobs = React.useMemo(() => {
    if (activeJobTab === "all") return scriptJobs;
    return scriptJobs.filter((j) => j.script_type === activeJobTab);
  }, [scriptJobs, activeJobTab]);

  const jobCounts = React.useMemo(() => {
    const counts: Record<string, number> = { all: scriptJobs.length };
    for (const job of scriptJobs) {
      counts[job.script_type] = (counts[job.script_type] || 0) + 1;
    }
    return counts;
  }, [scriptJobs]);

  const totalCasesInJobs = React.useMemo(() => {
    return scriptJobs.reduce((sum, job) => {
      const summary = job.result_summary as Record<string, number> | null | undefined;
      return sum + (summary?.total || 0);
    }, 0);
  }, [scriptJobs]);

  if (runLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (runError || !testRun) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-muted-foreground">{runError || "测试运行不存在"}</p>
        <Button variant="outline" onClick={loadDetail}>
          <RefreshCw className="mr-2 h-4 w-4" />
          重试
        </Button>
      </div>
    );
  }

  const p = testRun.overall_progress;
  const progress = progressDoneRatio(testRun);
  const stateInfo = RUN_STATE_BADGE[testRun.run_state];
  const closed = testRun.active_state === "closed";

  return (
    <div className="space-y-6">
      {!hideHeader && (
        <>
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
                  {TRIGGER_TYPE_ICON[testRun.trigger_type]}
                  {TRIGGER_TYPE_BADGE[testRun.trigger_type]?.label ?? "手动触发"}
                </span>
              )}
              {testRun.trigger_type === "scheduled" && testRun.schedule_name && (
                <span className="flex items-center gap-1">
                  <CalendarClock className="h-3.5 w-3.5" />
                  来源: {testRun.schedule_name}
                </span>
              )}
              <span>创建于 {new Date(testRun.created_at).toLocaleString()}</span>
              {testRun.assignee && <span>负责人: {testRun.assignee}</span>}
            </div>
          </div>
          {showViewFullDetail && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push(`/projects/${projectId}/test-runs/${testRun.identifier}`)}
            >
              <Eye className="mr-2 h-4 w-4" />
              查看完整详情
            </Button>
          )}
        </div>

        {/* 进度概览 */}
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border p-4">
            <div className="text-sm text-muted-foreground">通过率</div>
            <div className="mt-1 text-2xl font-bold">
              {testRun.test_cases_count ? Math.round((p.passed / testRun.test_cases_count) * 100) : 0}%
            </div>
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
      </>
      )}

      {/* 脚本作业 */}
      {scriptJobs.length > 0 && (
        <div className="rounded-lg border bg-card">
          <div className="border-b p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-medium">脚本作业</h2>
                <p className="text-sm text-muted-foreground">
                  该测试运行包含 {scriptJobs.length} 个脚本作业
                  {totalCasesInJobs > 0 && `，共 ${totalCasesInJobs} 个用例`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {selectedJobIds && selectedJobIds.size > 0 && onBatchRetry && !readOnly && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={batchRetrying}
                    onClick={onBatchRetry}
                  >
                    {batchRetrying ? (
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-2 h-3.5 w-3.5" />
                    )}
                    批量重试 ({selectedJobIds.size})
                  </Button>
                )}
                {onMapJobsToCases && !readOnly && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={mappingJobs}
                    onClick={onMapJobsToCases}
                  >
                    {mappingJobs ? (
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <MapPin className="mr-2 h-3.5 w-3.5" />
                    )}
                    同步到用例
                  </Button>
                )}
              </div>
            </div>
          </div>
          <Tabs value={activeJobTab} onValueChange={(v) => setActiveJobTab(v as ScriptType | "all")}>
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
            <TabsContent value={activeJobTab} className="p-0">
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
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-3 min-w-0">
                            {canRetry && onToggleJobSelection && !readOnly && (
                              <div className="mt-1 shrink-0">
                                <Checkbox
                                  checked={selectedJobIds?.has(job.id) ?? false}
                                  onCheckedChange={() => onToggleJobSelection(job.id)}
                                />
                              </div>
                            )}
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                              {SCRIPT_TYPE_ICON[job.script_type]}
                            </div>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium truncate">
                                  {job.script_name || job.script_identifier || job.script_id}
                                </span>
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

                          <div className="flex shrink-0 flex-wrap items-center gap-1">
                            {(!readOnly || snapshotId) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 gap-1 text-xs"
                                onClick={() => handleViewLogs(job)}
                              >
                                <Logs className="h-3.5 w-3.5" />
                                日志
                              </Button>
                            )}
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
                            {job.report_path && (!readOnly || snapshotId) && (
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
                                  onClick={async () => {
                                    try {
                                      const response = snapshotId
                                        ? await getSnapshotJobReportUrl(projectId, runId, snapshotId, job.id)
                                        : await getJobReportUrl(projectId, runId, job.id);
                                      const url = response.data.url;
                                      if (url) window.open(url, "_blank");
                                    } catch {
                                      // 静默失败
                                    }
                                  }}
                                >
                                  <FileText className="h-3.5 w-3.5" />
                                  报告
                                </Button>
                              </>
                            )}
                            {canRetry && !readOnly && (
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

                        {total > 0 && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="text-muted-foreground">
                                {String(passed)} 通过 · {String(failed)} 失败 · {String(skipped)} 跳过 · 共 {String(total)}
                              </span>
                              <span className="font-mono">{Math.round((Number(passed) / Number(total)) * 100)}%</span>
                            </div>
                            <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
                              <div className="bg-green-500 transition-all" style={{ width: `${passedPct}%` }} />
                              <div className="bg-red-500 transition-all" style={{ width: `${failedPct}%` }} />
                              <div className="bg-amber-400 transition-all" style={{ width: `${skippedPct}%` }} />
                            </div>
                          </div>
                        )}

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

      {/* 测试用例列表 */}
      {testRun.test_cases && testRun.test_cases.length > 0 && (
        <div className="rounded-lg border bg-card">
          <div className="border-b p-4">
            <h2 className="font-medium">测试用例</h2>
            <p className="text-sm text-muted-foreground">共 {testRun.test_cases.length} 个测试用例</p>
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
                <Badge
                  variant={
                    tc.latest_status === "passed"
                      ? "default"
                      : tc.latest_status === "failed"
                        ? "destructive"
                        : "secondary"
                  }
                >
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

      {/* 日志弹窗 */}
      <Dialog open={!!logDialogJob} onOpenChange={(open) => { if (!open) { setLogDialogJob(null); setLogDialogData(null); } }}>
        <DialogContent className="max-w-4xl h-[80vh] max-h-[80vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>执行日志</DialogTitle>
            <DialogDescription>{logDialogJob?.script_name || logDialogJob?.script_id}</DialogDescription>
          </DialogHeader>
          {logDialogLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : logDialogData ? (
            <div className="min-h-0 flex-1 overflow-hidden">
              <ScrollArea className="h-full border rounded-md">
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
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* 报告预览弹窗 */}
      <Dialog open={!!reportDialogJob} onOpenChange={(open) => { if (!open) { setReportDialogJob(null); setReportDialogUrl(null); setReportDialogError(null); } }}>
        <DialogContent className="max-w-6xl max-h-[90vh] flex flex-col p-0">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>报告预览</DialogTitle>
            <DialogDescription>{reportDialogJob?.script_name || reportDialogJob?.script_id}</DialogDescription>
          </DialogHeader>
          {reportDialogLoading ? (
            <div className="flex h-96 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : reportDialogError ? (
            <div className="flex h-96 items-center justify-center px-6">
              <p className="text-destructive">{reportDialogError}</p>
            </div>
          ) : reportDialogUrl ? (
            <div className="flex-1 overflow-hidden border-t">
              <iframe src={reportDialogUrl} className="w-full h-[70vh]" sandbox="allow-scripts allow-same-origin" title="报告预览" />
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* 历史趋势弹窗 */}
      <Dialog open={!!historyDialogJob} onOpenChange={(open) => { if (!open) { setHistoryDialogJob(null); setHistoryDialogData(null); } }}>
        <DialogContent className="max-w-2xl h-[80vh] max-h-[80vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>执行历史趋势</DialogTitle>
            <DialogDescription>{historyDialogJob?.script_name || historyDialogJob?.script_id}</DialogDescription>
          </DialogHeader>
          {historyDialogLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : historyDialogData && typeof historyDialogData === "object" && !("error" in historyDialogData) ? (
            <div className="min-h-0 flex-1 overflow-hidden">
              <ScrollArea className="h-full">
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
            </div>
          ) : (
            <div className="text-sm text-destructive text-center py-8">
              {(historyDialogData as any)?.error || "暂无历史数据"}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* 性能基准弹窗 */}
      <Dialog open={!!benchmarkDialogJob} onOpenChange={(open) => { if (!open) { setBenchmarkDialogJob(null); setBenchmarkDialogData(null); } }}>
        <DialogContent className="max-w-2xl h-[80vh] max-h-[80vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>性能基准</DialogTitle>
            <DialogDescription>{benchmarkDialogJob?.script_name || benchmarkDialogJob?.script_id}</DialogDescription>
          </DialogHeader>
          {benchmarkDialogLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : benchmarkDialogData && typeof benchmarkDialogData === "object" && !("error" in benchmarkDialogData) ? (
            <div className="min-h-0 flex-1 overflow-hidden">
              <ScrollArea className="h-full">
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
            </div>
          ) : (
            <div className="text-sm text-destructive text-center py-8">
              {(benchmarkDialogData as any)?.error || "暂无基准数据"}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
