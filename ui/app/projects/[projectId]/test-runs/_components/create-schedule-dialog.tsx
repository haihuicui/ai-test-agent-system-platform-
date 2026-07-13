"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  createSchedule,
  listEnvironments,
  type TestRunScheduleCreate,
  type ScheduleTriggerType,
  type ScriptSelection,
  type ExecutionMode,
  type EnvironmentInfo,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { ScriptSelector } from "./script-selector";

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

export interface CreateScheduleDialogProps {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export function CreateScheduleDialog({
  projectId,
  open,
  onOpenChange,
  onSuccess,
}: CreateScheduleDialogProps) {
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

  React.useEffect(() => {
    if (!open || !projectId) return;

    let cancelled = false;
    setEnvironmentsLoading(true);
    listEnvironments(projectId)
      .then((res) => {
        if (cancelled) return;
        const envs = res.data || [];
        setEnvironments(envs);
        if (envs.length > 0) {
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
        console.error("[CreateScheduleDialog] 加载环境列表失败:", err);
      })
      .finally(() => {
        if (!cancelled) setEnvironmentsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, projectId]);

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
      onOpenChange(false);
      resetCreateForm();
      onSuccess?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "创建调度失败";
      // eslint-disable-next-line no-console
      console.error("[CreateScheduleDialog] 创建调度失败:", msg);
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

  return (
    <Dialog
      open={open}
      onOpenChange={(newOpen) => {
        if (!newOpen) {
          resetCreateForm();
        }
        onOpenChange(newOpen);
      }}
    >
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>新建定时调度</DialogTitle>
          <DialogDescription>创建定时调度以自动执行测试运行。</DialogDescription>
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
                    environment_id: v === "__default__" ? undefined : v,
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
              onCheckedChange={(checked) =>
                setCreateForm({ ...createForm, is_enabled: checked === true })
              }
            />
            <Label htmlFor="sch-enabled">立即启用</Label>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={creating}
          >
            取消
          </Button>
          <Button onClick={handleCreate} disabled={creating || !createForm.name.trim()}>
            {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
