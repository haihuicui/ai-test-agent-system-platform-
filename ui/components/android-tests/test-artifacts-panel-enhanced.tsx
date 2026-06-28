"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG1GVWR3PT06MmU2YjRmZmM=

import * as React from "react";
import {
  FileText,
  Code,
  Play,
  Download,
  FileCode,
  CheckCircle,
  XCircle,
  Clock,
  Smartphone,
  Zap,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG1GVWR3PT06MmU2YjRmZmM=

// 简化的测试成果物面板，用于 Android 测试
interface EnhancedTestArtifactsPanelProps {
  subFunctionId: string;
  projectId: string;
  onRefresh?: () => void;
  onTestCasesCountChange?: (count: number, subFunctionId?: string) => void;
  onExecuteScript?: (artifactId: string, fileName: string) => void;
  refreshTrigger?: number;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG1GVWR3PT06MmU2YjRmZmM=

interface TestArtifact {
  id: string;
  name: string;
  type: "plan" | "case" | "script" | "report";
  status: "pending" | "generating" | "completed" | "failed";
  created_at: string;
  content?: string;
  file_path?: string;
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG1GVWR3PT06MmU2YjRmZmM=

export function EnhancedTestArtifactsPanel({
  subFunctionId,
  projectId,
  onExecuteScript,
  refreshTrigger,
}: EnhancedTestArtifactsPanelProps) {
  const [artifacts, setArtifacts] = React.useState<TestArtifact[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [activeTab, setActiveTab] = React.useState("all");

  const loadArtifacts = React.useCallback(async () => {
    try {
      setLoading(true);
      // 模拟加载数据，实际项目中应该从 API 获取
      // 这里使用 setTimeout 模拟 API 调用
      await new Promise((resolve) => setTimeout(resolve, 500));

      // 生成模拟数据
      const mockArtifacts: TestArtifact[] = [
        {
          id: `plan-${subFunctionId}`,
          name: "测试计划",
          type: "plan",
          status: "completed",
          created_at: new Date().toISOString(),
        },
        {
          id: `cases-${subFunctionId}`,
          name: "测试用例集",
          type: "case",
          status: "completed",
          created_at: new Date().toISOString(),
        },
        {
          id: `script-${subFunctionId}`,
          name: "测试脚本",
          type: "script",
          status: "completed",
          created_at: new Date().toISOString(),
        },
      ];

      setArtifacts(mockArtifacts);
    } catch (error) {
      console.error("Failed to load artifacts:", error);
      toast.error("加载测试成果物失败");
    } finally {
      setLoading(false);
    }
  }, [subFunctionId, projectId]);

  React.useEffect(() => {
    if (subFunctionId) {
      loadArtifacts();
    }
  }, [subFunctionId, projectId, loadArtifacts, refreshTrigger]);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "plan":
        return <FileText className="h-4 w-4 text-blue-500" />;
      case "case":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "script":
        return <Code className="h-4 w-4 text-purple-500" />;
      case "report":
        return <Zap className="h-4 w-4 text-orange-500" />;
      default:
        return <FileCode className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case "plan":
        return "测试计划";
      case "case":
        return "测试用例";
      case "script":
        return "测试脚本";
      case "report":
        return "测试报告";
      default:
        return "未知";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "generating":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const filteredArtifacts =
    activeTab === "all"
      ? artifacts
      : artifacts.filter((a) => a.type === activeTab);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>加载测试成果物...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="all">全部</TabsTrigger>
          <TabsTrigger value="plan">测试计划</TabsTrigger>
          <TabsTrigger value="case">测试用例</TabsTrigger>
          <TabsTrigger value="script">测试脚本</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          {filteredArtifacts.length === 0 ? (
            <div className="text-center py-8 border-2 border-dashed rounded-lg bg-muted/10">
              <FileCode className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">暂无测试成果物</p>
              <p className="text-xs text-muted-foreground mt-1">
                使用 AI 助手生成测试后将显示在此处
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredArtifacts.map((artifact) => (
                <Card
                  key={artifact.id}
                  className="hover:shadow-md transition-shadow"
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getTypeIcon(artifact.type)}
                        <CardTitle className="text-base">
                          {artifact.name}
                        </CardTitle>
                        <Badge variant="outline" className="text-xs">
                          {getTypeLabel(artifact.type)}
                        </Badge>
                      </div>
                      {getStatusIcon(artifact.status)}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-muted-foreground">
                        创建于{" "}
                        {new Date(artifact.created_at).toLocaleString("zh-CN")}
                      </div>
                      <div className="flex items-center gap-2">
                        {artifact.type === "script" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              onExecuteScript?.(
                                artifact.id,
                                `${artifact.name}.ts`
                              )
                            }
                          >
                            <Play className="mr-1 h-3 w-3" />
                            执行
                          </Button>
                        )}
                        <Button variant="ghost" size="sm">
                          <Download className="mr-1 h-3 w-3" />
                          下载
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
