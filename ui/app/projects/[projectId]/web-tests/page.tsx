"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0ZGMk5RPT06N2Y2NWVlMGM=

import * as React from "react";
import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";
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
  batchRunWebFunctions,
  type WebFunction,
  type WebSubFunction,
  type CreateWebFunctionRequest,
} from "@/lib/api/web-functions";
import {
  createFolder,
  updateFolder,
  deleteFolder,
} from "@/lib/api/folders";
import { listEnvironments, updateEnvironment } from "@/lib/api/environments";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getAttachmentDownloadUrl } from "@/lib/api/attachments";
import {
  generateStorageState,
  getLatestStorageState,
  getStorageStateJob,
  type StorageStateGenerateRequest,
  type StorageStateLatestInfo,
  type StorageStateJobInfo,
} from "@/lib/api/storage-state";
import type {
  FolderInfo,
  FolderCreate,
  EnvironmentInfo,
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
  const router = useRouter();
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
  const [batchRunning, setBatchRunning] = React.useState(false);
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

  // 登录态管理
  const [defaultEnv, setDefaultEnv] = React.useState<EnvironmentInfo | null>(null);
  const [storageStateStatus, setStorageStateStatus] = React.useState<"none" | "ok" | "expired">("none");
  const [storageStateGeneratedAt, setStorageStateGeneratedAt] = React.useState<string | null>(null);
  const [storageStateDialogOpen, setStorageStateDialogOpen] = React.useState(false);
  const [generatingStorageState, setGeneratingStorageState] = React.useState(false);
  const [storageStateForm, setStorageStateForm] = React.useState<StorageStateGenerateRequest>({
    password: "",
    captcha: "",
    selectors: {
      login_url: "",
      username_selector: "",
      password_selector: "",
      captcha_selector: "",
      submit_selector: "",
      success_selector: "",
    },
  });
  const [storageStateJobResult, setStorageStateJobResult] = React.useState<StorageStateJobInfo | null>(null);
  const [screenshotPreviewOpen, setScreenshotPreviewOpen] = React.useState(false);
  const [screenshotPreviewUrl, setScreenshotPreviewUrl] = React.useState<string | null>(null);

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

  // 加载默认环境
  const loadDefaultEnvironment = React.useCallback(async () => {
    try {
      const response = await listEnvironments(projectId);
      const envs = (response as any).data || (response as any).items || [];
      const defaultEnv = envs.find((e: EnvironmentInfo) => e.is_default) || envs[0] || null;
      setDefaultEnv(defaultEnv);
    } catch (error) {
      console.error("Failed to load environments:", error);
    }
  }, [projectId]);

  // 加载登录态状态
  const loadStorageStateStatus = React.useCallback(
    async (envId: string) => {
      try {
        const response = await getLatestStorageState(projectId, envId);
        const data: StorageStateLatestInfo | null = (response as any).data ?? null;
        if (!data) {
          setStorageStateStatus("none");
          setStorageStateGeneratedAt(null);
          return;
        }
        const generatedAt = new Date(data.generated_at);
        const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
        setStorageStateGeneratedAt(data.generated_at);
        setStorageStateStatus(generatedAt > sevenDaysAgo ? "ok" : "expired");
      } catch (error) {
        console.error("Failed to load storage state:", error);
        setStorageStateStatus("none");
      }
    },
    [projectId]
  );

  // 根据模式加载数据
  React.useEffect(() => {
    if (projectId) {
      loadWebFunctions();
      loadDefaultEnvironment();
    }
  }, [projectId, testMode, loadWebFunctions, loadDefaultEnvironment]);

  // 默认环境变化后加载登录态状态
  React.useEffect(() => {
    if (defaultEnv?.id) {
      loadStorageStateStatus(defaultEnv.id);
    }
  }, [defaultEnv, loadStorageStateStatus]);

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

  // 打开登录态弹窗，优先从环境 auth_config.storage_state 预填充
  const handleOpenStorageStateDialog = () => {
    const authConfig = (defaultEnv?.auth_config as any) || {};
    const stored = authConfig.storage_state || authConfig.form_login || {};
    const storedSelectors = stored.selectors || {};
    setStorageStateForm((prev) => ({
      password: stored.password || "",
      captcha: "",
      username: stored.username || "",
      selectors: {
        login_url: stored.login_url || prev.selectors?.login_url || "",
        username_selector: storedSelectors.username_selector || "",
        password_selector: storedSelectors.password_selector || "",
        captcha_selector: storedSelectors.captcha_selector || "",
        submit_selector: storedSelectors.submit_selector || "",
        success_selector: storedSelectors.success_selector || "",
      },
    }));
    setStorageStateJobResult(null);
    setStorageStateDialogOpen(true);
  };

  // 轮询登录态生成任务
  const pollStorageStateJob = React.useCallback(
    async (jobId: string, envId: string) => {
      const maxAttempts = 120; // 最多轮询 120 次，每次 2 秒
      for (let i = 0; i < maxAttempts; i++) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const response = await getStorageStateJob(projectId, envId, jobId);
        const job = (response as any).data as StorageStateJobInfo;
        if (job?.status === "completed") {
          toast.success("登录态已更新，后续 Web 测试将自动携带会话");
          setStorageStateJobResult(null);
          // 成功后把本次输入的选择器保存到环境配置，下次打开自动回填
          try {
            await updateEnvironment(projectId, envId, {
              auth_config: {
                ...(defaultEnv?.auth_config || {}),
                storage_state: {
                  username: storageStateForm.username,
                  password: storageStateForm.password,
                  login_url: storageStateForm.selectors?.login_url,
                  selectors: storageStateForm.selectors,
                },
              },
            });
          } catch (saveErr) {
            console.error("Failed to save storage state selectors:", saveErr);
          }
          await loadStorageStateStatus(envId);
          return;
        }
        if (job?.status === "failed") {
          setStorageStateJobResult(job);
          toast.error(`登录态生成失败：${job.error_message || "未知错误"}`);
          return;
        }
      }
      setStorageStateJobResult(null);
      toast.warning("登录态生成超时，请稍后刷新页面查看状态");
    },
    [projectId, loadStorageStateStatus, defaultEnv, storageStateForm]
  );

  // 提交登录态生成
  const handleSubmitStorageState = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!defaultEnv?.id) {
      toast.error("未找到默认环境，无法生成登录态");
      return;
    }
    if (!storageStateForm.password) {
      toast.error("密码不能为空");
      return;
    }
    if (!storageStateForm.selectors?.login_url) {
      toast.error("登录页 URL 不能为空");
      return;
    }
    const hasCaptchaValue = Boolean(storageStateForm.captcha?.trim());
    const hasCaptchaSelector = Boolean(storageStateForm.selectors?.captcha_selector?.trim());
    if (hasCaptchaValue !== hasCaptchaSelector) {
      toast.error("验证码和验证码选择器需同时填写或同时留空");
      return;
    }

    setGeneratingStorageState(true);
    setStorageStateJobResult(null);
    try {
      const response = await generateStorageState(projectId, defaultEnv.id, storageStateForm);
      const job = (response as any).data;
      toast.info("正在后台生成登录态...");
      await pollStorageStateJob(job.job_id, defaultEnv.id);
    } catch (error: any) {
      console.error("Failed to generate storage state:", error);
      toast.error(error?.message || "生成登录态失败");
    } finally {
      setGeneratingStorageState(false);
    }
  };

  const handleViewScreenshot = async (attachmentId: string) => {
    setScreenshotPreviewUrl(null);
    try {
      const url = await getAttachmentDownloadUrl(projectId, attachmentId);
      setScreenshotPreviewUrl(url);
      setScreenshotPreviewOpen(true);
    } catch (error: any) {
      console.error("Failed to get screenshot url:", error);
      toast.error("获取截图链接失败");
    }
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

请按以下步骤执行测试并保存报告：
1. 使用 \`download_web_script\` 工具下载脚本到测试工作目录（参数：script_id="${artifactId}"）
2. 使用 \`execute_web_script\` 工具执行测试（参数：local_script_path=从步骤1获取的路径、framework="playwright"、reporter="html"、project_identifier="${projectId}"、sub_function_id="${selectedSubFunctionId || ""}"）
3. 从步骤2返回的 execution_result 中提取：
   - stats（total/passed/failed/skipped）
   - cases（用例级结果：title/status/duration_ms/error）
   - screenshots（截图文件路径列表）
   - videos（视频文件路径列表）
4. 生成 Markdown 格式执行摘要（包含执行统计、关键失败信息）
5. **必须**调用 \`save_web_test_report(test_run_id=<步骤2返回的 test_run_id>, report_content=<Markdown 摘要>, screenshots=<截图路径列表>, videos=<视频路径列表>, execution_info=<步骤2的 execution_result>, project_identifier="${projectId}")\` 将执行摘要持久化到成果物面板；该摘要会内嵌截图、视频和执行信息
6. 向用户报告：完整 HTML 报告附件 ID（report_attachment_id，含截图/视频/trace）和执行摘要附件 ID（save_web_test_report 返回的 attachment_id）
7. （可选）使用 \`delete_web_script\` 清理临时脚本`;

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

  // 处理批量运行 Web 功能
  const handleBatchRun = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    try {
      setBatchRunning(true);
      const result = await batchRunWebFunctions(projectId, {
        function_ids: ids,
      });
      toast.success(
        `批量运行已提交: ${result.identifier} (${result.job_count} 个脚本)`
      );
      setSelectedIds(new Set());
      router.push(`/projects/${projectId}/test-runs/${result.identifier}`);
    } catch (error: any) {
      console.error("Failed to batch run web functions:", error);
      console.error("Error details:", {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      toast.error(`批量运行失败: ${error.message || "Unknown error"}`);
    } finally {
      setBatchRunning(false);
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
                  onClick={handleOpenStorageStateDialog}
                  className={cn(
                    "relative",
                    storageStateStatus === "ok" && "border-green-500 text-green-700 hover:bg-green-50",
                    storageStateStatus === "expired" && "border-red-500 text-red-700 hover:bg-red-50"
                  )}
                >
                  <Globe className="mr-2 h-4 w-4" />
                  登录态
                  {storageStateStatus === "ok" && (
                    <Badge variant="default" className="ml-2 h-5 bg-green-500 hover:bg-green-500 text-[10px]">
                      已配置
                    </Badge>
                  )}
                  {storageStateStatus === "expired" && (
                    <Badge variant="destructive" className="ml-2 h-5 text-[10px]">
                      已过期
                    </Badge>
                  )}
                  {storageStateStatus === "none" && (
                    <Badge variant="secondary" className="ml-2 h-5 text-[10px]">
                      未配置
                    </Badge>
                  )}
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
                  onBatchRun={handleBatchRun}
                  batchRunning={batchRunning}
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
                      loadWebFunctions();
                      folderTreeRef.current?.refresh();
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

        {/* 登录态管理对话框 */}
        <Dialog
          open={storageStateDialogOpen}
          onOpenChange={(open) => {
            if (!open) {
              setStorageStateJobResult(null);
            }
            setStorageStateDialogOpen(open);
          }}
        >
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>登录态管理</DialogTitle>
              <DialogDescription>
                配置表单登录信息并生成 Playwright storageState，后续 Web 测试将自动携带已登录会话。
                {storageStateGeneratedAt && (
                  <span className="block mt-1">
                    最近生成时间：{new Date(storageStateGeneratedAt).toLocaleString()}
                  </span>
                )}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmitStorageState}>
              <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
                <div className="space-y-2">
                  <Label htmlFor="ss-username">用户名</Label>
                  <Input
                    id="ss-username"
                    value={storageStateForm.username || ""}
                    onChange={(e) =>
                      setStorageStateForm({ ...storageStateForm, username: e.target.value })
                    }
                    placeholder="输入登录账号"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ss-password">密码</Label>
                  <Input
                    id="ss-password"
                    value={storageStateForm.password}
                    onChange={(e) =>
                      setStorageStateForm({ ...storageStateForm, password: e.target.value })
                    }
                    placeholder="输入登录密码"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ss-captcha">验证码</Label>
                  <Input
                    id="ss-captcha"
                    value={storageStateForm.captcha || ""}
                    onChange={(e) =>
                      setStorageStateForm({ ...storageStateForm, captcha: e.target.value })
                    }
                    placeholder="输入当前验证码（如页面无需验证码请留空）"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ss-login-url">登录页 URL</Label>
                  <Input
                    id="ss-login-url"
                    value={storageStateForm.selectors?.login_url || ""}
                    onChange={(e) =>
                      setStorageStateForm({
                        ...storageStateForm,
                        selectors: { ...storageStateForm.selectors, login_url: e.target.value },
                      })
                    }
                    placeholder="https://example.com/login"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="ss-username-selector">用户名选择器</Label>
                    <Input
                      id="ss-username-selector"
                      value={storageStateForm.selectors?.username_selector || ""}
                      onChange={(e) =>
                        setStorageStateForm({
                          ...storageStateForm,
                          selectors: { ...storageStateForm.selectors, username_selector: e.target.value },
                        })
                      }
                      placeholder="input[data-test='username']"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ss-password-selector">密码选择器</Label>
                    <Input
                      id="ss-password-selector"
                      value={storageStateForm.selectors?.password_selector || ""}
                      onChange={(e) =>
                        setStorageStateForm({
                          ...storageStateForm,
                          selectors: { ...storageStateForm.selectors, password_selector: e.target.value },
                        })
                      }
                      placeholder="input[data-test='password']"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ss-captcha-selector">验证码选择器</Label>
                    <Input
                      id="ss-captcha-selector"
                      value={storageStateForm.selectors?.captcha_selector || ""}
                      onChange={(e) =>
                        setStorageStateForm({
                          ...storageStateForm,
                          selectors: { ...storageStateForm.selectors, captcha_selector: e.target.value },
                        })
                      }
                      placeholder="input[data-test='captcha']（无需验证码请留空）"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ss-submit-selector">提交按钮选择器</Label>
                    <Input
                      id="ss-submit-selector"
                      value={storageStateForm.selectors?.submit_selector || ""}
                      onChange={(e) =>
                        setStorageStateForm({
                          ...storageStateForm,
                          selectors: { ...storageStateForm.selectors, submit_selector: e.target.value },
                        })
                      }
                      placeholder="input[data-test='login-button']"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ss-success-selector">成功标识选择器</Label>
                    <Input
                      id="ss-success-selector"
                      value={storageStateForm.selectors?.success_selector || ""}
                      onChange={(e) =>
                        setStorageStateForm({
                          ...storageStateForm,
                          selectors: { ...storageStateForm.selectors, success_selector: e.target.value },
                        })
                      }
                      placeholder="[data-test='inventory-container']"
                    />
                  </div>
                </div>
              </div>

              {storageStateJobResult?.status === "failed" && (
                <div className="space-y-3 rounded-md border border-destructive/50 bg-destructive/5 p-3">
                  <div className="text-sm font-medium text-destructive">
                    生成失败
                  </div>
                  {storageStateJobResult.error_message && (
                    <p className="text-sm text-destructive whitespace-pre-wrap">
                      {storageStateJobResult.error_message}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {storageStateJobResult.failure_screenshot_attachment_id && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleViewScreenshot(storageStateJobResult.failure_screenshot_attachment_id!)
                        }
                      >
                        查看截图
                      </Button>
                    )}
                  </div>
                  {(storageStateJobResult.stdout || storageStateJobResult.stderr) && (
                    <div className="space-y-2">
                      {storageStateJobResult.stdout && (
                        <Collapsible>
                          <CollapsibleTrigger asChild>
                            <Button type="button" variant="ghost" size="sm" className="h-auto p-0 text-xs">
                              <ChevronDown className="h-3 w-3 mr-1" />
                              查看 stdout
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <ScrollArea className="h-40 w-full rounded-md border bg-muted/50 p-2">
                              <pre className="text-xs whitespace-pre-wrap break-all">
                                {storageStateJobResult.stdout}
                              </pre>
                            </ScrollArea>
                          </CollapsibleContent>
                        </Collapsible>
                      )}
                      {storageStateJobResult.stderr && (
                        <Collapsible>
                          <CollapsibleTrigger asChild>
                            <Button type="button" variant="ghost" size="sm" className="h-auto p-0 text-xs">
                              <ChevronDown className="h-3 w-3 mr-1" />
                              查看 stderr
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <ScrollArea className="h-40 w-full rounded-md border bg-muted/50 p-2">
                              <pre className="text-xs whitespace-pre-wrap break-all">
                                {storageStateJobResult.stderr}
                              </pre>
                            </ScrollArea>
                          </CollapsibleContent>
                        </Collapsible>
                      )}
                    </div>
                  )}
                </div>
              )}

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setStorageStateDialogOpen(false)}
                  disabled={generatingStorageState}
                >
                  取消
                </Button>
                <Button type="submit" disabled={generatingStorageState}>
                  {generatingStorageState ? "生成中..." : "生成登录态"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* 失败截图预览 */}
        <Dialog open={screenshotPreviewOpen} onOpenChange={setScreenshotPreviewOpen}>
          <DialogContent className="max-w-5xl">
            <DialogHeader>
              <DialogTitle>登录态生成失败截图</DialogTitle>
              <DialogDescription>失败时 Playwright 截取的全屏页面快照</DialogDescription>
            </DialogHeader>
            <div className="flex items-center justify-center overflow-auto py-2">
              {screenshotPreviewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={screenshotPreviewUrl}
                  alt="登录态生成失败截图"
                  className="max-w-full rounded-md border"
                />
              ) : (
                <div className="text-sm text-muted-foreground">加载中...</div>
              )}
            </div>
            <DialogFooter>
              <Button type="button" onClick={() => setScreenshotPreviewOpen(false)}>
                关闭
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
