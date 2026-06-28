/**
 * Web 子功能详情侧边栏
 *
 * 显示选中子功能的详细信息，包括：
 * - 基本信息（标识符、显示名称、测试类型、优先级）
 * - 目标页面、测试场景、测试数据
 * - 关联的测试用例和脚本
 * - 测试执行报告
 * - AI 生成测试入口
 */
"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZnNVJRPT06MzM5MzRkZjA=

import * as React from "react";
import { useState, useEffect } from "react";
import {
  X,
  Loader2,
  FileCode,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Play,
  Globe,
  Zap,
  RefreshCw,
  Save,
  Pencil,
  Check,
  Trash2,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/providers/LanguageProvider";
import {
  getWebSubFunction,
  updateWebSubFunction,
  deleteWebSubFunction,
  type WebSubFunction,
} from "@/lib/api/web-functions";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZnNVJRPT06MzM5MzRkZjA=

interface WebSubFunctionSidebarProps {
  subFunctionId: string;
  projectId: string;
  onClose: () => void;
  onGenerateTest: (subFunctionId: string) => void;
  onOpenAIChat?: (prompt: string) => void;
  onRefresh?: () => void;
}

export function WebSubFunctionSidebar({
  subFunctionId,
  projectId,
  onClose,
  onGenerateTest,
  onOpenAIChat,
  onRefresh,
}: WebSubFunctionSidebarProps) {
  const { t } = useLanguage();
  const [subFunction, setSubFunction] = useState<WebSubFunction | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // 编辑表单状态
  const [editForm, setEditForm] = useState({
    identifier: "",
    display_name: "",
    name: "",
    description: "",
    test_type: "",
    target_pages: "",
    test_scenario: "",
    test_data: "",
    expected_results: "",
    priority: "",
  });

  // JSON 解析辅助函数
  const parseJSON = (jsonStr: string, defaultValue: any) => {
    if (!jsonStr || jsonStr.trim() === "") return defaultValue;
    try {
      return JSON.parse(jsonStr);
    } catch {
      return defaultValue;
    }
  };

  // 用户要求输入
  const [userRequirements, setUserRequirements] = useState<string>("");

  // 删除确认对话框
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // 处理删除子功能
  const handleDelete = async () => {
    if (!subFunction) return;

    try {
      setDeleting(true);
      await deleteWebSubFunction(projectId, subFunctionId);
      toast.success("子功能删除成功");
      setShowDeleteDialog(false);
      onClose();
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Failed to delete sub-function:", error);
      toast.error("子功能删除失败: " + (error as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  // 进入编辑模式
  const handleStartEdit = () => {
    if (!subFunction) return;
    setEditForm({
      identifier: subFunction.identifier,
      display_name: subFunction.display_name,
      name: subFunction.name,
      description: subFunction.description || "",
      test_type: subFunction.test_type,
      target_pages: subFunction.target_pages ? JSON.stringify(subFunction.target_pages, null, 2) : "",
      test_scenario: subFunction.test_scenario || "",
      test_data: subFunction.test_data ? JSON.stringify(subFunction.test_data, null, 2) : "",
      expected_results: subFunction.expected_results ? JSON.stringify(subFunction.expected_results, null, 2) : "",
      priority: subFunction.priority,
    });
    setEditing(true);
  };

  // 取消编辑
  const handleCancelEdit = () => {
    setEditing(false);
    setEditForm({
      identifier: "",
      display_name: "",
      name: "",
      description: "",
      test_type: "",
      target_pages: "",
      test_scenario: "",
      test_data: "",
      expected_results: "",
      priority: "",
    });
  };

  // 保存编辑
  const handleSaveEdit = async () => {
    if (!subFunction) return;

    try {
      setSaving(true);

      // 解析 JSON 字段
      const target_pages = parseJSON(editForm.target_pages, null);
      const test_data = parseJSON(editForm.test_data, null);
      const expected_results = parseJSON(editForm.expected_results, null);

      const updated = await updateWebSubFunction(projectId, subFunctionId, {
        display_name: editForm.display_name,
        name: editForm.name,
        description: editForm.description || undefined,
        test_type: editForm.test_type,
        target_pages,
        test_scenario: editForm.test_scenario || undefined,
        test_data,
        expected_results,
        priority: editForm.priority,
      });
      setSubFunction(updated);
      setEditing(false);
      toast.success("子功能信息保存成功");
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Failed to update sub-function:", error);
      toast.error("子功能信息保存失败: " + (error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // 可折叠分组状态
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["basic", "pages", "scenario", "data", "requirements"])
  );

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  // 加载子功能详情
  useEffect(() => {
    const loadSubFunction = async () => {
      try {
        setLoading(true);
        const data = await getWebSubFunction(projectId, subFunctionId);
        setSubFunction(data);
      } catch (error) {
        console.error("Failed to load sub-function:", error);
        toast.error("加载子功能详情失败");
      } finally {
        setLoading(false);
      }
    };

    loadSubFunction();
  }, [subFunctionId, projectId]);

  // 生成 AI 提示词
  const handleAIGenerate = () => {
    if (!subFunction) return;

    const prompt = `基于你的技能和工具完成如下任务：
1. 获取子功能详细信息
2. 生成测试计划并保存
3. 生成测试用例并保存
4. 生成测试脚本并保存
5. 保存测试成果到数据库

子功能 ID: ${subFunctionId}
项目 ID: ${projectId}${userRequirements.trim() ? `

用户要求: ${userRequirements.trim()}` : ""}`;

    if (onOpenAIChat) {
      onOpenAIChat(prompt);
    } else {
      onGenerateTest(subFunctionId);
    }
  };

  // 获取优先级对应的颜色
  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: "bg-red-100 text-red-700 border-red-200",
      medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
      low: "bg-green-100 text-green-700 border-green-200",
    };
    return colors[priority.toLowerCase()] || "bg-gray-100 text-gray-700 border-gray-200";
  };

  // 获取测试类型对应的颜色
  const getTestTypeColor = (testType: string) => {
    const colors: Record<string, string> = {
      functional: "bg-blue-100 text-blue-700 border-blue-200",
      ui: "bg-purple-100 text-purple-700 border-purple-200",
      performance: "bg-orange-100 text-orange-700 border-orange-200",
      security: "bg-red-100 text-red-700 border-red-200",
    };
    return colors[testType.toLowerCase()] || "bg-gray-100 text-gray-700 border-gray-200";
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-background">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">子功能详情</h3>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* 加载中 */}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
            <p className="text-sm text-muted-foreground">加载子功能详情中...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!subFunction) {
    return (
      <div className="flex flex-col h-full bg-background">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">子功能详情</h3>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-muted-foreground">未找到子功能</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* 头部 - 优化设计 */}
      <div className="border-b bg-gradient-to-r from-blue-50 via-purple-50 to-pink-50 dark:from-blue-950/30 dark:via-purple-950/30 dark:to-pink-950/30">
        <div className="px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                {editing ? (
                  <Input
                    value={editForm.test_type}
                    onChange={(e) => setEditForm({ ...editForm, test_type: e.target.value })}
                    placeholder="测试类型"
                    className="h-7 w-32 text-xs"
                  />
                ) : (
                  <Badge
                    className={cn("text-xs font-bold border-2 shadow-sm", getTestTypeColor(subFunction.test_type))}
                  >
                    {subFunction.test_type}
                  </Badge>
                )}
                {editing ? (
                  <select
                    value={editForm.priority}
                    onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                    className="px-3 py-1.5 rounded-lg text-sm font-bold border-2 shadow-sm bg-white"
                  >
                    <option value="high">高优先级</option>
                    <option value="medium">中优先级</option>
                    <option value="low">低优先级</option>
                  </select>
                ) : (
                  <Badge
                    className={cn("text-xs font-bold border-2 shadow-sm", getPriorityColor(subFunction.priority))}
                  >
                    {subFunction.priority === "high" ? "高优先级" : subFunction.priority === "medium" ? "中优先级" : "低优先级"}
                  </Badge>
                )}
              </div>
              {editing ? (
                <div className="space-y-2">
                  <Input
                    value={editForm.display_name}
                    onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                    placeholder="显示名称"
                    className="font-bold"
                  />
                  <Input
                    value={editForm.identifier}
                    onChange={(e) => setEditForm({ ...editForm, identifier: e.target.value })}
                    placeholder="标识符"
                    className="font-mono text-sm"
                  />
                </div>
              ) : (
                <>
                  <h3 className="text-xl font-bold mb-1 truncate bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    {subFunction.display_name}
                  </h3>
                  <code className="text-sm text-muted-foreground font-mono bg-white/50 dark:bg-black/20 px-2 py-1 rounded">
                    {subFunction.identifier}
                  </code>
                </>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {editing ? (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-gray-100"
                    onClick={handleCancelEdit}
                    disabled={saving}
                  >
                    <X className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-green-50 hover:text-green-600"
                    onClick={handleSaveEdit}
                    disabled={saving}
                  >
                    {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Check className="h-5 w-5" />}
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-green-50 hover:text-green-600"
                    onClick={onRefresh}
                    title="刷新数据"
                  >
                    <RefreshCw className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-blue-50 hover:text-blue-600"
                    onClick={handleStartEdit}
                    title="编辑子功能信息"
                  >
                    <Pencil className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-red-50 hover:text-red-600"
                    onClick={() => setShowDeleteDialog(true)}
                    title="删除子功能"
                  >
                    <Trash2 className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-gray-100 hover:text-gray-600"
                    onClick={onClose}
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* 统计信息卡片 */}
          <div className="grid grid-cols-3 gap-3 mt-4">
            <div className="bg-white/60 dark:bg-black/20 rounded-lg p-3 border">
              <div className="flex items-center gap-2 mb-1">
                <FileCode className="h-4 w-4 text-blue-500" />
                <span className="text-xs text-muted-foreground">测试用例</span>
              </div>
              <div className="text-2xl font-bold text-blue-600">
                {subFunction.total_test_cases || 0}
              </div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 rounded-lg p-3 border">
              <div className="flex items-center gap-2 mb-1">
                <Play className="h-4 w-4 text-green-500" />
                <span className="text-xs text-muted-foreground">执行次数</span>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {subFunction.total_test_runs || 0}
              </div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 rounded-lg p-3 border">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="h-4 w-4 text-purple-500" />
                <span className="text-xs text-muted-foreground">最后状态</span>
              </div>
              <div className="text-sm font-semibold">
                {subFunction.last_run_status ? (
                  <Badge variant="default">
                    {subFunction.last_run_status}
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">未执行</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto">
        {/* 快速操作区 */}
        <div className="p-6 space-y-4">
          {/* 描述信息卡片 */}
          {(subFunction.description || editing) && (
            <div className="rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50/50 to-indigo-50/50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Globe className="h-4 w-4 text-blue-500" />
                <span className="font-semibold text-sm">描述信息</span>
              </div>
              {editing ? (
                <Textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  placeholder="子功能描述"
                  className="min-h-[80px] resize-none"
                />
              ) : (
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {subFunction.description}
                </p>
              )}
            </div>
          )}
        </div>

        {editing && (
          <>
            <Separator />
            {/* 高级编辑区域 */}
            <div className="p-6 space-y-4">
              <div className="rounded-xl border-2 border-orange-200 bg-gradient-to-br from-orange-50/50 to-amber-50/50 dark:from-orange-950/20 dark:to-amber-950/20 p-4">
                <div className="flex items-center gap-2 mb-4">
                  <FileCode className="h-4 w-4 text-orange-500" />
                  <span className="font-semibold text-sm">高级编辑</span>
                  <span className="text-xs text-muted-foreground ml-auto">JSON 格式</span>
                </div>
                <div className="space-y-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">目标页面</Label>
                    <Textarea
                      value={editForm.target_pages}
                      onChange={(e) => setEditForm({ ...editForm, target_pages: e.target.value })}
                      placeholder='[{"url": "/page1", "name": "Page 1"}]'
                      className="mt-1 min-h-[100px] resize-none font-mono text-xs"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">测试数据</Label>
                    <Textarea
                      value={editForm.test_data}
                      onChange={(e) => setEditForm({ ...editForm, test_data: e.target.value })}
                      placeholder='{"username": "test", "password": "123456"}'
                      className="mt-1 min-h-[100px] resize-none font-mono text-xs"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">预期结果</Label>
                    <Textarea
                      value={editForm.expected_results}
                      onChange={(e) => setEditForm({ ...editForm, expected_results: e.target.value })}
                      placeholder='{"status": "success", "message": "操作成功"}'
                      className="mt-1 min-h-[100px] resize-none font-mono text-xs"
                    />
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        <Separator />

        {/* 详细信息区域 */}
        <div className="px-6 pb-6 space-y-4">
          {/* 基本信息 */}
          <CollapsibleSection
            title="基本信息"
            icon={<Globe className="h-4 w-4" />}
            expanded={expandedSections.has("basic")}
            onToggle={() => toggleSection("basic")}
          >
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between py-2">
                <span className="text-muted-foreground w-24 shrink-0">标识符</span>
                <code className="font-mono text-xs break-all flex-1 text-right">
                  {subFunction.identifier}
                </code>
              </div>
              <div className="flex items-center justify-between py-2 border-b">
                <span className="text-muted-foreground w-24 shrink-0">显示名称</span>
                <span className="font-semibold flex-1 text-right">
                  {subFunction.display_name}
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b">
                <span className="text-muted-foreground w-24 shrink-0">测试类型</span>
                <Badge className={getTestTypeColor(subFunction.test_type)}>
                  {subFunction.test_type}
                </Badge>
              </div>
              <div className="flex items-center justify-between py-2 border-b">
                <span className="text-muted-foreground w-24 shrink-0">优先级</span>
                <Badge className={getPriorityColor(subFunction.priority)}>
                  {subFunction.priority === "high" ? "高" : subFunction.priority === "medium" ? "中" : "低"}
                </Badge>
              </div>
              {subFunction.description && (
                <div className="flex items-start justify-between py-2 gap-3">
                  <span className="text-muted-foreground w-24 shrink-0">描述</span>
                  <div className="text-xs flex-1 text-right">
                    {subFunction.description}
                  </div>
                </div>
              )}
            </div>
          </CollapsibleSection>

          {/* 目标页面 */}
          {subFunction.target_pages && (
            <CollapsibleSection
              title="目标页面"
              icon={<Layers className="h-4 w-4" />}
              expanded={expandedSections.has("pages")}
              onToggle={() => toggleSection("pages")}
            >
              <div className="rounded-xl border-2 bg-gradient-to-br from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 p-4">
                <pre className="text-xs overflow-x-auto font-mono bg-white dark:bg-black p-3 rounded border">
                  {JSON.stringify(subFunction.target_pages, null, 2)}
                </pre>
              </div>
            </CollapsibleSection>
          )}

          {/* 测试场景 */}
          {subFunction.test_scenario && (
            <CollapsibleSection
              title="测试场景"
              icon={<FileCode className="h-4 w-4" />}
              expanded={expandedSections.has("scenario")}
              onToggle={() => toggleSection("scenario")}
            >
              <div className="rounded-xl border-2 bg-gradient-to-br from-blue-50/50 to-indigo-50/50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
                <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {subFunction.test_scenario}
                </p>
              </div>
            </CollapsibleSection>
          )}

          {/* 测试数据 */}
          {subFunction.test_data && (
            <CollapsibleSection
              title="测试数据"
              icon={<FileCode className="h-4 w-4" />}
              expanded={expandedSections.has("data")}
              onToggle={() => toggleSection("data")}
            >
              <div className="rounded-xl border-2 bg-gradient-to-br from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 p-4">
                <pre className="text-xs overflow-x-auto font-mono bg-white dark:bg-black p-3 rounded border">
                  {JSON.stringify(subFunction.test_data, null, 2)}
                </pre>
              </div>
            </CollapsibleSection>
          )}

          {/* 用户要求输入 */}
          <CollapsibleSection
            title="生成要求"
            icon={<Zap className="h-4 w-4" />}
            expanded={expandedSections.has("requirements")}
            onToggle={() => toggleSection("requirements")}
          >
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-2 block">
                  输入测试生成要求
                </label>
                <Textarea
                  placeholder="描述你希望生成的测试的具体要求..."
                  value={userRequirements}
                  onChange={(e) => setUserRequirements(e.target.value)}
                  className="min-h-[120px] resize-none"
                />
              </div>
              <div className="text-xs text-muted-foreground bg-blue-50 dark:bg-blue-950/20 p-3 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="font-medium text-blue-700 dark:text-blue-400 mb-1">提示</p>
                <p>AI 将根据子功能信息和你提供的生成要求自动创建测试计划、测试用例和测试脚本。</p>
              </div>
            </div>
          </CollapsibleSection>
        </div>
      </div>

      {/* 底部操作栏 */}
      <div className="border-t-2 px-6 py-4 bg-gradient-to-r from-slate-50 via-gray-50 to-slate-50 dark:from-slate-900 dark:via-gray-900 dark:to-slate-900">
        {editing ? (
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleCancelEdit}
              disabled={saving}
              className="flex-1 border-2 hover:bg-gray-50"
            >
              <X className="mr-2 h-4 w-4" />
              取消
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={saving}
              className="flex-1 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 shadow-md hover:shadow-lg transition-all"
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  保存
                </>
              )}
            </Button>
          </div>
        ) : (
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleStartEdit}
              className="flex-1 border-2 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200"
            >
              <Pencil className="mr-2 h-4 w-4" />
              编辑信息
            </Button>
            <Button
              onClick={handleAIGenerate}
              className="flex-1 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 shadow-md hover:shadow-lg transition-all"
            >
              <Zap className="mr-2 h-5 w-5" />
              AI 生成测试
            </Button>
          </div>
        )}
      </div>

      {/* 删除确认对话框 */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除子功能</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除子功能 "{subFunction?.display_name}" 吗？
              <br />
              <span className="text-destructive">此操作无法撤销</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  删除中...
                </>
              ) : (
                "确认删除"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZnNVJRPT06MzM5MzRkZjA=

// 可折叠分组组件
interface CollapsibleSectionProps {
  title: string;
  icon?: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function CollapsibleSection({
  title,
  icon,
  expanded,
  onToggle,
  children,
}: CollapsibleSectionProps) {
  return (
    <div className={cn(
      "border-2 rounded-xl overflow-hidden bg-card transition-all",
      expanded && "shadow-md border-primary/30"
    )}>
      <button
        onClick={onToggle}
        className={cn(
          "w-full flex items-center justify-between px-5 py-4 transition-all",
          "hover:bg-gradient-to-r hover:from-blue-50/50 hover:to-purple-50/50",
          expanded && "bg-gradient-to-r from-blue-50/30 to-purple-50/30"
        )}
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "p-1.5 rounded-lg transition-colors",
            expanded ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
          )}>
            {icon}
          </div>
          <span className={cn(
            "font-semibold text-sm transition-colors",
            expanded && "text-primary"
          )}>
            {title}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="h-5 w-5 text-primary transition-transform" />
        ) : (
          <ChevronRight className="h-5 w-5 text-muted-foreground transition-transform" />
        )}
      </button>
      {expanded && (
        <div className="px-5 py-4 border-t bg-gradient-to-br from-background to-muted/10">
          {children}
        </div>
      )}
    </div>
  );
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZnNVJRPT06MzM5MzRkZjA=
