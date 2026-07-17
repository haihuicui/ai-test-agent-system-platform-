"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0ZGMk5RPT06N2Y2NWVlMGM=

import * as React from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import {
  Zap,
  FileCode,
  Sparkles,
  MessageSquare,
  RefreshCw,
  Workflow,
  Layers,
  Plus,
  ChevronRight,
  ChevronDown,
  Play,
  Globe,
  Filter,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { useLanguage } from "@/providers/LanguageProvider";
import { WebFunctionFolderTree } from "@/components/web-tests/folder-tree";
import type { WebFunctionFolderTreeRef } from "@/components/web-tests/folder-tree";
import { WebFunctionList, WebSubFunctionList } from "@/components/web-tests";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerTitle as DrawerTitleComp,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AIChatSkeleton } from "@/components/langgraph/ai-chat-skeleton";
import { ClientProvider } from "@/providers/ClientProvider";
import { useDelayedUnmount } from "@/hooks/useDelayedUnmount";
import { Assistant } from "@langchain/langgraph-sdk";
import { cn } from "@/lib/utils";
import {
  listWebFunctions,
  listWebSubFunctions,
  createWebFunction,
  updateWebFunction,
  deleteWebFunction,
  type WebFunction,
  type WebSubFunction,
  type CreateWebFunctionRequest,
} from "@/lib/api/web-functions";
import {
  createFolder,
  updateFolder,
  deleteFolder,
} from "@/lib/api/folders";
import type {
  FolderInfo,
  FolderCreate,
} from "@/lib/api/types";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0ZGMk5RPT06N2Y2NWVlMGM=

// 重型组件代码分割
const AIChatContainer = dynamic(
  () =>
    import("@/components/langgraph/AIChatContainer").then((m) => ({
      default: m.AIChatContainer,
    })),
  { ssr: false, loading: () => <AIChatSkeleton /> }
);

const WebSubFunctionSidebar = dynamic(
  () =>
    import("@/components/web-tests/web-function-sidebar").then((m) => ({
      default: m.WebSubFunctionSidebar,
    })),
  { ssr: false }
);

const EnhancedTestArtifactsPanel = dynamic(
  () =>
    import("@/components/web-tests/test-artifacts-panel-enhanced").then(
      (m) => ({ default: m.EnhancedTestArtifactsPanel })
    ),
  { ssr: false }
);

const CreateWebFunctionDialog = dynamic(
  () =>
    import("@/components/web-tests").then((m) => ({
      default: m.CreateWebFunctionDialog,
    })),
  { ssr: false }
);

const AIGenerateDialog = dynamic(
  () =>
    import("@/components/web-tests").then((m) => ({
      default: m.AIGenerateDialog,
    })),
  { ssr: false }
);

const MoveFolderDialog = dynamic(
  () =>
    import("@/components/test-cases/move-folder-dialog").then((m) => ({
      default: m.MoveFolderDialog,
    })),
  { ssr: false }
);



// Simplified to only function mode
type TestMode = "function";
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0ZGMk5RPT06N2Y2NWVlMGM=

