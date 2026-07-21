"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Plus,
  Search,
  PlayCircle,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  MoreHorizontal,
  Pencil,
  Trash2,
  Eye,
  Loader2,
  AlertCircle,
  Lock,
  RefreshCw,
  CalendarClock,
  Zap,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
  Pagination,
} from "@/components/ui/pagination";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  listTestRuns,
  createTestRun,
  getTestRun,
  closeTestRun,
  deleteTestRun,
  patchTestRun,
  executeTestRun,
  listEnvironments,
  getSchedules,
  type TestRunListInfo,
  type TestRunInfo,
  type TestRunState,
  type TestRunCreate,
  type ExecutionMode,
  type TriggerType,
  type ScriptSelection,
  type EnvironmentInfo,
  type TestRunScheduleInfo,
  type FailurePolicy,
  FAILURE_POLICY_OPTIONS,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import {
  TRIGGER_TYPE_LABEL,
  formatNextRun,
  formatScheduleDate,
  buildCronDescription,
} from "./_components/schedule-rules-panel";
import { ScheduleRuleActions } from "./_components/schedule-rule-actions";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNKaVRBPT06NjI0YTJkOWQ=

const PAGE_SIZE = 20;

// 重型组件代码分割
const ScriptSelector = dynamic(
  () => import("./_components/script-selector").then((m) => ({ default: m.ScriptSelector })),
  { ssr: false }
);

const ScheduleRulesPanel = dynamic(
  () =>
    import("./_components/schedule-rules-panel").then((m) => ({
      default: m.ScheduleRulesPanel,
    })),
  { ssr: false }
);

const CreateScheduleDialog = dynamic(
  () =>
    import("./_components/create-schedule-dialog").then((m) => ({
      default: m.CreateScheduleDialog,
    })),
  { ssr: false }
);


const RUN_STATE_OPTIONS: { value: TestRunState; label: string }[] = [
  { value: "new_run", label: "新建" },
  { value: "in_progress", label: "进行中" },
  { value: "under_review", label: "评审中" },
  { value: "rejected", label: "已拒绝" },
  { value: "approved", label: "已批准" },
  { value: "done", label: "已完成" },
  { value: "done_with_failures", label: "已完成（含失败）" },
  { value: "closed", label: "已关闭" },
];
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNKaVRBPT06NjI0YTJkOWQ=

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
  done_with_failures: { label: "已完成（含失败）", variant: "destructive" },
  closed: { label: "已关闭", variant: "secondary" },
};
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNKaVRBPT06NjI0YTJkOWQ=

const EXECUTION_MODE_BADGE: Record<ExecutionMode, { label: string; icon: React.ReactNode }> = {
  sequential: { label: "顺序", icon: <Clock className="mr-1 h-3 w-3" /> },
  parallel: { label: "并行", icon: <Zap className="mr-1 h-3 w-3" /> },
};

const TRIGGER_TYPE_BADGE: Record<TriggerType, { label: string; icon: React.ReactNode; variant: "default" | "secondary" | "outline" | "destructive" }> = {
  manual: { label: "手动", icon: <Play className="mr-1 h-3 w-3" />, variant: "secondary" },
  scheduled: { label: "定时", icon: <CalendarClock className="mr-1 h-3 w-3" />, variant: "outline" },
  api: { label: "API", icon: <Play className="mr-1 h-3 w-3" />, variant: "default" },
};

