"use client";

import * as React from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Code,
  Layers,
  Globe,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  TRIGGER_TYPE_LABEL,
  formatNextRun,
  formatScheduleDate,
  buildCronDescription,
} from "./schedule-rules-panel";
import { SCRIPT_TYPE_LABEL } from "./test-run-shared";
import type {
  TestRunScheduleInfo,
  EnvironmentInfo,
  ScriptSelection,
  ExecutionMode,
} from "@/lib/api";

const SCRIPT_TYPE_ICON: Record<
  ScriptSelection["script_type"],
  React.ReactNode
> = {
  api_test: <Code className="h-3.5 w-3.5" />,
  scenario: <Layers className="h-3.5 w-3.5" />,
  web_test: <Globe className="h-3.5 w-3.5" />,
  test_case: <Code className="h-3.5 w-3.5" />,
};

interface ScheduleConfigCardProps {
  schedule: TestRunScheduleInfo;
  environments?: EnvironmentInfo[];
  environmentsLoading?: boolean;
}

function normalizeTemplate(
  template?: Record<string, unknown>
): {
  name: string;
  execution_mode: ExecutionMode;
  scripts: ScriptSelection[];
  environment_id?: string;
} {
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

export function ScheduleConfigCard({
  schedule,
  environments = [],
  environmentsLoading = false,
}: ScheduleConfigCardProps) {
  const template = normalizeTemplate(schedule.test_run_template);
  const env = environments.find((e) => e.id === template.environment_id);

  return (
    <div className="rounded-lg border bg-card p-6 space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{schedule.name}</h2>
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Label className="text-muted-foreground">触发类型</Label>
          <div className="mt-1">{TRIGGER_TYPE_LABEL[schedule.trigger_type]}</div>
        </div>
        <div>
          <Label className="text-muted-foreground">触发配置</Label>
          <div className="mt-1 flex items-center gap-1">
            <Clock className="h-3.5 w-3.5 text-muted-foreground" />
            {buildCronDescription(schedule.trigger_config)}
          </div>
        </div>
        <div>
          <Label className="text-muted-foreground">下次执行</Label>
          <div className="mt-1">
            {formatNextRun(schedule.next_run_at, schedule.is_enabled)}
          </div>
        </div>
        <div>
          <Label className="text-muted-foreground">上次执行</Label>
          <div className="mt-1">{formatScheduleDate(schedule.last_run_at)}</div>
        </div>
        <div>
          <Label className="text-muted-foreground">创建时间</Label>
          <div className="mt-1">
            {new Date(schedule.created_at).toLocaleString()}
          </div>
        </div>
        <div>
          <Label className="text-muted-foreground">更新时间</Label>
          <div className="mt-1">
            {schedule.updated_at
              ? new Date(schedule.updated_at).toLocaleString()
              : "暂无"}
          </div>
        </div>
      </div>

      <div>
        <Label className="text-muted-foreground">描述</Label>
        <div className="mt-1 text-sm">{schedule.description || "无描述"}</div>
      </div>

      <div className="rounded-lg border p-4 space-y-4">
        <h4 className="font-medium">测试运行模板</h4>
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
                    {SCRIPT_TYPE_ICON[s.script_type]}
                    {typeInfo}
                    <span className="text-muted-foreground">
                      {s.script_name || s.script_identifier || s.script_id}
                    </span>
                  </Badge>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
