/**
 * API 端点测试成果物展示面板
 *
 * 显示已生成的测试计划、测试用例和测试脚本
 * 支持查看详情和编辑测试脚本
 */
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U201QlZ3PT06YWM4ZDEzNWQ=

"use client";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U201QlZ3PT06YWM4ZDEzNWQ=

import * as React from "react";
import { useState, useEffect } from "react";
import {
  FileText,
  Code,
  ScrollText,
  Download,
  Eye,
  Edit,
  Trash2,
  Loader2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface TestArtifact {
  id: string;
  type: string;
  file_name: string;
  description: string;
  file_size: number;
  content_type: string;
  object_name: string;
  created_at: string;
  updated_at?: string;
}

interface TestArtifactsPanelProps {
  endpointId: string;
  projectId: string;
  onRefresh?: () => void;
  onTestCasesCountChange?: (count: number) => void;
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U201QlZ3PT06YWM4ZDEzNWQ=

// 成果物类型映射
const artifactTypeConfig = {
  API_TEST_PLAN: {
    icon: FileText,
    label: "测试计划",
    color: "text-blue-500",
    bgColor: "bg-blue-50 dark:bg-blue-950",
  },
  API_TEST_CASE: {
    icon: ScrollText,
    label: "测试用例",
    color: "text-green-500",
    bgColor: "bg-green-50 dark:bg-green-950",
  },
  API_TEST_SCRIPT: {
    icon: Code,
    label: "测试脚本",
    color: "text-purple-500",
    bgColor: "bg-purple-50 dark:bg-purple-950",
  },
};
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U201QlZ3PT06YWM4ZDEzNWQ=

export function TestArtifactsPanel({
  endpointId,
  projectId,
  onRefresh,
  onTestCasesCountChange,
}: TestArtifactsPanelProps) {
  const [artifacts, setArtifacts] = useState<TestArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(
    new Set(["API_TEST_PLAN", "API_TEST_CASE", "API_TEST_SCRIPT"])
  );

  // 当前查看/编辑的成果物
  const [viewingArtifact, setViewingArtifact] = useState<TestArtifact | null>(null);
  const [artifactContent, setArtifactContent] = useState<string>("");
  const [contentLoading, setContentLoading] = useState(false);

  // 加载成果物列表
  const loadArtifacts = async () => {
    try {
      setLoading(true);
      console.log('Loading artifacts for endpoint:', endpointId);
      const response = await fetch(
        `/api/v2/api-endpoints/${endpointId}/artifacts`
      );
      console.log('Response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to load artifacts:', errorText);
        throw new Error("加载测试成果物失败");
      }
      const data = await response.json();
      console.log('Artifacts data:', data);
      const artifacts = data.artifacts || [];
      setArtifacts(artifacts);

      // 查找test-cases artifact并解析测试用例数量
      const testCasesArtifact = artifacts.find((a: TestArtifact) => a.type === 'API_TEST_CASE');
      if (testCasesArtifact && onTestCasesCountChange) {
        try {
          // 读取test-cases文件内容
          console.log('Found test-cases artifact:', testCasesArtifact);
          const contentResponse = await fetch(`/api/v2/attachments/${testCasesArtifact.id}/content`);
          console.log('Content response status:', contentResponse.status);

          if (contentResponse.ok) {
            const contentData = await contentResponse.json();
            console.log('Content data type:', typeof contentData.content);
            console.log('Content data preview:', contentData.content?.substring(0, 200));

            const testCasesData = JSON.parse(contentData.content);
            console.log('Parsed testCasesData:', testCasesData);
            console.log('Is array?', Array.isArray(testCasesData));

            // 处理不同的数据格式
            let count = 0;
            if (Array.isArray(testCasesData)) {
              count = testCasesData.length;
            } else if (typeof testCasesData === 'object' && testCasesData !== null) {
              // 可能是 {test_cases: [...]} 或其他格式
              if (testCasesData.test_cases && Array.isArray(testCasesData.test_cases)) {
                count = testCasesData.test_cases.length;
              } else if (testCasesData.cases && Array.isArray(testCasesData.cases)) {
                count = testCasesData.cases.length;
              } else {
                count = Object.keys(testCasesData).length;
              }
            }

            console.log('Final test cases count:', count);
            onTestCasesCountChange(count);
          } else {
            console.error('Failed to load content:', contentResponse.status, await contentResponse.text());
          }
        } catch (error) {
          console.error('Failed to parse test cases count:', error);
        }
      }

      // 如果成功加载到成果物，通知父组件刷新数据
      if (artifacts.length > 0 && onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Failed to load artifacts:", error);
      // 不显示错误，可能是还没有生成成果物
      setArtifacts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (endpointId) {
      loadArtifacts();
    }
  }, [endpointId]);

  // 加载成果物内容
  const loadArtifactContent = async (artifact: TestArtifact) => {
    try {
      setContentLoading(true);
      const response = await fetch(
        `/api/v2/attachments/${artifact.id}/content`
      );
      if (!response.ok) {
        throw new Error("加载文件内容失败");
      }
      const data = await response.json();
      setArtifactContent(data.content || "");
      setViewingArtifact(artifact);
    } catch (error) {
      console.error("Failed to load artifact content:", error);
      toast.error("加载文件内容失败");
    } finally {
      setContentLoading(false);
    }
  };

  // 切换展开/折叠
  const toggleExpand = (type: string) => {
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  // 按类型分组成果物，每个类型内按创建时间降序排序（最新的在前）
  const groupedArtifacts = artifacts.reduce((acc, artifact) => {
    if (!acc[artifact.type]) {
      acc[artifact.type] = [];
    }
    acc[artifact.type].push(artifact);
    return acc;
  }, {} as Record<string, TestArtifact[]>);

  // 对每个分组内的 artifacts 按创建时间降序排序
  Object.keys(groupedArtifacts).forEach(type => {
    groupedArtifacts[type].sort((a, b) =>
      new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()
    );
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">加载中...</span>
      </div>
    );
  }

  if (artifacts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <FileText className="h-12 w-12 text-muted-foreground mb-3" />
        <p className="text-sm font-medium mb-1">暂无测试成果物</p>
        <p className="text-xs text-muted-foreground mb-4">
          点击上方"AI 生成测试"按钮为该接口生成测试计划、测试用例和测试脚本
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={loadArtifacts}
          className="gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          刷新
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 成果物列表 */}
      {Object.entries(groupedArtifacts).map(([type, items]) => {
        const config = artifactTypeConfig[type as keyof typeof artifactTypeConfig];
        if (!config) return null;

        const Icon = config.icon;
        const isExpanded = expandedTypes.has(type);

        return (
          <div key={type}>
            <button
              onClick={() => toggleExpand(type)}
              className="flex items-center justify-between w-full p-3 rounded-lg hover:bg-accent transition-colors"
            >
              <div className="flex items-center gap-2">
                <Icon className={cn("h-4 w-4", config.color)} />
                <span className="font-medium text-sm">{config.label}</span>
                <Badge variant="secondary" className="text-xs">
                  {items.length}
                </Badge>
              </div>
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </button>

            {isExpanded && (
              <div className="mt-2 space-y-2">
                {items.map((artifact) => (
                  <div
                    key={artifact.id}
                    className={cn(
                      "rounded-lg border p-3 hover:shadow-sm transition-all",
                      config.bgColor
                    )}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {artifact.file_name}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {artifact.description}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        {artifact.type === "API_TEST_SCRIPT" ? (
                          <>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => loadArtifactContent(artifact)}
                              title="编辑"
                            >
                              <Edit className="h-3.5 w-3.5" />
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => loadArtifactContent(artifact)}
                            title="查看"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{(artifact.file_size / 1024).toFixed(1)} KB</span>
                      <span>•</span>
                      <span>
                        {new Date(artifact.updated_at || artifact.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* 成果物内容查看器/编辑器 */}
      {viewingArtifact && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm">
          <div className="fixed inset-y-0 right-0 w-[600px] bg-background border-l shadow-xl">
            <div className="flex flex-col h-full">
              {/* 头部 */}
              <div className="flex items-center justify-between border-b p-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate">
                    {viewingArtifact.file_name}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {viewingArtifact.description}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    setViewingArtifact(null);
                    setArtifactContent("");
                  }}
                >
                  ✕
                </Button>
              </div>

              {/* 内容区域 */}
              <ScrollArea className="flex-1">
                <div className="p-4">
                  {contentLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin" />
                    </div>
                  ) : (
                    <pre className="text-xs bg-muted p-4 rounded-lg overflow-x-auto">
                      <code>{artifactContent}</code>
                    </pre>
                  )}
                </div>
              </ScrollArea>

              {/* 底部操作栏 */}
              <div className="flex items-center justify-between border-t p-4">
                <Button variant="outline" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  下载
                </Button>
                {viewingArtifact.type === "API_TEST_SCRIPT" && (
                  <Button size="sm">
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    保存修改
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
