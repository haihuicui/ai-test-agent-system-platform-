"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Play,
  Loader2,
  Pencil,
  Trash2,
  MoreHorizontal,
  History,
  Eye,
  CalendarClock,
  Clock,
  CheckCircle2,
  XCircle,
  Code,
  Layers,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
} from "@/components/ui/pagination";
import {
  updateSchedule,
  deleteSchedule,
  triggerSchedule,
  getSchedule,
  getScheduleRuns,
  listEnvironments,
  type TestRunScheduleInfo,
  type TestRunScheduleCreate,
  type ScheduleTriggerType,
  type ScriptSelection,
  type ScriptType,
  type ExecutionMode,
  type EnvironmentInfo,
  type TestRunListInfo,
  type TestRunState,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { ScriptSelector } from "./script-selector";
import { TestRunExecutionPanel } from "./test-run-execution-panel";
import {
  RUN_STATE_BADGE,
} from "./test-run-shared";

interface TemplateFormValue extends Record<string, unknown> {
  name: string;
  execution_mode: ExecutionMode;
  scripts: ScriptSelection[];
  environment_id?: string;
}

function normalizeTemplate(template?: Record<string, unknown>): TemplateFormValue {
  return {
    name: typeof template?.name === "string" ? template.name : "定时执行",
    execution_mode: (template?.execution_mode as ExecutionMode) || "sequential",
    scripts: Array.isArray(template?.scripts)
      ? (template.scripts as ScriptSelection[])
      : [],
    environment_id:
      typeof template?.environment_id === "string"
        ? template.environment_id
        : undefined,
  };
}

const PAGE_SIZE = 20;

const TRIGGER_TYPE_LABEL: Record<ScheduleTriggerType, string> = {
  cron: "Cron 表达式",
  interval: "间隔触发",
  date: "一次性",
};

function formatNextRun(dateStr?: string): string {
  if (!dateStr) return "未计算";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "无效时间";
  return d.toLocaleString();
}

function buildCronDescription(config: Record<string, unknown>): string {
  if (config.cron_expression) {
    return String(config.cron_expression);
  }
  if (config.minutes !== undefined) {
    return `每 ${config.minutes} 分钟`;
  }
  if (config.hours !== undefined) {
    return `每 ${config.hours} 小时`;
  }
  if (config.days !== undefined) {
    return `每 ${config.days} 天`;
  }
  return JSON.stringify(config);
}

const SCRIPT_TYPE_LABEL: Record<ScriptType, { label: string; icon: React.ReactNode }> = {
  api_test: { label: "API 测试", icon: <Code className="h-3.5 w-3.5" /> },
  scenario: { label: "场景测试", icon: <Layers className="h-3.5 w-3.5" /> },
  web_test: { label: "Web 测试", icon: <Globe className="h-3.5 w-3.5" /> },
  test_case: { label: "测试用例", icon: <Code className="h-3.5 w-3.5" /> },
};

export interface ScheduleRuleActionsProps {
  projectId: string;
  schedule: TestRunScheduleInfo;
  onMutated?: () => void;
  onError?: (message: string) => void;
  showViewButton?: boolean;
}

export function ScheduleRuleActions({
  projectId,
  schedule,
  onMutated,
  onError,
  showViewButton = false,
}: ScheduleRuleActionsProps) {
  const router = useRouter();

  const [editingSchedule, setEditingSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [editForm, setEditForm] = React.useState<Partial<TestRunScheduleCreate>>({});
  const [editSaving, setEditSaving] = React.useState(false);

  const [deletingSchedule, setDeletingSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const [triggeringSchedule, setTriggeringSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [triggering, setTriggering] = React.useState(false);

  const [runHistorySchedule, setRunHistorySchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [runHistoryItems, setRunHistoryItems] = React.useState<TestRunListInfo[]>([]);
  const [runHistoryTotal, setRunHistoryTotal] = React.useState(0);
  const [runHistoryPage, setRunHistoryPage] = React.useState(1);
  const [runHistoryLoading, setRunHistoryLoading] = React.useState(false);

  const [viewingSchedule, setViewingSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [viewLoading, setViewLoading] = React.useState(false);

  const [viewRuns, setViewRuns] = React.useState<TestRunListInfo[]>([]);
  const [viewRunsTotal, setViewRunsTotal] = React.useState(0);
  const [viewRunsLoading, setViewRunsLoading] = React.useState(false);
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);

  const [latestRunSchedule, setLatestRunSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [latestRunLoading, setLatestRunLoading] = React.useState(false);

  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [environmentsLoading, setEnvironmentsLoading] = React.useState(false);

  React.useEffect(() => {
    if (!projectId) return;
    if (!editingSchedule && !viewingSchedule) return;

    let cancelled = false;
    setEnvironmentsLoading(true);
    listEnvironments(projectId)
      .then((res) => {
        if (cancelled) return;
        setEnvironments(res.data || []);
      })
      .catch((err) => {
        if (cancelled) return;
        // eslint-disable-next-line no-console
        console.error("[ScheduleRuleActions] 加载环境列表失败:", err);
      })
      .finally(() => {
        if (!cancelled) setEnvironmentsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [editingSchedule, viewingSchedule, projectId]);

  function updateEditTemplateScripts(scripts: ScriptSelection[]) {
    setEditForm((prev) => ({
      ...prev,
      test_run_template: {
        ...(prev.test_run_template ?? {}),
        scripts,
      },
    }));
  }

  function openEdit(s: TestRunScheduleInfo) {
    setEditingSchedule(s);
    setEditForm({
      name: s.name,
      description: s.description,
      trigger_type: s.trigger_type,
      trigger_config: s.trigger_config,
      test_run_template: normalizeTemplate(s.test_run_template),
      is_enabled: s.is_enabled,
    });
  }

  async function handleEditSave() {
    if (!editingSchedule) return;
    setEditSaving(true);
    try {
      await updateSchedule(projectId, editingSchedule.id, editForm);
      setEditingSchedule(null);
      onMutated?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "更新调度失败";
      onError?.(msg);
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDelete() {
    if (!deletingSchedule) return;
    setDeleting(true);
    try {
      await deleteSchedule(projectId, deletingSchedule.id);
      setDeletingSchedule(null);
      onMutated?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "删除调度失败";
      onError?.(msg);
    } finally {
      setDeleting(false);
    }
  }

  async function handleTrigger(s: TestRunScheduleInfo) {
    setTriggeringSchedule(s);
    setTriggering(true);
    try {
      await triggerSchedule(projectId, s.id);
      onMutated?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "触发调度失败";
      onError?.(msg);
    } finally {
      setTriggering(false);
      setTriggeringSchedule(null);
    }
  }

  async function handleView(s: TestRunScheduleInfo) {
    setViewingSchedule(s);
    setViewLoading(true);
    setViewRunsLoading(true);
    setViewRuns([]);
    setViewRunsTotal(0);
    try {
      const [scheduleResponse, runsResponse] = await Promise.all([
        getSchedule(projectId, s.id),
        getScheduleRuns(projectId, s.id, { page: 1, page_size: 20 }),
      ]);
      setViewingSchedule(scheduleResponse.data);
      setViewRuns(runsResponse.data.items);
      setViewRunsTotal(runsResponse.data.total);
      setSelectedRunId(runsResponse.data.items[0]?.id ?? null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载调度详情失败";
      onError?.(msg);
      setViewingSchedule(null);
    } finally {
      setViewLoading(false);
      setViewRunsLoading(false);
    }
  }

  async function handleViewLatestRun(s: TestRunScheduleInfo) {
    setLatestRunSchedule(s);
    setLatestRunLoading(true);
    try {
      const response = await getScheduleRuns(projectId, s.id, {
        page: 1,
        page_size: 1,
      });
      const items = response.data.items;
      if (items.length > 0) {
        router.push(`/projects/${projectId}/test-runs/${items[0].identifier}`);
      } else {
        onError?.("该调度暂无执行记录");
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载最新运行失败";
      onError?.(msg);
    } finally {
      setLatestRunLoading(false);
      setLatestRunSchedule(null);
    }
  }

  async function loadRunHistory(s: TestRunScheduleInfo, pageNum = 1) {
    setRunHistorySchedule(s);
    setRunHistoryLoading(true);
    try {
      const response = await getScheduleRuns(projectId, s.id, {
        page: pageNum,
        page_size: PAGE_SIZE,
      });
      setRunHistoryItems(response.data.items);
      setRunHistoryTotal(response.data.total);
      setRunHistoryPage(response.data.page);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载执行历史失败";
      onError?.(msg);
      setRunHistoryItems([]);
      setRunHistoryTotal(0);
    } finally {
      setRunHistoryLoading(false);
    }
  }

  const selectedRun = React.useMemo(
    () => viewRuns.find((r) => r.id === selectedRunId),
    [viewRuns, selectedRunId]
  );

  const runStats = React.useMemo(() => {
    const total = viewRuns.length;
    const passed = viewRuns.filter(
      (r) => r.run_state === "done" || r.run_state === "approved"
    ).length;
    const failed = viewRuns.filter(
      (r) => r.run_state === "rejected" || r.run_state === "done_with_failures"
    ).length;
    const successRate = total > 0 ? Math.round((passed / total) * 100) : 0;
    return { total, passed, failed, successRate };
  }, [viewRuns]);

  return (
    <>
      {showViewButton && (
        <div className="inline-flex -space-x-px rounded-md shadow-sm">
          <Button
            variant="outline"
            size="sm"
            className="rounded-r-none focus:z-10"
            onClick={() => handleView(schedule)}
            disabled={viewLoading && viewingSchedule?.id === schedule.id}
          >
            {viewLoading && viewingSchedule?.id === schedule.id ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Eye className="mr-2 h-4 w-4" />
            )}
            查看
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="rounded-l-none focus:z-10"
            title="查看最新运行"
            onClick={() => handleViewLatestRun(schedule)}
            disabled={latestRunLoading && latestRunSchedule?.id === schedule.id}
          >
            {latestRunLoading && latestRunSchedule?.id === schedule.id ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <History className="mr-2 h-4 w-4" />
            )}
            最新
          </Button>
        </div>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onClick={() => handleTrigger(schedule)}
            disabled={triggering && triggeringSchedule?.id === schedule.id}
          >
            {triggering && triggeringSchedule?.id === schedule.id ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            立即触发
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => loadRunHistory(schedule)}>
            <History className="mr-2 h-4 w-4" />
            执行历史
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => openEdit(schedule)}>
            <Pencil className="mr-2 h-4 w-4" />
            编辑
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive"
            onClick={() => setDeletingSchedule(schedule)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            删除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* 编辑对话框 */}
      <Dialog open={editingSchedule !== null} onOpenChange={(open) => !open && setEditingSchedule(null)}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>编辑调度</DialogTitle>
            <DialogDescription>
              {editingSchedule ? `修改 ${editingSchedule.name}` : "修改选中的调度规则"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>名称</Label>
              <Input
                value={editForm.name || ""}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea
                value={(editForm.description as string) || ""}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label>触发器类型</Label>
              <Select
                value={editForm.trigger_type || "cron"}
                onValueChange={(v) => {
                  const type = v as ScheduleTriggerType;
                  let config: Record<string, unknown> = {};
                  if (type === "cron") config = { cron_expression: "0 9 * * *" };
                  else if (type === "interval") config = { minutes: 60 };
                  else if (type === "date") config = { run_date: new Date().toISOString() };
                  setEditForm({ ...editForm, trigger_type: type, trigger_config: config });
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cron">Cron 表达式</SelectItem>
                  <SelectItem value="interval">间隔触发</SelectItem>
                  <SelectItem value="date">一次性</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {editForm.trigger_type === "cron" && (
              <div className="space-y-2">
                <Label htmlFor="edit-cron">Cron 表达式</Label>
                <Input
                  id="edit-cron"
                  value={String(editForm.trigger_config?.cron_expression || "")}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      trigger_config: { cron_expression: e.target.value },
                    })
                  }
                  placeholder="0 9 * * *"
                />
                <p className="text-xs text-muted-foreground">格式: 分 时 日 月 周</p>
              </div>
            )}
            {editForm.trigger_type === "interval" && (
              <div className="space-y-2">
                <Label htmlFor="edit-interval">间隔分钟数</Label>
                <Input
                  id="edit-interval"
                  type="number"
                  value={Number(editForm.trigger_config?.minutes || 60)}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      trigger_config: { minutes: Number(e.target.value) },
                    })
                  }
                />
              </div>
            )}
            {editForm.trigger_type === "date" && (
              <div className="space-y-2">
                <Label htmlFor="edit-date">执行时间</Label>
                <Input
                  id="edit-date"
                  type="datetime-local"
                  value={String(editForm.trigger_config?.run_date || "").slice(0, 16)}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      trigger_config: { run_date: new Date(e.target.value).toISOString() },
                    })
                  }
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="edit-template-name">测试运行名称模板</Label>
              <Input
                id="edit-template-name"
                value={String(
                  (editForm.test_run_template as Record<string, unknown>)?.name ?? ""
                )}
                onChange={(e) =>
                  setEditForm((prev) => ({
                    ...prev,
                    test_run_template: {
                      ...(prev.test_run_template ?? {}),
                      name: e.target.value,
                    },
                  }))
                }
                placeholder="定时执行"
              />
            </div>
            <div className="space-y-2">
              <Label>执行模式</Label>
              <Select
                value={String(
                  (editForm.test_run_template as Record<string, unknown>)
                    ?.execution_mode || "sequential"
                )}
                onValueChange={(v) =>
                  setEditForm((prev) => ({
                    ...prev,
                    test_run_template: {
                      ...(prev.test_run_template ?? {}),
                      execution_mode: v as ExecutionMode,
                    },
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sequential">顺序执行</SelectItem>
                  <SelectItem value="parallel">并行执行</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>执行环境</Label>
              <Select
                value={
                  normalizeTemplate(
                    editForm.test_run_template as Record<string, unknown>
                  ).environment_id ?? "__default__"
                }
                onValueChange={(v) =>
                  setEditForm((prev) => ({
                    ...prev,
                    test_run_template: {
                      ...(prev.test_run_template ?? {}),
                      environment_id:
                        v === "__default__" ? undefined : v,
                    },
                  }))
                }
                disabled={environmentsLoading}
              >
                <SelectTrigger>
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
            <ScriptSelector
              projectId={projectId}
              scripts={
                (
                  (editForm.test_run_template as Record<string, unknown>)
                    ?.scripts as ScriptSelection[]
                ) ?? []
              }
              onScriptsChange={updateEditTemplateScripts}
            />
            <div className="flex items-center gap-2">
              <Checkbox
                id="edit-enabled"
                checked={editForm.is_enabled}
                onCheckedChange={(checked) => setEditForm({ ...editForm, is_enabled: checked === true })}
              />
              <Label htmlFor="edit-enabled">启用</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingSchedule(null)} disabled={editSaving}>
              取消
            </Button>
            <Button onClick={handleEditSave} disabled={editSaving || !editForm.name?.trim()}>
              {editSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认 */}
      <AlertDialog
        open={deletingSchedule !== null}
        onOpenChange={(open) => !open && setDeletingSchedule(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除调度?</AlertDialogTitle>
            <AlertDialogDescription>
              确认删除 {deletingSchedule?.name}？此操作不可恢复。
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

      {/* 执行历史 */}
      <Dialog
        open={runHistorySchedule !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRunHistorySchedule(null);
            setRunHistoryItems([]);
            setRunHistoryTotal(0);
          }
        }}
      >
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>执行历史</DialogTitle>
            <DialogDescription>
              {runHistorySchedule
                ? `调度 ${runHistorySchedule.name} 产生的测试运行`
                : "查看调度规则产生的测试运行"}
            </DialogDescription>
          </DialogHeader>
          {runHistoryLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : runHistoryItems.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2">
              <History className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">暂无执行历史</p>
            </div>
          ) : (
            <div className="divide-y">
              {runHistoryItems.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between p-4 hover:bg-muted/50"
                >
                  <div className="min-w-0">
                    <div className="font-medium">{run.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {run.identifier} · {run.run_state} ·{" "}
                      {new Date(run.created_at).toLocaleString()}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      router.push(`/projects/${projectId}/test-runs/${run.identifier}`)
                    }
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    查看
                  </Button>
                </div>
              ))}
            </div>
          )}
          {runHistoryTotal > 0 && (
            <Pagination
              page={runHistoryPage}
              pageSize={PAGE_SIZE}
              total={runHistoryTotal}
              onPageChange={(p) =>
                runHistorySchedule && loadRunHistory(runHistorySchedule, p)
              }
              showPageSizeSelector={false}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* 查看详情 */}
      <Dialog
        open={viewingSchedule !== null}
        onOpenChange={(open) => {
          if (!open) {
            setViewingSchedule(null);
            setViewRuns([]);
            setViewRunsTotal(0);
            setSelectedRunId(null);
          }
        }}
      >
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>调度规则详情</DialogTitle>
            <DialogDescription>
              {viewingSchedule ? `查看 ${viewingSchedule.name} 的详细信息` : ""}
            </DialogDescription>
          </DialogHeader>
          {viewLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : !viewingSchedule ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              加载失败
            </div>
          ) : (
            <div className="py-4">
              <Tabs defaultValue="config" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="config">规则配置</TabsTrigger>
                  <TabsTrigger value="execution">最新执行</TabsTrigger>
                </TabsList>
                <TabsContent value="config" className="space-y-6 pt-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <Label className="text-muted-foreground">名称</Label>
                  <div className="mt-1 font-medium">{viewingSchedule.name}</div>
                </div>
                <div>
                  <Label className="text-muted-foreground">状态</Label>
                  <div className="mt-1">
                    <Badge variant={viewingSchedule.is_enabled ? "default" : "secondary"}>
                      {viewingSchedule.is_enabled ? (
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
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">触发类型</Label>
                  <div className="mt-1">{TRIGGER_TYPE_LABEL[viewingSchedule.trigger_type]}</div>
                </div>
                <div>
                  <Label className="text-muted-foreground">触发配置</Label>
                  <div className="mt-1 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    {buildCronDescription(viewingSchedule.trigger_config)}
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">下次执行</Label>
                  <div className="mt-1">{formatNextRun(viewingSchedule.next_run_at)}</div>
                </div>
                <div>
                  <Label className="text-muted-foreground">上次执行</Label>
                  <div className="mt-1">
                    {viewingSchedule.last_run_at
                      ? new Date(viewingSchedule.last_run_at).toLocaleString()
                      : "暂无"}
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">创建时间</Label>
                  <div className="mt-1">{new Date(viewingSchedule.created_at).toLocaleString()}</div>
                </div>
                <div>
                  <Label className="text-muted-foreground">更新时间</Label>
                  <div className="mt-1">
                    {viewingSchedule.updated_at
                      ? new Date(viewingSchedule.updated_at).toLocaleString()
                      : "暂无"}
                  </div>
                </div>
              </div>
              <div>
                <Label className="text-muted-foreground">描述</Label>
                <div className="mt-1 text-sm">{viewingSchedule.description || "无描述"}</div>
              </div>
              <div className="rounded-lg border p-4 space-y-4">
                <h4 className="font-medium">测试运行模板</h4>
                {(() => {
                  const template = normalizeTemplate(viewingSchedule.test_run_template);
                  const env = environments.find((e) => e.id === template.environment_id);
                  return (
                    <>
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                          <Label className="text-muted-foreground">名称模板</Label>
                          <div className="mt-1">{template.name}</div>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">执行模式</Label>
                          <div className="mt-1">
                            {template.execution_mode === "parallel" ? "并行执行" : "顺序执行"}
                          </div>
                        </div>
                        <div className="sm:col-span-2">
                          <Label className="text-muted-foreground">执行环境</Label>
                          <div className="mt-1">
                            {environmentsLoading
                              ? "加载中..."
                              : env
                                ? `${env.name}${env.is_default ? "（默认）" : ""}`
                                : template.environment_id || "使用项目默认环境"}
                          </div>
                        </div>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">已选脚本</Label>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {template.scripts.length === 0 ? (
                            <span className="text-sm text-muted-foreground">未选择脚本</span>
                          ) : (
                            template.scripts.map((s, idx) => {
                              const typeInfo = SCRIPT_TYPE_LABEL[s.script_type];
                              return (
                                <Badge key={idx} variant="secondary" className="gap-1">
                                  {typeInfo?.icon}
                                  {typeInfo?.label || s.script_type}
                                  <span className="text-muted-foreground">
                                    {s.script_name || s.script_identifier || s.script_id}
                                  </span>
                                </Badge>
                              );
                            })
                          )}
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>

              </TabsContent>
              <TabsContent value="execution" className="pt-4">
                {viewRunsLoading ? (
                  <div className="flex h-64 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : viewRuns.length === 0 ? (
                  <div className="flex h-64 flex-col items-center justify-center gap-2">
                    <History className="h-12 w-12 text-muted-foreground/50" />
                    <p className="text-sm text-muted-foreground">暂无执行历史</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Label className="text-muted-foreground">选择执行记录</Label>
                      {viewRunsTotal > viewRuns.length && viewingSchedule && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadRunHistory(viewingSchedule)}
                        >
                          查看全部
                        </Button>
                      )}
                    </div>
                    <Select
                      value={selectedRunId ?? ""}
                      onValueChange={(v) => setSelectedRunId(v)}
                    >
                      <SelectTrigger className="w-full sm:w-[320px]">
                        <SelectValue placeholder="选择执行记录" />
                      </SelectTrigger>
                      <SelectContent>
                        {viewRuns.map((run) => {
                          const stateInfo = RUN_STATE_BADGE[run.run_state];
                          return (
                            <SelectItem key={run.id} value={run.id}>
                              {run.identifier} · {run.name} · {stateInfo.label}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                    {selectedRun && (
                      <TestRunExecutionPanel
                        projectId={projectId}
                        runId={selectedRun.identifier}
                        showViewFullDetail
                        onError={onError}
                      />
                    )}
                  </div>
                )}
              </TabsContent>
          </Tabs>
        </div>
      )}
      <DialogFooter>
        <Button variant="outline" onClick={() => setViewingSchedule(null)}>
          关闭
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</>
  );
}
