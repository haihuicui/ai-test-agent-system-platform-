"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Play,
  History,
  CalendarClock,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getSchedule,
  getScheduleRuns,
  triggerSchedule,
  listEnvironments,
  type TestRunScheduleInfo,
  type TestRunListInfo,
  type EnvironmentInfo,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { ScheduleConfigCard } from "../../_components/schedule-config-card";
import { ScheduleRunHistoryDialog } from "../../_components/schedule-run-history-dialog";
import { ScheduleRuleActions } from "../../_components/schedule-rule-actions";
import { TestRunExecutionPanel } from "../../_components/test-run-execution-panel";
import { RUN_STATE_BADGE } from "../../_components/test-run-shared";

const PAGE_SIZE = 20;

export default function ScheduleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const scheduleId = params.scheduleId as string;

  const [schedule, setSchedule] = React.useState<TestRunScheduleInfo | null>(
    null
  );
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [runs, setRuns] = React.useState<TestRunListInfo[]>([]);
  const [runsTotal, setRunsTotal] = React.useState(0);
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);

  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [environmentsLoading, setEnvironmentsLoading] = React.useState(false);

  const [triggering, setTriggering] = React.useState(false);
  const [historyOpen, setHistoryOpen] = React.useState(false);

  const loadSchedule = React.useCallback(async () => {
    if (!projectId || !scheduleId) return;
    try {
      const response = await getSchedule(projectId, scheduleId);
      setSchedule(response.data);
      setError(null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "加载调度规则失败";
      setError(msg);
      setSchedule(null);
    }
  }, [projectId, scheduleId]);

  const loadRuns = React.useCallback(async () => {
    if (!projectId || !scheduleId) return;
    try {
      const response = await getScheduleRuns(projectId, scheduleId, {
        page: 1,
        page_size: PAGE_SIZE,
      });
      setRuns(response.data.items);
      setRunsTotal(response.data.total);
      // 默认选中最新一条；若当前选中项仍在列表中则保持
      setSelectedRunId((prev) => {
        if (prev && response.data.items.some((r) => r.id === prev)) {
          return prev;
        }
        return response.data.items[0]?.id ?? null;
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[ScheduleDetailPage] 加载执行记录失败:", err);
      setRuns([]);
      setRunsTotal(0);
      setSelectedRunId(null);
    }
  }, [projectId, scheduleId]);

  const loadEnvironments = React.useCallback(async () => {
    if (!projectId) return;
    setEnvironmentsLoading(true);
    try {
      const response = await listEnvironments(projectId);
      setEnvironments(response.data || []);
    } catch {
      setEnvironments([]);
    } finally {
      setEnvironmentsLoading(false);
    }
  }, [projectId]);

  const loadAll = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    await Promise.all([loadSchedule(), loadRuns(), loadEnvironments()]);
    setLoading(false);
  }, [loadSchedule, loadRuns, loadEnvironments]);

  React.useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function handleTrigger() {
    if (!projectId || !scheduleId) return;
    setTriggering(true);
    try {
      await triggerSchedule(projectId, scheduleId);
      await loadRuns();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "触发调度失败";
      setError(msg);
    } finally {
      setTriggering(false);
    }
  }

  const selectedRun = React.useMemo(
    () => runs.find((r) => r.id === selectedRunId),
    [runs, selectedRunId]
  );

  if (loading) {
    return (
      <MainLayout title="调度规则详情">
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </MainLayout>
    );
  }

  if (error || !schedule) {
    return (
      <MainLayout title="调度规则详情">
        <div className="flex h-64 flex-col items-center justify-center gap-4">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <p className="text-muted-foreground">
            {error || "调度规则不存在"}
          </p>
          <Button variant="outline" onClick={loadAll}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            重试
          </Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout title={`调度规则: ${schedule.name}`}>
      <div className="space-y-6">
        {/* 顶部导航与操作 */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              router.push(`/projects/${projectId}/test-runs?tab=scheduled`)
            }
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回列表
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTrigger}
              disabled={triggering}
            >
              {triggering ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              立即触发
            </Button>
            <ScheduleRuleActions
              projectId={projectId}
              schedule={schedule}
              showViewButton={false}
              onMutated={loadAll}
              onDeleted={() =>
                router.push(`/projects/${projectId}/test-runs?tab=scheduled`)
              }
              onError={(msg) => setError(msg)}
            />
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        )}

        {/* 规则配置 */}
        <ScheduleConfigCard
          schedule={schedule}
          environments={environments}
          environmentsLoading={environmentsLoading}
        />

        {/* 执行记录 */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center gap-2 border-b p-4">
            <CalendarClock className="h-5 w-5 text-primary" />
            <h2 className="font-medium">执行记录</h2>
          </div>

          <div className="p-4">
            {runs.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center gap-2">
                <History className="h-12 w-12 text-muted-foreground/50" />
                <p className="text-muted-foreground">暂无执行记录</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTrigger}
                  disabled={triggering}
                >
                  {triggering ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  立即触发
                </Button>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="space-y-1">
                      <Label className="text-muted-foreground">选择执行记录</Label>
                      <Select
                        value={selectedRunId ?? ""}
                        onValueChange={(v) => setSelectedRunId(v)}
                      >
                        <SelectTrigger className="w-[360px]">
                          <SelectValue placeholder="选择执行记录" />
                        </SelectTrigger>
                        <SelectContent>
                          {runs.map((run) => {
                            const stateInfo = RUN_STATE_BADGE[run.run_state];
                            return (
                              <SelectItem key={run.id} value={run.id}>
                                {run.identifier} · {run.name} · {stateInfo.label}
                              </SelectItem>
                            );
                          })}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {runsTotal > runs.length && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHistoryOpen(true)}
                    >
                      <History className="mr-2 h-4 w-4" />
                      查看全部
                    </Button>
                  )}
                </div>

                {selectedRun && (
                  <TestRunExecutionPanel
                    projectId={projectId}
                    runId={selectedRun.identifier}
                    showViewFullDetail
                    onError={(msg) => setError(msg)}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <ScheduleRunHistoryDialog
        projectId={projectId}
        schedule={schedule}
        open={historyOpen}
        onOpenChange={setHistoryOpen}
      />
    </MainLayout>
  );
}
