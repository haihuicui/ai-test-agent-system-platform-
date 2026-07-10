"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkVwd2NRPT06NTRjMTI5N2Q=

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Plus,
  ArrowLeft,
  CalendarClock,
  Clock,
  Play,
  Loader2,
  AlertCircle,
  RefreshCw,
  Pencil,
  Trash2,
  MoreHorizontal,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
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
import {
  Pagination,
} from "@/components/ui/pagination";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  getSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  listEnvironments,
  type TestRunScheduleInfo,
  type TestRunScheduleCreate,
  type ScheduleTriggerType,
  type ScriptSelection,
  type ExecutionMode,
  type EnvironmentInfo,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { ScriptSelector } from "../_components/script-selector";

const PAGE_SIZE = 20;
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkVwd2NRPT06NTRjMTI5N2Q=

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
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkVwd2NRPT06NTRjMTI5N2Q=

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
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkVwd2NRPT06NTRjMTI5N2Q=

export default function SchedulesPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;

  const [items, setItems] = React.useState<TestRunScheduleInfo[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [createOpen, setCreateOpen] = React.useState(false);
  const [createForm, setCreateForm] = React.useState<TestRunScheduleCreate>({
    name: "",
    description: "",
    trigger_type: "cron",
    trigger_config: { cron_expression: "0 9 * * *" },
    test_run_template: {
      name: "定时执行",
      execution_mode: "sequential",
      scripts: [] as ScriptSelection[],
    },
    is_enabled: true,
  });
  const [creating, setCreating] = React.useState(false);
  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [environmentsLoading, setEnvironmentsLoading] = React.useState(false);

  const [editingSchedule, setEditingSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [editForm, setEditForm] = React.useState<Partial<TestRunScheduleCreate>>({});
  const [editSaving, setEditSaving] = React.useState(false);

  const [deletingSchedule, setDeletingSchedule] = React.useState<TestRunScheduleInfo | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const loadList = React.useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await getSchedules(projectId, { page, page_size: PAGE_SIZE });
      setItems(response.data.items);
      setTotal(response.data.total);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载调度列表失败";
      setError(msg);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [projectId, page]);

  React.useEffect(() => {
    loadList();
  }, [loadList]);

  // 创建/编辑对话框打开时加载环境列表
  React.useEffect(() => {
    if (!projectId) return;
    if (!createOpen && !editingSchedule) return;

    let cancelled = false;
    setEnvironmentsLoading(true);
    listEnvironments(projectId)
      .then((res) => {
        if (cancelled) return;
        const envs = res.data || [];
        setEnvironments(envs);
        // 新建时默认选中项目默认环境
        if (createOpen && envs.length > 0) {
          const currentTemplate = normalizeTemplate(
            createForm.test_run_template as Record<string, unknown>
          );
          if (!currentTemplate.environment_id) {
            const defaultEnv = envs.find((e) => e.is_default);
            if (defaultEnv) {
              setCreateForm((prev) => ({
                ...prev,
                test_run_template: {
                  ...prev.test_run_template,
                  environment_id: defaultEnv.id,
                },
              }));
            }
          }
        }
      })
      .catch((err) => {
        if (cancelled) return;
        // eslint-disable-next-line no-console
        console.error("[SchedulesPage] 加载环境列表失败:", err);
      })
      .finally(() => {
        if (!cancelled) setEnvironmentsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [createOpen, editingSchedule, projectId]);

  function resetCreateForm() {
    setCreateForm({
      name: "",
      description: "",
      trigger_type: "cron",
      trigger_config: { cron_expression: "0 9 * * *" },
      test_run_template: {
        name: "定时执行",
        execution_mode: "sequential",
        scripts: [] as ScriptSelection[],
      },
      is_enabled: true,
    });
  }

  // 获取当前创建表单中的 template 对象（带默认值）
  const createTemplate = normalizeTemplate(
    createForm.test_run_template as Record<string, unknown>
  );

  async function handleCreate() {
    if (!createForm.name.trim()) return;
    setCreating(true);
    try {
      await createSchedule(projectId, {
        ...createForm,
        name: createForm.name.trim(),
        description: createForm.description?.trim() || undefined,
      });
      setCreateOpen(false);
      resetCreateForm();
      setPage(1);
      await loadList();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "创建调度失败";
      setError(msg);
    } finally {
      setCreating(false);
    }
  }

  function updateCreateTemplateScripts(scripts: ScriptSelection[]) {
    setCreateForm((prev) => ({
      ...prev,
      test_run_template: {
        ...prev.test_run_template,
        scripts,
      },
    }));
  }

  function updateEditTemplateScripts(scripts: ScriptSelection[]) {
    setEditForm((prev) => ({
      ...prev,
      test_run_template: {
        ...(prev.test_run_template ?? {}),
        scripts,
      },
    }));
  }

  function openEdit(schedule: TestRunScheduleInfo) {
    setEditingSchedule(schedule);
    setEditForm({
      name: schedule.name,
      description: schedule.description,
      trigger_type: schedule.trigger_type,
      trigger_config: schedule.trigger_config,
      test_run_template: normalizeTemplate(schedule.test_run_template),
      is_enabled: schedule.is_enabled,
    });
  }

  async function handleEditSave() {
    if (!editingSchedule) return;
    setEditSaving(true);
    try {
      await updateSchedule(projectId, editingSchedule.id, editForm);
      setEditingSchedule(null);
      await loadList();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "更新调度失败";
      setError(msg);
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
      await loadList();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "删除调度失败";
      setError(msg);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <MainLayout title="定时调度">
      <div className="space-y-6">
        {/* 导航 */}
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => router.push(`/projects/${projectId}/test-runs`)}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回测试运行
          </Button>
        </div>

        {/* 工具栏 */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={loadList} disabled={loading} title="刷新">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            新建调度
          </Button>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
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
              <CalendarClock className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">暂无定时调度</p>
            </div>
          ) : (
            <div className="divide-y">
              {items.map((schedule) => (
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
                      <span>下次执行: {formatNextRun(schedule.next_run_at)}</span>
                      {schedule.last_run_at && (
                        <span>上次执行: {new Date(schedule.last_run_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>
                  <div className="ml-4 flex items-center gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
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
                  </div>
                </div>
              ))}
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
      </div>

      {/* 创建对话框 */}
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) resetCreateForm();
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>新建定时调度</DialogTitle>
            <DialogDescription>
              创建定时调度以自动执行测试运行。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="sch-name">名称 *</Label>
              <Input
                id="sch-name"
                value={createForm.name}
                onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                placeholder="例如: 每日回归测试"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sch-desc">描述</Label>
              <Textarea
                id="sch-desc"
                value={(createForm.description as string) ?? ""}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                placeholder="可选描述"
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label>触发器类型</Label>
              <Select
                value={createForm.trigger_type}
                onValueChange={(v) => {
                  const type = v as ScheduleTriggerType;
                  let config: Record<string, unknown> = {};
                  if (type === "cron") config = { cron_expression: "0 9 * * *" };
                  else if (type === "interval") config = { minutes: 60 };
                  else if (type === "date") config = { run_date: new Date().toISOString() };
                  setCreateForm({ ...createForm, trigger_type: type, trigger_config: config });
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
            {createForm.trigger_type === "cron" && (
              <div className="space-y-2">
                <Label htmlFor="sch-cron">Cron 表达式</Label>
                <Input
                  id="sch-cron"
                  value={String(createForm.trigger_config.cron_expression || "")}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      trigger_config: { cron_expression: e.target.value },
                    })
                  }
                  placeholder="0 9 * * *"
                />
                <p className="text-xs text-muted-foreground">格式: 分 时 日 月 周</p>
              </div>
            )}
            {createForm.trigger_type === "interval" && (
              <div className="space-y-2">
                <Label htmlFor="sch-interval">间隔分钟数</Label>
                <Input
                  id="sch-interval"
                  type="number"
                  value={Number(createForm.trigger_config.minutes || 60)}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      trigger_config: { minutes: Number(e.target.value) },
                    })
                  }
                />
              </div>
            )}
            {createForm.trigger_type === "date" && (
              <div className="space-y-2">
                <Label htmlFor="sch-date">执行时间</Label>
                <Input
                  id="sch-date"
                  type="datetime-local"
                  value={String(createForm.trigger_config.run_date || "").slice(0, 16)}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      trigger_config: { run_date: new Date(e.target.value).toISOString() },
                    })
                  }
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="sch-template-name">测试运行名称模板</Label>
              <Input
                id="sch-template-name"
                value={String(
                  (createForm.test_run_template as Record<string, unknown>).name ?? ""
                )}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    test_run_template: {
                      ...prev.test_run_template,
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
                value={createTemplate.execution_mode || "sequential"}
                onValueChange={(v) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    test_run_template: {
                      ...prev.test_run_template,
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
                value={createTemplate.environment_id ?? "__default__"}
                onValueChange={(v) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    test_run_template: {
                      ...prev.test_run_template,
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
              scripts={createTemplate.scripts}
              onScriptsChange={updateCreateTemplateScripts}
            />
            <div className="flex items-center gap-2">
              <Checkbox
                id="sch-enabled"
                checked={createForm.is_enabled}
                onCheckedChange={(checked) => setCreateForm({ ...createForm, is_enabled: checked === true })}
              />
              <Label htmlFor="sch-enabled">立即启用</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creating}>
              取消
            </Button>
            <Button onClick={handleCreate} disabled={creating || !createForm.name.trim()}>
              {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 编辑对话框 */}
      <Dialog open={editingSchedule !== null} onOpenChange={(open) => !open && setEditingSchedule(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>编辑调度</DialogTitle>
            <DialogDescription>
              {editingSchedule ? `修改 ${editingSchedule.name}` : ""}
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
    </MainLayout>
  );
}
