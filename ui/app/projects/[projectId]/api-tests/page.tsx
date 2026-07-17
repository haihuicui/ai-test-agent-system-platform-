"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlVSaVdBPT06MmUzZDY0N2Y=

import * as React from "react";
import dynamic from "next/dynamic";
import { useParams, useSearchParams } from "next/navigation";
import { useQueryState } from "nuqs";
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
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { useLanguage } from "@/providers/LanguageProvider";
import { APIEndpointList } from "@/components/api-tests/APIEndpointList";
import { APIFolderTree } from "@/components/api-tests/folder-tree";
import type { APIFolderTreeRef } from "@/components/api-tests/folder-tree";
import { ScenarioListPanel } from "@/components/scenario-tests/scenario-list-panel";
import { EnvironmentSelector } from "@/components/api-tests/environment-selector";
import { AIChatSkeleton } from "@/components/langgraph/ai-chat-skeleton";
import { useProjectEnvironment } from "@/providers/ProjectEnvironmentProvider";
import { useDelayedUnmount } from "@/hooks/useDelayedUnmount";
import { Assistant } from "@langchain/langgraph-sdk";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ClientProvider } from "@/providers/ClientProvider";
import {
  getFolderAPITests,
  listAPITests,
  createAPITest,
  updateAPITest,
  deleteAPITest,
  runAPITest,
} from "@/lib/api/api-tests";
import {
  listAPIEndpoints,
  type APIEndpoint,
} from "@/lib/api/api-endpoints";
import {
  createFolder,
  updateFolder,
  deleteFolder,
} from "@/lib/api/folders";
import { listScenarios, executeScenario } from "@/lib/api/scenarios";
import type {
  FolderInfo,
  FolderCreate,
} from "@/lib/api/types";
import type { APITest, CreateAPITestRequest } from "@/lib/api/api-tests";
import type { Scenario } from "@/types/scenario";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlVSaVdBPT06MmUzZDY0N2Y=

// 重型组件代码分割，减少初始 chunk 体积
const AIChatContainer = dynamic(
  () =>
    import("@/components/langgraph/AIChatContainer").then((m) => ({
      default: m.AIChatContainer,
    })),
  { ssr: false, loading: () => <AIChatSkeleton /> }
);

const ScenarioOrchestrationView = dynamic(
  () =>
    import("@/components/scenario-tests/scenario-orchestration-view").then(
      (m) => ({ default: m.ScenarioOrchestrationView })
    ),
  { ssr: false }
);

const ScenarioExecutionMonitor = dynamic(
  () =>
    import("@/components/scenario-tests/scenario-execution-monitor").then(
      (m) => ({ default: m.ScenarioExecutionMonitor })
    ),
  { ssr: false }
);

const EnhancedTestArtifactsPanel = dynamic(
  () =>
    import("@/components/api-tests/test-artifacts-panel-enhanced").then(
      (m) => ({ default: m.EnhancedTestArtifactsPanel })
    ),
  { ssr: false }
);

const EndpointExecutionResultsPanel = dynamic(
  () =>
    import("@/components/api-tests/endpoint-execution-results-panel").then(
      (m) => ({ default: m.EndpointExecutionResultsPanel })
    ),
  { ssr: false }
);

const APIEndpointSidebar = dynamic(
  () =>
    import("@/components/api-tests/api-endpoint-sidebar").then(
      (m) => ({ default: m.APIEndpointSidebar })
    ),
  { ssr: false }
);

const ScenarioDetailSidebar = dynamic(
  () =>
    import("@/components/scenario-tests/scenario-detail-sidebar").then(
      (m) => ({ default: m.ScenarioDetailSidebar })
    ),
  { ssr: false }
);

const APIParseDialog = dynamic(
  () =>
    import("@/components/api-tests/api-parse-dialog").then((m) => ({
      default: m.APIParseDialog,
    })),
  { ssr: false }
);

const AIGenerateAPITestDialog = dynamic(
  () =>
    import("@/components/api-tests/ai-generate-dialog").then((m) => ({
      default: m.AIGenerateAPITestDialog,
    })),
  { ssr: false }
);

