"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkV0WE53PT06MDFkOWUxNjI=

import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  GripVertical,
  FileText,
  Play,
  MoreHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AndroidSubFunction } from "@/lib/api/android-tests";
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
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkV0WE53PT06MDFkOWUxNjI=

interface AndroidSubFunctionListProps {
  subFunctions: AndroidSubFunction[];
  loading: boolean;
  selectedId?: string | null;
  onSelectSubFunction: (subFunctionId: string) => void;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
  };
  showHeader?: boolean;
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkV0WE53PT06MDFkOWUxNjI=

export function AndroidSubFunctionList({
  subFunctions,
  loading,
  selectedId,
  onSelectSubFunction,
  pagination,
  showHeader = true,
}: AndroidSubFunctionListProps) {
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [localSubFunctions, setLocalSubFunctions] = React.useState<AndroidSubFunction[]>(subFunctions || []);

  React.useEffect(() => { setLocalSubFunctions(subFunctions || []); }, [subFunctions]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const handleDragStart = (event: DragStartEvent) => setActiveId(event.active.id as string);
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    if (!over || active.id === over.id) return;
    setLocalSubFunctions((items) => {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);
      return arrayMove(items, oldIndex, newIndex);
    });
  };

  const DraggableSubFunctionRow = ({ subFunction }: { subFunction: AndroidSubFunction }) => {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: subFunction.id });
    const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };

    return (
      <div
        ref={setNodeRef}
        style={style}
        className={cn(
          "group flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-all hover:shadow-md",
          selectedId === subFunction.id
            ? "border-green-500 bg-green-50/50 dark:bg-green-950/20 shadow-sm"
            : "border-border bg-card hover:bg-accent/50"
        )}
        onClick={() => onSelectSubFunction(subFunction.id)}
      >
        <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="h-4 w-4 text-green-500 shrink-0" />
            <span className="font-medium text-sm truncate">{subFunction.display_name}</span>
            <Badge variant="outline" className="text-[10px] h-4 px-1 shrink-0">{subFunction.identifier}</Badge>
          </div>
          {subFunction.description && (
            <p className="text-xs text-muted-foreground truncate ml-6">{subFunction.description}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5 ml-6">
            <Badge className={cn("text-[10px] h-5",
              subFunction.test_type === "functional" ? "bg-green-500 text-white" :
              subFunction.test_type === "validation" ? "bg-blue-500 text-white" :
              subFunction.test_type === "ui" ? "bg-purple-500 text-white" :
              "bg-gray-500 text-white"
            )}>{subFunction.test_type}</Badge>
            <Badge className={cn("text-[10px] h-5",
              subFunction.priority === "critical" ? "bg-red-500 text-white" :
              subFunction.priority === "high" ? "bg-orange-500 text-white" :
              subFunction.priority === "medium" ? "bg-yellow-500 text-white" :
              "bg-gray-500 text-white"
            )}>{subFunction.priority}</Badge>
            <span className="text-xs text-muted-foreground">{subFunction.total_test_cases} 用例</span>
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 shrink-0">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onSelectSubFunction(subFunction.id)}>
              <FileText className="mr-2 h-4 w-4" />查看详情
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Play className="mr-2 h-4 w-4" />执行测试
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {showHeader && (
        <div className="flex items-center justify-between border-b p-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-green-500" />
            <h3 className="font-semibold">子功能列表</h3>
            <span className="text-sm text-muted-foreground">({subFunctions.length})</span>
          </div>
        </div>
      )}
      <ScrollArea className="flex-1 p-4">
        {loading ? (
          <div className="flex h-32 items-center justify-center text-muted-foreground">加载中...</div>
        ) : subFunctions.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-8">
            <FileText className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">暂无子功能</p>
            <p className="text-xs text-muted-foreground">创建功能后，AI 助手将自动生成子功能</p>
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
            <SortableContext items={localSubFunctions.map((sf) => sf.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {localSubFunctions.map((subFunction) => (
                  <DraggableSubFunctionRow key={subFunction.id} subFunction={subFunction} />
                ))}
              </div>
            </SortableContext>
            <DragOverlay>
              {activeId ? (
                <div className="rounded-lg border bg-card p-3 shadow-lg">
                  <span className="text-sm font-medium">{localSubFunctions.find((sf) => sf.id === activeId)?.display_name}</span>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </ScrollArea>
      {pagination && pagination.total > pagination.pageSize && (
        <div className="flex items-center justify-end border-t px-4 py-2 gap-2">
          <div className="text-xs text-muted-foreground">
            {(pagination.page - 1) * pagination.pageSize + 1} - {Math.min(pagination.page * pagination.pageSize, pagination.total)} / {pagination.total}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-7 w-7" disabled={pagination.page === 1} onClick={() => pagination.onPageChange(pagination.page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7" disabled={pagination.page >= Math.ceil(pagination.total / pagination.pageSize)} onClick={() => pagination.onPageChange(pagination.page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkV0WE53PT06MDFkOWUxNjI=
