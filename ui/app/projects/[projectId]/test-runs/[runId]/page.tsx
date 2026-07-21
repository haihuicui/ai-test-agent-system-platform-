"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Play,
  PlayCircle,
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
  MoreHorizontal,
  Trash2,
  Pencil,
  History,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  DialogFooter,
} from "@/components/ui/dialog";
import {
  getTestRun,
  listTestRuns,
  executeTestRun,
  cancelTestRun,
  patchTestRun,
  deleteTestRun,
  getScriptJobs,
  batchRetryJobs,
  mapJobsToTestCases,
  subscribeToTestRunEvents,
  listEnvironments,
  csvToList,
  listToCsv,
  listExecutionSnapshots,
  getExecutionSnapshot,
  type TestRunInfo,
  type TestRunListInfo,
  type TestRunScriptJobInfo,
  type TestRunState,
  type ExecutionMode,
  type TriggerType,
  type EnvironmentInfo,
  type ScriptSelection,
  type FailurePolicy,
  type TestRunExecutionSnapshotInfo,
  FAILURE_POLICY_OPTIONS,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { ScriptSelector } from "../_components/script-selector";
import { TestRunExecutionPanel } from "../_components/test-run-execution-panel";
import {
  RUN_STATE_BADGE,
  RUN_STATE_OPTIONS,
  EXECUTION_MODE_BADGE,
  TRIGGER_TYPE_BADGE,
  progressDoneRatio,
} from "../_components/test-run-shared";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZCR1lnPT06Zjc3ZTQ2ZTk=

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
  const [cancelling, setCancelling] = React.useState(false);

  // 批量重试状态
  const [selectedJobIds, setSelectedJobIds] = React.useState<Set<string>>(new Set());
  const [batchRetrying, setBatchRetrying] = React.useState(false);

  // 映射到用例状态
  const [mappingJobs, setMappingJobs] = React.useState(false);

  // 编辑弹窗状态
  const [editOpen, setEditOpen] = React.useState(false);
  const [editForm, setEditForm] = React.useState<{
    name: string;
    description: string;
    run_state: TestRunState;
    assignee: string;
    test_case_assignee: string;
    tags: string;
    issues: string;
    execution_mode: ExecutionMode;
    max_concurrency: number;
    failure_policy: FailurePolicy;
    environment_id: string;
    scripts: ScriptSelection[];
  }>({
    name: "",
    description: "",
    run_state: "new_run",
    assignee: "",
    test_case_assignee: "",
    tags: "",
    issues: "",
    execution_mode: "sequential",
    max_concurrency: 5,
    failure_policy: "continue",
    environment_id: "__default__",
    scripts: [],
  });
  const [editSaving, setEditSaving] = React.useState(false);
  const [editEnvironments, setEditEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [editEnvironmentsLoading, setEditEnvironmentsLoading] = React.useState(false);

  // 删除确认状态
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);

  // 历史执行记录状态
  const SNAPSHOT_PAGE_SIZE = 100;
  const [snapshots, setSnapshots] = React.useState<TestRunExecutionSnapshotInfo[]>([]);
  const [snapshotsTotal, setSnapshotsTotal] = React.useState(0);
  const [snapshotsLoading, setSnapshotsLoading] = React.useState(false);
  const [selectedSnapshotId, setSelectedSnapshotId] = React.useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = React.useState<TestRunExecutionSnapshotInfo | null>(null);
  const [snapshotDetailLoading, setSnapshotDetailLoading] = React.useState(false);

  // ref 用于 SSE handler 中读取最新状态，避免闭包问题
  const testRunRef = React.useRef<TestRunInfo | null>(null);
  React.useEffect(() => {
    testRunRef.current = testRun;
  }, [testRun]);

  // 编辑弹窗打开时加载环境列表
  React.useEffect(() => {
    if (!projectId || !editOpen) return;
    let cancelled = false;
    setEditEnvironmentsLoading(true);
    listEnvironments(projectId)
      .then((res) => {
        if (cancelled) return;
        setEditEnvironments(res.data || []);
      })
      .catch(() => {
        if (cancelled) return;
        setEditEnvironments([]);
      })
      .finally(() => {
        if (!cancelled) setEditEnvironmentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [editOpen, projectId]);

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

  const loadSnapshots = React.useCallback(async () => {
    if (!projectId || !runId || !testRun) return;

    setSnapshotsLoading(true);
    try {
      const response = await listExecutionSnapshots(projectId, runId, {
        page: 1,
        page_size: SNAPSHOT_PAGE_SIZE,
      });
      const items = response.data?.items ?? [];
      setSnapshots(items);
      setSnapshotsTotal(response.data?.total ?? 0);
      setSelectedSnapshotId((prev) => {
        if (prev && items.some((s) => s.id === prev)) {
          return prev;
        }
        // 默认选中"当前"，不自动选中快照
        return "__current__";
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[TestRunDetailPage] 加载执行快照失败:", err);
      setSnapshots([]);
      setSnapshotsTotal(0);
      setSelectedSnapshotId("__current__");
    } finally {
      setSnapshotsLoading(false);
    }
  }, [projectId, runId, testRun]);

  // 加载选中快照的详情
  const loadSnapshotDetail = React.useCallback(
    async (snapshotId: string) => {
      if (!projectId || !runId || snapshotId === "__current__") return;
      setSnapshotDetailLoading(true);
      try {
        const response = await getExecutionSnapshot(projectId, runId, snapshotId);
        setSelectedSnapshot(response.data);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[TestRunDetailPage] 加载快照详情失败:", err);
        setSelectedSnapshot(null);
      } finally {
        setSnapshotDetailLoading(false);
      }
    },
    [projectId, runId]
  );

  React.useEffect(() => {
    if (selectedSnapshotId && selectedSnapshotId !== "__current__") {
      loadSnapshotDetail(selectedSnapshotId);
    } else {
      setSelectedSnapshot(null);
    }
  }, [selectedSnapshotId, loadSnapshotDetail]);

  React.useEffect(() => {
    loadDetail();
    loadScriptJobs();
  }, [loadDetail, loadScriptJobs]);

  React.useEffect(() => {
    if (testRun) {
      loadSnapshots();
    }
  }, [testRun, loadSnapshots]);

  // 没有快照时，默认选中当前运行
  React.useEffect(() => {
    if (testRun && !selectedSnapshotId) {
      setSelectedSnapshotId("__current__");
    }
  }, [testRun, selectedSnapshotId]);

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
      // 重试会把 run 置回 in_progress，刷新详情以触发 SSE 实时订阅
      await loadDetailSilent();
      await loadScriptJobs();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "批量重试失败";
      setError(msg);
    } finally {
      setBatchRetrying(false);
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

  function openEdit() {
    if (!testRun) return;
    setEditForm({
      name: testRun.name,
      description: testRun.description ?? "",
      run_state: testRun.run_state,
      assignee: testRun.assignee ?? "",
      test_case_assignee: testRun.test_case_assignee ?? "",
      tags: listToCsv(testRun.tags) ?? "",
      issues: listToCsv(testRun.issues) ?? "",
      execution_mode: testRun.execution_mode ?? "sequential",
      max_concurrency: testRun.max_concurrency ?? 5,
      failure_policy: testRun.failure_policy ?? "continue",
      environment_id: testRun.environment_id ?? "__default__",
      scripts:
        testRun.script_jobs?.map((job) => ({
          script_type: job.script_type,
          script_id: job.script_id,
          script_identifier: job.script_identifier,
          script_name: job.script_name,
          execution_order: job.execution_order,
          execution_mode: job.execution_mode,
        })) ?? [],
    });
    setEditOpen(true);
  }

  async function handleEditSave() {
    if (!testRun) return;
    setEditSaving(true);
    try {
      const isManual = testRun.trigger_type === "manual";
      await patchTestRun(projectId, testRun.identifier, {
        name: editForm.name.trim() || undefined,
        description: editForm.description.trim() || undefined,
        run_state: editForm.run_state,
        assignee: editForm.assignee.trim() || undefined,
        test_case_assignee: editForm.test_case_assignee.trim() || undefined,
        tags: editForm.tags.trim() ? csvToList(editForm.tags) : [],
        issues: editForm.issues.trim() ? csvToList(editForm.issues) : [],
        ...(isManual
          ? {
              execution_mode: editForm.execution_mode,
              max_concurrency: editForm.max_concurrency,
              failure_policy: editForm.failure_policy,
              environment_id:
                editForm.environment_id === "__default__"
                  ? undefined
                  : editForm.environment_id,
              scripts: editForm.scripts,
            }
          : {}),
      });
      setEditOpen(false);
      await loadDetail();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "更新测试运行失败";
      setError(msg);
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDelete() {
    if (!testRun) return;
    setDeleting(true);
    try {
      await deleteTestRun(projectId, testRun.identifier);
      router.push(`/projects/${projectId}/test-runs`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "删除测试运行失败";
      setError(msg);
      setDeleting(false);
    }
  }

  const isViewingSnapshot = selectedSnapshotId !== "__current__";

  const runOptions = React.useMemo(() => {
    const currentOption = {
      id: "__current__",
      identifier: runId,
      name: testRun?.name ?? "当前执行",
      run_state: testRun?.run_state ?? "new_run",
      created_at: testRun?.created_at ?? "",
    } as unknown as TestRunListInfo;
    return [currentOption, ...(snapshots as unknown as TestRunListInfo[])];
  }, [testRun, snapshots, runId]);

  const selectedHistoryRun = React.useMemo(
    () =>
      runOptions.find((r) => r.id === selectedSnapshotId) || runOptions[0] || null,
    [runOptions, selectedSnapshotId]
  );

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
        {/* 顶部导航与操作 */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push(`/projects/${projectId}/test-runs`)}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回列表
          </Button>

          <div className="flex items-center gap-2">
            {testRun.run_state === "in_progress" ? (
              <Button variant="destructive" onClick={handleCancel} disabled={cancelling}>
                {cancelling ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Square className="mr-2 h-4 w-4" />
                )}
                取消执行
              </Button>
            ) : testRun.trigger_type === "scheduled" ? (
              <Button
                variant="outline"
                onClick={() =>
                  router.push(
                    `/projects/${projectId}/test-runs?tab=scheduled&show_schedules=1`
                  )
                }
              >
                <CalendarClock className="mr-2 h-4 w-4" />
                查看调度规则
              </Button>
            ) : (
              <Button onClick={handleExecute} disabled={executing || closed}>
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
                <DropdownMenuItem onClick={openEdit}>
                  <Pencil className="mr-2 h-4 w-4" />
                  编辑
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => setDeleteConfirmOpen(true)}
                  className="text-destructive"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  删除
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* 基本信息卡片 */}
        <div className="rounded-lg border bg-card p-6">
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
                  ) : (
                    <Play className="h-3.5 w-3.5" />
                  )}
                  {TRIGGER_TYPE_BADGE[testRun.trigger_type]?.label ?? "手动触发"}
                </span>
              )}
              {testRun.trigger_type === "scheduled" && (
                <span
                  className="flex cursor-pointer items-center gap-1 hover:underline"
                  onClick={() =>
                    router.push(
                      testRun.schedule_id
                        ? `/projects/${projectId}/test-runs/schedules/${testRun.schedule_id}`
                        : `/projects/${projectId}/test-runs?tab=scheduled`
                    )
                  }
                >
                  <CalendarClock className="h-3.5 w-3.5" />
                  来源: {testRun.schedule_name ?? "已删除的调度"}
                </span>
              )}
              <span>创建于 {new Date(testRun.created_at).toLocaleString()}</span>
              {testRun.assignee && <span>负责人: {testRun.assignee}</span>}
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

        {/* 执行记录 */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center gap-2 border-b p-4">
            <History className="h-5 w-5 text-primary" />
            <h2 className="font-medium">执行记录</h2>
          </div>
          <div className="p-4">
            {snapshotsLoading ? (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : runOptions.length === 0 ? (
              <div className="flex h-32 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
                <History className="h-10 w-10 text-muted-foreground/50" />
                <p>暂无执行记录</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <Label className="text-muted-foreground">选择执行记录</Label>
                    <Select
                      value={selectedSnapshotId ?? ""}
                      onValueChange={(v) => setSelectedSnapshotId(v)}
                    >
                      <SelectTrigger className="w-[360px]">
                        <SelectValue placeholder="选择执行记录" />
                      </SelectTrigger>
                      <SelectContent>
                        {runOptions.map((option) => {
                          const stateInfo = RUN_STATE_BADGE[option.run_state];
                          const isCurrent = option.id === "__current__";
                          const snapshot = snapshots.find((s) => s.id === option.id);
                          const label = snapshot
                            ? `第 ${snapshot.execution_number} 次执行 · ${stateInfo.label}`
                            : `${option.identifier} · ${option.name} · ${stateInfo.label}`;
                          return (
                            <SelectItem key={option.id} value={option.id}>
                              {label}
                              {isCurrent && " · (当前)"}
                              {snapshot?.completed_at &&
                                ` · ${new Date(snapshot.completed_at).toLocaleString()}`}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>

                  {false && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {}}
                    >
                      <History className="mr-2 h-4 w-4" />
                      查看全部
                    </Button>
                  )}
                </div>

                {isViewingSnapshot ? (
                  snapshotDetailLoading ? (
                    <div className="flex h-32 items-center justify-center">
                      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                  ) : selectedSnapshot ? (
                    <TestRunExecutionPanel
                      projectId={projectId}
                      runId={runId}
                      testRun={{
                        ...testRun,
                        run_state: selectedSnapshot.run_state as TestRunInfo["run_state"],
                        overall_progress: selectedSnapshot.overall_progress ?? testRun.overall_progress,
                        test_cases_count: selectedSnapshot.overall_progress
                          ? Object.values(selectedSnapshot.overall_progress).reduce(
                              (a, b) => a + (b as number),
                              0
                            )
                          : testRun.test_cases_count,
                      }}
                      scriptJobs={(selectedSnapshot.snapshot_jobs ?? []) as TestRunScriptJobInfo[]}
                      hideHeader
                      readOnly
                      snapshotId={selectedSnapshot.id}
                      onError={(msg) => setError(msg)}
                    />
                  ) : null
                ) : testRun ? (
                  <TestRunExecutionPanel
                    projectId={projectId}
                    runId={runId}
                    testRun={testRun}
                    scriptJobs={scriptJobs}
                    hideHeader
                    onTestRunChange={setTestRun}
                    onScriptJobsChange={setScriptJobs}
                    selectedJobIds={selectedJobIds}
                    onToggleJobSelection={toggleJobSelection}
                    batchRetrying={batchRetrying}
                    onBatchRetry={handleBatchRetry}
                    mappingJobs={mappingJobs}
                    onMapJobsToCases={handleMapJobsToCases}
                    onError={(msg) => setError(msg)}
                  />
                ) : null}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 编辑弹窗 */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>编辑测试运行</DialogTitle>
            <DialogDescription>
              {testRun ? `修改 ${testRun.identifier} 的基础信息` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="detail-edit-name">名称</Label>
              <Input
                id="detail-edit-name"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-edit-description">描述</Label>
              <Textarea
                id="detail-edit-description"
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                placeholder="请输入描述（可选）"
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-edit-state">运行状态</Label>
              <Select
                value={editForm.run_state}
                onValueChange={(v) => setEditForm({ ...editForm, run_state: v as TestRunState })}
              >
                <SelectTrigger id="detail-edit-state">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RUN_STATE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-edit-assignee">负责人邮箱</Label>
              <Input
                id="detail-edit-assignee"
                value={editForm.assignee}
                onChange={(e) => setEditForm({ ...editForm, assignee: e.target.value })}
                placeholder="user@example.com（可选）"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-edit-test-case-assignee">用例默认负责人邮箱</Label>
              <Input
                id="detail-edit-test-case-assignee"
                value={editForm.test_case_assignee}
                onChange={(e) => setEditForm({ ...editForm, test_case_assignee: e.target.value })}
                placeholder="user@example.com（可选）"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-edit-tags">标签（逗号分隔）</Label>
              <Input
                id="detail-edit-tags"
                value={editForm.tags}
                onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                placeholder="tag1, tag2, tag3"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-edit-issues">关联问题（逗号分隔）</Label>
              <Input
                id="detail-edit-issues"
                value={editForm.issues}
                onChange={(e) => setEditForm({ ...editForm, issues: e.target.value })}
                placeholder="ISSUE-1, ISSUE-2"
              />
            </div>
            {testRun.trigger_type === "scheduled" && (
              <p className="text-sm text-muted-foreground">
                该测试运行为定时触发，执行模式、环境及脚本由调度模板控制，不可在此处修改。
              </p>
            )}
            {testRun.trigger_type === "manual" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="detail-edit-exec-mode">执行模式</Label>
                  <Select
                    value={editForm.execution_mode}
                    onValueChange={(v) => setEditForm({ ...editForm, execution_mode: v as ExecutionMode })}
                  >
                    <SelectTrigger id="detail-edit-exec-mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sequential">顺序执行</SelectItem>
                      <SelectItem value="parallel">并行执行</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {editForm.execution_mode === "parallel" && (
                  <div className="space-y-2">
                    <Label htmlFor="detail-edit-max-concurrency">最大并发数</Label>
                    <Input
                      id="detail-edit-max-concurrency"
                      type="number"
                      min={1}
                      max={50}
                      value={editForm.max_concurrency}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          max_concurrency: parseInt(e.target.value) || 5,
                        })
                      }
                    />
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="detail-edit-failure-policy">失败策略</Label>
                  <Select
                    value={editForm.failure_policy}
                    onValueChange={(v) =>
                      setEditForm({
                        ...editForm,
                        failure_policy: v as FailurePolicy,
                      })
                    }
                  >
                    <SelectTrigger id="detail-edit-failure-policy">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {FAILURE_POLICY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="detail-edit-environment">执行环境</Label>
                  <Select
                    value={editForm.environment_id}
                    onValueChange={(v) =>
                      setEditForm({
                        ...editForm,
                        environment_id: v,
                      })
                    }
                    disabled={editEnvironmentsLoading}
                  >
                    <SelectTrigger id="detail-edit-environment">
                      <SelectValue placeholder="选择执行环境" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__default__">使用项目默认环境</SelectItem>
                      {editEnvironments.map((env) => (
                        <SelectItem key={env.id} value={env.id}>
                          {env.name}
                          {env.is_default ? "（默认）" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {editEnvironmentsLoading && (
                    <p className="text-xs text-muted-foreground">加载环境中...</p>
                  )}
                </div>
                <div className="space-y-2 pt-2">
                  <ScriptSelector
                    projectId={projectId}
                    scripts={editForm.scripts}
                    onScriptsChange={(scripts) =>
                      setEditForm({ ...editForm, scripts })
                    }
                    disabled={editSaving}
                  />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)} disabled={editSaving}>
              取消
            </Button>
            <Button onClick={handleEditSave} disabled={editSaving || !editForm.name.trim()}>
              {editSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认弹窗 */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>删除测试运行?</DialogTitle>
            <DialogDescription>
              确认删除 {testRun?.identifier} ({testRun?.name})？此操作不可恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)} disabled={deleting}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