function progressDoneRatio(run: TestRunListInfo): number {
  const total = run.test_cases_count;
  if (!total) return 0;
  const p = run.overall_progress;
  const finished = p.passed + p.failed + p.blocked + p.skipped + p.retest;
  return Math.round((finished / total) * 100);
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNKaVRBPT06NjI0YTJkOWQ=

export default function TestRunsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;

  type ExecutionTab = "all" | "manual" | "scheduled";
  const TABS: { value: ExecutionTab; label: string }[] = [
    { value: "all", label: "全部" },
    { value: "manual", label: "手动" },
    { value: "scheduled", label: "定时" },
  ];

  const activeTab: ExecutionTab =
    (searchParams.get("tab") as ExecutionTab) ?? "all";
  const isScheduleTab = activeTab === "scheduled";

  const setActiveTab = (tab: ExecutionTab) => {
    const current = new URLSearchParams(Array.from(searchParams.entries()));
    if (tab === "all") {
      current.delete("tab");
    } else {
      current.set("tab", tab);
    }
    current.delete("p");
    router.push(`/projects/${projectId}/test-runs?${current.toString()}`);
  };

  const [items, setItems] = React.useState<TestRunListInfo[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // “全部”Tab 中展示的定时规则预览
  const [schedulesPreview, setSchedulesPreview] = React.useState<TestRunScheduleInfo[]>([]);
  const [schedulesPreviewLoading, setSchedulesPreviewLoading] = React.useState(false);

  const [searchQuery, setSearchQuery] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [runStateFilter, setRunStateFilter] = React.useState<TestRunState | "all">("all");
  const [includeClosed, setIncludeClosed] = React.useState(false);

  const [createOpen, setCreateOpen] = React.useState(false);
  const [createForm, setCreateForm] = React.useState<TestRunCreate>({
    name: "",
    description: "",
    run_state: "new_run",
    execution_mode: "sequential",
    max_concurrency: 5,
    failure_policy: "continue",
    scripts: [],
    environment_id: undefined,
  });
  const [creating, setCreating] = React.useState(false);
  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [environmentsLoading, setEnvironmentsLoading] = React.useState(false);

  const [editingRun, setEditingRun] = React.useState<TestRunListInfo | null>(null);
  const [editRunDetail, setEditRunDetail] = React.useState<TestRunInfo | null>(null);
  const [editForm, setEditForm] = React.useState<{
    name: string;
    description: string;
    run_state: TestRunState;
    execution_mode: ExecutionMode;
    max_concurrency: number;
    failure_policy: FailurePolicy;
    environment_id: string;
    scripts: ScriptSelection[];
  }>({
    name: "",
    description: "",
    run_state: "new_run",
    execution_mode: "sequential",
    max_concurrency: 5,
    failure_policy: "continue",
    environment_id: "__default__",
    scripts: [],
  });
  const [editSaving, setEditSaving] = React.useState(false);
  const [editLoading, setEditLoading] = React.useState(false);
  const [editEnvironments, setEditEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [editEnvironmentsLoading, setEditEnvironmentsLoading] = React.useState(false);

  const [deletingRun, setDeletingRun] = React.useState<TestRunListInfo | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const [closingRun, setClosingRun] = React.useState<TestRunListInfo | null>(null);
  const [closing, setClosing] = React.useState(false);

  const [executingRun, setExecutingRun] = React.useState<TestRunListInfo | null>(null);
  const [executing, setExecuting] = React.useState(false);

  const [createScheduleOpen, setCreateScheduleOpen] = React.useState(false);

  // 合并加载测试运行列表与定时规则预览，二者并行执行
  const loadPageData = React.useCallback(async () => {
    if (!projectId || isScheduleTab) return;

    setLoading(true);
    setSchedulesPreviewLoading(true);
    setError(null);

    try {
      const [runsResponse, schedulesResponse] = await Promise.all([
        listTestRuns(projectId, {
          p: page,
          page_size: PAGE_SIZE,
          search: searchQuery || undefined,
          run_state: runStateFilter === "all" ? undefined : runStateFilter,
          include_closed: includeClosed,
          trigger_type: activeTab === "all" ? "manual" : activeTab,
        }),
        activeTab === "all"
          ? getSchedules(projectId, { page: 1, page_size: 5 })
          : Promise.resolve(null),
      ]);

      setItems(runsResponse.data);
      setTotal(runsResponse.info.total);

      if (activeTab === "all" && schedulesResponse) {
        setSchedulesPreview(schedulesResponse.data.items);
      } else {
        setSchedulesPreview([]);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载测试运行失败";
      setError(msg);
      setItems([]);
      setTotal(0);
      setSchedulesPreview([]);
    } finally {
      setLoading(false);
      setSchedulesPreviewLoading(false);
    }
  }, [
    projectId,
    page,
    searchQuery,
    runStateFilter,
    includeClosed,
    activeTab,
    isScheduleTab,
  ]);

  React.useEffect(() => {
    loadPageData();
  }, [loadPageData]);

  // 同步 URL 参数到本地状态（支持前进/后退）
  React.useEffect(() => {
    const urlPage = parseInt(searchParams.get("p") ?? "1", 10) || 1;
    setPage(urlPage);
  }, [searchParams]);


  React.useEffect(() => {
    const t = setTimeout(() => {
      setSearchQuery(searchInput.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  // 编辑对话框打开时加载环境列表
  React.useEffect(() => {
    if (!projectId || !editingRun) return;
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
  }, [editingRun, projectId]);

  // 创建对话框打开时加载环境列表，并默认选中项目默认环境
  React.useEffect(() => {
    if (!createOpen || !projectId) return;

    let cancelled = false;
    setEnvironmentsLoading(true);
    listEnvironments(projectId)
      .then((res) => {
        if (cancelled) return;
        const envs = res.data || [];
        setEnvironments(envs);
        const defaultEnv = envs.find((e) => e.is_default);
        if (defaultEnv) {
          setCreateForm((prev) => ({
            ...prev,
            environment_id: defaultEnv.id,
          }));
        }
      })
      .catch((err) => {
        if (cancelled) return;
        // eslint-disable-next-line no-console
        console.error("[TestRunsPage] 加载环境列表失败:", err);
      })
      .finally(() => {
        if (!cancelled) setEnvironmentsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [createOpen, projectId]);

  function resetCreateForm() {
    setCreateForm({
      name: "",
      description: "",
      run_state: "new_run",
      execution_mode: "sequential",
      max_concurrency: 5,
      failure_policy: "continue",
      scripts: [],
      environment_id: undefined,
    });
  }

  async function handleCreate() {
    if (!createForm.name.trim()) return;
    setCreating(true);
    try {
      await createTestRun(projectId, {
        ...createForm,
        name: createForm.name.trim(),
        description: createForm.description?.trim() || undefined,
      });
      setCreateOpen(false);
      resetCreateForm();
      setPage(1);
      await loadPageData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "创建测试运行失败";
      setError(msg);
    } finally {
      setCreating(false);
    }
  }

  async function openEdit(run: TestRunListInfo) {
    setEditingRun(run);
    setEditLoading(true);
    setEditRunDetail(null);
    try {
      const response = await getTestRun(projectId, run.identifier);
      const detail = response.data;
      setEditRunDetail(detail);
      setEditForm({
        name: detail.name,
        description: detail.description ?? "",
        run_state: detail.run_state,
        execution_mode: detail.execution_mode ?? "sequential",
        max_concurrency: detail.max_concurrency ?? 5,
        failure_policy: detail.failure_policy ?? "continue",
        environment_id: detail.environment_id ?? "__default__",
        scripts:
          detail.script_jobs?.map((job) => ({
            script_type: job.script_type,
            script_id: job.script_id,
            script_identifier: job.script_identifier,
            script_name: job.script_name,
            execution_order: job.execution_order,
            execution_mode: job.execution_mode,
          })) ?? [],
      });
    } catch {
      // 降级使用列表数据，脚本信息不可编辑
      setEditRunDetail(null);
      setEditForm({
        name: run.name,
        description: run.description ?? "",
        run_state: run.run_state,
        execution_mode: run.execution_mode ?? "sequential",
        max_concurrency: run.max_concurrency ?? 5,
        failure_policy: run.failure_policy ?? "continue",
        environment_id: run.environment_id ?? "__default__",
        scripts: [],
      });
    } finally {
      setEditLoading(false);
    }
  }

  async function handleEditSave() {
    if (!editingRun) return;
    setEditSaving(true);
    try {
      const isManual = editRunDetail?.trigger_type === "manual" || editingRun.trigger_type === "manual";
      await patchTestRun(projectId, editingRun.identifier, {
        name: editForm.name.trim() || undefined,
        description: editForm.description.trim() || undefined,
        run_state: editForm.run_state,
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
      setEditingRun(null);
      setEditRunDetail(null);
      await loadPageData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "更新测试运行失败";
      setError(msg);
    } finally {
      setEditSaving(false);
    }
  }

  async function handleClose() {
    if (!closingRun) return;
    setClosing(true);
    try {
      await closeTestRun(projectId, closingRun.identifier, { active_state: "closed" });
      setClosingRun(null);
      await loadPageData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "关闭测试运行失败";
      setError(msg);
    } finally {
      setClosing(false);
    }
  }

  async function handleDelete() {
    if (!deletingRun) return;
    setDeleting(true);
    try {
      await deleteTestRun(projectId, deletingRun.identifier);
      setDeletingRun(null);
      await loadPageData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "删除测试运行失败";
      setError(msg);
    } finally {
      setDeleting(false);
    }
  }

  async function handleExecute() {
    if (!executingRun) return;
    setExecuting(true);
    try {
      await executeTestRun(projectId, executingRun.identifier);
      setExecutingRun(null);
      await loadPageData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "执行测试运行失败";
      setError(msg);
    } finally {
      setExecuting(false);
    }
  }

  return (
    <MainLayout title="测试运行">
      <div className="space-y-6">
        {/* 触发方式 Tab */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as ExecutionTab)}>
          <TabsList>
            {TABS.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {isScheduleTab ? (
          <ScheduleRulesPanel projectId={projectId} />
        ) : (
          <>
            {/* 工具栏 */}
            <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索名称或标识符..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-64 pl-9"
              />
            </div>
            <Select
              value={runStateFilter}
              onValueChange={(v) => {
                setRunStateFilter(v as TestRunState | "all");
                setPage(1);
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="运行状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                {RUN_STATE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={includeClosed}
                onCheckedChange={(checked) => {
                  setIncludeClosed(checked === true);
                  setPage(1);
                }}
              />
              <span>包含已关闭</span>
            </label>
            <Button variant="ghost" size="icon" onClick={loadPageData} disabled={loading} title="刷新">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            {activeTab === "all" && (
              <Button variant="outline" onClick={() => setCreateScheduleOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                新建调度
              </Button>
            )}
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              新建测试运行
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        )}

        {activeTab === "all" && (
          <div className="rounded-lg border bg-card">
            <div className="flex items-center gap-2 border-b p-4">
              <CalendarClock className="h-5 w-5 text-primary" />
              <h2 className="font-medium">定时规则</h2>
            </div>
            {schedulesPreviewLoading ? (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : schedulesPreview.length === 0 ? (
              <div className="flex h-32 flex-col items-center justify-center gap-2">
                <p className="text-sm text-muted-foreground">暂无定时规则</p>
              </div>
            ) : (
              <div className="divide-y">
                {schedulesPreview.map((schedule) => (
                  <div
                    key={schedule.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <CalendarClock className="h-5 w-5 text-primary" />
                        <h3 className="font-medium truncate">{schedule.name}</h3>
                        <Badge variant={schedule.is_enabled ? "default" : "secondary"}>
                          {schedule.is_enabled ? (
                            <>
                              <CheckCircle2 className="mr-1 h-3 w-3" />
                              启用
                            </>
                          ) : (
                            <>
                              <XCircle className="mr-1 h-3 w-3" />
                              禁用
                            </>
                          )}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {TRIGGER_TYPE_LABEL[schedule.trigger_type]}
                        </Badge>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" />
                          {buildCronDescription(schedule.trigger_config)}
                        </span>
                        <span>下次执行: {formatNextRun(schedule.next_run_at, schedule.is_enabled)}</span>
                        {schedule.last_run_at && (
                          <span>上次执行: {formatScheduleDate(schedule.last_run_at)}</span>
                        )}
                      </div>
                    </div>
                    <div className="ml-4 flex items-center gap-2">
                      <ScheduleRuleActions
                        projectId={projectId}
                        schedule={schedule}
                        onMutated={loadPageData}
                        onError={(msg) => setError(msg)}
                        showViewButton
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 列表 */}
        <div className="rounded-lg border bg-card">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2">
              <PlayCircle className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">
                {searchQuery || runStateFilter !== "all"
                  ? "没有找到匹配的测试运行"
                  : "暂无测试运行"}
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {items.map((run) => {
                const p = run.overall_progress;
                const progress = progressDoneRatio(run);
                const closed = run.active_state === "closed";
                const stateInfo = RUN_STATE_BADGE[run.run_state];
                const execMode = run.execution_mode ? EXECUTION_MODE_BADGE[run.execution_mode] : null;
                const trigger = run.trigger_type ? TRIGGER_TYPE_BADGE[run.trigger_type] : null;
                return (
                  <div
                    key={run.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <PlayCircle className="h-5 w-5 text-primary" />
                        <h3 className="font-medium truncate">{run.name}</h3>
                        <Badge variant="outline" className="font-mono text-xs">
                          {run.identifier}
                        </Badge>
                        <Badge variant={stateInfo.variant}>{stateInfo.label}</Badge>
                        {execMode && (
                          <Badge variant="outline" className="text-xs">
                            {execMode.icon}
                            {execMode.label}
                          </Badge>
                        )}
                        {trigger && (
                          <Badge variant={trigger.variant} className="text-xs">
                            {trigger.icon}
                            {trigger.label}
                          </Badge>
                        )}
                        {closed && (
                          <Badge variant="secondary">
                            <Lock className="mr-1 h-3 w-3" />
                            已关闭
                          </Badge>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2">
                        <div className="flex flex-wrap items-center gap-4 text-sm">
                          <span className="flex items-center gap-1 text-green-600">
                            <CheckCircle2 className="h-4 w-4" />
                            {p.passed} 通过
                          </span>
                          <span className="flex items-center gap-1 text-red-600">
                            <XCircle className="h-4 w-4" />
                            {p.failed} 失败
                          </span>
                          <span className="flex items-center gap-1 text-amber-600">
                            <Clock className="h-4 w-4" />
                            {p.in_progress} 进行中
                          </span>
                          <span className="text-muted-foreground">
                            {p.untested} 未测 / {p.retest} 重测 / {p.blocked} 阻塞 / {p.skipped} 跳过
                          </span>
                          <span className="text-muted-foreground">共 {run.test_cases_count}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Progress value={progress} className="w-32" />
                          <span className="text-sm text-muted-foreground">{progress}%</span>
                        </div>
                      </div>
                    </div>
                    <div className="ml-4 flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push(`/projects/${projectId}/test-runs/${run.identifier}`)}
                      >
                        <Eye className="mr-2 h-4 w-4" />
                        查看
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => setExecutingRun(run)}
                            disabled={closed || run.run_state === "in_progress"}
                          >
                            <Play className="mr-2 h-4 w-4" />
                            执行
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => openEdit(run)} disabled={closed}>
                            <Pencil className="mr-2 h-4 w-4" />
                            编辑
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setClosingRun(run)}
                            disabled={closed}
                          >
                            <Lock className="mr-2 h-4 w-4" />
                            关闭
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => setDeletingRun(run)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            删除
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 分页 */}
        {total > 0 && (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
            showPageSizeSelector={false}
          />
        )}
      </>
      )}
      </div>

      {/* 创建对话框 */}
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) resetCreateForm();
        }}
      >
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>新建测试运行</DialogTitle>
            <DialogDescription>
              创建一个新的测试运行并选择需要执行的脚本。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">名称 *</Label>
              <Input
                id="name"
                value={createForm.name}
                onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                placeholder="请输入测试运行名称"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">描述</Label>
              <Textarea
                id="description"
                value={createForm.description ?? ""}
                onChange={(e) =>
                  setCreateForm({ ...createForm, description: e.target.value })
                }
                placeholder="请输入描述（可选）"
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="run_state">运行状态</Label>
              <Select
                value={createForm.run_state ?? "new_run"}
                onValueChange={(v) =>
                  setCreateForm({ ...createForm, run_state: v as TestRunState })
                }
              >
                <SelectTrigger id="run_state">
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

            {/* 执行模式 */}
            <div className="space-y-2">
              <Label htmlFor="exec_mode">执行模式</Label>
              <Select
                value={createForm.execution_mode ?? "sequential"}
                onValueChange={(v) =>
                  setCreateForm({ ...createForm, execution_mode: v as ExecutionMode })
                }
              >
                <SelectTrigger id="exec_mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sequential">顺序执行</SelectItem>
                  <SelectItem value="parallel">并行执行</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {createForm.execution_mode === "parallel" && (
              <div className="space-y-2">
                <Label htmlFor="max_concurrency">最大并发数</Label>
                <Input
                  id="max_concurrency"
                  type="number"
                  min={1}
                  max={20}
                  value={createForm.max_concurrency ?? 5}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      max_concurrency: parseInt(e.target.value) || 5,
                    })
                  }
                />
              </div>
            )}

            {/* 失败策略 */}
            <div className="space-y-2">
              <Label htmlFor="failure_policy">失败策略</Label>
              <Select
                value={createForm.failure_policy ?? "continue"}
                onValueChange={(v) =>
                  setCreateForm({
                    ...createForm,
                    failure_policy: v as FailurePolicy,
                  })
                }
              >
                <SelectTrigger id="failure_policy">
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

            {/* 执行环境 */}
            <div className="space-y-2">
              <Label htmlFor="environment">执行环境</Label>
              <Select
                value={createForm.environment_id ?? "__default__"}
                onValueChange={(v) =>
                  setCreateForm({
                    ...createForm,
                    environment_id:
                      v === "__default__" ? undefined : v,
                  })
                }
                disabled={environmentsLoading}
              >
                <SelectTrigger id="environment">
                  <SelectValue placeholder="选择执行环境" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">使用项目默认环境</SelectItem>
                  {environments.map((env) => (
                    <SelectItem key={env.id} value={env.id}>
                      {env.name}
                      {env.is_default ? "（默认）" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {environmentsLoading && (
                <p className="text-xs text-muted-foreground">加载环境中...</p>
              )}
            </div>

            {/* 脚本选择 —— 企业级 */}
            <ScriptSelector
              projectId={projectId}
              scripts={createForm.scripts ?? []}
              onScriptsChange={(scripts) =>
                setCreateForm({ ...createForm, scripts })
              }
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateOpen(false)}
              disabled={creating}
            >
              取消
            </Button>
            <Button
              onClick={handleCreate}
              disabled={creating || !createForm.name.trim()}
            >
              {creating && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 编辑对话框 */}
      <Dialog open={editingRun !== null} onOpenChange={(open) => { if (!open) { setEditingRun(null); setEditRunDetail(null); } }}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>编辑测试运行</DialogTitle>
            <DialogDescription>
              {editingRun ? `修改 ${editingRun.identifier} 的基础信息` : ""}
            </DialogDescription>
          </DialogHeader>
          {editLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-name">名称</Label>
                <Input
                  id="edit-name"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-description">描述</Label>
                <Textarea
                  id="edit-description"
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  placeholder="请输入描述（可选）"
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-state">运行状态</Label>
                <Select
                  value={editForm.run_state}
                  onValueChange={(v) => setEditForm({ ...editForm, run_state: v as TestRunState })}
                >
                  <SelectTrigger id="edit-state">
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
              {editRunDetail?.trigger_type === "scheduled" && (
                <p className="text-sm text-muted-foreground">
                  该测试运行为定时触发，执行模式、环境及脚本由调度模板控制，不可在此处修改。
                </p>
              )}
              {(editRunDetail?.trigger_type === "manual" ||
                (!editRunDetail && editingRun?.trigger_type === "manual")) && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="edit-exec-mode">执行模式</Label>
                    <Select
                      value={editForm.execution_mode}
                      onValueChange={(v) => setEditForm({ ...editForm, execution_mode: v as ExecutionMode })}
                    >
                      <SelectTrigger id="edit-exec-mode">
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
                      <Label htmlFor="edit-max-concurrency">最大并发数</Label>
                      <Input
                        id="edit-max-concurrency"
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
                    <Label htmlFor="edit-failure-policy">失败策略</Label>
                    <Select
                      value={editForm.failure_policy}
                      onValueChange={(v) =>
                        setEditForm({
                          ...editForm,
                          failure_policy: v as FailurePolicy,
                        })
                      }
                    >
                      <SelectTrigger id="edit-failure-policy">
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
                    <Label htmlFor="edit-environment">执行环境</Label>
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
                      <SelectTrigger id="edit-environment">
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
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditingRun(null)}
              disabled={editSaving || editLoading}
            >
              取消
            </Button>
            <Button onClick={handleEditSave} disabled={editSaving || editLoading || !editForm.name.trim()}>
              {editSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 执行确认 */}
      <AlertDialog open={executingRun !== null} onOpenChange={(open) => !open && setExecutingRun(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>执行测试运行?</AlertDialogTitle>
            <AlertDialogDescription>
              确认执行 {executingRun?.identifier} ({executingRun?.name})？
              这将遍历所有关联的测试用例并执行其自动化脚本，可能需要较长时间。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={executing}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleExecute} disabled={executing}>
              {executing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              执行
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 关闭确认 */}
      <AlertDialog open={closingRun !== null} onOpenChange={(open) => !open && setClosingRun(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>关闭测试运行?</AlertDialogTitle>
            <AlertDialogDescription>
              确认关闭 {closingRun?.identifier}？关闭后将无法再修改其内容。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={closing}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleClose} disabled={closing}>
              {closing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              关闭
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 删除确认 */}
      <AlertDialog
        open={deletingRun !== null}
        onOpenChange={(open) => !open && setDeletingRun(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除测试运行?</AlertDialogTitle>
            <AlertDialogDescription>
              确认删除 {deletingRun?.identifier} ({deletingRun?.name})？此操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <CreateScheduleDialog
        projectId={projectId}
        open={createScheduleOpen}
        onOpenChange={setCreateScheduleOpen}
        onSuccess={() => {
          loadPageData();
        }}
      />

    </MainLayout>
  );
}