export default function WebTestsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { t } = useLanguage();

  // 文件夹树 ref
  const folderTreeRef = React.useRef<WebFunctionFolderTreeRef>(null);

  // 模式切换状态 - hardcoded to "function" for now
  const [testMode, setTestMode] = React.useState<TestMode>("function");

  // Web函数测试相关状态
  const [webFunctions, setWebFunctions] = React.useState<WebFunction[]>([]);
  const [webSubFunctions, setWebSubFunctions] = React.useState<WebSubFunction[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [actualTestCasesCounts, setActualTestCasesCounts] = React.useState<Record<string, number>>({});
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  const [selectedSubFunctionId, setSelectedSubFunctionId] = React.useState<string | null>(null);
  const [showSubFunctionSidebar, setShowSubFunctionSidebar] = React.useState(false);
  const [subFunctionDrawerOpen, setSubFunctionDrawerOpen] = React.useState(false);
  const [selectedWebFunction, setSelectedWebFunction] = React.useState<WebFunction | null>(null);
  const [artifactsRefreshTrigger, setArtifactsRefreshTrigger] = React.useState(0);

  // 分页和筛选
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);
  const [total, setTotal] = React.useState(0);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [formatFilter, setFormatFilter] = React.useState("");

  // 对话框状态
  const [editingWebFunction, setEditingWebFunction] = React.useState<WebFunction | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [deletingWebFunction, setDeletingWebFunction] = React.useState<WebFunction | null>(null);
  const [folderDialogOpen, setFolderDialogOpen] = React.useState(false);
  const [editingFolder, setEditingFolder] = React.useState<FolderInfo | null>(null);
  const [folderParentId, setFolderParentId] = React.useState<string | undefined>();
  const [folderFormData, setFolderFormData] = React.useState<FolderCreate>({
    name: "",
    description: "",
  });
  const [deleteFolderDialogOpen, setDeleteFolderDialogOpen] = React.useState(false);
  const [deletingFolder, setDeletingFolder] = React.useState<FolderInfo | null>(null);
  const [moveFolderDialogOpen, setMoveFolderDialogOpen] = React.useState(false);
  const [movingFolder, setMovingFolder] = React.useState<FolderInfo | null>(null);
  const [createWebFunctionFolderId, setCreateWebFunctionFolderId] = React.useState<string | null>(null);
  const [selectedFolderName, setSelectedFolderName] = React.useState<string | undefined>();
  const [createFunctionDialogOpen, setCreateFunctionDialogOpen] = React.useState(false);
  const [aiGenerateDialogOpen, setAiGenerateDialogOpen] = React.useState(false);

  // AI 聊天状态
  const [aiChatOpen, setAiChatOpen] = React.useState(false);
  const renderAIChat = useDelayedUnmount(aiChatOpen, 300);
  const [aiChatInitialPrompt, setAiChatInitialPrompt] = React.useState<string>("");
  const [aiChatKey, setAiChatKey] = React.useState<number>(0);

  // 使用 useMemo 稳定 assistant 对象
  const assistant = React.useMemo<Assistant | null>(() => {
    if (!projectId) return null;
    return {
      assistant_id: "web_agent",
      graph_id: "web_agent",
      config: {
        configurable: {
          project_identifier: projectId,
          folder_id: selectedFolderId || "",
          template_type: "web_test",
        }
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: {},
      version: 1,
      name: t("webTests.webFunctionAssistant"),
      context: {},
    };
  }, [projectId, selectedFolderId, t]);

  // 加载 Web 函数测试数据
  const loadWebFunctions = React.useCallback(async () => {
    if (testMode !== "function") return;

    try {
      setLoading(true);

      const subFunctionsParams: any = {
        p: page,
        page_size: pageSize,
      };
      if (selectedFolderId) {
        subFunctionsParams.folder_id = selectedFolderId;
      }

      const params = {
        p: page,
        page_size: pageSize,
        search: searchQuery || undefined,
      };

      // 子功能列表与功能列表相互独立，并行请求
      const [subFunctions, response] = await Promise.all([
        listWebSubFunctions(projectId, subFunctionsParams),
        selectedFolderId
          ? listWebFunctions(projectId, { ...params, folder_id: selectedFolderId })
          : listWebFunctions(projectId, params),
      ]);

      const subFunctionsItems = subFunctions.items || [];
      setWebSubFunctions(subFunctionsItems);

      let items, total;
      if ((response as any).data) {
        const data = (response as any).data;
        items = data.items || data.data || [];
        total = data.total || 0;
      } else {
        items = (response as any).items || (response as any).data || [];
        total = (response as any).total || 0;
      }

      setWebFunctions(items);
      setTotal(total);
    } catch (error) {
      console.error("Failed to load web functions:", error);
      toast.error(t("webTests.loadWebFunctionsFailed"));
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedFolderId, page, pageSize, searchQuery, formatFilter, testMode, t]);

  // 根据模式加载数据
  React.useEffect(() => {
    if (projectId) {
      loadWebFunctions();
    }
  }, [projectId, testMode, loadWebFunctions]);

  const handleSelectFolder = (folder: FolderInfo | null) => {
    setSelectedFolderId(folder?.id || null);
    setSelectedFolderName(folder?.name);
    setPage(1);
    setSelectedIds(new Set());
    // 切换文件夹时清除子功能选择，避免显示错误的测试成果物
    setSelectedSubFunctionId(null);
  };

  // 处理创建函数
  const handleCreateWebFunction = (folderId?: string | null) => {
    setEditingWebFunction(null);
    setCreateWebFunctionFolderId(folderId || null);
    setCreateFunctionDialogOpen(true);
  };

  // 处理函数创建成功
  const handleFunctionCreated = () => {
    loadWebFunctions();
    folderTreeRef.current?.refresh();
  };

  const handleTestCasesCountChange = React.useCallback(async (count: number, subFunctionId?: string) => {
    const targetSubFunctionId = subFunctionId || selectedSubFunctionId || webSubFunctions[0]?.id;
    if (!targetSubFunctionId) return;

    setActualTestCasesCounts(prev => ({
      ...prev,
      [targetSubFunctionId]: count,
    }));

    setWebSubFunctions(prev => prev.map(sf => {
      if (sf.id === targetSubFunctionId) {
        return { ...sf, total_test_cases: count };
      }
      return sf;
    }));
  }, [selectedSubFunctionId, webSubFunctions]);

  // 加载特定功能的子功能
  const loadSubFunctionsForFunction = React.useCallback(async (functionId: string) => {
    try {
      const subFunctions = await listWebSubFunctions(projectId, {
        function_id: functionId,
        p: 1,
        page_size: 100,
      });
      setWebSubFunctions(subFunctions.items || []);
    } catch (error) {
      console.error("Failed to load sub-functions:", error);
      toast.error("加载子功能失败");
    }
  }, [projectId]);

  const handleExecuteScript = (artifactId: string, fileName: string) => {
    const prompt = `${t("webTests.executeTestPrompt")}:

**Script ID**: ${artifactId}
**Script File**: ${fileName}
**Project ID**: ${projectId}
**Sub Function ID**: ${selectedSubFunctionId || "N/A"}

请按以下步骤执行测试：
1. 使用 \`download_web_script\` 工具下载脚本到 测试工作目录（参数：script_id="${artifactId}"）
2. 使用 \`execute_web_script\` 工具执行测试（参数：local_script_path=从步骤1获取的路径、framework="playwright"、reporter="html"、project_identifier="${projectId}"、sub_function_id="${selectedSubFunctionId || ""}"）
3. 解析执行结果并报告测试状态
4. （可选）使用 \`delete_web_script\` 清理临时脚本`;

    setAiChatInitialPrompt(prompt);
    setAiChatKey(prev => prev + 1);
    setShowSubFunctionSidebar(false);
    setAiChatOpen(true);
  };

  // 处理提交文件夹
  const handleSubmitFolder = async () => {
    if (!folderFormData.name.trim()) {
      toast.error(t("webTests.folderNameRequired"));
      return;
    }
    try {
      setSubmitting(true);
      if (editingFolder) {
        // 编辑文件夹 - 使用本地更新
        const response = await updateFolder(projectId, editingFolder.id, folderFormData);
        toast.success(t("webTests.folderUpdateSuccess"));
        setFolderDialogOpen(false);
        // 本地更新文件夹
        if (response.success && response.data) {
          folderTreeRef.current?.updateFolderLocally(editingFolder.id, response.data);
        }
      } else {
        // 创建文件夹 - 使用本地添加
        const response = await createFolder(projectId, {
          ...folderFormData,
          parent_id: folderParentId,
          folder_type: "web_test",  // 指定为 Web 测试类型文件夹
        });
        toast.success(t("webTests.folderCreateSuccess"));
        setFolderDialogOpen(false);
        // 本地添加文件夹
        if (response.success && response.data) {
          folderTreeRef.current?.addFolderLocally(response.data, folderParentId || null);
        }
      }
    } catch (error) {
      console.error("Failed to save folder:", error);
      toast.error(editingFolder ? t("webTests.folderUpdateFailed") : t("webTests.folderCreateFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 处理删除文件夹
  const handleDeleteFolder = async () => {
    if (!deletingFolder) return;

    try {
      await deleteFolder(projectId, deletingFolder.id);
      toast.success(t("webTests.folderDeleteSuccess"));
      setDeleteFolderDialogOpen(false);
      setDeletingFolder(null);

      // 如果删除的是当前选中的文件夹，清空选中状态
      if (selectedFolderId === deletingFolder.id) {
        setSelectedFolderId(null);
        setSelectedFolderName(undefined);
        setWebSubFunctions([]);
        setWebFunctions([]);
      }

      // 刷新文件夹树
      folderTreeRef.current?.refresh();
    } catch (error) {
      console.error("Failed to delete folder:", error);
      toast.error(t("webTests.folderDeleteFailed"));
    }
  };

  // 移动文件夹成功回调 - 本地更新树
  const handleMoveFolderSuccess = (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => {
    folderTreeRef.current?.moveFolderLocally(folderId, newParentId, updatedFolder);
  };

  // 处理 AI 生成
  const handleAIGenerate = (prompt: string) => {
    setAiChatInitialPrompt(prompt);
    setAiChatKey(prev => prev + 1);
    setAiChatOpen(true);
  };

  // 处理删除 Web 功能 - 打开确认对话框
  const handleDeleteWebFunction = (webFunction: WebFunction) => {
    setDeletingWebFunction(webFunction);
    setDeleteDialogOpen(true);
  };

  // 实际执行删除
  const confirmDeleteWebFunction = async () => {
    if (!deletingWebFunction) return;

    try {
      console.log("Deleting web function:", deletingWebFunction.id, deletingWebFunction);
      const result = await deleteWebFunction(projectId, deletingWebFunction.id);
      console.log("Delete result:", result);
      toast.success(t("webTests.functionDeleteSuccess"));
      setDeleteDialogOpen(false);
      setDeletingWebFunction(null);
      await loadWebFunctions();
      // 刷新文件夹树
      folderTreeRef.current?.refresh();
    } catch (error: any) {
      console.error("Failed to delete web function:", error);
      console.error("Error details:", {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      toast.error(`${t("webTests.functionDeleteFailed")}: ${error.message || "Unknown error"}`);
    }
  };

  // 处理批量删除 Web 功能
  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    try {
      console.log("Bulk deleting web functions:", ids);
      for (const id of ids) {
        console.log("Deleting function:", id);
        const result = await deleteWebFunction(projectId, id);
        console.log("Delete result for", id, ":", result);
      }
      toast.success(t("webTests.bulkDeleteSuccess", { count: ids.length.toString() }));
      setSelectedIds(new Set());
      await loadWebFunctions();
      // 刷新文件夹树
      folderTreeRef.current?.refresh();
    } catch (error: any) {
      console.error("Failed to bulk delete web functions:", error);
      console.error("Error details:", {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      toast.error(`${t("webTests.bulkDeleteFailed")}: ${error.message || "Unknown error"}`);
    }
  };

  return (
    <MainLayout title={t("webTests.title")}>
      <div className="relative flex h-[calc(100vh-8rem)] rounded-lg border bg-card overflow-hidden">
        <div className="flex h-full w-full">
          {/* 左侧面板 (320px) */}
          <div className="w-80 shrink-0 border-r bg-muted/10 flex flex-col">
            {/* 标题 */}
            <div className="p-3 border-b bg-background">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold flex items-center gap-2">
                  <Globe className="h-4 w-4 text-blue-500" />
                  {t("webTests.testManagement")}
                </h3>
              </div>
            </div>

            {/* 文件夹树 */}
            <div className="flex-1 overflow-hidden">
              <WebFunctionFolderTree
                ref={folderTreeRef}
                projectId={projectId}
                selectedFolderId={selectedFolderId}
                onSelectFolder={handleSelectFolder}
                onCreateFolder={(parentId) => {
                  setEditingFolder(null);
                  setFolderParentId(parentId);
                  setFolderFormData({ name: "", description: "" });
                  setFolderDialogOpen(true);
                }}
                onEditFolder={(folder) => {
                  setEditingFolder(folder);
                  setFolderParentId(undefined);
                  setFolderFormData({
                    name: folder.name,
                    description: folder.description || "",
                  });
                  setFolderDialogOpen(true);
                }}
                onDeleteFolder={(folder) => {
                  setDeletingFolder(folder);
                  setDeleteFolderDialogOpen(true);
                }}
                onMoveFolder={(folder) => {
                  setMovingFolder(folder);
                  setMoveFolderDialogOpen(true);
                }}
                onCreateWebFunction={handleCreateWebFunction}
                onSelectWebSubFunction={(subFunctionId: string) => {
                  setSelectedSubFunctionId(subFunctionId);
                  setShowSubFunctionSidebar(true);
                }}
                selectedWebSubFunctionId={selectedSubFunctionId}
              />
            </div>
          </div>

          {/* 中间主区域 */}
          <div className="flex-1 flex flex-col min-h-0 bg-background">
            {/* 工具栏 */}
            <div className="flex items-center justify-between border-b px-4 py-3 bg-muted/20">
              <div className="flex items-center gap-2">
                <Layers className="h-5 w-5 text-blue-500" />
                <div>
                  <h2 className="text-lg font-semibold">
                    {selectedFolderName || t("webTests.allFunctions")}
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    {webSubFunctions.length}{t("webTests.subFunctionsCount")}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAiGenerateDialogOpen(true)}
                  className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all"
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  AI 生成
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCreateWebFunction(null)}
                  className="bg-background hover:bg-accent"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  新建
                </Button>
                <Button
                  size="sm"
                  onClick={() => setAiChatOpen(true)}
                  className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all"
                >
                  <MessageSquare className="mr-2 h-4 w-4" />
                  AI 助手
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadWebFunctions()}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* 模式内容区域 */}
            <div className="flex-1 overflow-hidden relative flex flex-col">
              {/* Web函数列表 - 让内容决定高度 */}
              <div className="overflow-y-auto">
                <WebFunctionList
                  webFunctions={webFunctions}
                  loading={loading}
                  selectedIds={selectedIds}
                  onSelectIds={setSelectedIds}
                  onBulkDelete={handleBulkDelete}
                  onDeleteWebFunction={handleDeleteWebFunction}
                  onViewWebFunction={async (webFunction) => {
                    // 设置选中的功能，用于显示标题
                    setSelectedWebFunction(webFunction);
                    // 加载该功能下的子功能
                    await loadSubFunctionsForFunction(webFunction.id);
                    // 打开抽屉
                    setSubFunctionDrawerOpen(true);
                  }}
                  folderName={selectedFolderName}
                  pagination={{
                    page,
                    pageSize,
                    total,
                    onPageChange: setPage,
                  }}
                />
              </div>

              {/* 测试成果物 */}
              <div className="flex-1 min-h-0 overflow-y-auto bg-gradient-to-b from-muted/20 to-background p-6">
                <div className="max-w-7xl mx-auto">
                  {/* 当前选中的子功能信息卡片 */}
                  {selectedSubFunctionId && (() => {
                    const currentSubFunction = webSubFunctions.find(
                      sf => sf.id === selectedSubFunctionId
                    );
                    if (!currentSubFunction) return null;
                    return (
                      <div className="mb-6 rounded-xl border-2 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30 p-4 shadow-sm">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 mb-2">
                              <FileCode className="h-5 w-5 text-blue-500 shrink-0" />
                              <h3 className="text-lg font-semibold truncate">
                                {currentSubFunction.display_name}
                              </h3>
                              <Badge variant="outline" className="shrink-0 text-xs">
                                {currentSubFunction.identifier}
                              </Badge>
                              <Badge
                                className={cn(
                                  "shrink-0 text-xs",
                                  currentSubFunction.test_type === "functional" ? "bg-blue-500 text-white" :
                                  currentSubFunction.test_type === "validation" ? "bg-green-500 text-white" :
                                  currentSubFunction.test_type === "ui" ? "bg-purple-500 text-white" :
                                  "bg-gray-500 text-white"
                                )}
                              >
                                {currentSubFunction.test_type}
                              </Badge>
                              <Badge
                                className={cn(
                                  "shrink-0 text-xs",
                                  currentSubFunction.priority === "critical" ? "bg-red-500 text-white" :
                                  currentSubFunction.priority === "high" ? "bg-orange-500 text-white" :
                                  currentSubFunction.priority === "medium" ? "bg-yellow-500 text-white" :
                                  "bg-gray-500 text-white"
                                )}
                              >
                                {currentSubFunction.priority}
                              </Badge>
                            </div>
                            {currentSubFunction.description && (
                              <p className="text-sm text-muted-foreground line-clamp-2 ml-8">
                                {currentSubFunction.description}
                              </p>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSubFunctionDrawerOpen(true)}
                            className="shrink-0 gap-2"
                          >
                            <span className="text-xs">查看子功能列表</span>
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    );
                  })()}

                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="text-xl font-bold flex items-center gap-2">
                        <Zap className="h-5 w-5 text-purple-500" />
                        {t("webTests.testArtifacts")}
                      </h2>
                      <p className="text-sm text-muted-foreground mt-1">
                        {selectedSubFunctionId
                          ? t("webTests.testArtifactsDesc")
                          : webSubFunctions.length > 0
                          ? "请在抽屉中选择一个子功能以查看其测试成果物"
                          : t("webTests.noFunctionData")
                        }
                      </p>
                    </div>
                  </div>

                  {webSubFunctions.length === 0 && (
                    <div className="text-center py-12 border-2 border-dashed rounded-lg bg-muted/10">
                      <FileCode className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                      <p className="text-lg font-medium mb-2">{t("webTests.noFunctionData")}</p>
                      <p className="text-sm text-muted-foreground mb-4">
                        {t("webTests.selectFolderOrImportWeb")}
                      </p>
                    </div>
                  )}

                  {webSubFunctions.length > 0 && !selectedSubFunctionId && (
                    <div className="text-center py-12 border-2 border-dashed rounded-xl bg-gradient-to-br from-blue-50/50 to-purple-50/50 dark:from-blue-950/20 dark:to-purple-950/20">
                      <FileCode className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                      <p className="text-lg font-semibold mb-2">请在抽屉中选择一个子功能</p>
                      <p className="text-sm text-muted-foreground mb-4">
                        点击右上角的按钮打开子功能列表抽屉，选择一个子功能后即可查看其测试成果物
                      </p>
                      <Button
                        variant="outline"
                        onClick={() => setSubFunctionDrawerOpen(true)}
                        className="gap-2"
                      >
                        <FileCode className="h-4 w-4" />
                        打开子功能列表
                      </Button>
                    </div>
                  )}

                  {selectedSubFunctionId && (
                    <EnhancedTestArtifactsPanel
                      key={`artifacts-${selectedSubFunctionId}`}
                      subFunctionId={selectedSubFunctionId}
                      projectId={projectId}
                      onRefresh={loadWebFunctions}
                      onTestCasesCountChange={handleTestCasesCountChange}
                      onExecuteScript={handleExecuteScript}
                      refreshTrigger={artifactsRefreshTrigger}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* 右侧悬浮 AI 聊天面板 */}
          {assistant && (
            <div
              className={cn(
                "absolute right-0 top-0 z-50 h-full w-[1200px] bg-background transition-transform duration-300 ease-in-out",
                aiChatOpen ? "translate-x-0 border-l shadow-2xl" : "translate-x-full"
              )}
            >
              {renderAIChat && (
                <ClientProvider
                  deploymentUrl={process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || "http://127.0.0.1:2025"}
                  apiKey={process.env.NEXT_PUBLIC_LANGSMITH_API_KEY || ""}
                >
                  <AIChatContainer
                    assistant={assistant}
                    initialPrompt={aiChatInitialPrompt}
                    onClose={() => {
                      setAiChatOpen(false);
                      setAiChatKey(0);
                      setAiChatInitialPrompt("");
                    }}
                    createNewThread={aiChatKey > 0}
                    reconnectOnMount={true}
                    fetchHistoryOnMount={true}
                    onTestCreated={() => {
                      loadWebFunctions();
                      folderTreeRef.current?.refresh();
                      setArtifactsRefreshTrigger(prev => prev + 1);
                    }}
                    onArtifactSaved={() => {
                      setArtifactsRefreshTrigger(prev => prev + 1);
                    }}
                  />
                </ClientProvider>
              )}
            </div>
          )}

          {/* 右侧悬浮详情侧边栏 */}
          {testMode === "function" && showSubFunctionSidebar && selectedSubFunctionId && (
            <div
              className={cn(
                "absolute right-0 top-0 z-30 h-full w-[600px] bg-background transition-transform duration-300 ease-in-out border-l shadow-xl",
                showSubFunctionSidebar ? "translate-x-0" : "translate-x-full"
              )}
            >
              <WebSubFunctionSidebar
                subFunctionId={selectedSubFunctionId}
                projectId={projectId}
                onClose={() => {
                  setShowSubFunctionSidebar(false);
                  setSelectedSubFunctionId(null);
                  loadWebFunctions();
                }}
                onGenerateTest={() => {
                  setShowSubFunctionSidebar(false);
                  setAiChatOpen(true);
                  setAiChatInitialPrompt(t("webTests.generateTestsForFunction", { id: selectedSubFunctionId }));
                }}
                onOpenAIChat={(prompt) => {
                  setAiChatInitialPrompt(prompt);
                  setAiChatKey(prev => prev + 1);
                  setShowSubFunctionSidebar(false);
                  setAiChatOpen(true);
                }}
                onRefresh={() => {
                  loadWebFunctions();
                  folderTreeRef.current?.refresh();
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* 各种对话框 */}
        {/* 创建/编辑函数对话框 */}
        <CreateWebFunctionDialog
          open={createFunctionDialogOpen}
          onOpenChange={(open) => {
            setCreateFunctionDialogOpen(open);
            if (!open) {
              setCreateWebFunctionFolderId(null);
              setEditingWebFunction(null);
            }
          }}
          projectId={projectId}
          folderId={createWebFunctionFolderId ?? selectedFolderId}
          editingFunction={editingWebFunction}
          onSuccess={handleFunctionCreated}
        />

        {/* AI 生成对话框 */}
        <AIGenerateDialog
          open={aiGenerateDialogOpen}
          onOpenChange={setAiGenerateDialogOpen}
          onGenerate={handleAIGenerate}
        />

        {/* 文件夹对话框 */}
        <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingFolder ? t("webTests.editFolder") : t("webTests.createFolder")}
              </DialogTitle>
              <DialogDescription>
                {editingFolder ? t("webTests.editFolderInfo") : t("webTests.createNewFolder")}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="folder-name">{t("webTests.folderNameLabel")}</Label>
                <Input
                  id="folder-name"
                  value={folderFormData.name}
                  onChange={(e) =>
                    setFolderFormData({ ...folderFormData, name: e.target.value })
                  }
                  placeholder={t("webTests.enterFolderName")}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="folder-description">{t("webTests.descriptionLabel")}</Label>
                <Textarea
                  id="folder-description"
                  value={folderFormData.description}
                  onChange={(e) =>
                    setFolderFormData({
                      ...folderFormData,
                      description: e.target.value,
                    })
                  }
                  placeholder={t("webTests.enterDescription")}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setFolderDialogOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button onClick={handleSubmitFolder} disabled={submitting}>
                {submitting ? t("common.saving") : editingFolder ? t("common.save") : t("common.create")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 删除文件夹确认对话框 */}
        <Dialog open={deleteFolderDialogOpen} onOpenChange={setDeleteFolderDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("webTests.deleteFolderTitle")}</DialogTitle>
              <DialogDescription>
                {t("webTests.deleteFolderMessage", { name: deletingFolder?.name || "" })}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setDeleteFolderDialogOpen(false);
                  setDeletingFolder(null);
                }}
              >
                {t("common.cancel")}
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteFolder}
              >
                {t("common.delete")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 删除 Web 功能确认对话框 */}
        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("webTests.deleteFunctionTitle")}</DialogTitle>
              <DialogDescription>
                {t("webTests.deleteFunctionMessage", { name: deletingWebFunction?.display_name || "" })}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setDeleteDialogOpen(false);
                  setDeletingWebFunction(null);
                }}
              >
                {t("common.cancel")}
              </Button>
              <Button
                variant="destructive"
                onClick={confirmDeleteWebFunction}
              >
                {t("common.delete")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 子功能列表抽屉 */}
        <Drawer open={subFunctionDrawerOpen} onOpenChange={(open) => {
          setSubFunctionDrawerOpen(open);
          // 关闭抽屉时，恢复所有子功能列表
          if (!open) {
            loadWebFunctions();
            setSelectedWebFunction(null);
          }
        }}>
          <DrawerContent direction="right" className="h-full w-[500px] border-l rounded-none">
            <DrawerHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b">
              <div className="flex items-center gap-2">
                <FileCode className="h-5 w-5 text-blue-500" />
                <DrawerTitleComp>子功能列表</DrawerTitleComp>
                <span className="text-sm text-muted-foreground">
                  ({selectedWebFunction ? `${selectedWebFunction.display_name} - ` : ""}{webSubFunctions.length})
                </span>
              </div>
              <DrawerClose asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <span className="sr-only">关闭</span>
                  ×
                </Button>
              </DrawerClose>
            </DrawerHeader>
            <div className="flex-1 overflow-y-auto p-0">
              <WebSubFunctionList
                subFunctions={webSubFunctions}
                loading={loading}
                selectedId={selectedSubFunctionId}
                onSelectSubFunction={(subFunctionId) => {
                  setSelectedSubFunctionId(subFunctionId);
                }}
                pagination={{
                  page,
                  pageSize,
                  total: webSubFunctions.length,
                  onPageChange: setPage,
                }}
                showHeader={false}
              />
            </div>
          </DrawerContent>
        </Drawer>
        {/* 移动文件夹对话框 */}
        <MoveFolderDialog
          open={moveFolderDialogOpen}
          onOpenChange={setMoveFolderDialogOpen}
          projectId={projectId}
          folder={movingFolder}
          folderType="web_test"
          onMoveSuccess={handleMoveFolderSuccess}
        />
      </MainLayout>
    );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0ZGMk5RPT06N2Y2NWVlMGM=
