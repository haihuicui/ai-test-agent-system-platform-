"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGNVFRPT06OWExMDllNDA=

import * as React from "react";
import {
  Search,
  Plus,
  MoreVertical,
  Pencil,
  Trash2,
  Copy,
  FileText,
  ChevronDown,
  ChevronUp,
  GripVertical,
  Sparkles,
  Upload,
  Download,
  ClipboardList,
  Keyboard,
  Filter,
  MessageSquare,
  Loader2,
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
import { Pagination } from "@/components/ui/pagination";
import { useLanguage } from "@/providers/LanguageProvider";
import {
  TestCaseFilterPanel,
  type TestCaseFilters,
} from "./test-case-filter-panel";
import { TableRowSkeleton, FilterBarSkeleton } from "./test-case-skeleton";
import type { TestCaseInfo, Priority, TestCaseState, TestCaseTemplate } from "@/lib/api/types";
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
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGNVFRPT06OWExMDllNDA=

interface TestCaseListProps {
  testCases: TestCaseInfo[];
  loading: boolean;
  selectedIds: Set<string>;
  onSelectIds: (ids: Set<string>) => void;
  onSearch: (query: string) => void;
  // 新的筛选接口（推荐）
  onFilterChange?: (filters: TestCaseFilters) => void;
  // 旧的筛选接口（向后兼容）
  onFilterPriority?: (priority: string) => void;
  onFilterStatus?: (status: string) => void;
  onCreateTestCase: () => void;
  onEditTestCase: (testCase: TestCaseInfo) => void;
  onDeleteTestCase: (testCase: TestCaseInfo) => void;
  onBulkDelete?: () => void;
  onViewTestCase: (testCase: TestCaseInfo) => void;
  onQuickCreateTestCase?: (title: string, template: TestCaseTemplate) => void;
  onAIGenerate?: () => void;
  onAIGenerateFromDocument?: () => void;
  onOpenAIChat?: () => void;
  aiChatOpen?: boolean;
  folderName?: string;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
    onPageSizeChange?: (pageSize: number) => void;
  };
  availableTags?: string[];
  availableOwners?: string[];
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGNVFRPT06OWExMDllNDA=

const priorityColors: Record<Priority, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
};

