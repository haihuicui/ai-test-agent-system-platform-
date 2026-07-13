"use client";

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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Pagination,
} from "@/components/ui/pagination";
import {
  getSchedules,
  type TestRunScheduleInfo,
  type ScheduleTriggerType,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { CreateScheduleDialog } from "../_components/create-schedule-dialog";
import { ScheduleRuleActions } from "../_components/schedule-rule-actions";

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
  const [items, setItems] = React.useState<TestRunScheduleInfo[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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

  React.useEffect(() => {
    loadList();
  }, [loadList]);

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
