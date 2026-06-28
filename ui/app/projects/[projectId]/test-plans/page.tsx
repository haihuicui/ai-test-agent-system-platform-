"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjFobE5nPT06YzEyNjMzMjg=

import * as React from "react";
import { useParams } from "next/navigation";
import {
  Plus,
  Search,
  ClipboardList,
  Calendar,
  MoreHorizontal,
  Pencil,
  Trash2,
  Eye,
  PlayCircle,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjFobE5nPT06YzEyNjMzMjg=

// 模拟数据
const mockTestPlans = [
  {
    id: "1",
    name: "Sprint 23 测试计划",
    description: "Sprint 23 迭代的完整测试计划",
    start_date: "2024-01-15",
    end_date: "2024-01-29",
    created_at: "2024-01-10T10:00:00Z",
    test_runs: [
      { id: "1", name: "回归测试", state: "in_progress" },
      { id: "2", name: "冒烟测试", state: "completed" },
    ],
  },
  {
    id: "2",
    name: "v2.1.0 发布测试计划",
    description: "v2.1.0 版本发布前的测试计划",
    start_date: "2024-01-08",
    end_date: "2024-01-12",
    created_at: "2024-01-05T09:00:00Z",
    test_runs: [
      { id: "3", name: "功能测试", state: "completed" },
      { id: "4", name: "性能测试", state: "completed" },
      { id: "5", name: "安全测试", state: "completed" },
    ],
  },
  {
    id: "3",
    name: "用户模块测试计划",
    description: "用户模块的专项测试计划",
    start_date: "2024-02-01",
    end_date: "2024-02-15",
    created_at: "2024-01-20T14:00:00Z",
    test_runs: [],
  },
];
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjFobE5nPT06YzEyNjMzMjg=

export default function TestPlansPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [testPlans, setTestPlans] = React.useState(mockTestPlans);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [formData, setFormData] = React.useState({
    name: "",
    description: "",
    start_date: "",
    end_date: "",
  });

  const filteredPlans = React.useMemo(() => {
    if (!searchQuery) return testPlans;
    const query = searchQuery.toLowerCase();
    return testPlans.filter(
      (plan) =>
        plan.name.toLowerCase().includes(query) ||
        plan.description?.toLowerCase().includes(query)
    );
  }, [testPlans, searchQuery]);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("zh-CN");
  };

  return (
    <MainLayout title="测试计划">
      <div className="space-y-6">
        {/* 工具栏 */}
        <div className="flex items-center justify-between">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索测试计划..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 pl-9"
            />
          </div>
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            新建测试计划
          </Button>
        </div>

        {/* 测试计划列表 */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredPlans.length === 0 ? (
            <div className="col-span-full flex h-64 flex-col items-center justify-center gap-2 rounded-lg border bg-card">
              <ClipboardList className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">
                {searchQuery ? "没有找到匹配的测试计划" : "暂无测试计划"}
              </p>
            </div>
          ) : (
            filteredPlans.map((plan) => (
              <div
                key={plan.id}
                className="rounded-lg border bg-card p-4 transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <ClipboardList className="h-5 w-5 text-primary" />
                    <h3 className="font-medium">{plan.name}</h3>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>
                        <Eye className="mr-2 h-4 w-4" />
                        查看
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Pencil className="mr-2 h-4 w-4" />
                        编辑
                      </DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive">
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                  {plan.description || "暂无描述"}
                </p>

                <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>
                    {formatDate(plan.start_date)} - {formatDate(plan.end_date)}
                  </span>
                </div>

                <div className="mt-4 border-t pt-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      测试运行
                    </span>
                    <Badge variant="secondary">
                      {plan.test_runs.length} 个
                    </Badge>
                  </div>
                  {plan.test_runs.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {plan.test_runs.slice(0, 3).map((run) => (
                        <div
                          key={run.id}
                          className="flex items-center gap-2 text-sm"
                        >
                          <PlayCircle className="h-3 w-3" />
                          <span className="truncate">{run.name}</span>
                          <Badge
                            variant={
                              run.state === "completed"
                                ? "default"
                                : "secondary"
                            }
                            className="ml-auto text-xs"
                          >
                            {run.state === "completed" ? "已完成" : "进行中"}
                          </Badge>
                        </div>
                      ))}
                      {plan.test_runs.length > 3 && (
                        <div className="text-xs text-muted-foreground">
                          还有 {plan.test_runs.length - 3} 个测试运行...
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 创建对话框 */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建测试计划</DialogTitle>
            <DialogDescription>创建一个新的测试计划</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">名称</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="请输入测试计划名称"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">描述</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="请输入描述（可选）"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_date">开始日期</Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) =>
                    setFormData({ ...formData, start_date: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_date">结束日期</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) =>
                    setFormData({ ...formData, end_date: e.target.value })
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={() => setCreateDialogOpen(false)}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjFobE5nPT06YzEyNjMzMjg=

