"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { History, Eye, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Pagination } from "@/components/ui/pagination";
import { getScheduleRuns, type TestRunScheduleInfo } from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { RUN_STATE_BADGE } from "./test-run-shared";

const PAGE_SIZE = 20;

export interface ScheduleRunHistoryDialogProps {
  projectId: string;
  schedule: TestRunScheduleInfo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pageSize?: number;
}

export function ScheduleRunHistoryDialog({
  projectId,
  schedule,
  open,
  onOpenChange,
  pageSize = PAGE_SIZE,
}: ScheduleRunHistoryDialogProps) {
  const router = useRouter();

  const [items, setItems] = React.useState<
    Awaited<ReturnType<typeof getScheduleRuns>>["data"]["items"]
  >([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const loadHistory = React.useCallback(
    async (pageNum = 1) => {
      if (!projectId || !schedule) return;
      setLoading(true);
      setError(null);
      try {
        const response = await getScheduleRuns(projectId, schedule.id, {
          page: pageNum,
          page_size: pageSize,
        });
        setItems(response.data.items);
        setTotal(response.data.total);
        setPage(response.data.page);
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : "加载执行历史失败";
        setError(msg);
        setItems([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [projectId, schedule, pageSize]
  );

  React.useEffect(() => {
    if (open && schedule) {
      setPage(1);
      loadHistory(1);
    } else if (!open) {
      setItems([]);
      setTotal(0);
      setPage(1);
      setError(null);
    }
  }, [open, schedule, loadHistory]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>执行历史</DialogTitle>
          <DialogDescription>
            {schedule
              ? `调度 ${schedule.name} 产生的测试运行`
              : "查看调度规则产生的测试运行"}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex h-64 flex-col items-center justify-center gap-4">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={() => loadHistory(page)}>
              重试
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <History className="h-12 w-12 text-muted-foreground/50" />
            <p className="text-muted-foreground">暂无执行历史</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="divide-y">
              {items.map((run) => {
                const stateInfo = RUN_STATE_BADGE[run.run_state];
                return (
                  <div
                    key={run.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50"
                  >
                    <div className="min-w-0">
                      <div className="font-medium">{run.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {run.identifier} · {stateInfo.label} ·{" "}
                        {new Date(run.created_at).toLocaleString()}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        onOpenChange(false);
                        router.push(
                          `/projects/${projectId}/test-runs/${run.identifier}`
                        );
                      }}
                    >
                      <Eye className="mr-2 h-4 w-4" />
                      查看
                    </Button>
                  </div>
                );
              })}
            </div>
            {total > 0 && (
              <Pagination
                page={page}
                pageSize={pageSize}
                total={total}
                onPageChange={(p) => loadHistory(p)}
                showPageSizeSelector={false}
              />
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
