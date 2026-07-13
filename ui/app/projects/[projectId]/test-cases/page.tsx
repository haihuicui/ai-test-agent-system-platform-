"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWprd2VBPT06ODAxNDMxNTY=

import * as React from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { MainLayout } from "@/components/layout";
import { useLanguage } from "@/providers/LanguageProvider";
import {
  FolderTree,
  TestCaseList,
} from "@/components/test-cases";
import type { FolderTreeRef } from "@/components/test-cases";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { TestCaseFilters } from "@/components/test-cases";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ClientProvider } from "@/providers/ClientProvider";
import { useDelayedUnmount } from "@/hooks/useDelayedUnmount";
import { Assistant } from "@langchain/langgraph-sdk";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getTestCases,
  getFolderTestCases,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  bulkDeleteTestCases,
} from "@/lib/api/testCases";
import {
  createFolder,
  updateFolder,
  deleteFolder,
} from "@/lib/api/folders";
import type {
  TestCaseInfo,
  TestCaseCreate,
  FolderInfo,
  FolderCreate,
  Priority,
  TestCaseState,
} from "@/lib/api/types";
import { AIChatSkeleton } from "@/components/langgraph/ai-chat-skeleton";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWprd2VBPT06ODAxNDMxNTY=

// 重型对话框与 AI 聊天面板代码分割
const AIChatContainer = dynamic(
  () =>
    import("@/components/langgraph/AIChatContainer").then((m) => ({
      default: m.AIChatContainer,
    })),
  { ssr: false, loading: () => <AIChatSkeleton /> }
);

const TestCaseDialog = dynamic(
  () =>
    import("@/components/test-cases/test-case-dialog").then((m) => ({
      default: m.TestCaseDialog,
    })),
  { ssr: false }
);

const AIGenerateDialog = dynamic(
  () =>
    import("@/components/test-cases/ai-generate-dialog").then((m) => ({
      default: m.AIGenerateDialog,
    })),
  { ssr: false }
);

const AIGenerateFromDocumentDialog = dynamic(
  () =>
    import("@/components/test-cases/ai-generate-from-document-dialog").then(
      (m) => ({ default: m.AIGenerateFromDocumentDialog })
    ),
  { ssr: false }
);

