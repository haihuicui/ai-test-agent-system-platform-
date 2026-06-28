"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vlc1SU53PT06NWNhZGUzZDU=

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
  Filter,
  Sparkles,
  Play,
  Database,
  FileCode,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import type { APITest } from "@/lib/api/api-tests";
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
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vlc1SU53PT06NWNhZGUzZDU=

interface APITestListProps {
  apiTests: APITest[];
  loading: boolean;
  selectedIds: Set<string>;
  onSelectIds: (ids: Set<string>) => void;
  onSearch: (query: string) => void;
  onFilterFormat: (format: string) => void;
  onCreateAPITest: () => void;
  onEditAPITest: (apiTest: APITest) => void;
  onDeleteAPITest: (apiTest: APITest) => void;
  onBulkDelete?: () => void;
  onViewAPITest: (apiTest: APITest) => void;
  onRunAPITest: (apiTest: APITest) => void;
  onAIGenerate?: () => void;
  onAPIParse?: () => void;  // 新增：API 解析回调
  onOpenAIChat?: () => void;
  aiChatOpen?: boolean;
  folderName?: string;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
  };
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vlc1SU53PT06NWNhZGUzZDU=

const scriptFormatLabels: Record<string, string> = {
  playwright: "Playwright",
  postman: "Postman",
  rest_assured: "REST Assured",
  other: "其他",
};

