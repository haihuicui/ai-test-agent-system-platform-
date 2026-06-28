"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkcwM1RBPT06NDllMmU4MDg=

import * as React from "react";
import { X, FileText, Play, Sparkles, Smartphone, Tag, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { getAndroidSubFunction, type AndroidSubFunction } from "@/lib/api/android-tests";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkcwM1RBPT06NDllMmU4MDg=

interface AndroidSubFunctionSidebarProps {
  subFunctionId: string;
  projectId: string;
  onClose: () => void;
  onGenerateTest: () => void;
  onOpenAIChat: (prompt: string) => void;
  onRefresh?: () => void;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkcwM1RBPT06NDllMmU4MDg=

export function AndroidSubFunctionSidebar({
  subFunctionId,
  projectId,
  onClose,
  onGenerateTest,
  onOpenAIChat,
}: AndroidSubFunctionSidebarProps) {
  const [subFunction, setSubFunction] = React.useState<AndroidSubFunction | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const loadSubFunction = async () => {
      try {
        setLoading(true);
        const data = await getAndroidSubFunction(projectId, subFunctionId);
        setSubFunction(data);
      } catch (error) {
        console.error("Failed to load sub-function:", error);
      } finally {
        setLoading(false);
      }
    };
    if (subFunctionId && projectId) loadSubFunction();
  }, [subFunctionId, projectId]);

  if (loading) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b p-4">
          <h3 className="font-semibold">加载中...</h3>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <div className="flex-1 flex items-center justify-center text-muted-foreground">加载子功能详情...</div>
      </div>
    );
  }

  if (!subFunction) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b p-4">
          <h3 className="font-semibold">未找到</h3>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <div className="flex-1 flex items-center justify-center text-muted-foreground">未找到子功能信息</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center justify-between border-b p-4">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-green-500" />
          <h3 className="font-semibold truncate">{subFunction.display_name}</h3>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}><X className="h-4 w-4" /></Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* 基本信息 */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground">基本信息</h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">标识符</span>
                <Badge variant="outline" className="text-xs">{subFunction.identifier}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">测试类型</span>
                <Badge className={cn("text-xs",
                  subFunction.test_type === "functional" ? "bg-green-500 text-white" :
                  subFunction.test_type === "validation" ? "bg-blue-500 text-white" :
                  subFunction.test_type === "ui" ? "bg-purple-500 text-white" :
                  "bg-gray-500 text-white"
                )}>{subFunction.test_type}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">优先级</span>
                <Badge className={cn("text-xs",
                  subFunction.priority === "critical" ? "bg-red-500 text-white" :
                  subFunction.priority === "high" ? "bg-orange-500 text-white" :
                  subFunction.priority === "medium" ? "bg-yellow-500 text-white" :
                  "bg-gray-500 text-white"
                )}>{subFunction.priority}</Badge>
              </div>
            </div>
          </div>

          <Separator />

          {/* 描述 */}
          {subFunction.description && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">描述</h4>
              <p className="text-sm">{subFunction.description}</p>
            </div>
          )}

          {/* 测试场景 */}
          {subFunction.test_scenario && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">测试场景</h4>
              <div className="rounded-lg bg-muted/50 p-3">
                <p className="text-sm whitespace-pre-wrap">{subFunction.test_scenario}</p>
              </div>
            </div>
          )}

          <Separator />

          {/* 统计信息 */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground">统计信息</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border p-3 text-center">
                <FileText className="h-4 w-4 text-green-500 mx-auto mb-1" />
                <div className="text-lg font-semibold">{subFunction.total_test_cases}</div>
                <div className="text-xs text-muted-foreground">测试用例</div>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <Play className="h-4 w-4 text-blue-500 mx-auto mb-1" />
                <div className="text-lg font-semibold">{subFunction.total_test_runs}</div>
                <div className="text-xs text-muted-foreground">测试运行</div>
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="space-y-2">
            <Button className="w-full bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white" onClick={onGenerateTest}>
              <Sparkles className="mr-2 h-4 w-4" />AI 生成测试
            </Button>
            <Button variant="outline" className="w-full" onClick={() => onOpenAIChat(`请为 Android 子功能 "${subFunction.display_name}" 生成测试`)}>
              <Smartphone className="mr-2 h-4 w-4" />打开 AI 助手
            </Button>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkcwM1RBPT06NDllMmU4MDg=