const BulkEditDialog = dynamic(
  () =>
    import("@/components/test-cases/bulk-edit-dialog").then((m) => ({
      default: m.BulkEditDialog,
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


export default function TestCasesPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { t } = useLanguage();

  // 文件夹树 ref
  const folderTreeRef = React.useRef<FolderTreeRef>(null);

  // 状态
  const [testCases, setTestCases] = React.useState<TestCaseInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(
    null
  );
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());

  // 分页
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);
  const [total, setTotal] = React.useState(0);

  // 筛选 - 改用新的筛选接口
  const [searchQuery, setSearchQuery] = React.useState("");
  const [priorityFilter, setPriorityFilter] = React.useState<Priority | undefined>(undefined);
  const [statusFilter, setStatusFilter] = React.useState<TestCaseState | undefined>(undefined);

  // 可用的标签和负责人（从测试用例列表中提取）
  const [availableTags, setAvailableTags] = React.useState<string[]>([]);
  const [availableOwners, setAvailableOwners] = React.useState<string[]>([]);

  // 测试用例对话框
  const [testCaseDialogOpen, setTestCaseDialogOpen] = React.useState(false);
  const [editingTestCase, setEditingTestCase] =
    React.useState<TestCaseInfo | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  // 删除确认对话框
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [deletingTestCase, setDeletingTestCase] =
    React.useState<TestCaseInfo | null>(null);

  // 批量删除确认对话框
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = React.useState(false);

  // 批量编辑对话框
  const [bulkEditDialogOpen, setBulkEditDialogOpen] = React.useState(false);

  // 文件夹对话框
  const [folderDialogOpen, setFolderDialogOpen] = React.useState(false);
  const [editingFolder, setEditingFolder] = React.useState<FolderInfo | null>(
    null
  );
  const [folderParentId, setFolderParentId] = React.useState<string | undefined>();
  const [folderFormData, setFolderFormData] = React.useState<FolderCreate>({
    name: "",
    description: "",
  });

  // 删除文件夹对话框
  const [deleteFolderDialogOpen, setDeleteFolderDialogOpen] =
    React.useState(false);
  const [deletingFolder, setDeletingFolder] = React.useState<FolderInfo | null>(
    null
  );

  // 创建测试用例时指定的文件夹
  const [createTestCaseFolder, setCreateTestCaseFolder] = React.useState<FolderInfo | null>(null);

  // 当前选中的文件夹名称
  const [selectedFolderName, setSelectedFolderName] = React.useState<string | undefined>();

  // 加载测试用例
  const loadTestCases = React.useCallback(async () => {
    try {
      setLoading(true);
      const params = {
        p: page,
        page_size: pageSize,
        search: searchQuery || undefined,
        priority: priorityFilter,
        status: statusFilter,
      };

      let response;
      if (selectedFolderId) {
        response = await getFolderTestCases(projectId, selectedFolderId, params);
      } else {
        response = await getTestCases(projectId, params);
      }

      if (response.success) {
        const cases = response.data || response.test_cases || [];
        setTestCases(cases);
        setTotal(response.info?.total || 0);

        // 提取可用的标签和负责人
        const tags = new Set<string>();
        const owners = new Set<string>();
        cases.forEach((tc: TestCaseInfo) => {
          tc.tags?.forEach((tag) => tags.add(tag));
          if (tc.owner || tc.created_by) {
            owners.add(tc.owner || tc.created_by!);
          }
        });
        setAvailableTags(Array.from(tags));
        setAvailableOwners(Array.from(owners));
      }
    } catch (error) {
      console.error("Failed to load test cases:", error);
      toast.error(t("testCases.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedFolderId, page, pageSize, searchQuery, priorityFilter, statusFilter]);

  React.useEffect(() => {
    if (projectId) {
      loadTestCases();
    }
  }, [projectId, loadTestCases]);

  // 选择文件夹
  const handleSelectFolder = (folder: FolderInfo | null) => {
    setSelectedFolderId(folder?.id || null);
    setSelectedFolderName(folder?.name);
    setPage(1);
    setSelectedIds(new Set());
  };

  // 筛选变化处理
  const handleFilterChange = React.useCallback((filters: TestCaseFilters) => {
    setSearchQuery(filters.search);
    setPriorityFilter(filters.priority);
    setStatusFilter(filters.status);
    setPage(1); // 筛选变化时重置页码
    setSelectedIds(new Set()); // 清空选择
  }, []);

  // 创建/编辑测试用例
  const handleSubmitTestCase = async (data: TestCaseCreate) => {
    try {
      setSubmitting(true);
      if (editingTestCase) {
        await updateTestCase(projectId, editingTestCase.id, data);
        toast.success(t("testCases.updateSuccess"));
      } else {
        // 优先使用从文件夹菜单指定的文件夹
        const targetFolderId = createTestCaseFolder?.id || selectedFolderId;
        await createTestCase(projectId, targetFolderId, data);
        toast.success(t("testCases.createSuccess"));
      }
      setTestCaseDialogOpen(false);
      setEditingTestCase(null);
      setCreateTestCaseFolder(null);
      loadTestCases();
      // 刷新文件夹树以更新用例计数（测试用例操作需要刷新计数）
      folderTreeRef.current?.refresh();
    } catch (error) {
      console.error("Failed to save test case:", error);
      toast.error(editingTestCase ? t("testCases.updateFailed") : t("testCases.createFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 从文件夹菜单创建测试用例
  const handleCreateTestCaseInFolder = (folder: FolderInfo) => {
    setCreateTestCaseFolder(folder);
    setEditingTestCase(null);
    setTestCaseDialogOpen(true);
  };

  // 批量删除测试用例
  const handleBulkDelete = () => {
    if (selectedIds.size === 0) {
      toast.error(t("testCases.selectToDelete"));
      return;
    }
    setBulkDeleteDialogOpen(true);
  };

  // 批量编辑测试用例
  const handleBulkEdit = () => {
    if (selectedIds.size === 0) {
      toast.error(t("testCases.selectToEdit"));
      return;
    }
    setBulkEditDialogOpen(true);
  };

  const handleBulkEditSuccess = () => {
    setSelectedIds(new Set());
    loadTestCases();
    folderTreeRef.current?.refresh();
  };

  const confirmBulkDelete = async () => {
    try {
      const idsArray = Array.from(selectedIds);
      const response = await bulkDeleteTestCases(projectId, idsArray);

      if (response.success) {
        toast.success(response.message || t("testCases.bulkDeleteSuccess", { count: response.affected_count.toString() }));
        setSelectedIds(new Set());
        setBulkDeleteDialogOpen(false);
        loadTestCases();
        folderTreeRef.current?.refresh();
      } else {
        toast.error(t("testCases.bulkDeleteFailed"));
      }
    } catch (error) {
      console.error("Failed to bulk delete test cases:", error);
      toast.error(t("testCases.bulkDeleteFailedRetry"));
    }
  };

  // 移动文件夹状态
  const [moveFolderDialogOpen, setMoveFolderDialogOpen] = React.useState(false);
  const [movingFolder, setMovingFolder] = React.useState<FolderInfo | null>(null);

  // AI生成对话框状态
  const [aiGenerateDialogOpen, setAiGenerateDialogOpen] = React.useState(false);
  const [aiGenerateFromDocDialogOpen, setAiGenerateFromDocDialogOpen] = React.useState(false);

  // AI聊天面板状态
  const [aiChatOpen, setAiChatOpen] = React.useState(false);
  const renderAIChat = useDelayedUnmount(aiChatOpen, 300);
  const [aiChatInitialPrompt, setAiChatInitialPrompt] = React.useState<string>("");
  const [aiChatKey, setAiChatKey] = React.useState<number>(0);
  const [assistant, setAssistant] = React.useState<Assistant | null>(null);

  // 初始化 Assistant
  React.useEffect(() => {
    const initAssistant = async () => {
      try {
        const assistantId = "testcase_generator_agent";
        const mockAssistant: Assistant = {
          assistant_id: assistantId,
          graph_id: assistantId,
          config: {
            configurable: {
              // 添加上下文信息，供智能体使用
              project_identifier: projectId,
              folder_id: selectedFolderId || "",
              template_type: "test_case", // 默认使用普通测试用例模板
            }
          },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: {},
          version: 1,
          name: t("testCases.aiAssistantName"),
          context: {},
        };
        setAssistant(mockAssistant);
      } catch (error) {
        console.error("Failed to initialize assistant:", error);
      }
    };
    initAssistant();
  }, [projectId, selectedFolderId]); // 当 projectId 或 selectedFolderId 变化时重新初始化

  // 移动文件夹
  const handleMoveFolder = (folder: FolderInfo) => {
    setMovingFolder(folder);
    setMoveFolderDialogOpen(true);
  };

  // AI生成成功回调
  const handleAIGenerateSuccess = (testCases: TestCaseInfo[]) => {
    toast.success(t("testCases.aiGenerateSuccess", { count: testCases.length.toString() }));
    loadTestCases();
    folderTreeRef.current?.refresh();
  };

  // 从对话框打开AI聊天面板
  const handleOpenAIChatFromDialog = (prompt: string) => {
    // 设置初始提示词并更新 key 以创建新对话
    setAiChatInitialPrompt(prompt);
    setAiChatKey(prev => prev + 1); // 更新 key 强制重新挂载，创建新对话

    setAiChatOpen(true);
    // 关闭生成对话框
    setAiGenerateDialogOpen(false);
    setAiGenerateFromDocDialogOpen(false);
  };

  // 移动文件夹成功回调 - 本地更新树
  const handleMoveFolderSuccess = (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => {
    folderTreeRef.current?.moveFolderLocally(folderId, newParentId, updatedFolder);
  };

  // 快速创建测试用例
  const handleQuickCreateTestCase = async (title: string, template: "test_case" | "test_case_bdd") => {
    try {
      const data: TestCaseCreate = {
        name: title,
        priority: "medium",
        case_type: "functional",
        template,
      };

      // BDD 测试用例需要提供 feature 和 scenario
      if (template === "test_case_bdd") {
        data.feature = `Feature: ${title}`;
        data.scenario = `Scenario: 验证${title}\n  Given [前置条件]\n  When [操作]\n  Then [预期结果]`;
      }

      await createTestCase(projectId, selectedFolderId || null, data);
      toast.success(t("testCases.createSuccess"));
      loadTestCases();
      folderTreeRef.current?.refresh();
    } catch (error) {
      console.error("Failed to create test case:", error);
      toast.error(t("testCases.createFailed"));
    }
  };

  // 删除测试用例
  const handleDeleteTestCase = async () => {
    if (!deletingTestCase) return;
    try {
      setSubmitting(true);
      await deleteTestCase(projectId, deletingTestCase.id);
      toast.success(t("testCases.deleteSuccess"));
      setDeleteDialogOpen(false);
      setDeletingTestCase(null);
      loadTestCases();
      // 刷新文件夹树以更新用例计数
      folderTreeRef.current?.refresh();
    } catch (error) {
      console.error("Failed to delete test case:", error);
      toast.error(t("testCases.deleteFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 创建文件夹
  const handleCreateFolder = (parentId?: string) => {
    setEditingFolder(null);
    setFolderParentId(parentId);
    setFolderFormData({ name: "", description: "" });
    setFolderDialogOpen(true);
  };

  // 编辑文件夹
  const handleEditFolder = (folder: FolderInfo) => {
    setEditingFolder(folder);
    setFolderParentId(undefined);
    setFolderFormData({
      name: folder.name,
      description: folder.description || "",
    });
    setFolderDialogOpen(true);
  };

  // 提交文件夹
  const handleSubmitFolder = async () => {
    if (!folderFormData.name.trim()) {
      toast.error(t("testCases.folderNameRequired"));
      return;
    }
    try {
      setSubmitting(true);
      if (editingFolder) {
        // 编辑文件夹 - 使用本地更新
        const response = await updateFolder(projectId, editingFolder.id, folderFormData);
        toast.success(t("testCases.folderUpdateSuccess"));
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
          folder_type: "test_case",  // 指定为测试用例类型文件夹
        });
        toast.success(t("testCases.folderCreateSuccess"));
        setFolderDialogOpen(false);
        // 本地添加文件夹
        if (response.success && response.data) {
          folderTreeRef.current?.addFolderLocally(response.data, folderParentId || null);
        }
      }
    } catch (error) {
      console.error("Failed to save folder:", error);
      toast.error(editingFolder ? t("testCases.folderUpdateFailed") : t("testCases.folderCreateFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 删除文件夹
  const handleDeleteFolder = async () => {
    if (!deletingFolder) return;
    try {
      setSubmitting(true);
      await deleteFolder(projectId, deletingFolder.id);
      toast.success(t("testCases.folderDeleteSuccess"));
      setDeleteFolderDialogOpen(false);
      // 本地删除文件夹
      folderTreeRef.current?.removeFolderLocally(deletingFolder.id);
      if (selectedFolderId === deletingFolder.id) {
        setSelectedFolderId(null);
      }
      setDeletingFolder(null);
    } catch (error) {
      console.error("Failed to delete folder:", error);
      toast.error(t("testCases.folderDeleteFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <MainLayout title={t("testCases.title")}>
      <div className="relative flex h-[calc(100vh-8rem)] rounded-lg border bg-card overflow-hidden">
        <div className="flex h-full w-full">
          {/* 文件夹树 */}
          <div className="w-80 shrink-0">
            <FolderTree
              ref={folderTreeRef}
              projectId={projectId}
              folderType="test_case"
              selectedFolderId={selectedFolderId}
              onSelectFolder={handleSelectFolder}
              onCreateFolder={handleCreateFolder}
              onEditFolder={handleEditFolder}
              onDeleteFolder={(folder) => {
                setDeletingFolder(folder);
                setDeleteFolderDialogOpen(true);
              }}
              onCreateTestCase={handleCreateTestCaseInFolder}
              onMoveFolder={handleMoveFolder}
            />
          </div>

          {/* 测试用例列表 */}
          <div className="flex-1">
            <TestCaseList
              projectId={projectId}
              testCases={testCases}
              loading={loading}
              selectedIds={selectedIds}
              onSelectIds={setSelectedIds}
              onSearch={(query) => {
                setSearchQuery(query);
                setPage(1);
              }}
              onFilterChange={handleFilterChange}
              onCreateTestCase={() => {
                setEditingTestCase(null);
                setTestCaseDialogOpen(true);
              }}
              onEditTestCase={(tc) => {
                setEditingTestCase(tc);
                setTestCaseDialogOpen(true);
              }}
              onDeleteTestCase={(tc) => {
                setDeletingTestCase(tc);
                setDeleteDialogOpen(true);
              }}
              onBulkDelete={handleBulkDelete}
              onBulkEdit={handleBulkEdit}
              onViewTestCase={(tc) => {
                setEditingTestCase(tc);
                setTestCaseDialogOpen(true);
              }}
              onQuickCreateTestCase={handleQuickCreateTestCase}
              onAIGenerate={() => setAiGenerateDialogOpen(true)}
              onAIGenerateFromDocument={() => setAiGenerateFromDocDialogOpen(true)}
              onOpenAIChat={() => setAiChatOpen(true)}
              aiChatOpen={aiChatOpen}
              folderName={selectedFolderName}
              pagination={{
                page,
                pageSize,
                total,
                onPageChange: (newPage) => {
                  setPage(newPage);
                  setSelectedIds(new Set()); // 页码变化时清空选择
                },
                onPageSizeChange: (newSize) => {
                  setPageSize(newSize);
                  setPage(1);
                  setSelectedIds(new Set());
                },
              }}
              availableTags={availableTags}
              availableOwners={availableOwners}
            />
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
                  onTestCaseCreated={() => {
                    // AI 生成测试用例后自动刷新列表
                    loadTestCases();
                    folderTreeRef.current?.refresh();
                  }}
                />
              </ClientProvider>
            )}
          </div>
        )}
      </div>

      {/* 测试用例对话框 */}
      <TestCaseDialog
        open={testCaseDialogOpen}
        onOpenChange={setTestCaseDialogOpen}
        testCase={editingTestCase}
        onSubmit={handleSubmitTestCase}
        submitting={submitting}
        folderName={createTestCaseFolder?.name || selectedFolderName}
        projectId={projectId}
      />

      {/* 删除测试用例确认 */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("testCases.deleteConfirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("testCases.deleteConfirmMessage", { name: deletingTestCase?.name || "" })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteTestCase}
              disabled={submitting}
            >
              {submitting ? t("testCases.deleting") : t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 文件夹对话框 */}
      <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingFolder ? t("testCases.editFolder") : t("testCases.createFolder")}
            </DialogTitle>
            <DialogDescription>
              {editingFolder ? t("testCases.editFolder") : t("testCases.createFolder")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="folder-name">{t("testCases.folderName")}</Label>
              <Input
                id="folder-name"
                value={folderFormData.name}
                onChange={(e) =>
                  setFolderFormData({ ...folderFormData, name: e.target.value })
                }
                placeholder={t("testCases.folderNamePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="folder-description">{t("testCases.folderDescription")}</Label>
              <Textarea
                id="folder-description"
                value={folderFormData.description}
                onChange={(e) =>
                  setFolderFormData({
                    ...folderFormData,
                    description: e.target.value,
                  })
                }
                placeholder={t("testCases.descriptionPlaceholder")}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFolderDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSubmitFolder} disabled={submitting}>
              {submitting ? t("testCases.saving") : editingFolder ? t("common.save") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除文件夹确认 */}
      <Dialog
        open={deleteFolderDialogOpen}
        onOpenChange={setDeleteFolderDialogOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("testCases.folderDeleteConfirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("testCases.folderDeleteConfirmMessage", { name: deletingFolder?.name || "" })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteFolderDialogOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteFolder}
              disabled={submitting}
            >
              {submitting ? t("testCases.deleting") : t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 批量编辑对话框 */}
      <BulkEditDialog
        open={bulkEditDialogOpen}
        onOpenChange={setBulkEditDialogOpen}
        projectId={projectId}
        selectedIds={selectedIds}
        onSuccess={handleBulkEditSuccess}
      />

      {/* 批量删除确认对话框 */}
      <Dialog
        open={bulkDeleteDialogOpen}
        onOpenChange={setBulkDeleteDialogOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("testCases.bulkDeleteConfirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("testCases.bulkDeleteConfirmMessage", { count: selectedIds.size.toString() })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setBulkDeleteDialogOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={confirmBulkDelete}
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
        folderType="test_case"
        onMoveSuccess={handleMoveFolderSuccess}
      />

      {/* AI生成测试用例对话框 */}
      <AIGenerateDialog
        open={aiGenerateDialogOpen}
        onOpenChange={setAiGenerateDialogOpen}
        projectId={projectId}
        folderId={selectedFolderId}
        onSuccess={handleAIGenerateSuccess}
        onOpenChat={handleOpenAIChatFromDialog}
      />

      {/* AI从文档生成测试用例对话框 */}
      <AIGenerateFromDocumentDialog
        open={aiGenerateFromDocDialogOpen}
        onOpenChange={setAiGenerateFromDocDialogOpen}
        projectId={projectId}
        folderId={selectedFolderId}
        onSuccess={handleAIGenerateSuccess}
        onOpenChat={handleOpenAIChatFromDialog}
      />
    </MainLayout>
  );
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWprd2VBPT06ODAxNDMxNTY=

// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWprd2VBPT06ODAxNDMxNTY=
