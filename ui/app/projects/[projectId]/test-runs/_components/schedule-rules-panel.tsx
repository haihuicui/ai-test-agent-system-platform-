"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import {
  Plus,
  CalendarClock,
  Clock,
  Loader2,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  PlayCircle,
  Lock,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Pagination,
} from "@/components/ui/pagination";
import {
  getSchedules,
  listTestRuns,
  type TestRunScheduleInfo,
  type ScheduleTriggerType,
  type TestRunListInfo,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { CreateScheduleDialog } from "../_components/create-schedule-dialog";
import { ScheduleRuleActions } from "../_components/schedule-rule-actions";
import {
  RUN_STATE_BADGE,
  EXECUTION_MODE_BADGE,
  progressDoneRatio,
} from "./test-run-shared";

const PAGE_SIZE = 20;

export const TRIGGER_TYPE_LABEL: Record<ScheduleTriggerType, string> = {
  cron: "Cron 表达式",
  interval: "间隔触发",
  date: "一次性",
};

export function formatNextRun(dateStr?: string, isEnabled?: boolean): string {
  if (isEnabled === false) return "已禁用";
  if (!dateStr) return "未计算";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "无效时间";
  // 允许 60 秒时钟偏差，过早的时间视为已过期
  if (d.getTime() < Date.now() - 60_000) return "已过期";
  return d.toLocaleString();
}

export function buildCronDescription(config: Record<string, unknown>): string {
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

export interface ScheduleRulesPanelProps {
  projectId: string;
}

export function ScheduleRulesPanel({ projectId }: ScheduleRulesPanelProps) {
  const router = useRouter();
  const [items, setItems] = React.useState<TestRunScheduleInfo[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [runs, setRuns] = React.useState<TestRunListInfo[]>([]);
  const [runsTotal, setRunsTotal] = React.useState(0);
  const [runsPage, setRunsPage] = React.useState(1);
  const [runsLoading, setRunsLoading] = React.useState(false);

  const [createOpen, setCreateOpen] = React.useState(false);

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

  const loadRuns = React.useCallback(async (pageNum = 1) => {
    if (!projectId) return;
    setRunsLoading(true);
    try {
      const response = await listTestRuns(projectId, {
        p: pageNum,
        page_size: PAGE_SIZE,
        trigger_type: "scheduled",
      });
      setRuns(response.data);
      setRunsTotal(response.info.total);
      setRunsPage(response.info.page);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[ScheduleRulesPanel] 加载定时执行记录失败:", err);
      setRuns([]);
      setRunsTotal(0);
    } finally {
      setRunsLoading(false);
    }
  }, [projectId]);

  React.useEffect(() => {
    loadList();
  }, [loadList]);

  React.useEffect(() => {
    loadRuns(runsPage);
  }, [loadRuns, runsPage]);

  return (
    <>
      <div className="space-y-6">
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
                      <span>下次执行: {formatNextRun(schedule.next_run_at, schedule.is_enabled)}</span>
                      {schedule.last_run_at && (
                        <span>上次执行: {new Date(schedule.last_run_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>
                  <div className="ml-4 flex items-center gap-2">
                    <ScheduleRuleActions
                      projectId={projectId}
                      schedule={schedule}
                      onMutated={loadList}
                      onError={(msg) => setError(msg)}
                      showViewButton
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 执行记录 */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center gap-2 border-b p-4">
            <PlayCircle className="h-5 w-5 text-primary" />
            <h2 className="font-medium">执行记录</h2>
          </div>
          {runsLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : runs.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2">
              <PlayCircle className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">暂无定时执行记录</p>
            </div>
          ) : (
            <div className="divide-y">
              {runs.map((run) => {
                const p = run.overall_progress;
                const progress = progressDoneRatio(run);
                const closed = run.active_state === "closed";
                const stateInfo = RUN_STATE_BADGE[run.run_state];
                const execMode = run.execution_mode ? EXECUTION_MODE_BADGE[run.execution_mode] : null;
                return (
                  <div
                    key={run.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-medium truncate">{run.name}</h3>
                        <Badge variant="outline" className="font-mono text-xs">
                          {run.identifier}
                        </Badge>
                        <Badge variant={stateInfo.variant}>{stateInfo.label}</Badge>
                        {execMode && (
                          <Badge variant="outline" className="text-xs">
                            {execMode.label}
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
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {runsTotal > 0 && (
            <Pagination
              page={runsPage}
              pageSize={PAGE_SIZE}
              total={runsTotal}
              onPageChange={setRunsPage}
              showPageSizeSelector={false}
            />
          )}
        </div>
      </div>

      {/* 创建对话框 */}
      <CreateScheduleDialog
        projectId={projectId}
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={() => {
          setPage(1);
        }}
      />
    </>
  );
}
