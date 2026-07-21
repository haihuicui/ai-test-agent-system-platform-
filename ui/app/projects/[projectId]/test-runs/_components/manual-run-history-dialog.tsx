"use client";

import * as React from "react";
import { History, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Pagination } from "@/components/ui/pagination";
import { listTestRuns, type TestRunListInfo } from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { RUN_STATE_BADGE } from "./test-run-shared";

const PAGE_SIZE = 20;

export interface ManualRunHistoryDialogProps {
  projectId: string;
  currentRunId: string;
  scriptIds: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect?: (run: TestRunListInfo) => void;
  pageSize?: number;
}

export function ManualRunHistoryDialog({
  projectId,
  currentRunId,
  scriptIds,
  open,
  onOpenChange,
  onSelect,
  pageSize = PAGE_SIZE,
}: ManualRunHistoryDialogProps) {
  const [items, setItems] = React.useState<TestRunListInfo[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const loadHistory = React.useCallback(
    async (pageNum = 1) => {
      if (!projectId || scriptIds.length === 0) return;
      setLoading(true);
      setError(null);
      try {
        const response = await listTestRuns(projectId, {
          trigger_type: "manual",
          script_ids: scriptIds.join(","),
          include_closed: true,
          p: pageNum,
          page_size: pageSize,
        });
        setItems(response.data);
        setTotal(response.info.total);
        setPage(response.info.page);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "加载历史执行记录失败";
        setError(msg);
        setItems([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [projectId, scriptIds, pageSize]
  );

  React.useEffect(() => {
    if (open) {
      setPage(1);
      loadHistory(1);
    } else {
      setItems([]);
      setTotal(0);
      setPage(1);
      setError(null);
    }
  }, [open, loadHistory]);

  const handleSelect = (run: TestRunListInfo) => {
    onSelect?.(run);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>历史执行记录</DialogTitle>
          <DialogDescription>
            与该手动测试运行包含相同脚本的其他手动运行
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
            <p className="text-muted-foreground">暂无历史执行记录</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="divide-y">
              {items.map((run) => {
                const stateInfo = RUN_STATE_BADGE[run.run_state];
                const isCurrent = run.identifier === currentRunId;
                return (
                  <div
                    key={run.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 font-medium">
                        <span>{run.name}</span>
                        {isCurrent && (
                          <span className="text-xs text-muted-foreground">(当前)</span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {run.identifier} · {stateInfo.label} ·{" "}
                        {new Date(run.created_at).toLocaleString()}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isCurrent}
                      onClick={() => handleSelect(run)}
                    >
                      {isCurrent ? (
                        <Check className="mr-2 h-4 w-4" />
                      ) : null}
                      {isCurrent ? "当前" : "选择"}
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
