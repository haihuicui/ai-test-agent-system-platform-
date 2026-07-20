"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjB0WmVBPT06NzFmMzc4M2U=

import * as React from "react";
import {
  Search,
  Plus,
  MoreVertical,
  Pencil,
  Trash2,
  ChevronLeft,
  ChevronRight,
  GripVertical,
  Globe,
  FileText,
  Play,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import type { WebFunction } from "@/lib/api/web-functions";
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  useSortable,
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjB0WmVBPT06NzFmMzc4M2U=

interface WebFunctionListProps {
  webFunctions: WebFunction[];
  loading: boolean;
  selectedIds: Set<string>;
  onSelectIds: (ids: Set<string>) => void;
  onBulkDelete?: () => void;
  onBatchRun?: () => void;
  batchRunning?: boolean;
  onViewWebFunction: (webFunction: WebFunction) => void;
  onDeleteWebFunction?: (webFunction: WebFunction) => void;
  folderName?: string;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
  };
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjB0WmVBPT06NzFmMzc4M2U=

export function WebFunctionList({
  webFunctions,
  loading,
  selectedIds,
  onSelectIds,
  onBulkDelete,
  onBatchRun,
  batchRunning,
  onViewWebFunction,
  onDeleteWebFunction,
  folderName,
  pagination,
}: WebFunctionListProps) {
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [localWebFunctions, setLocalWebFunctions] = React.useState<WebFunction[]>(
    webFunctions || []
  );

  // 同步外部webFunctions到本地状态
  React.useEffect(() => {
    setLocalWebFunctions(webFunctions || []);
  }, [webFunctions]);

  // 配置拖动传感器
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // 拖动开始
  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  // 拖动结束
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over || active.id === over.id) {
      return;
    }

    setLocalWebFunctions((items) => {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);
      const newItems = arrayMove(items, oldIndex, newIndex);

      toast.success("Web功能顺序已更新");

      return newItems;
    });
  };

  // 全选/取消全选
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      onSelectIds(new Set(localWebFunctions.map((wf) => wf.id)));
    } else {
      onSelectIds(new Set());
    }
  };

  // 单选
  const handleSelect = (id: string, checked: boolean) => {
    const newIds = new Set(selectedIds);
    if (checked) {
      newIds.add(id);
    } else {
      newIds.delete(id);
    }
    onSelectIds(newIds);
  };

  const isAllSelected =
    localWebFunctions.length > 0 && selectedIds.size === localWebFunctions.length;
  const isPartialSelected =
    selectedIds.size > 0 && selectedIds.size < localWebFunctions.length;

  // 可拖动的Web功能行组件
  const DraggableWebFunctionRow = ({
    webFunction,
  }: {
    webFunction: WebFunction;
  }) => {
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: webFunction.id });

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
      opacity: isDragging ? 0.5 : 1,
    };

    return (
      <tr
        ref={setNodeRef}
        style={style}
        className={cn(
          "group border-b hover:bg-muted/50 transition-colors",
          selectedIds.has(webFunction.id) && "bg-muted/30"
        )}
      >
        <td className="p-3">
          <div className="flex items-center gap-1">
            <div
              {...attributes}
              {...listeners}
              className="cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100"
            >
              <GripVertical className="h-4 w-4 text-muted-foreground" />
            </div>
            <Checkbox
              checked={selectedIds.has(webFunction.id)}
              onCheckedChange={(checked) =>
                handleSelect(webFunction.id, checked as boolean)
              }
              aria-label={`选择 ${webFunction.display_name}`}
            />
          </div>
        </td>
        <td className="p-3 overflow-hidden">
          <button
            onClick={() => onViewWebFunction(webFunction)}
            className="truncate text-left text-sm font-medium hover:text-primary block w-full"
          >
            {webFunction.display_name}
          </button>
        </td>
        <td className="p-3 overflow-hidden">
          <span className="text-sm text-muted-foreground truncate block">
            {webFunction.identifier}
          </span>
        </td>
        <td className="p-3 overflow-hidden">
          {webFunction.business_module && (
            <Badge variant="outline" className="truncate">
              {webFunction.business_module}
            </Badge>
          )}
        </td>
        <td className="p-3 overflow-hidden">
          <div className="flex items-center gap-1 text-sm">
            <FileText className="h-3 w-3 text-muted-foreground" />
            <span>{webFunction.total_sub_functions}</span>
          </div>
        </td>
        <td className="p-3 overflow-hidden">
          <div className="flex items-center gap-1 text-sm">
            <Globe className="h-3 w-3 text-muted-foreground" />
            <span>{webFunction.total_test_cases}</span>
          </div>
        </td>
        <td className="p-3">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {new Date(webFunction.created_at).toLocaleDateString("zh-CN", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
            })}
          </span>
        </td>
        <td className="p-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 opacity-0 group-hover:opacity-100"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onViewWebFunction(webFunction)}>
                <Globe className="mr-2 h-4 w-4" />
                查看子功能
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => onDeleteWebFunction && onDeleteWebFunction(webFunction)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </td>
      </tr>
    );
  };

  return (
    <div className="flex flex-col">
      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 border-b bg-muted/50 px-4 py-2">
          <span className="text-sm text-muted-foreground">
            已选择 {selectedIds.size} 项
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={onBatchRun}
            disabled={batchRunning}
          >
            {batchRunning ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            {batchRunning ? "提交中..." : "批量运行"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
            onClick={onBulkDelete}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            批量删除
          </Button>
        </div>
      )}

      {/* 列表 */}
      <ScrollArea className="min-h-0">
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="text-muted-foreground">加载中...</div>
          </div>
        ) : webFunctions.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-6 py-12">
            {/* 图标 */}
            <div className="flex h-16 w-16 items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30">
              <Globe className="h-8 w-8 text-muted-foreground/50" />
            </div>

            {/* 标题和描述 */}
            <div className="text-center">
              <h3 className="text-lg font-semibold">添加Web功能</h3>
              <p className="text-sm text-muted-foreground">
                您可以通过上方工具栏中的"新建"或"AI生成"按钮创建Web功能
              </p>
            </div>

            {/* 操作提示 */}
            <div className="text-sm text-muted-foreground mt-4">
              提示：选择文件夹后可以筛选显示的功能
            </div>
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <table className="w-full table-fixed">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b text-left text-xs font-medium uppercase text-muted-foreground">
                  <th className="w-16 p-3">
                    <Checkbox
                      checked={isAllSelected}
                      onCheckedChange={handleSelectAll}
                      aria-label="全选"
                    />
                  </th>
                  <th className="w-48 p-3">显示名称</th>
                  <th className="w-32 p-3">标识符</th>
                  <th className="w-28 p-3">业务模块</th>
                  <th className="w-20 p-3">子功能数</th>
                  <th className="w-20 p-3">用例数</th>
                  <th className="w-36 p-3">创建时间</th>
                  <th className="w-16 p-3"></th>
                </tr>
              </thead>
              <SortableContext
                items={localWebFunctions.map((wf) => wf.id)}
                strategy={verticalListSortingStrategy}
              >
                <tbody>
                  {localWebFunctions.map((webFunction) => (
                    <DraggableWebFunctionRow
                      key={webFunction.id}
                      webFunction={webFunction}
                    />
                  ))}
                </tbody>
              </SortableContext>
            </table>

            {/* 拖动覆盖层 */}
            <DragOverlay>
              {activeId ? (
                <div className="rounded-md bg-accent p-3 shadow-lg">
                  <span className="text-sm font-medium">
                    {
                      localWebFunctions.find((wf) => wf.id === activeId)
                        ?.display_name
                    }
                  </span>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </ScrollArea>

      {/* 分页 */}
      {pagination && pagination.total > pagination.pageSize && (
        <div className="flex items-center justify-end border-t px-4 py-3 gap-2">
          <div className="text-sm text-muted-foreground">
            显示 {(pagination.page - 1) * pagination.pageSize + 1} -{" "}
            {Math.min(pagination.page * pagination.pageSize, pagination.total)}{" "}
            / {pagination.total} 条
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page === 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={
                pagination.page >=
                Math.ceil(pagination.total / pagination.pageSize)
              }
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              下一页
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjB0WmVBPT06NzFmMzc4M2U=