export function TestCaseList({
  testCases,
  loading,
  selectedIds,
  onSelectIds,
  onSearch,
  onFilterChange,
  onFilterPriority,
  onFilterStatus,
  onCreateTestCase,
  onEditTestCase,
  onDeleteTestCase,
  onBulkDelete,
  onViewTestCase,
  onQuickCreateTestCase,
  onAIGenerate,
  onAIGenerateFromDocument,
  onOpenAIChat,
  aiChatOpen,
  folderName,
  pagination,
  availableTags,
  availableOwners,
}: TestCaseListProps) {
  const { t } = useLanguage();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [quickCreateTitle, setQuickCreateTitle] = React.useState("");
  const [quickCreateTemplate, setQuickCreateTemplate] = React.useState<TestCaseTemplate>("test_case");
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [localTestCases, setLocalTestCases] = React.useState<TestCaseInfo[]>(testCases);
  const [filters, setFilters] = React.useState<TestCaseFilters>({ search: "" });
  const [showQuickCreate, setShowQuickCreate] = React.useState(false);
  const [showFilterBar, setShowFilterBar] = React.useState(false);

  // 优先级标签
  const priorityLabels: Record<Priority, string> = {
    critical: t("testCases.priorityCritical"),
    high: t("testCases.priorityHigh"),
    medium: t("testCases.priorityMedium"),
    low: t("testCases.priorityLow"),
  };

  // 状态标签
  const statusLabels: Record<TestCaseState, string> = {
    new: t("testCases.statusNew"),
    review_pending: t("testCases.statusReviewPending"),
    reviewed: t("testCases.statusReviewed"),
    not_run: t("testCases.statusNotRun"),
    passed: t("testCases.statusPassed"),
    failed: t("testCases.statusFailed"),
    blocked: t("testCases.statusBlocked"),
    skipped: t("testCases.statusSkipped"),
  };

  // 初始化：将搜索值同步到筛选状态
  React.useEffect(() => {
    setFilters((prev) => ({ ...prev, search: searchQuery }));
  }, []);

  // 同步外部testCases到本地状态
  React.useEffect(() => {
    setLocalTestCases(testCases);
  }, [testCases]);

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

    setLocalTestCases((items) => {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);
      const newItems = arrayMove(items, oldIndex, newIndex);

      toast.success(t("testCases.orderUpdated"));

      return newItems;
    });
  };

  // 全选/取消全选
  const handleSelectAll = React.useCallback((checked: boolean) => {
    if (checked) {
      onSelectIds(new Set(localTestCases.map((tc) => tc.id)));
    } else {
      onSelectIds(new Set());
    }
  }, [localTestCases, onSelectIds]);

  // 单选
  const handleSelect = React.useCallback((id: string, checked: boolean) => {
    const newIds = new Set(selectedIds);
    if (checked) {
      newIds.add(id);
    } else {
      newIds.delete(id);
    }
    onSelectIds(newIds);
  }, [selectedIds, onSelectIds]);

  // 搜索
  const handleSearch = React.useCallback((e: React.FormEvent) => {
    e.preventDefault();
    onSearch(searchQuery);
  }, [searchQuery, onSearch]);

  // 搜索输入变化（实时搜索）
  const handleSearchInputChange = React.useCallback((value: string) => {
    setSearchQuery(value);
    // 延迟更新筛选，避免频繁触发API调用
    const newFilters = { ...filters, search: value };
    setFilters(newFilters);

    // 如果使用新接口，立即触发
    if (onFilterChange) {
      onFilterChange(newFilters);
    } else {
      // 如果使用旧接口，触发搜索
      onSearch(value);
    }
  }, [filters, onFilterChange, onSearch]);

  // 快速创建
  const handleQuickCreate = React.useCallback(() => {
    if (!quickCreateTitle.trim()) {
      toast.error(t("testCases.pleaseEnterTitle"));
      return;
    }
    onQuickCreateTestCase?.(quickCreateTitle.trim(), quickCreateTemplate);
    setQuickCreateTitle("");
  }, [quickCreateTitle, quickCreateTemplate, onQuickCreateTestCase, t]);

  // 筛选变化
  const handleFiltersChange = React.useCallback((newFilters: TestCaseFilters) => {
    setFilters(newFilters);

    // 更新搜索输入框
    if (newFilters.search !== searchQuery) {
      setSearchQuery(newFilters.search);
    }

    // 如果有新的筛选接口，使用它
    if (onFilterChange) {
      onFilterChange(newFilters);
    } else {
      // 否则使用旧的接口
      if (newFilters.priority !== undefined && onFilterPriority) {
        onFilterPriority(newFilters.priority);
      }
      if (newFilters.status !== undefined && onFilterStatus) {
        onFilterStatus(newFilters.status);
      }
      // 搜索变化也需要通知
      if (newFilters.search !== searchQuery) {
        onSearch(newFilters.search);
      }
    }
  }, [searchQuery, onFilterChange, onFilterPriority, onFilterStatus, onSearch]);

  const isAllSelected =
    localTestCases.length > 0 && selectedIds.size === localTestCases.length;
  const isPartialSelected =
    selectedIds.size > 0 && selectedIds.size < localTestCases.length;

  // 使用 React.memo 优化可拖动的测试用例行组件
  const DraggableTestCaseRow = React.memo(({ testCase }: { testCase: TestCaseInfo }) => {
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: testCase.id });

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
          selectedIds.has(testCase.id) && "bg-muted/30"
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
              checked={selectedIds.has(testCase.id)}
              onCheckedChange={(checked) =>
                handleSelect(testCase.id, checked as boolean)
              }
              aria-label={`选择 ${testCase.name}`}
            />
          </div>
        </td>
        <td className="p-3 overflow-hidden">
          <span className="text-sm truncate block" title={testCase.module || "-"}>
            {testCase.module || "-"}
          </span>
        </td>
        <td className="p-3 overflow-hidden">
          <span
            className="text-sm text-muted-foreground truncate block"
            title={testCase.case_number || testCase.identifier}
          >
            {testCase.case_number || testCase.identifier}
          </span>
        </td>
        <td className="p-3 overflow-hidden">
          <button
            onClick={() => onViewTestCase(testCase)}
            className="truncate text-left text-sm font-medium hover:text-primary block w-full"
          >
            {testCase.name}
          </button>
        </td>
        <td className="p-3 overflow-hidden">
          <Badge
            className={cn(
              "truncate text-white border-0",
              priorityColors[testCase.priority]
            )}
          >
            {priorityLabels[testCase.priority]}
          </Badge>
        </td>
        <td className="p-3 overflow-hidden">
          <Badge
            variant="outline"
            className="truncate"
          >
            {statusLabels[testCase.status]}
          </Badge>
        </td>
        <td className="p-3 overflow-hidden">
          <span className="text-sm truncate block">
            {testCase.owner || testCase.created_by || "-"}
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
              <DropdownMenuItem onClick={() => onViewTestCase(testCase)}>
                <FileText className="mr-2 h-4 w-4" />
                查看详情
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEditTestCase(testCase)}>
                <Pencil className="mr-2 h-4 w-4" />
                编辑
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Copy className="mr-2 h-4 w-4" />
                复制
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => onDeleteTestCase(testCase)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </td>
      </tr>
    );
  });

  DraggableTestCaseRow.displayName = "DraggableTestCaseRow";

  return (
    <div className="flex h-full flex-col">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{folderName || "全部用例"}</h2>
          <span className="text-sm text-muted-foreground">
            ({pagination ? pagination.total : testCases.length})
          </span>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={handleSearch} className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索用例... (Ctrl+K)"
              value={searchQuery}
              onChange={(e) => handleSearchInputChange(e.target.value)}
              className="w-48 pl-9"
            />
          </form>

          {/* 筛选按钮 */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilterBar(!showFilterBar)}
            className={cn(
              "gap-2",
              (filters.status || filters.priority) && "border-primary/50"
            )}
          >
            <Filter className="h-4 w-4" />
            筛选
            {showFilterBar ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
            {(filters.status || filters.priority) && (
              <Badge variant="secondary" className="ml-1 h-5 min-w-5 rounded-full px-1 text-xs">
                {(filters.status ? 1 : 0) + (filters.priority ? 1 : 0)}
              </Badge>
            )}
          </Button>

          {onAIGenerate && (
            <Button
              size="sm"
              onClick={onAIGenerate}
              className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all"
            >
              <Sparkles className="mr-2 h-4 w-4" />
              AI 生成
            </Button>
          )}
          {onAIGenerateFromDocument && (
            <Button variant="outline" size="sm" onClick={onAIGenerateFromDocument}>
              <Upload className="mr-2 h-4 w-4" />
              从文档生成
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onCreateTestCase}>
            <Plus className="mr-2 h-4 w-4" />
            新建用例
          </Button>
          {onOpenAIChat && !aiChatOpen && (
            <Button
              size="sm"
              onClick={onOpenAIChat}
              className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all"
            >
              <MessageSquare className="mr-2 h-4 w-4" />
              AI 助手
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowQuickCreate(!showQuickCreate)}
          >
            <Keyboard className="mr-2 h-4 w-4" />
            快捷
          </Button>
        </div>
      </div>

      {/* 可折叠筛选栏 */}
      {showFilterBar && (
        <div className="flex items-center gap-3 border-b bg-muted/30 px-4 py-2">
          {/* 状态筛选 */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">状态:</span>
            <Select
              value={filters.status || "all"}
              onValueChange={(value) => {
                const newStatus = value === "all" ? undefined : value as TestCaseState;
                handleFiltersChange({ ...filters, status: newStatus });
              }}
            >
              <SelectTrigger className="w-[140px] h-8">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                {/* 设计阶段 */}
                <SelectItem value="new">🆕 新建</SelectItem>
                <SelectItem value="review_pending">⏳ 待评审</SelectItem>
                <SelectItem value="reviewed">✅ 已评审</SelectItem>
                {/* 执行阶段 */}
                <SelectItem value="not_run">⚪ 未执行</SelectItem>
                <SelectItem value="passed">✅ 通过</SelectItem>
                <SelectItem value="failed">❌ 失败</SelectItem>
                <SelectItem value="blocked">🚫 阻塞</SelectItem>
                <SelectItem value="skipped">⏭️ 跳过</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 优先级筛选 */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">优先级:</span>
            <Select
              value={filters.priority || "all"}
              onValueChange={(value) => {
                const newPriority = value === "all" ? undefined : value as Priority;
                handleFiltersChange({ ...filters, priority: newPriority });
              }}
            >
              <SelectTrigger className="w-[120px] h-8">
                <SelectValue placeholder="全部优先级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部优先级</SelectItem>
                <SelectItem value="critical">
                  <div className="flex items-center gap-2">
                    <span>🔴</span>
                    <span>紧急</span>
                  </div>
                </SelectItem>
                <SelectItem value="high">
                  <div className="flex items-center gap-2">
                    <span>🟠</span>
                    <span>高</span>
                  </div>
                </SelectItem>
                <SelectItem value="medium">
                  <div className="flex items-center gap-2">
                    <span>🟡</span>
                    <span>中</span>
                  </div>
                </SelectItem>
                <SelectItem value="low">
                  <div className="flex items-center gap-2">
                    <span>🟢</span>
                    <span>低</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 高级筛选按钮 */}
          <TestCaseFilterPanel
            filters={filters}
            onFiltersChange={handleFiltersChange}
            availableTags={availableTags}
            availableOwners={availableOwners}
            showQuickFilters={false}
          />

          {/* 清除筛选 */}
          {(filters.status || filters.priority) && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => {
                handleFiltersChange({
                  ...filters,
                  status: undefined,
                  priority: undefined,
                });
              }}
            >
              清除筛选
            </Button>
          )}
        </div>
      )}

      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 border-b bg-muted/50 px-4 py-2">
          <span className="text-sm text-muted-foreground">
            已选择 {selectedIds.size} 项
          </span>
          <Button variant="outline" size="sm">
            批量编辑
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
        {loading && testCases.length === 0 ? (
          <div className="p-4">
            <table className="w-full table-fixed">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b text-left text-xs font-medium uppercase text-muted-foreground">
                  <th className="w-16 p-3"></th>
                  <th className="w-44 p-3">MODULE</th>
                  <th className="w-40 p-3">用例编号</th>
                  <th className="p-3">TITLE</th>
                  <th className="w-28 p-3">PRIORITY</th>
                  <th className="w-28 p-3">STATUS</th>
                  <th className="w-36 p-3">OWNER</th>
                  <th className="w-16 p-3"></th>
                </tr>
              </thead>
              <tbody>
                <TableRowSkeleton rows={8} />
              </tbody>
            </table>
          </div>
        ) : testCases.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 py-16">
            {/* 图标 */}
            <div className="flex h-16 w-16 items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30">
              <ClipboardList className="h-8 w-8 text-muted-foreground/50" />
            </div>

            {/* 标题和描述 */}
            <div className="text-center">
              <h3 className="text-lg font-semibold">添加测试用例</h3>
              <p className="text-sm text-muted-foreground">
                您可以通过以下方式创建测试用例
              </p>
            </div>

            {/* 快速创建输入框 */}
            {onQuickCreateTestCase && showQuickCreate && (
              <div className="flex w-full max-w-xl items-center gap-2 px-4">
                <Select
                  value={quickCreateTemplate}
                  onValueChange={(value) => setQuickCreateTemplate(value as TestCaseTemplate)}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="test_case">测试步骤</SelectItem>
                    <SelectItem value="test_case_bdd">BDD测试用例</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder="输入测试用例标题"
                  value={quickCreateTitle}
                  onChange={(e) => setQuickCreateTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleQuickCreate();
                    }
                  }}
                  className="flex-1"
                />
                <Button onClick={handleQuickCreate}>创建</Button>
              </div>
            )}

            {/* 操作按钮 */}
            <div className="flex items-center gap-3">
              {onQuickCreateTestCase && !showQuickCreate && (
                <Button variant="outline" onClick={() => setShowQuickCreate(true)}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  快速创建
                </Button>
              )}
              {onAIGenerate && (
                <Button variant="outline" onClick={onAIGenerate}>
                  <Sparkles className="mr-2 h-4 w-4" />
                AI生成
                </Button>
              )}
              {onAIGenerateFromDocument && (
                <Button variant="outline" onClick={onAIGenerateFromDocument}>
                  <Upload className="mr-2 h-4 w-4" />
                  从文档生成
                </Button>
              )}
              <Button variant="outline" onClick={() => toast.info("导入测试用例功能开发中")}>
                <Download className="mr-2 h-4 w-4" />
                导入测试用例
              </Button>
            </div>
          </div>
        ) : (
          <div className="relative">
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
                    <th className="w-44 p-3">MODULE</th>
                    <th className="w-40 p-3">用例编号</th>
                    <th className="p-3">TITLE</th>
                    <th className="w-28 p-3">PRIORITY</th>
                    <th className="w-28 p-3">STATUS</th>
                    <th className="w-36 p-3">OWNER</th>
                    <th className="w-16 p-3"></th>
                  </tr>
                </thead>
                <SortableContext
                  items={localTestCases.map((tc) => tc.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <tbody>
                    {localTestCases.map((testCase) => (
                      <DraggableTestCaseRow key={testCase.id} testCase={testCase} />
                    ))}
                  </tbody>
                </SortableContext>
              </table>

              {/* 拖动覆盖层 */}
              <DragOverlay>
                {activeId ? (
                  <div className="rounded-md bg-accent p-3 shadow-lg">
                    <span className="text-sm font-medium">
                      {localTestCases.find((tc) => tc.id === activeId)?.name}
                    </span>
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>

            {loading && (
              <div className="absolute inset-0 z-10 flex items-start justify-center bg-background/50 pt-20">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
          </div>
        )}
      </ScrollArea>

      {/* 分页 */}
      {pagination && pagination.total > 0 && (
        <div className="border-t px-4 py-3">
          <Pagination
            page={pagination.page}
            pageSize={pagination.pageSize}
            total={pagination.total}
            onPageChange={pagination.onPageChange}
            onPageSizeChange={pagination.onPageSizeChange}
            showPageSizeSelector={!!pagination.onPageSizeChange}
          />
        </div>
      )}

      {/* 快速创建栏 */}
      {onQuickCreateTestCase && showQuickCreate && testCases.length > 0 && (
        <div className="flex items-center gap-2 border-t bg-muted/30 px-4 py-3">
          <Select
            value={quickCreateTemplate}
            onValueChange={(value) => setQuickCreateTemplate(value as TestCaseTemplate)}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="test_case">测试步骤</SelectItem>
              <SelectItem value="test_case_bdd">BDD测试用例</SelectItem>
            </SelectContent>
          </Select>
          <Input
            placeholder="输入测试用例标题"
            value={quickCreateTitle}
            onChange={(e) => setQuickCreateTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleQuickCreate();
              }
            }}
            className="flex-1"
          />
          <Button onClick={handleQuickCreate}>创建</Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowQuickCreate(false)}
          >
            <Keyboard className="mr-2 h-4 w-4" />
            隐藏
          </Button>
        </div>
      )}
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGNVFRPT06OWExMDllNDA=