const CreateEndpointDialog = dynamic(
  () =>
    import("@/components/api-tests/create-endpoint-dialog").then((m) => ({
      default: m.CreateEndpointDialog,
    })),
  { ssr: false }
);

const AIGenerateScenarioDialog = dynamic(
  () =>
    import("@/components/scenario-tests/ai-generate-scenario-dialog").then(
      (m) => ({ default: m.AIGenerateScenarioDialog })
    ),
  { ssr: false }
);

const ScenarioCreateDialog = dynamic(
  () =>
    import("@/components/scenario-tests/scenario-create-dialog").then((m) => ({
      default: m.ScenarioCreateDialog,
    })),
  { ssr: false }
);

const EnvironmentSheet = dynamic(
  () =>
    import("@/components/api-tests/environment-sheet").then((m) => ({
      default: m.EnvironmentSheet,
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


type TestMode = "endpoint" | "scenario";
type ScenarioViewMode = "orchestrate" | "monitor";
type EndpointTab = "artifacts" | "execution";

export default function APITestsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { t } = useLanguage();
  const {
    selectedEnvironmentId,
    selectedEnvironment,
    refreshEnvironments,
  } = useProjectEnvironment();

  // 文件夹树 ref
  const folderTreeRef = React.useRef<APIFolderTreeRef>(null);

  // 模式切换状态
  const [testMode, setTestMode] = React.useState<TestMode>("endpoint");

  // 接口测试相关状态
  const [apiTests, setApiTests] = React.useState<APITest[]>([]);
  const [apiEndpoints, setApiEndpoints] = React.useState<APIEndpoint[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [actualTestCasesCounts, setActualTestCasesCounts] = React.useState<Record<string, number>>({});
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  const [selectedEndpointId, setSelectedEndpointId] = useQueryState("endpointId");
  const [showEndpointSidebar, setShowEndpointSidebar] = React.useState(false);
  const [artifactsRefreshTrigger, setArtifactsRefreshTrigger] = React.useState(0);
  const [endpointTab, setEndpointTab] = React.useState<EndpointTab>("artifacts");

  // 环境配置 Sheet
  const [environmentSheetOpen, setEnvironmentSheetOpen] = React.useState(false);

  // 场景测试相关状态
  const [scenarios, setScenarios] = React.useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = React.useState<string | null>(null);
  const [scenarioViewMode, setScenarioViewMode] = React.useState<ScenarioViewMode>("orchestrate");
  const [showScenarioSidebar, setShowScenarioSidebar] = React.useState(false);
  const [scenarioDialogOpen, setScenarioDialogOpen] = React.useState(false);
  const [scenarioRefreshTrigger, setScenarioRefreshTrigger] = React.useState(0);
  const [scenarioSidebarEditing, setScenarioSidebarEditing] = React.useState(false);
  const [scenarioEditTrigger, setScenarioEditTrigger] = React.useState(0);

  // 分页和筛选
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);
  const [total, setTotal] = React.useState(0);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [formatFilter, setFormatFilter] = React.useState("");

  // 对话框状态
  const [apiTestDialogOpen, setApiTestDialogOpen] = React.useState(false);
  const [editingAPITest, setEditingAPITest] = React.useState<APITest | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [deletingAPITest, setDeletingAPITest] = React.useState<APITest | null>(null);
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
  const [createAPITestFolder, setCreateAPITestFolder] = React.useState<FolderInfo | null>(null);
  const [selectedFolderName, setSelectedFolderName] = React.useState<string | undefined>();
  const [aiGenerateDialogOpen, setAiGenerateDialogOpen] = React.useState(false);
  const [apiParseDialogOpen, setApiParseDialogOpen] = React.useState(false);
  const [aiGenerateScenarioDialogOpen, setAiGenerateScenarioDialogOpen] = React.useState(false);
  const [createEndpointDialogOpen, setCreateEndpointDialogOpen] = React.useState(false);

  // AI 聊天状态
  const [aiChatOpen, setAiChatOpen] = React.useState(false);
  const renderAIChat = useDelayedUnmount(aiChatOpen, 300);
  const [aiChatInitialPrompt, setAiChatInitialPrompt] = React.useState<string>("");
  const [aiChatKey, setAiChatKey] = React.useState<number>(0);

  // 使用 useMemo 稳定 assistant 对象，避免 testMode 切换触发额外重渲染
  const assistant = React.useMemo<Assistant | null>(() => {
    if (!projectId) return null;
    const isEndpoint = testMode === "endpoint";
    return {
      assistant_id: "api_agent",
      graph_id: "api_agent",
      config: {
        configurable: {
          project_identifier: projectId,
          folder_id: selectedFolderId || "",
          template_type: isEndpoint ? "api_test" : "scenario_test",
          environment_id: selectedEnvironmentId || "",
        }
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: {},
      version: 1,
      name: isEndpoint ? t("apiTests.apiTestAssistant") : t("apiTests.scenarioTestAssistant"),
      context: {},
    };
  }, [projectId, selectedFolderId, testMode, selectedEnvironmentId, t]);

  // 加载 API 测试数据
  const loadAPITests = React.useCallback(async () => {
    if (testMode !== "endpoint") return;

    try {
      setLoading(true);

      const params = {
        page,
        page_size: pageSize,
        search: searchQuery || undefined,
        script_format: formatFilter && formatFilter !== "all" ? formatFilter : undefined,
      };

      // 端点列表与测试列表相互独立，并行请求
      const [endpoints, response] = await Promise.all([
        listAPIEndpoints(projectId, {
          folder_id: selectedFolderId || undefined,
        }),
        selectedFolderId
          ? getFolderAPITests(projectId, selectedFolderId, params)
          : listAPITests(projectId, params),
      ]);

      setApiEndpoints(endpoints);

      let items, total;
      if ((response as any).data) {
        const data = (response as any).data;
        items = data.items || data.data || [];
        total = data.total || 0;
      } else {
        items = (response as any).items || (response as any).data || [];
        total = (response as any).total || 0;
      }

      setApiTests(items);
      setTotal(total);
    } catch (error) {
      console.error("Failed to load API tests:", error);
      toast.error(t("apiTests.loadAPITestsFailed"));
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedFolderId, page, pageSize, searchQuery, formatFilter, testMode, t]);

  // 加载场景测试数据
  const loadScenarios = React.useCallback(async () => {
    if (testMode !== "scenario") return;

    try {
      setLoading(true);
      const result = await listScenarios(projectId, { page: 1, page_size: 100 });
      setScenarios(result.items);
    } catch (error) {
      console.error("Failed to load scenarios:", error);
      toast.error(t("apiTests.loadScenariosFailed"));
    } finally {
      setLoading(false);
    }
  }, [projectId, testMode]);

  // 根据模式加载数据
  React.useEffect(() => {
    if (projectId) {
      if (testMode === "endpoint") {
        loadAPITests();
      } else {
        loadScenarios();
      }
    }
  }, [projectId, testMode, loadAPITests, loadScenarios]);

  const handleSelectFolder = (folder: FolderInfo | null) => {
    setSelectedFolderId(folder?.id || null);
    setSelectedFolderName(folder?.name);
    // 切换文件夹时清除选中的 endpoint，避免旧 endpoint 在新文件夹下不存在
    setSelectedEndpointId(null);
    setPage(1);
    setSelectedIds(new Set());
  };

  // 处理创建接口
  const handleCreateAPIEndpoint = (folderId?: string | null) => {
    setCreateEndpointDialogOpen(true);
  };

  // 处理接口创建成功
  const handleEndpointCreated = () => {
    loadAPITests();
    folderTreeRef.current?.refresh();
  };

  const handleTestCasesCountChange = async (count: number, endpointId?: string) => {
    const targetEndpointId = endpointId || selectedEndpointId || apiEndpoints[0]?.id;
    if (!targetEndpointId) return;

    setActualTestCasesCounts(prev => ({
      ...prev,
      [targetEndpointId]: count,
    }));

    setApiEndpoints(prev => prev.map(ep => {
      if (ep.id === targetEndpointId) {
        return { ...ep, total_test_cases: count };
      }
      return ep;
    }));
  };

  const handleExecuteScript = (artifactId: string, fileName: string, endpointId: string) => {
    const envHint = selectedEnvironment
      ? `\n**Environment ID**: ${selectedEnvironment.id}\n**Environment Name**: ${selectedEnvironment.name}`
      : selectedEnvironmentId
      ? `\n**Environment ID**: ${selectedEnvironmentId}`
      : "";

    const prompt = `${t("apiTests.executeTestPrompt")}:

**Script ID (Attachment ID)**: ${artifactId}
**Script File**: ${fileName}
**Endpoint ID**: ${endpointId}
**Project ID**: ${projectId}${envHint}

请使用 execute_api_script_by_artifact_id 工具执行此脚本，并确保生成 HTML 测试报告。`;

    setAiChatInitialPrompt(prompt);
    setAiChatKey(prev => prev + 1);
    setShowEndpointSidebar(false);
    setAiChatOpen(true);
  };

  const handleSelectScenario = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setShowScenarioSidebar(false); // 不自动打开详情侧边栏，避免遮挡编辑按钮
    setScenarioSidebarEditing(false);
    setScenarioViewMode("orchestrate");
  };

  const handleEditScenario = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setShowScenarioSidebar(true); // 点击编辑时打开详情侧边栏
    setScenarioSidebarEditing(true); // 并自动进入编辑模式
    setScenarioEditTrigger(prev => prev + 1); // 触发编辑模式（支持重复编辑同一场景）
    setScenarioViewMode("orchestrate");
  };

  const handleCloseScenarioSidebar = () => {
    setShowScenarioSidebar(false);
  };

  const handleOpenScenarioSidebar = () => {
    setShowScenarioSidebar(true);
  };

  const handleScenarioCreated = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setScenarioDialogOpen(false);
    setScenarioRefreshTrigger(prev => prev + 1);
    toast.success(t("apiTests.scenarioCreated"));
  };

  // 处理提交文件夹
  const handleSubmitFolder = async () => {
    if (!folderFormData.name.trim()) {
      toast.error(t("apiTests.folderNameRequired"));
      return;
    }
    try {
      setSubmitting(true);
      if (editingFolder) {
        // 编辑文件夹 - 使用本地更新
        const response = await updateFolder(projectId, editingFolder.id, folderFormData);
        toast.success(t("apiTests.folderUpdateSuccess"));
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
          folder_type: "api_test",  // 指定为 API 测试类型文件夹
        });
        toast.success(t("apiTests.folderCreateSuccess"));
        setFolderDialogOpen(false);
        // 本地添加文件夹
        if (response.success && response.data) {
          folderTreeRef.current?.addFolderLocally(response.data, folderParentId || null);
        }
      }
    } catch (error) {
      console.error("Failed to save folder:", error);
      toast.error(editingFolder ? t("apiTests.folderUpdateFailed") : t("apiTests.folderCreateFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 处理删除文件夹
  const handleDeleteFolder = async () => {
    if (!deletingFolder) return;

    try {
      await deleteFolder(projectId, deletingFolder.id);
      toast.success(t("apiTests.folderDeleteSuccess"));
      setDeleteFolderDialogOpen(false);
      setDeletingFolder(null);

      // 如果删除的是当前选中的文件夹，清空选中状态
      if (selectedFolderId === deletingFolder.id) {
        setSelectedFolderId(null);
        setSelectedFolderName(undefined);
        setApiEndpoints([]);
        setApiTests([]);
      }

      // 刷新文件夹树
      folderTreeRef.current?.refresh();
    } catch (error) {
      console.error("Failed to delete folder:", error);
      toast.error(t("apiTests.folderDeleteFailed"));
    }
  };

  // 移动文件夹成功回调 - 本地更新树
  const handleMoveFolderSuccess = (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => {
    folderTreeRef.current?.moveFolderLocally(folderId, newParentId, updatedFolder);
  };

  return (
    <MainLayout title={t("apiTests.title")}>
      <div className="relative flex h-[calc(100vh-8rem)] rounded-lg border bg-card overflow-hidden">
        <div className="flex h-full w-full">
          {/* 左侧面板 (320px) */}
          <div className="w-80 shrink-0 border-r bg-muted/10 flex flex-col">
            {/* 模式切换 Tab */}
            <div className="p-3 border-b bg-background">
              <Tabs value={testMode} onValueChange={(v) => setTestMode(v as TestMode)}>
                <TabsList className="w-full grid grid-cols-2">
                  <TabsTrigger value="endpoint" className="gap-1.5 data-[state=active]:bg-green-50 data-[state=active]:text-green-700 data-[state=active]:border-green-200">
                    <FileCode className="h-4 w-4" />
                    {t("apiTests.endpointTest")}
                  </TabsTrigger>
                  <TabsTrigger value="scenario" className="gap-1.5 data-[state=active]:bg-purple-50 data-[state=active]:text-purple-700 data-[state=active]:border-purple-200">
                    <Workflow className="h-4 w-4" />
                    {t("apiTests.scenarioTest")}
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {/* 文件夹树 / 场景列表 */}
            <div className="flex-1 overflow-hidden">
              {testMode === "endpoint" ? (
                <APIFolderTree
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
                  onCreateAPIEndpoint={handleCreateAPIEndpoint}
                  onSelectAPIEndpoint={(endpointId) => {
                    setSelectedEndpointId(endpointId);
                    setShowEndpointSidebar(true);
                  }}
                  selectedAPIEndpointId={selectedEndpointId}
                />
              ) : (
                <ScenarioListPanel
                  key={scenarioRefreshTrigger}
                  projectId={projectId}
                  selectedScenarioId={selectedScenarioId}
                  onSelectScenario={handleSelectScenario}
                  onEditScenario={handleEditScenario}
                  onViewExecutionHistory={(scenarioId) => {
                    setSelectedScenarioId(scenarioId);
                    setScenarioViewMode("monitor");
                  }}
                />
              )}
            </div>

            {/* 底部操作按钮 */}
            <div className="p-3 border-t bg-background">
              {testMode === "endpoint" ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start gap-2"
                  onClick={() => setAiGenerateDialogOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                  {t("apiTests.aiGenerateTests")}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start gap-2"
                  onClick={() => setScenarioDialogOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                  {t("apiTests.manuallyCreateScenario")}
                </Button>
              )}
            </div>
          </div>

          {/* 中间主区域 */}
          <div className="flex-1 flex flex-col min-h-0 bg-background">
            {/* 工具栏 */}
            <div className="flex items-center justify-between border-b px-4 py-3 bg-muted/20">
              <div className="flex items-center gap-2">
                {testMode === "endpoint" ? (
                  <>
                    <Layers className="h-5 w-5 text-blue-500" />
                    <div>
                      <h2 className="text-lg font-semibold">
                        {selectedFolderName || t("apiTests.allEndpoints")}
                      </h2>
                      <p className="text-xs text-muted-foreground">
                        {apiEndpoints.length}{t("apiTests.endpointsCount")}
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <Workflow className="h-5 w-5 text-purple-500" />
                    <div>
                      <h2 className="text-lg font-semibold">
                        {scenarioViewMode === "orchestrate" ? t("apiTests.scenarioOrchestration") : t("apiTests.executionMonitor")}
                      </h2>
                      <p className="text-xs text-muted-foreground">
                        {scenarios.length}{t("apiTests.scenariosCount")}
                      </p>
                    </div>
                  </>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* 环境选择器 */}
                <div className="mr-2">
                  <EnvironmentSelector onManage={() => setEnvironmentSheetOpen(true)} />
                </div>

                {testMode === "endpoint" ? (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setApiParseDialogOpen(true)}
                    >
                      <FileCode className="mr-2 h-4 w-4" />
                      {t("apiTests.parseAPI")}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => setAiChatOpen(true)}
                      className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all"
                    >
                      <MessageSquare className="mr-2 h-4 w-4" />
                      {t("apiTests.aiAssistant")}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="sm"
                      onClick={() => setAiGenerateScenarioDialogOpen(true)}
                      className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all gap-2"
                    >
                      <Sparkles className="h-4 w-4" />
                      {t("apiTests.aiGenerateScenarios")}
                    </Button>
                    <div className="flex bg-muted p-1 rounded-lg">
                      <Button
                        variant={scenarioViewMode === "orchestrate" ? "default" : "ghost"}
                        size="sm"
                        className="h-8 px-3"
                        onClick={() => setScenarioViewMode("orchestrate")}
                      >
                        <Layers className="h-4 w-4 mr-1" />
                        {t("apiTests.orchestrate")}
                      </Button>
                      <Button
                        variant={scenarioViewMode === "monitor" ? "default" : "ghost"}
                        size="sm"
                        className="h-8 px-3"
                        onClick={() => setScenarioViewMode("monitor")}
                      >
                        <Play className="h-4 w-4 mr-1" />
                        {t("apiTests.monitor")}
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => setAiChatOpen(true)}
                      className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-md hover:shadow-lg transition-all"
                    >
                      <MessageSquare className="mr-2 h-4 w-4" />
                      {t("apiTests.aiAssistant")}
                    </Button>
                  </>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (testMode === "endpoint") {
                      loadAPITests();
                    } else {
                      setScenarioRefreshTrigger(prev => prev + 1);
                    }
                  }}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* 模式内容区域 */}
            <div className="flex-1 overflow-hidden relative flex flex-col">
              {testMode === "endpoint" ? (
                <>
                  {/* 接口列表 - 上半部分 */}
                  <div className="max-h-[300px] overflow-y-auto border-b">
                    <APIEndpointList
                      endpoints={apiEndpoints}
                      loading={loading}
                      selectedEndpointId={selectedEndpointId}
                      actualTestCasesCounts={actualTestCasesCounts}
                      onSelectEndpoint={(endpointId) => {
                        setSelectedEndpointId(endpointId);
                        setShowEndpointSidebar(true);
                      }}
                      onSearch={() => {}}
                      folderName={selectedFolderName}
                    />
                  </div>

                  {/* 测试成果物 / 执行结果 - 下半部分 */}
                  <div className="flex-1 min-h-0 overflow-hidden bg-gradient-to-b from-muted/20 to-background p-6 flex flex-col">
                    <div className="max-w-7xl mx-auto w-full flex-1 flex flex-col min-h-0">
                      <Tabs
                        value={endpointTab}
                        onValueChange={(v) => setEndpointTab(v as EndpointTab)}
                        className="flex flex-col h-full"
                      >
                        <TabsList className="w-fit mb-4">
                          <TabsTrigger value="artifacts" className="gap-1.5">
                            <Zap className="h-4 w-4" />
                            {t("apiTests.testArtifacts")}
                          </TabsTrigger>
                          <TabsTrigger value="execution" className="gap-1.5">
                            <Play className="h-4 w-4" />
                            {t("apiTests.executionResults") || "执行结果"}
                          </TabsTrigger>
                        </TabsList>

                        <TabsContent value="artifacts" className="flex-1 min-h-0 overflow-y-auto mt-0">
                          {apiEndpoints.length === 0 ? (
                            <div className="text-center py-12 border-2 border-dashed rounded-lg bg-muted/10">
                              <FileCode className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                              <p className="text-lg font-medium mb-2">{t("apiTests.noEndpointData")}</p>
                              <p className="text-sm text-muted-foreground mb-4">
                                {t("apiTests.selectFolderOrImportAPI")}
                              </p>
                            </div>
                          ) : (
                            <EnhancedTestArtifactsPanel
                              key={`artifacts-${selectedEndpointId || apiEndpoints[0]?.id}`}
                              endpointId={selectedEndpointId || apiEndpoints[0]?.id}
                              projectId={projectId}
                              onRefresh={loadAPITests}
                              onTestCasesCountChange={handleTestCasesCountChange}
                              onExecuteScript={handleExecuteScript}
                              refreshTrigger={artifactsRefreshTrigger}
                            />
                          )}
                        </TabsContent>

                        <TabsContent value="execution" className="flex-1 min-h-0 overflow-hidden mt-0">
                          {apiEndpoints.length === 0 ? (
                            <div className="text-center py-12 border-2 border-dashed rounded-lg bg-muted/10">
                              <Play className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                              <p className="text-lg font-medium mb-2">{t("apiTests.noEndpointData")}</p>
                              <p className="text-sm text-muted-foreground mb-4">
                                {t("apiTests.selectFolderOrImportAPI")}
                              </p>
                            </div>
                          ) : (
                            <EndpointExecutionResultsPanel
                              endpointId={selectedEndpointId || apiEndpoints[0]?.id}
                              projectId={projectId}
                              refreshTrigger={artifactsRefreshTrigger}
                            />
                          )}
                        </TabsContent>
                      </Tabs>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* Scenario test mode */}
                  {scenarioViewMode === "orchestrate" ? (
                    <div className="flex-1 min-h-0 overflow-y-auto p-6">
                      <ScenarioOrchestrationView
                        projectId={projectId}
                        scenarioId={selectedScenarioId}
                        selectedEnvironmentId={selectedEnvironmentId}
                        onScenarioUpdate={() => setScenarioRefreshTrigger(prev => prev + 1)}
                        onOpenSidebar={handleOpenScenarioSidebar}
                        onScenarioNotFound={() => {
                          // 场景被删除（AI 同对话重生成会替换旧场景）：
                          // 清空失效的选中态并刷新列表，避免停留在旧 ID 上反复 404
                          setSelectedScenarioId(null);
                          setScenarioRefreshTrigger(prev => prev + 1);
                        }}
                      />
                    </div>
                  ) : (
                    <div className="flex-1 min-h-0 overflow-y-auto p-6">
                      <ScenarioExecutionMonitor
                        scenarioId={selectedScenarioId}
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* 右侧悬浮 AI 聊天面板 */}
          {assistant && (
            <div
              key={aiChatKey}
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
                      if (testMode === "endpoint") {
                        loadAPITests();
                        folderTreeRef.current?.refresh();
                        setArtifactsRefreshTrigger(prev => prev + 1);
                      } else {
                        setScenarioRefreshTrigger(prev => prev + 1);
                      }
                    }}
                    onArtifactSaved={() => {
                      if (testMode === "endpoint") {
                        setArtifactsRefreshTrigger(prev => prev + 1);
                      }
                    }}
                  />
                </ClientProvider>
              )}
            </div>
          )}

          {/* 右侧悬浮详情侧边栏 */}
          {testMode === "endpoint" && showEndpointSidebar && selectedEndpointId && (
            <div
              className={cn(
                "absolute right-0 top-0 z-30 h-full w-[600px] bg-background transition-transform duration-300 ease-in-out border-l shadow-xl",
                showEndpointSidebar ? "translate-x-0" : "translate-x-full"
              )}
            >
              <APIEndpointSidebar
                endpointId={selectedEndpointId}
                projectId={projectId}
                onClose={() => {
                  setShowEndpointSidebar(false);
                  setSelectedEndpointId(null);
                  loadAPITests();
                }}
                onGenerateTest={() => {
                  setShowEndpointSidebar(false);
                  setAiChatOpen(true);
                  setAiChatInitialPrompt(t("apiTests.generateTestsForEndpoint", { id: selectedEndpointId }));
                }}
                onOpenAIChat={(prompt) => {
                  setAiChatInitialPrompt(prompt);
                  setAiChatKey(prev => prev + 1);
                  setShowEndpointSidebar(false);
                  setAiChatOpen(true);
                }}
                onRefresh={() => {
                  loadAPITests();
                  folderTreeRef.current?.refresh();
                }}
              />
            </div>
          )}

          {testMode === "scenario" && showScenarioSidebar && selectedScenarioId && (
            <div
              className={cn(
                "absolute right-0 top-0 z-30 h-full w-[500px] bg-background transition-transform duration-300 ease-in-out border-l shadow-xl",
                showScenarioSidebar ? "translate-x-0" : "translate-x-full"
              )}
            >
              <ScenarioDetailSidebar
                scenarioId={selectedScenarioId}
                projectId={projectId}
                selectedEnvironmentId={selectedEnvironmentId}
                defaultEditing={scenarioSidebarEditing}
                editTrigger={scenarioEditTrigger}
                onClose={() => {
                  setShowScenarioSidebar(false);
                  setScenarioSidebarEditing(false);
                }}
                onScenarioUpdated={() => {
                  setScenarioRefreshTrigger(prev => prev + 1);
                  setScenarioSidebarEditing(false);
                }}
                onOpenAIChat={(prompt) => {
                  // 关闭侧边栏
                  setShowScenarioSidebar(false);
                  setScenarioSidebarEditing(false);
                  // 打开 AI 助手
                  setAiChatInitialPrompt(prompt);
                  setAiChatKey(prev => prev + 1);
                  setAiChatOpen(true);
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* 环境配置 Sheet */}
      <EnvironmentSheet
        projectId={projectId}
        open={environmentSheetOpen}
        onOpenChange={setEnvironmentSheetOpen}
        onEnvironmentsChange={() => {
          refreshEnvironments();
        }}
      />

      {/* 各种对话框 */}
        {/* API解析对话框 */}
        <APIParseDialog
          open={apiParseDialogOpen}
          onOpenChange={setApiParseDialogOpen}
          projectIdentifier={projectId}
          onSuccess={() => {
            toast.success(t("apiTests.apiDocParseSuccess"));
            loadAPITests();
            folderTreeRef.current?.refresh();
          }}
        />

        {/* AI生成测试对话框 */}
        <AIGenerateAPITestDialog
          open={aiGenerateDialogOpen}
          onOpenChange={setAiGenerateDialogOpen}
          projectIdentifier={projectId}
          onSuccess={() => {
            loadAPITests();
            folderTreeRef.current?.refresh();
          }}
          onOpenChat={(prompt) => {
            setAiChatInitialPrompt(prompt);
            setAiChatKey(prev => prev + 1);
            setAiGenerateDialogOpen(false);
            setAiChatOpen(true);
          }}
        />

        {/* 创建接口对话框 */}
        <CreateEndpointDialog
          open={createEndpointDialogOpen}
          onOpenChange={setCreateEndpointDialogOpen}
          projectId={projectId}
          folderId={selectedFolderId}
          onSuccess={handleEndpointCreated}
        />

        {/* 场景AI生成对话框 */}
        <AIGenerateScenarioDialog
          open={aiGenerateScenarioDialogOpen}
          onOpenChange={setAiGenerateScenarioDialogOpen}
          projectIdentifier={projectId}
          onOpenChat={(prompt) => {
            setAiChatInitialPrompt(prompt);
            setAiChatKey(prev => prev + 1);
            setAiChatOpen(true);
          }}
        />

        {/* 场景创建对话框 */}
        <ScenarioCreateDialog
          open={scenarioDialogOpen}
          onOpenChange={setScenarioDialogOpen}
          projectId={projectId}
          onSuccess={handleScenarioCreated}
        />

        {/* 文件夹对话框 */}
        <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingFolder ? t("apiTests.editFolder") : t("apiTests.createFolder")}
              </DialogTitle>
              <DialogDescription>
                {editingFolder ? t("apiTests.editFolderInfo") : t("apiTests.createNewFolder")}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="folder-name">{t("apiTests.folderNameLabel")}</Label>
                <Input
                  id="folder-name"
                  value={folderFormData.name}
                  onChange={(e) =>
                    setFolderFormData({ ...folderFormData, name: e.target.value })
                  }
                  placeholder={t("apiTests.enterFolderName")}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="folder-description">{t("apiTests.descriptionLabel")}</Label>
                <Textarea
                  id="folder-description"
                  value={folderFormData.description}
                  onChange={(e) =>
                    setFolderFormData({
                      ...folderFormData,
                      description: e.target.value,
                    })
                  }
                  placeholder={t("apiTests.enterDescription")}
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
              <DialogTitle>{t("apiTests.deleteFolderTitle")}</DialogTitle>
              <DialogDescription>
                {t("apiTests.deleteFolderMessage", { name: deletingFolder?.name || "" })}
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
        {/* 移动文件夹对话框 */}
        <MoveFolderDialog
          open={moveFolderDialogOpen}
          onOpenChange={setMoveFolderDialogOpen}
          projectId={projectId}
          folder={movingFolder}
          folderType="api_test"
          onMoveSuccess={handleMoveFolderSuccess}
        />
      </MainLayout>
    );
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlVSaVdBPT06MmUzZDY0N2Y=
