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
} from "lucide-react";
import { Button } from "@/components/ui/button";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  updateSchedule,
  deleteSchedule,
  triggerSchedule,
  listEnvironments,
  type TestRunScheduleInfo,
  type TestRunScheduleCreate,
  type ScheduleTriggerType,
  type ScriptSelection,
  type ExecutionMode,
  type EnvironmentInfo,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { ScriptSelector } from "./script-selector";
import { ScheduleRunHistoryDialog } from "./schedule-run-history-dialog";

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

export interface ScheduleRuleActionsProps {
  projectId: string;
  schedule: TestRunScheduleInfo;
  onMutated?: () => void;
  onDeleted?: () => void;
  onError?: (message: string) => void;
  showViewButton?: boolean;
}

export function ScheduleRuleActions({
  projectId,
  schedule,
  onMutated,
  onDeleted,
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

  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [environmentsLoading, setEnvironmentsLoading] = React.useState(false);

  React.useEffect(() => {
    if (!projectId) return;
    if (!editingSchedule) return;

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
  }, [editingSchedule, projectId]);

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
      if (onDeleted) {
        onDeleted();
      } else {
        onMutated?.();
      }
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

  function handleViewDetail(s: TestRunScheduleInfo) {
    router.push(`/projects/${projectId}/test-runs/schedules/${s.id}`);
  }

  return (
    <>
      {showViewButton && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleViewDetail(schedule)}
        >
          <Eye className="mr-2 h-4 w-4" />
          查看
        </Button>
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
          <DropdownMenuItem onClick={() => setRunHistorySchedule(schedule)}>
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
      <ScheduleRunHistoryDialog
        projectId={projectId}
        schedule={runHistorySchedule}
        open={runHistorySchedule !== null}
        onOpenChange={(open) => {
          if (!open) setRunHistorySchedule(null);
        }}
      />
    </>
  );
}
