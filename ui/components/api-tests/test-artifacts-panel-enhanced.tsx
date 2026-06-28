/**
 * 增强版 API 端点测试成果物展示面板
 *
 * 支持默认显示、代码编辑和执行功能
 */
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdSaVFRPT06ZGI0NjBkNDk=

"use client";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdSaVFRPT06ZGI0NjBkNDk=

import * as React from "react";
import { useState, useEffect } from "react";
import {
  FileText,
  Code,
  ScrollText,
  Download,
  Eye,
  Edit,
  Play,
  Loader2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Save,
  Terminal,
  Clock,
  FileCode,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { MonacoCodeEditor } from "@/components/editor/MonacoCodeEditor";

interface TestArtifact {
  id: string;
  type: string;
  file_name: string;
  description: string;
  file_size: number;
  content_type: string;
  object_name: string;
  created_at: string;
}

interface EnhancedTestArtifactsPanelProps {
  endpointId: string;
  projectId: string;
  onRefresh?: () => void;
  onTestCasesCountChange?: (count: number, endpointId?: string) => void;
  onExecuteScript?: (artifactId: string, fileName: string) => void; // 新增：执行脚本回调（只传递 ID 和文件名）
  refreshTrigger?: number; // 新增：刷新触发器，当这个值变化时重新加载数据
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdSaVFRPT06ZGI0NjBkNDk=

// 成果物类型映射
const artifactTypeConfig = {
  API_TEST_PLAN: {
    icon: FileText,
    label: "测试计划",
    color: "text-blue-500",
    bgColor: "bg-blue-50 dark:bg-blue-950",
    borderColor: "border-blue-200 dark:border-blue-800",
  },
  API_TEST_CASE: {
    icon: ScrollText,
    label: "测试用例",
    color: "text-green-500",
    bgColor: "bg-green-50 dark:bg-green-950",
    borderColor: "border-green-200 dark:border-green-800",
  },
  API_TEST_SCRIPT: {
    icon: Code,
    label: "测试脚本",
    color: "text-purple-500",
    bgColor: "bg-purple-50 dark:bg-purple-950",
    borderColor: "border-purple-200 dark:border-purple-800",
  },
  API_TEST_RESULT: {
    icon: CheckCircle2,
    label: "执行结果",
    color: "text-orange-500",
    bgColor: "bg-orange-50 dark:bg-orange-950",
    borderColor: "border-orange-200 dark:border-orange-800",
  },
  API_TEST_REPORT: {
    icon: FileCode,
    label: "测试报告",
    color: "text-pink-500",
    bgColor: "bg-pink-50 dark:bg-pink-950",
    borderColor: "border-pink-200 dark:border-pink-800",
  },
};

export function EnhancedTestArtifactsPanel({
  endpointId,
  projectId,
  onRefresh,
  onTestCasesCountChange,
  onExecuteScript,
  refreshTrigger,
}: EnhancedTestArtifactsPanelProps) {
  const [artifacts, setArtifacts] = useState<TestArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(
    new Set(["API_TEST_PLAN", "API_TEST_CASE", "API_TEST_SCRIPT", "API_TEST_RESULT", "API_TEST_REPORT"])
  );

  // 编辑状态
  const [editingArtifact, setEditingArtifact] = useState<TestArtifact | null>(null);
  const [scriptContent, setScriptContent] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [loadingScript, setLoadingScript] = useState(false);

  // 执行结果状态
  const [executionResult, setExecutionResult] = useState<{
    status: 'success' | 'error' | 'running' | null;
    output: string;
    duration?: number;
  }>({ status: null, output: '' });

  // 加载成果物列表
  const loadArtifacts = async () => {
    try {
      setLoading(true);
      console.log('[Enhanced Panel] ===== Loading artifacts for endpoint =====');
      console.log('[Enhanced Panel] Endpoint ID:', endpointId);
      console.log('[Enhanced Panel] Project ID:', projectId);

      const apiUrl = `/api/v2/api-endpoints/${endpointId}/artifacts`;
      console.log('[Enhanced Panel] Fetching from:', apiUrl);

      const response = await fetch(apiUrl);
      console.log('[Enhanced Panel] Response status:', response.status);
      console.log('[Enhanced Panel] Response OK:', response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[Enhanced Panel] Failed to load artifacts. Status:', response.status);
        console.error('[Enhanced Panel] Error response:', errorText);
        toast.error(`加载测试成果物失败 (${response.status})`);
        setArtifacts([]);
        return;
      }

      const data = await response.json();
      console.log('[Enhanced Panel] Response data keys:', Object.keys(data));
      console.log('[Enhanced Panel] Full response data:', data);

      const artifacts = data.artifacts || [];
      console.log('[Enhanced Panel] Total artifacts found:', artifacts.length);
      console.log('[Enhanced Panel] Artifacts:', artifacts);

      if (artifacts.length > 0) {
        console.log('[Enhanced Panel] Artifact types:', artifacts.map((a: any) => a.type));
      }

      setArtifacts(artifacts);

      // 查找test-cases artifact并解析测试用例数量
      const testCasesArtifact = artifacts.find((a: TestArtifact) => a.type === 'API_TEST_CASE');
      if (testCasesArtifact) {
        console.log('[Enhanced Panel] Found test-cases artifact:', testCasesArtifact);

        if (onTestCasesCountChange) {
          try {
            const contentResponse = await fetch(`/api/v2/attachments/${testCasesArtifact.id}/content`);
            console.log('[Enhanced Panel] Content response status:', contentResponse.status);

            if (contentResponse.ok) {
              const contentData = await contentResponse.json();
              console.log('[Enhanced Panel] Content data type:', typeof contentData.content);
              console.log('[Enhanced Panel] Content preview:', contentData.content?.substring(0, 300));

              const testCasesData = JSON.parse(contentData.content);
              console.log('[Enhanced Panel] Parsed testCasesData type:', typeof testCasesData);
              console.log('[Enhanced Panel] Is array?', Array.isArray(testCasesData));

              // 处理不同的数据格式
              let count = 0;
              if (Array.isArray(testCasesData)) {
                count = testCasesData.length;
              } else if (typeof testCasesData === 'object' && testCasesData !== null) {
                if (testCasesData.test_cases && Array.isArray(testCasesData.test_cases)) {
                  count = testCasesData.test_cases.length;
                } else if (testCasesData.cases && Array.isArray(testCasesData.cases)) {
                  count = testCasesData.cases.length;
                } else {
                  count = Object.keys(testCasesData).length;
                }
              }

              console.log('[Enhanced Panel] Final test cases count:', count);
              onTestCasesCountChange(count, endpointId);
            } else {
              console.error('[Enhanced Panel] Failed to load content:', contentResponse.status);
            }
          } catch (error) {
            console.error('[Enhanced Panel] Failed to parse test cases count:', error);
          }
        }
      }

      if (artifacts.length > 0 && onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("[Enhanced Panel] Failed to load artifacts:", error);
      setArtifacts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (endpointId) {
      console.log('[Enhanced Panel] Loading artifacts for endpoint:', endpointId);
      loadArtifacts();
    }
  }, [endpointId, refreshTrigger]); // 添加 refreshTrigger 依赖

  // 加载脚本内容
  const loadScriptContent = async (artifact: TestArtifact) => {
    try {
      // 立即打开弹窗并显示loading
      setEditingArtifact(artifact);
      setScriptContent(""); // 清空之前的内容
      setLoadingScript(true);

      console.log('[Enhanced Panel] Loading script content for artifact:', artifact.id);

      const response = await fetch(`/api/v2/attachments/${artifact.id}/content`);
      console.log('[Enhanced Panel] Script content response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[Enhanced Panel] Failed to load script:', errorText);
        toast.error("加载脚本内容失败");
        setEditingArtifact(null); // 关闭弹窗
        return;
      }

      const data = await response.json();
      console.log('[Enhanced Panel] Script content loaded, length:', data.content?.length);
      console.log('[Enhanced Panel] Script content preview:', data.content?.substring(0, 200));

      setScriptContent(data.content || "");
    } catch (error) {
      console.error('[Enhanced Panel] Failed to load script content:', error);
      toast.error("加载脚本内容失败");
      setEditingArtifact(null); // 关闭弹窗
    } finally {
      setLoadingScript(false);
    }
  };

  // 保存脚本
  const saveScript = async () => {
    if (!editingArtifact) return;

    try {
      setSaving(true);
      const response = await fetch(`/api/v2/attachments/${editingArtifact.id}/content`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: scriptContent }),
      });

      if (!response.ok) {
        throw new Error("保存脚本失败");
      }

      toast.success("脚本保存成功");
      setEditingArtifact(null);
    } catch (error) {
      console.error("Failed to save script:", error);
      toast.error("保存脚本失败");
    } finally {
      setSaving(false);
    }
  };

  // 执行脚本 - 打开 AI 对话助手
  const executeScript = async (artifact?: TestArtifact) => {
    const targetArtifact = artifact || editingArtifact;

    if (!targetArtifact) {
      console.error('[测试成果物] 没有找到目标 artifact');
      return;
    }

    // 如果提供了执行回调，调用它打开 AI 对话助手
    if (onExecuteScript) {
      console.log('[测试成果物] 打开 AI 助手执行脚本');
      console.log('[测试成果物] Artifact ID:', targetArtifact.id);
      console.log('[测试成果物] Artifact 文件名:', targetArtifact.file_name);
      console.log('[测试成果物] Artifact 完整对象:', targetArtifact);
      // 只传递脚本 ID 和文件名，后端会自己下载和执行
      onExecuteScript(targetArtifact.id, targetArtifact.file_name);
      // 关闭编辑器弹窗
      setEditingArtifact(null);
      setExecutionResult({ status: null, output: '' });
      return;
    }

    // 如果没有提供回调，使用模拟执行（向后兼容）
    try {
      setExecuting(true);
      setExecutionResult({ status: 'running', output: '正在执行测试脚本...\n' });

      const startTime = Date.now();

      // 模拟执行
      await new Promise(resolve => setTimeout(resolve, 2000));

      const duration = (Date.now() - startTime) / 1000;

      // 模拟执行结果
      const mockOutput = `
✓ 测试执行完成

执行摘要:
  总测试数: 5
  通过: 4
  失败: 1
  跳过: 0

执行时间: ${duration.toFixed(2)}s

详细结果:
  ✓ GET /api/users - 200 OK (125ms)
  ✓ POST /api/users - 201 Created (234ms)
  ✓ PUT /api/users/1 - 200 OK (156ms)
  ✗ DELETE /api/users/1 - 404 Not Found (89ms)
    Expected: 200, Received: 404
  ✓ GET /api/users/1 - 200 OK (98ms)
`;

      setExecutionResult({
        status: 'success',
        output: mockOutput,
        duration
      });

      toast.success("脚本执行完成");
    } catch (error) {
      console.error("Failed to execute script:", error);
      setExecutionResult({
        status: 'error',
        output: `执行失败: ${error instanceof Error ? error.message : '未知错误'}`
      });
      toast.error("执行脚本失败");
    } finally {
      setExecuting(false);
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
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  });

  // Debug: Log grouped artifacts
  console.log('[Enhanced Panel] ===== Rendering artifacts =====');
  console.log('[Enhanced Panel] Total artifacts:', artifacts.length);
  console.log('[Enhanced Panel] Grouped artifacts:', Object.keys(groupedArtifacts));
  console.log('[Enhanced Panel] Expanded types:', Array.from(expandedTypes));
  Object.entries(groupedArtifacts).forEach(([type, items]) => {
    console.log(`[Enhanced Panel] Type ${type}: ${items.length} items, expanded: ${expandedTypes.has(type)}`);
  });

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
        <p className="text-sm text-muted-foreground">加载测试成果物中...</p>
      </div>
    );
  }

  if (artifacts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center border-2 border-dashed rounded-xl bg-gradient-to-br from-blue-50/50 to-purple-50/50 dark:from-blue-950/20 dark:to-purple-950/20">
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-400 to-purple-400 rounded-full blur-xl opacity-20 animate-pulse"></div>
          <FileText className="relative h-20 w-20 text-muted-foreground mb-4" />
        </div>
        <p className="text-lg font-semibold mb-2 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          暂无测试成果物
        </p>
        <p className="text-sm text-muted-foreground max-w-md mb-4">
          该接口尚未生成测试成果物。点击下方按钮开始生成测试计划、测试用例和测试脚本。
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={loadArtifacts}
          className="gap-2 hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50"
        >
          <RefreshCw className="h-4 w-4" />
          刷新
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* 成果物统计卡片 - 自适应网格布局 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-4">
        {Object.entries(groupedArtifacts).map(([type, items]) => {
          const config = artifactTypeConfig[type as keyof typeof artifactTypeConfig];
          if (!config) return null;
          const Icon = config.icon;
          return (
            <div
              key={`stat-${type}`}
              className={cn(
                "rounded-lg p-3 border-2 cursor-pointer transition-all hover:shadow-md",
                config.borderColor,
                config.bgColor,
                expandedTypes.has(type) && "ring-2 ring-offset-2 ring-primary/50"
              )}
              onClick={() => toggleExpand(type)}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon className={cn("h-4 w-4", config.color)} />
                <span className="text-xs font-medium text-muted-foreground truncate">{config.label}</span>
              </div>
              <div className="text-2xl font-bold">{items.length}</div>
            </div>
          );
        })}
      </div>

      {/* 成果物列表 */}
      {Object.entries(groupedArtifacts).map(([type, items]) => {
        const config = artifactTypeConfig[type as keyof typeof artifactTypeConfig];
        if (!config) return null;

        const Icon = config.icon;
        const isExpanded = expandedTypes.has(type);

        return (
          <div
            key={type}
            className={cn(
              "rounded-xl border-2 bg-card shadow-sm overflow-hidden transition-all",
              config.borderColor,
              isExpanded && "shadow-lg"
            )}
          >
            {/* 标题栏 */}
            <button
              onClick={() => toggleExpand(type)}
              className={cn(
                "w-full px-4 py-3 transition-all flex items-center justify-between",
                "hover:bg-gradient-to-r",
                type === "API_TEST_PLAN" && "hover:from-blue-50/50 hover:to-blue-100/50",
                type === "API_TEST_CASE" && "hover:from-green-50/50 hover:to-green-100/50",
                type === "API_TEST_SCRIPT" && "hover:from-purple-50/50 hover:to-purple-100/50"
              )}
            >
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", config.bgColor)}>
                  <Icon className={cn("h-5 w-5", config.color)} />
                </div>
                <div className="text-left">
                  <span className="font-semibold text-sm block">{config.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {items.length} 个文件
                  </span>
                </div>
              </div>
              {isExpanded ? (
                <ChevronDown className="h-5 w-5 text-muted-foreground transition-transform" />
              ) : (
                <ChevronRight className="h-5 w-5 text-muted-foreground transition-transform" />
              )}
            </button>

            {/* 内容区域 */}
            {isExpanded && (
              <div className="border-t border-border/50 p-3 space-y-2 bg-gradient-to-br from-background to-muted/20">
                {items.map((artifact) => (
                  <div
                    key={artifact.id}
                    className={cn(
                      "group rounded-lg border bg-background p-4 hover:shadow-lg transition-all cursor-pointer",
                      "hover:border-primary/50"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <p className="text-sm font-semibold truncate group-hover:text-primary transition-colors">
                            {artifact.file_name}
                          </p>
                          <Badge variant="outline" className="text-xs shrink-0">
                            {(artifact.file_size / 1024).toFixed(1)} KB
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                          {artifact.description}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          <span>{new Date(artifact.created_at).toLocaleString('zh-CN')}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {artifact.type === "API_TEST_SCRIPT" ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-blue-50 hover:text-blue-600"
                              onClick={() => loadScriptContent(artifact)}
                              title="编辑脚本"
                            >
                              <Edit className="h-4 w-4" />
                              <span className="text-xs">编辑</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-green-50 hover:text-green-600"
                              onClick={() => {
                                // 直接执行，不需要预先加载脚本内容
                                executeScript(artifact);
                              }}
                              title="执行测试"
                            >
                              <Play className="h-4 w-4" />
                              <span className="text-xs">执行</span>
                            </Button>
                          </>
                        ) : artifact.type === "API_TEST_RESULT" ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-orange-50 hover:text-orange-600"
                              onClick={() => loadScriptContent(artifact)}
                              title="查看详情"
                            >
                              <Eye className="h-4 w-4" />
                              <span className="text-xs">查看</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-slate-50 hover:text-slate-600"
                              onClick={() => {
                                // TODO: 实现下载功能
                                toast.info("下载功能开发中...");
                              }}
                              title="下载报告"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </>
                        ) : artifact.type === "API_TEST_REPORT" ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-pink-50 hover:text-pink-600"
                              onClick={async () => {
                                try {
                                  // 获取报告查看器 URL
                                  const response = await fetch(`/api/v2/attachments/${artifact.id}/report-viewer`);
                                  if (!response.ok) {
                                    toast.error("无法打开测试报告");
                                    return;
                                  }
                                  const data = await response.json();
                                  // 在新窗口中打开报告
                                  window.open(data.index_url, '_blank');
                                } catch (error) {
                                  console.error("打开报告失败:", error);
                                  toast.error("打开报告失败");
                                }
                              }}
                              title="查看报告"
                            >
                              <Eye className="h-4 w-4" />
                              <span className="text-xs">查看</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-slate-50 hover:text-slate-600"
                              onClick={() => {
                                // 下载 ZIP 文件
                                window.open(`/api/v2/attachments/${artifact.id}/download`, '_blank');
                              }}
                              title="下载 ZIP"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-purple-50 hover:text-purple-600"
                              onClick={() => loadScriptContent(artifact)}
                              title="查看内容"
                            >
                              <Eye className="h-4 w-4" />
                              <span className="text-xs">查看</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 px-3 gap-2 hover:bg-slate-50 hover:text-slate-600"
                              onClick={() => {
                                // TODO: 实现下载功能
                                toast.info("下载功能开发中...");
                              }}
                              title="下载文件"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* 代码编辑器弹窗 */}
      {editingArtifact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-background rounded-xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col border-2 border-border">
            {/* 头部 */}
            <div className={cn(
              "flex items-center justify-between px-6 py-4 border-b shrink-0",
              editingArtifact.type === "API_TEST_SCRIPT" && "bg-gradient-to-r from-blue-50/50 to-purple-50/50 dark:from-blue-950/20 dark:to-purple-950/20",
              editingArtifact.type === "API_TEST_RESULT" && "bg-gradient-to-r from-orange-50/50 to-amber-50/50 dark:from-orange-950/20 dark:to-amber-950/20",
              editingArtifact.type === "API_TEST_REPORT" && "bg-gradient-to-r from-pink-50/50 to-rose-50/50 dark:from-pink-950/20 dark:to-rose-950/20",
              (editingArtifact.type === "API_TEST_PLAN" || editingArtifact.type === "API_TEST_CASE") && "bg-gradient-to-r from-green-50/50 to-emerald-50/50 dark:from-green-950/20 dark:to-emerald-950/20"
            )}>
              <div className="flex items-center gap-3">
                <div className={cn(
                  "p-2 rounded-lg",
                  editingArtifact.type === "API_TEST_SCRIPT" && "bg-purple-100 dark:bg-purple-900",
                  editingArtifact.type === "API_TEST_RESULT" && "bg-orange-100 dark:bg-orange-900",
                  editingArtifact.type === "API_TEST_REPORT" && "bg-pink-100 dark:bg-pink-900",
                  (editingArtifact.type === "API_TEST_PLAN" || editingArtifact.type === "API_TEST_CASE") && "bg-green-100 dark:bg-green-900"
                )}>
                  {editingArtifact.type === "API_TEST_SCRIPT" && <Code className="h-5 w-5 text-purple-600 dark:text-purple-400" />}
                  {editingArtifact.type === "API_TEST_RESULT" && <CheckCircle2 className="h-5 w-5 text-orange-600 dark:text-orange-400" />}
                  {editingArtifact.type === "API_TEST_REPORT" && <FileCode className="h-5 w-5 text-pink-600 dark:text-pink-400" />}
                  {editingArtifact.type === "API_TEST_PLAN" && <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />}
                  {editingArtifact.type === "API_TEST_CASE" && <ScrollText className="h-5 w-5 text-green-600 dark:text-green-400" />}
                </div>
                <div>
                  <h3 className="text-lg font-bold">
                    {editingArtifact.type === "API_TEST_SCRIPT" && "编辑测试脚本"}
                    {editingArtifact.type === "API_TEST_RESULT" && "查看执行结果"}
                    {editingArtifact.type === "API_TEST_REPORT" && "查看测试报告"}
                    {editingArtifact.type === "API_TEST_PLAN" && "查看测试计划"}
                    {editingArtifact.type === "API_TEST_CASE" && "查看测试用例"}
                  </h3>
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <span>{editingArtifact.file_name}</span>
                    <Badge variant="outline" className="text-xs">
                      {(editingArtifact.file_size / 1024).toFixed(1)} KB
                    </Badge>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    loadScriptContent(editingArtifact);
                    setExecutionResult({ status: null, output: '' });
                    toast.success("已重置为原始内容");
                  }}
                  disabled={loadingScript || executing}
                  className="gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  重置
                </Button>
                {editingArtifact.type === "API_TEST_SCRIPT" && (
                  <>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={saveScript}
                      disabled={saving || loadingScript || executing}
                      className="gap-2"
                    >
                      {saving ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      保存
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => executeScript()}
                      disabled={executing || loadingScript}
                      className="gap-2 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                    >
                      {executing ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                      执行测试
                    </Button>
                  </>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    setEditingArtifact(null);
                    setExecutionResult({ status: null, output: '' });
                  }}
                  disabled={loadingScript || executing}
                  className="hover:bg-red-50 hover:text-red-600"
                >
                  <XCircle className="h-5 w-5" />
                </Button>
              </div>
            </div>

            {/* 主内容区域 - 分为编辑器和执行结果 */}
            <div className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">
              {/* 编辑器区域 */}
              <div className={cn(
                "flex-1 min-h-0 overflow-hidden bg-background relative border-r",
                executionResult.status && "lg:w-1/2"
              )}>
                {loadingScript || scriptContent === "" ? (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-background">
                    <div className="flex flex-col items-center gap-3">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <p className="text-sm text-muted-foreground">
                        {loadingScript ? "加载脚本内容中..." : "准备编辑器..."}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="h-full w-full">
                    <MonacoCodeEditor
                      key={`editor-${editingArtifact.id}`}
                      value={scriptContent}
                      onChange={setScriptContent}
                      language={
                        editingArtifact.file_name.endsWith('.json') ? 'json' :
                        editingArtifact.file_name.endsWith('.py') ? 'python' :
                        'typescript'
                      }
                      readOnly={loadingScript || editingArtifact.type !== "API_TEST_SCRIPT"}
                      height="100%"
                      minimap={true}
                      fontSize={14}
                      onSave={saveScript}
                    />
                  </div>
                )}
              </div>

              {/* 执行结果区域 */}
              {executionResult.status && (
                <div className={cn(
                  "flex-1 min-h-0 flex flex-col bg-slate-50 dark:bg-slate-950",
                  "lg:w-1/2"
                )}>
                  {/* 结果头部 */}
                  <div className={cn(
                    "px-4 py-3 border-b flex items-center justify-between",
                    executionResult.status === 'success' && "bg-green-50 dark:bg-green-950/20 border-green-200",
                    executionResult.status === 'error' && "bg-red-50 dark:bg-red-950/20 border-red-200",
                    executionResult.status === 'running' && "bg-blue-50 dark:bg-blue-950/20 border-blue-200"
                  )}>
                    <div className="flex items-center gap-2">
                      <Terminal className={cn(
                        "h-4 w-4",
                        executionResult.status === 'success' && "text-green-600",
                        executionResult.status === 'error' && "text-red-600",
                        executionResult.status === 'running' && "text-blue-600"
                      )} />
                      <span className="font-semibold text-sm">
                        {executionResult.status === 'success' && "执行成功"}
                        {executionResult.status === 'error' && "执行失败"}
                        {executionResult.status === 'running' && "执行中..."}
                      </span>
                      {executionResult.duration && (
                        <Badge variant="outline" className="text-xs">
                          {executionResult.duration.toFixed(2)}s
                        </Badge>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExecutionResult({ status: null, output: '' })}
                      className="h-7 px-2"
                    >
                      <XCircle className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* 结果内容 */}
                  <ScrollArea className="flex-1 p-4">
                    <pre className={cn(
                      "text-xs font-mono whitespace-pre-wrap",
                      executionResult.status === 'success' && "text-green-800 dark:text-green-200",
                      executionResult.status === 'error' && "text-red-800 dark:text-red-200",
                      executionResult.status === 'running' && "text-blue-800 dark:text-blue-200"
                    )}>
                      {executionResult.output}
                    </pre>
                  </ScrollArea>
                </div>
              )}
            </div>

            {/* 底部状态栏 */}
            <div className="px-6 py-3 border-t bg-muted/30 shrink-0 flex items-center justify-between">
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <FileCode className="h-3 w-3" />
                  <span>
                    {editingArtifact.file_name.endsWith('.json') ? 'JSON' :
                     editingArtifact.file_name.endsWith('.py') ? 'Python' :
                     'TypeScript'}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  <span>创建于 {new Date(editingArtifact.created_at).toLocaleString('zh-CN')}</span>
                </div>
              </div>
              <div className="text-xs text-muted-foreground">
                {editingArtifact.type === "API_TEST_SCRIPT" ? (
                  <span>按 Ctrl+S 保存 • 点击"执行测试"运行脚本</span>
                ) : (
                  <span>只读模式</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdSaVFRPT06ZGI0NjBkNDk=
