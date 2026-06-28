import * as React from "react";
import { X, Filter, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { Priority, TestCaseState } from "@/lib/api/types";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW0xa053PT06Njg4NGIyNjk=

const priorityColors: Record<Priority, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
};

export interface TestCaseFilters {
  search: string;
  priority?: Priority;
  status?: TestCaseState;
  tags?: string[];
  owner?: string;
}
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW0xa053PT06Njg4NGIyNjk=

interface TestCaseFilterPanelProps {
  /**
   * 当前筛选条件
   */
  filters: TestCaseFilters;
  /**
   * 筛选变化回调
   */
  onFiltersChange: (filters: TestCaseFilters) => void;
  /**
   * 可用的标签列表
   */
  availableTags?: string[];
  /**
   * 可用的负责人列表
   */
  availableOwners?: string[];
  /**
   * 是否显示快捷筛选栏
   * @default true
   */
  showQuickFilters?: boolean;
}

const priorityOptions: { value: Priority; label: string; icon: string }[] = [
  { value: "critical", label: "紧急", icon: "🔴" },
  { value: "high", label: "高", icon: "🟠" },
  { value: "medium", label: "中", icon: "🟡" },
  { value: "low", label: "低", icon: "🟢" },
];
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW0xa053PT06Njg4NGIyNjk=

const statusOptions: { value: TestCaseState; label: string }[] = [
  // 设计阶段
  { value: "new", label: "🆕 新建" },
  { value: "review_pending", label: "⏳ 待评审" },
  { value: "reviewed", label: "✅ 已评审" },
  // 执行阶段
  { value: "not_run", label: "⚪ 未执行" },
  { value: "passed", label: "✅ 通过" },
  { value: "failed", label: "❌ 失败" },
  { value: "blocked", label: "🚫 阻塞" },
  { value: "skipped", label: "⏭️ 跳过" },
];

/**
 * 获取活跃筛选数量
 */
function getActiveFilterCount(filters: TestCaseFilters): number {
  let count = 0;
  if (filters.search) count++;
  if (filters.priority) count++;
  if (filters.status) count++;
  if (filters.tags && filters.tags.length > 0) count++;
  if (filters.owner) count++;
  return count;
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW0xa053PT06Njg4NGIyNjk=

export function TestCaseFilterPanel({
  filters,
  onFiltersChange,
  availableTags = [],
  availableOwners = [],
  showQuickFilters = true,
}: TestCaseFilterPanelProps) {
  const [open, setOpen] = React.useState(false);
  const [localFilters, setLocalFilters] = React.useState<TestCaseFilters>(filters);

  // 同步外部 filters 到本地
  React.useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  const activeFilterCount = getActiveFilterCount(filters);

  const handleApply = () => {
    onFiltersChange(localFilters);
    setOpen(false);
  };

  const handleReset = () => {
    const resetFilters: TestCaseFilters = {
      search: localFilters.search, // 保留搜索词
    };
    setLocalFilters(resetFilters);
    onFiltersChange(resetFilters);
  };

  const handleClearSearch = () => {
    const newFilters = { ...localFilters, search: "" };
    setLocalFilters(newFilters);
    onFiltersChange(newFilters);
  };

  const toggleTag = (tag: string) => {
    const tags = localFilters.tags || [];
    const newTags = tags.includes(tag)
      ? tags.filter((t) => t !== tag)
      : [...tags, tag];
    setLocalFilters({ ...localFilters, tags: newTags.length > 0 ? newTags : undefined });
  };

  return (
    <>
      {/* 快捷筛选栏 - 只显示优先级筛选 */}
      {showQuickFilters && (
        <div className="flex items-center gap-2 border-b px-4 py-2">
          <div className="flex items-center gap-2">
            <Select
              value={filters.priority || "all"}
              onValueChange={(value) => {
                const newPriority = value === "all" ? undefined : value as Priority;
                onFiltersChange({ ...filters, priority: newPriority });
              }}
            >
              <SelectTrigger className="w-[120px] h-8">
                <SelectValue placeholder="全部优先级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部优先级</SelectItem>
                {priorityOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <div className="flex items-center gap-2">
                      <span>{option.icon}</span>
                      <span>{option.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {activeFilterCount > 0 && (
            <>
              <Separator orientation="vertical" className="h-6" />
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={handleReset}
              >
                <RotateCcw className="mr-1 h-3 w-3" />
                清除筛选
              </Button>
            </>
          )}
        </div>
      )}

      {/* 高级筛选弹出框 */}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="relative">
            <Filter className="mr-2 h-4 w-4" />
            高级筛选
            {activeFilterCount > 0 && (
              <Badge
                variant="secondary"
                className="ml-2 h-5 min-w-5 rounded-full px-1 text-center text-xs"
              >
                {activeFilterCount}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80" align="end">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold">高级筛选</h4>
              <Button variant="ghost" size="sm" className="h-8" onClick={handleReset}>
                重置
              </Button>
            </div>

            <Separator />

            {/* 搜索关键词 */}
            <div className="space-y-2">
              <label className="text-sm font-medium">搜索关键词</label>
              <div className="relative">
                <Input
                  placeholder="输入搜索关键词..."
                  value={localFilters.search}
                  onChange={(e) =>
                    setLocalFilters({ ...localFilters, search: e.target.value })
                  }
                />
                {localFilters.search && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full px-2"
                    onClick={() => setLocalFilters({ ...localFilters, search: "" })}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>

            {/* 优先级 */}
            <div className="space-y-2">
              <label className="text-sm font-medium">优先级</label>
              <Select
                value={localFilters.priority || "all"}
                onValueChange={(value) =>
                  setLocalFilters({
                    ...localFilters,
                    priority: value === "all" ? undefined : (value as Priority),
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择优先级" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  {priorityOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      <div className="flex items-center gap-2">
                        <span>{option.icon}</span>
                        <span>{option.label}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 状态 */}
            <div className="space-y-2">
              <label className="text-sm font-medium">状态</label>
              <Select
                value={localFilters.status || "all"}
                onValueChange={(value) =>
                  setLocalFilters({
                    ...localFilters,
                    status: value === "all" ? undefined : (value as TestCaseState),
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 标签 */}
            {availableTags.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">标签</label>
                <div className="flex flex-wrap gap-2">
                  {availableTags.map((tag) => (
                    <Badge
                      key={tag}
                      variant={
                        localFilters.tags?.includes(tag) ? "default" : "outline"
                      }
                      className="cursor-pointer transition-colors"
                      onClick={() => toggleTag(tag)}
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* 负责人 */}
            {availableOwners.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">负责人</label>
                <Select
                  value={localFilters.owner || "all"}
                  onValueChange={(value) =>
                    setLocalFilters({
                      ...localFilters,
                      owner: value === "all" ? undefined : value,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择负责人" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    {availableOwners.map((owner) => (
                      <SelectItem key={owner} value={owner}>
                        {owner}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <Separator />

            {/* 操作按钮 */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setLocalFilters(filters);
                  setOpen(false);
                }}
              >
                取消
              </Button>
              <Button className="flex-1" onClick={handleApply}>
                应用筛选
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </>
  );
}
