"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  FileText,
  Download,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVRabVZ3PT06MWNkMGI0NzY=

// 模拟统计数据
const mockStats = {
  totalTestCases: 156,
  totalTestRuns: 12,
  passRate: 85.5,
  passRateTrend: 2.3,
  avgExecutionTime: "2.5h",
  executionTimeTrend: -0.5,
  openDefects: 8,
  defectsTrend: -3,
};
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVRabVZ3PT06MWNkMGI0NzY=

const mockTestRunStats = [
  { name: "回归测试 - Sprint 23", passed: 45, failed: 3, skipped: 2, total: 50 },
  { name: "冒烟测试 - v2.1.0", passed: 18, failed: 2, skipped: 0, total: 20 },
  { name: "功能测试 - 用户模块", passed: 30, failed: 5, skipped: 0, total: 35 },
  { name: "API 测试", passed: 25, failed: 0, skipped: 1, total: 26 },
];

const mockPriorityStats = [
  { priority: "紧急", count: 12, percentage: 8 },
  { priority: "高", count: 45, percentage: 29 },
  { priority: "中", count: 78, percentage: 50 },
  { priority: "低", count: 21, percentage: 13 },
];

const mockTypeStats = [
  { type: "功能测试", count: 80 },
  { type: "回归测试", count: 35 },
  { type: "冒烟测试", count: 20 },
  { type: "集成测试", count: 15 },
  { type: "其他", count: 6 },
];
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVRabVZ3PT06MWNkMGI0NzY=

export default function ReportsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [dateRange, setDateRange] = React.useState("7d");

  return (
    <MainLayout title="报告">
      <div className="space-y-6">
        {/* 工具栏 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">最近 7 天</SelectItem>
                <SelectItem value="30d">最近 30 天</SelectItem>
                <SelectItem value="90d">最近 90 天</SelectItem>
                <SelectItem value="all">全部时间</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            导出报告
          </Button>
        </div>

        {/* 概览卡片 */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">测试用例总数</span>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="mt-2 text-2xl font-bold">
              {mockStats.totalTestCases}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {mockStats.totalTestRuns} 个测试运行
            </div>
          </div>

          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">通过率</span>
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold">{mockStats.passRate}%</span>
              <span className="flex items-center text-xs text-green-500">
                <TrendingUp className="h-3 w-3" />
                {mockStats.passRateTrend}%
              </span>
            </div>
            <Progress value={mockStats.passRate} className="mt-2" />
          </div>

          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">平均执行时间</span>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold">
                {mockStats.avgExecutionTime}
              </span>
              <span className="flex items-center text-xs text-green-500">
                <TrendingDown className="h-3 w-3" />
                {Math.abs(mockStats.executionTimeTrend)}h
              </span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              较上周减少
            </div>
          </div>

          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">待处理缺陷</span>
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold">{mockStats.openDefects}</span>
              <span className="flex items-center text-xs text-green-500">
                <TrendingDown className="h-3 w-3" />
                {Math.abs(mockStats.defectsTrend)}
              </span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              较上周减少
            </div>
          </div>
        </div>

        {/* 详细报告 */}
        <Tabs defaultValue="runs" className="space-y-4">
          <TabsList>
            <TabsTrigger value="runs">测试运行统计</TabsTrigger>
            <TabsTrigger value="priority">优先级分布</TabsTrigger>
            <TabsTrigger value="type">类型分布</TabsTrigger>
          </TabsList>

          <TabsContent value="runs" className="space-y-4">
            <div className="rounded-lg border bg-card">
              <div className="border-b p-4">
                <h3 className="font-medium">测试运行结果</h3>
              </div>
              <div className="divide-y">
                {mockTestRunStats.map((run, index) => (
                  <div key={index} className="flex items-center gap-4 p-4">
                    <div className="flex-1">
                      <div className="font-medium">{run.name}</div>
                      <div className="mt-1 flex items-center gap-4 text-sm">
                        <span className="flex items-center gap-1 text-green-600">
                          <CheckCircle2 className="h-4 w-4" />
                          {run.passed} 通过
                        </span>
                        <span className="flex items-center gap-1 text-red-600">
                          <XCircle className="h-4 w-4" />
                          {run.failed} 失败
                        </span>
                        <span className="text-muted-foreground">
                          共 {run.total} 个用例
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Progress
                        value={(run.passed / run.total) * 100}
                        className="w-32"
                      />
                      <span className="w-12 text-right text-sm">
                        {Math.round((run.passed / run.total) * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="priority" className="space-y-4">
            <div className="rounded-lg border bg-card">
              <div className="border-b p-4">
                <h3 className="font-medium">用例优先级分布</h3>
              </div>
              <div className="p-4">
                <div className="space-y-4">
                  {mockPriorityStats.map((item, index) => (
                    <div key={index} className="flex items-center gap-4">
                      <div className="w-16 text-sm font-medium">
                        {item.priority}
                      </div>
                      <div className="flex-1">
                        <Progress value={item.percentage} />
                      </div>
                      <div className="w-20 text-right text-sm text-muted-foreground">
                        {item.count} ({item.percentage}%)
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="type" className="space-y-4">
            <div className="rounded-lg border bg-card">
              <div className="border-b p-4">
                <h3 className="font-medium">用例类型分布</h3>
              </div>
              <div className="grid gap-4 p-4 md:grid-cols-2 lg:grid-cols-3">
                {mockTypeStats.map((item, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <span className="font-medium">{item.type}</span>
                    <Badge variant="secondary">{item.count}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  );
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVRabVZ3PT06MWNkMGI0NzY=