export function APITestList({
  apiTests,
  loading,
  selectedIds,
  onSelectIds,
  onSearch,
  onFilterFormat,
  onCreateAPITest,
  onEditAPITest,
  onDeleteAPITest,
  onBulkDelete,
  onViewAPITest,
  onRunAPITest,
  onAIGenerate,
  onAPIParse,  // 新增
  onOpenAIChat,
  aiChatOpen,
  folderName,
  pagination,
}: APITestListProps) {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [localAPITests, setLocalAPITests] = React.useState<APITest[]>(apiTests || []);

  // 同步外部apiTests到本地状态
  React.useEffect(() => {
    setLocalAPITests(apiTests || []);
  }, [apiTests]);

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

    setLocalAPITests((items) => {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);
      const newItems = arrayMove(items, oldIndex, newIndex);

      toast.success("API测试顺序已更新");

      return newItems;
    });
  };

  // 全选/取消全选
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      onSelectIds(new Set(localAPITests.map((tc) => tc.id)));
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

  // 搜索
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(searchQuery);
  };

  const isAllSelected =
    localAPITests.length > 0 && selectedIds.size === localAPITests.length;
  const isPartialSelected =
    selectedIds.size > 0 && selectedIds.size < localAPITests.length;

  // 可拖动的API测试行组件
  const DraggableAPITestRow = ({ apiTest }: { apiTest: APITest }) => {
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: apiTest.id });

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
          selectedIds.has(apiTest.id) && "bg-muted/30"
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
              checked={selectedIds.has(apiTest.id)}
              onCheckedChange={(checked) =>
                handleSelect(apiTest.id, checked as boolean)
              }
              aria-label={`选择 ${apiTest.name}`}
            />
          </div>
        </td>
        <td className="p-3 overflow-hidden">
          <button
            onClick={() => onViewAPITest(apiTest)}
            className="truncate text-left text-sm font-medium hover:text-primary block w-full"
          >
            {apiTest.name}
          </button>
        </td>
        <td className="p-3 overflow-hidden">
          <span className="text-sm text-muted-foreground truncate block">
            {apiTest.identifier}
          </span>
        </td>
        <td className="p-3 overflow-hidden">
          <Badge variant="outline" className="truncate">
            {scriptFormatLabels[apiTest.script_format] || apiTest.script_format}
          </Badge>
        </td>
        <td className="p-3 overflow-hidden">
          <div className="flex items-center gap-1 text-sm">
            <Database className="h-3 w-3 text-muted-foreground" />
            <span>{apiTest.total_endpoints}</span>
          </div>
        </td>
        <td className="p-3 overflow-hidden">
          <div className="flex items-center gap-1 text-sm">
            <FileCode className="h-3 w-3 text-muted-foreground" />
            <span>{apiTest.total_scenarios}</span>
          </div>
        </td>
        <td className="p-3 overflow-hidden">
          <span className="text-sm text-muted-foreground truncate block">
            {new Date(apiTest.created_at).toLocaleDateString("zh-CN")}
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
              <DropdownMenuItem onClick={() => onViewAPITest(apiTest)}>
                <FileCode className="mr-2 h-4 w-4" />
                查看详情
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onRunAPITest(apiTest)}>
                <Play className="mr-2 h-4 w-4" />
                运行测试
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onEditAPITest(apiTest)}>
                <Pencil className="mr-2 h-4 w-4" />
                编辑
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => onDeleteAPITest(apiTest)}
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
    <div className="flex h-full flex-col">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">API测试</h2>
          <span className="text-sm text-muted-foreground">
            ({pagination?.total || apiTests.length})
          </span>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={handleSearch} className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索API测试..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 pl-9"
            />
          </form>
          <Button variant="outline" size="sm">
            <Filter className="mr-2 h-4 w-4" />
            筛选
          </Button>
          {onAPIParse && (
            <Button variant="outline" size="sm" onClick={onAPIParse}>
              <FileCode className="mr-2 h-4 w-4" />
              API解析
            </Button>
          )}
          {onAIGenerate && (
            <Button variant="outline" size="sm" onClick={onAIGenerate}>
              <Sparkles className="mr-2 h-4 w-4" />
              AI生成
            </Button>
          )}
          <Button onClick={onCreateAPITest}>
            <Plus className="mr-2 h-4 w-4" />
            新建
          </Button>
          {onOpenAIChat && !aiChatOpen && (
            <Button variant="outline" size="sm" onClick={onOpenAIChat}>
              <ChevronLeft className="mr-2 h-4 w-4" />
              AI 助手
            </Button>
          )}
        </div>
      </div>

      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 border-b bg-muted/50 px-4 py-2">
          <span className="text-sm text-muted-foreground">
            已选择 {selectedIds.size} 项
          </span>
          <Button variant="outline" size="sm">
            批量运行
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
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="text-muted-foreground">加载中...</div>
          </div>
        ) : apiTests.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 py-16">
            {/* 图标 */}
            <div className="flex h-16 w-16 items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30">
              <FileCode className="h-8 w-8 text-muted-foreground/50" />
            </div>

            {/* 标题和描述 */}
            <div className="text-center">
              <h3 className="text-lg font-semibold">添加API测试</h3>
              <p className="text-sm text-muted-foreground">
                您可以通过以下方式创建API测试
              </p>
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-3">
              {onAPIParse && (
                <Button variant="outline" onClick={onAPIParse}>
                  <FileCode className="mr-2 h-4 w-4" />
                  API解析
                </Button>
              )}
              {onAIGenerate && (
                <Button variant="outline" onClick={onAIGenerate}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  AI生成测试
                </Button>
              )}
              <Button variant="outline" onClick={onCreateAPITest}>
                <Plus className="mr-2 h-4 w-4" />
                手动创建
              </Button>
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
                  <th className="w-48 p-3">名称</th>
                  <th className="w-32 p-3">标识符</th>
                  <th className="w-28 p-3">脚本格式</th>
                  <th className="w-20 p-3">端点数</th>
                  <th className="w-20 p-3">场景数</th>
                  <th className="w-28 p-3">创建时间</th>
                  <th className="w-16 p-3"></th>
                </tr>
              </thead>
              <SortableContext
                items={localAPITests.map((tc) => tc.id)}
                strategy={verticalListSortingStrategy}
              >
                <tbody>
                  {localAPITests.map((apiTest) => (
                    <DraggableAPITestRow key={apiTest.id} apiTest={apiTest} />
                  ))}
                </tbody>
              </SortableContext>
            </table>

            {/* 拖动覆盖层 */}
            <DragOverlay>
              {activeId ? (
                <div className="rounded-md bg-accent p-3 shadow-lg">
                  <span className="text-sm font-medium">
                    {localAPITests.find((tc) => tc.id === activeId)?.name}
                  </span>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </ScrollArea>

      {/* 分页 */}
      {pagination && pagination.total > pagination.pageSize && (
        <div className="flex items-center justify-between border-t px-4 py-3">
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
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vlc1SU53PT06NWNhZGUzZDU=
