/**
 * API 端点详情侧边栏
 *
 * 显示选中接口的详细信息，包括：
 * - 基本信息（方法、路径、描述）
 * - 参数、请求体、响应
 * - 关联的测试用例和脚本
 * - 测试执行报告
 * - AI 生成测试入口
 */
"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVcxbWVRPT06YmM4MjgxNTg=

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
import { updateAPIEndpoint, deleteAPIEndpoint } from "@/lib/api/api-endpoints";

interface APIEndpointSidebarProps {
  endpointId: string;
  projectId: string;
  onClose: () => void;
  onGenerateTest: (endpointId: string) => void;
  onOpenAIChat?: (prompt: string) => void;
  onRefresh?: () => void;
}

interface APIEndpoint {
  id: string;
  display_name: string;
  path: string;
  method: string;
  summary: string | null;
  description: string | null;
  tag_group: string | null;
  parameters: any[] | null;
  request_body: any | null;
  responses: any | null;
  total_test_cases: number;
  total_test_runs: number;
  last_run_status: string | null;
}
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVcxbWVRPT06YmM4MjgxNTg=


// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVcxbWVRPT06YmM4MjgxNTg=

export function APIEndpointSidebar({
  endpointId,
  projectId,
  onClose,
  onGenerateTest,
  onOpenAIChat,
  onRefresh,
}: APIEndpointSidebarProps) {
  const { t } = useLanguage();
  const [endpoint, setEndpoint] = useState<APIEndpoint | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // 编辑表单状态
  const [editForm, setEditForm] = useState({
    display_name: "",
    path: "",
    method: "",
    summary: "",
    description: "",
    tag_group: "",
    parameters: "",
    request_body: "",
    responses: "",
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

  // 处理删除接口
  const handleDelete = async () => {
    if (!endpoint) return;

    try {
      setDeleting(true);
      await deleteAPIEndpoint(endpointId);
      toast.success(t("apiTests.endpointDeleteSuccess"));
      setShowDeleteDialog(false);
      onClose();
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Failed to delete endpoint:", error);
      toast.error(t("apiTests.endpointDeleteFailed") + ": " + (error as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  // 进入编辑模式
  const handleStartEdit = () => {
    if (!endpoint) return;
    setEditForm({
      display_name: endpoint.display_name,
      path: endpoint.path,
      method: endpoint.method,
      summary: endpoint.summary || "",
      description: endpoint.description || "",
      tag_group: endpoint.tag_group || "",
      parameters: endpoint.parameters ? JSON.stringify(endpoint.parameters, null, 2) : "",
      request_body: endpoint.request_body ? JSON.stringify(endpoint.request_body, null, 2) : "",
      responses: endpoint.responses ? JSON.stringify(endpoint.responses, null, 2) : "",
    });
    setEditing(true);
  };

  // 取消编辑
  const handleCancelEdit = () => {
    setEditing(false);
    setEditForm({
      display_name: "",
      path: "",
      method: "",
      summary: "",
      description: "",
      tag_group: "",
      parameters: "",
      request_body: "",
      responses: "",
    });
  };

  // 保存编辑
  const handleSaveEdit = async () => {
    if (!endpoint) return;

    try {
      setSaving(true);

      // 解析 JSON 字段
      const parameters = parseJSON(editForm.parameters, null);
      const request_body = parseJSON(editForm.request_body, null);
      const responses = parseJSON(editForm.responses, null);

      const updated = await updateAPIEndpoint(endpointId, {
        display_name: editForm.display_name,
        path: editForm.path,
        method: editForm.method,
        summary: editForm.summary || undefined,
        description: editForm.description || undefined,
        tag_group: editForm.tag_group || undefined,
        parameters,
        request_body,
        responses,
      });
      setEndpoint(updated);
      setEditing(false);
      toast.success(t("apiTests.endpointInfoSaveSuccess"));
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Failed to update endpoint:", error);
      toast.error(t("apiTests.endpointInfoSaveFailed") + ": " + (error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // 可折叠分组状态
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["basic", "parameters", "responses", "requirements"])
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

  // 加载端点详情
  useEffect(() => {
    const loadEndpoint = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `/api/v2/api-endpoints/${endpointId}`
        );
        if (!response.ok) {
          throw new Error(t("apiTests.loadEndpointDetailsFailed"));
        }
        const data = await response.json();
        setEndpoint(data);
      } catch (error) {
        console.error("Failed to load endpoint:", error);
        toast.error(t("apiTests.loadEndpointDetailsFailed"));
      } finally {
        setLoading(false);
      }
    };

    loadEndpoint();
  }, [endpointId]);



  // 生成 AI 提示词
  const handleAIGenerate = () => {
    if (!endpoint) return;

    // 简化的 prompt：只包含基本指令和关键参数
    // 详细流程已在系统提示词中定义，agent 会自动获取接口详细信息
    const prompt = `基于你的技能和工具完成如下任务：
1. 获取接口详细信息
2. 生成测试计划并保存
3. 生成测试用例并保存
4. 生成测试脚本并保存
5. 保存测试成果到数据库

端点 ID: ${endpointId}
项目 ID: ${projectId}${userRequirements.trim() ? `

用户要求: ${userRequirements.trim()}` : ""}`;

    if (onOpenAIChat) {
      onOpenAIChat(prompt);
    } else {
      onGenerateTest(endpointId);
    }
  };

  // 获取方法对应的颜色
  const getMethodColor = (method: string) => {
    const colors: Record<string, string> = {
      GET: "bg-blue-100 text-blue-700 border-blue-200",
      POST: "bg-green-100 text-green-700 border-green-200",
      PUT: "bg-orange-100 text-orange-700 border-orange-200",
      DELETE: "bg-red-100 text-red-700 border-red-200",
      PATCH: "bg-purple-100 text-purple-700 border-purple-200",
    };
    return colors[method.toUpperCase()] || "bg-gray-100 text-gray-700 border-gray-200";
  };



  if (loading) {
    return (
      <div className="flex flex-col h-full bg-background">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">{t("apiTests.endpointDetails")}</h3>
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
            <p className="text-sm text-muted-foreground">{t("apiTests.loadingEndpointDetails")}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!endpoint) {
    return (
      <div className="flex flex-col h-full bg-background">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">{t("apiTests.endpointDetails")}</h3>
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
          <p className="text-sm text-muted-foreground">{t("apiTests.endpointNotFound")}</p>
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
                  <select
                    value={editForm.method}
                    onChange={(e) => setEditForm({ ...editForm, method: e.target.value })}
                    className={`px-3 py-1.5 rounded-lg text-sm font-bold border-2 shadow-sm ${getMethodColor(editForm.method)}`}
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                ) : (
                  <span
                    className={`px-3 py-1.5 rounded-lg text-sm font-bold border-2 shadow-sm ${getMethodColor(
                      endpoint.method
                    )}`}
                  >
                    {endpoint.method}
                  </span>
                )}
                {(editing || endpoint.tag_group) && (
                  editing ? (
                    <Input
                      value={editForm.tag_group}
                      onChange={(e) => setEditForm({ ...editForm, tag_group: e.target.value })}
                      placeholder={t("apiTests.tagGroup")}
                      className="h-7 w-24 text-xs"
                    />
                  ) : (
                    <Badge variant="secondary" className="text-xs">
                      {endpoint.tag_group}
                    </Badge>
                  )
                )}
              </div>
              {editing ? (
                <div className="space-y-2">
                  <Input
                    value={editForm.display_name}
                    onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                    placeholder={t("apiTests.endpointSummary")}
                    className="font-bold"
                  />
                  <Input
                    value={editForm.path}
                    onChange={(e) => setEditForm({ ...editForm, path: e.target.value })}
                    placeholder={t("apiTests.requestPath")}
                    className="font-mono text-sm"
                  />
                </div>
              ) : (
                <>
                  <h3 className="text-xl font-bold mb-1 truncate bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    {endpoint.display_name}
                  </h3>
                  <code className="text-sm text-muted-foreground font-mono bg-white/50 dark:bg-black/20 px-2 py-1 rounded">
                    {endpoint.path}
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
                    title={t("apiTests.refreshData")}
                  >
                    <RefreshCw className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-blue-50 hover:text-blue-600"
                    onClick={handleStartEdit}
                    title={t("apiTests.editEndpointInfo")}
                  >
                    <Pencil className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 hover:bg-red-50 hover:text-red-600"
                    onClick={() => setShowDeleteDialog(true)}
                    title={t("apiTests.deleteEndpoint")}
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
                <span className="text-xs text-muted-foreground">{t("apiTests.testCases")}</span>
              </div>
              <div className="text-2xl font-bold text-blue-600">
                {endpoint.total_test_cases || 0}
              </div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 rounded-lg p-3 border">
              <div className="flex items-center gap-2 mb-1">
                <Play className="h-4 w-4 text-green-500" />
                <span className="text-xs text-muted-foreground">{t("apiTests.executionCount")}</span>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {endpoint.total_test_runs || 0}
              </div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 rounded-lg p-3 border">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="h-4 w-4 text-purple-500" />
                <span className="text-xs text-muted-foreground">{t("apiTests.lastStatus")}</span>
              </div>
              <div className="text-sm font-semibold">
                {endpoint.last_run_status ? (
                  <Badge variant="default">
                    {endpoint.last_run_status}
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">{t("apiTests.notExecuted")}</span>
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
          {(endpoint.summary || endpoint.description || editing) && (
            <div className="rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50/50 to-indigo-50/50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Globe className="h-4 w-4 text-blue-500" />
                <span className="font-semibold text-sm">{t("apiTests.endpointDescription")}</span>
              </div>
              {editing ? (
                <div className="space-y-3">
                  <div>
                    <Label className="text-xs text-muted-foreground">{t("apiTests.endpointSummary")}</Label>
                    <Input
                      value={editForm.summary}
                      onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                      placeholder={t("apiTests.endpointSummary")}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">{t("apiTests.detailedDescription")}</Label>
                    <Textarea
                      value={editForm.description}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                      placeholder={t("apiTests.endpointDetailedDescription")}
                      className="mt-1 min-h-[80px] resize-none"
                    />
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {endpoint.summary || endpoint.description}
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
                  <span className="font-semibold text-sm">{t("apiTests.advancedEdit")}</span>
                  <span className="text-xs text-muted-foreground ml-auto">JSON {t("common.format")}</span>
                </div>
                <div className="space-y-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">{t("apiTests.parametersLabel")}</Label>
                    <Textarea
                      value={editForm.parameters}
                      onChange={(e) => setEditForm({ ...editForm, parameters: e.target.value })}
                      placeholder='[{"name": "id", "in": "path", "required": true, "schema": {"type": "string"}}]'
                      className="mt-1 min-h-[100px] resize-none font-mono text-xs"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">{t("apiTests.requestBodyLabel")}</Label>
                    <Textarea
                      value={editForm.request_body}
                      onChange={(e) => setEditForm({ ...editForm, request_body: e.target.value })}
                      placeholder='{"content": {"application/json": {"schema": {"type": "object"}}}}'
                      className="mt-1 min-h-[100px] resize-none font-mono text-xs"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">{t("apiTests.responsesLabel")}</Label>
                    <Textarea
                      value={editForm.responses}
                      onChange={(e) => setEditForm({ ...editForm, responses: e.target.value })}
                      placeholder={`{"200": {"${t("common.description")}": "${t("common.success")}", "content": {"application/json": {"schema": {"type": "object"}}}}}`}
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
            title={t("apiTests.basicInfo")}
            icon={<Globe className="h-4 w-4" />}
            expanded={expandedSections.has("basic")}
            onToggle={() => toggleSection("basic")}
          >
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between py-2">
                <span className="text-muted-foreground w-24 shrink-0">{t("apiTests.requestMethod")}</span>
                <span
                  className={`px-3 py-1 rounded-md text-sm font-semibold border ${getMethodColor(
                    endpoint.method
                  )}`}
                >
                  {endpoint.method}
                </span>
              </div>
              <div className="flex items-start justify-between py-2 border-b">
                <span className="text-muted-foreground w-24 shrink-0">{t("apiTests.requestPath")}</span>
                <span className="font-mono text-xs break-all flex-1 text-right">
                  {endpoint.path}
                </span>
              </div>
              {(endpoint.summary || endpoint.description || editing) && (
                <div className="flex items-start justify-between py-2 gap-3">
                  <span className="text-muted-foreground w-24 shrink-0">{t("apiTests.endpointDescription")}</span>
                  {editing ? (
                    <div className="flex-1 space-y-2">
                      <Input
                        value={editForm.summary}
                        onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                        placeholder={t("apiTests.endpointSummary")}
                        className="text-xs"
                      />
                      <Textarea
                        value={editForm.description}
                        onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                        placeholder={t("apiTests.endpointDetailedDescription")}
                        className="text-xs min-h-[60px] resize-none"
                      />
                    </div>
                  ) : (
                    <div className="text-xs flex-1 text-right space-y-1">
                      <div>{endpoint.summary}</div>
                      <div className="text-muted-foreground">{endpoint.description}</div>
                    </div>
                  )}
                </div>
              )}
              {(endpoint.tag_group || editing) && (
                <div className="flex items-center justify-between py-2 border-t">
                  <span className="text-muted-foreground w-24 shrink-0">{t("apiTests.tagGroup")}</span>
                  {editing ? (
                    <Input
                      value={editForm.tag_group}
                      onChange={(e) => setEditForm({ ...editForm, tag_group: e.target.value })}
                      placeholder={t("apiTests.tagGroup")}
                      className="text-xs w-40"
                    />
                  ) : (
                    <Badge variant="outline">{endpoint.tag_group}</Badge>
                  )}
                </div>
              )}
            </div>
          </CollapsibleSection>

          {/* 参数 */}
          {endpoint.parameters && endpoint.parameters.length > 0 && (
            <CollapsibleSection
              title={`${t("apiTests.params")} (${endpoint.parameters.length})`}
              icon={<FileCode className="h-4 w-4" />}
              expanded={expandedSections.has("parameters")}
              onToggle={() => toggleSection("parameters")}
            >
              <div className="space-y-3">
                {endpoint.parameters.map((param: any, index: number) => (
                  <div
                    key={index}
                    className="rounded-xl border-2 bg-gradient-to-br from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 p-4 hover:shadow-md hover:border-primary/50 transition-all"
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <code className="font-semibold text-sm bg-white dark:bg-black px-2 py-1 rounded border">
                        {param.name}
                      </code>
                      <Badge variant="secondary" className="text-xs">
                        {param.in}
                      </Badge>
                      {param.required && (
                        <Badge variant="destructive" className="text-xs">
                          {t("common.required")}
                        </Badge>
                      )}
                    </div>
                    {param.description && (
                      <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                        {param.description}
                      </p>
                    )}
                    {param.schema && (
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground">{t("testCases.type")}:</span>
                        <code className="font-mono bg-white dark:bg-black px-2 py-0.5 rounded border">
                          {param.schema.type || t("common.unknown")}
                        </code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* 请求体 */}
          {endpoint.request_body && (
            <CollapsibleSection
              title={t("apiTests.requestBodyTitle")}
              icon={<FileCode className="h-4 w-4" />}
              expanded={expandedSections.has("requestBody")}
              onToggle={() => toggleSection("requestBody")}
            >
              <div className="rounded-xl border-2 bg-gradient-to-br from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 p-4">
                <pre className="text-xs overflow-x-auto font-mono bg-white dark:bg-black p-3 rounded border">
                  {JSON.stringify(endpoint.request_body, null, 2)}
                </pre>
              </div>
            </CollapsibleSection>
          )}

          {/* 响应 */}
          {endpoint.responses && (
            <CollapsibleSection
              title={`${t("apiTests.response")} (${Object.keys(endpoint.responses).length})`}
              icon={<CheckCircle2 className="h-4 w-4" />}
              expanded={expandedSections.has("responses")}
              onToggle={() => toggleSection("responses")}
            >
              <div className="space-y-3">
                {Object.entries(endpoint.responses).map(([code, response]: [string, any]) => (
                  <div
                    key={code}
                    className="rounded-xl border-2 bg-gradient-to-br from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 p-4 hover:shadow-md hover:border-primary/50 transition-all"
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <Badge
                        variant={
                          code.startsWith('2') ? 'default' :
                          code.startsWith('4') ? 'destructive' :
                          code.startsWith('5') ? 'destructive' :
                          'secondary'
                        }
                        className="text-sm font-bold"
                      >
                        {code}
                      </Badge>
                      {response.description && (
                        <span className="text-sm text-muted-foreground">
                          {response.description}
                        </span>
                      )}
                    </div>
                    {response.content && (
                      <pre className="text-xs overflow-x-auto font-mono bg-white dark:bg-black p-3 rounded border mt-2">
                        {JSON.stringify(response.content, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* 用户要求输入 */}
          <CollapsibleSection
            title={t("apiTests.generationRequirements")}
            icon={<Zap className="h-4 w-4" />}
            expanded={expandedSections.has("requirements")}
            onToggle={() => toggleSection("requirements")}
          >
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-2 block">
                  {t("apiTests.enterRequirements")}
                </label>
                <Textarea
                  placeholder={t("apiTests.requirementsPlaceholder")}
                  value={userRequirements}
                  onChange={(e) => setUserRequirements(e.target.value)}
                  className="min-h-[120px] resize-none"
                />
              </div>
              <div className="text-xs text-muted-foreground bg-blue-50 dark:bg-blue-950/20 p-3 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="font-medium text-blue-700 dark:text-blue-400 mb-1">💡 {t("common.info")}</p>
                <p>{t("apiTests.autoGenerateNote")}</p>
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
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={saving}
              className="flex-1 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 shadow-md hover:shadow-lg transition-all"
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("apiTests.saving")}
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  {t("common.save")}
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
              {t("apiTests.editInfo")}
            </Button>
            <Button
              onClick={handleAIGenerate}
              className="flex-1 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 shadow-md hover:shadow-lg transition-all"
            >
              <Zap className="mr-2 h-5 w-5" />
              {t("apiTests.aiGenerateTest")}
            </Button>
          </div>
        )}
      </div>

      {/* 删除确认对话框 */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("apiTests.confirmDeleteEndpoint")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("apiTests.confirmDeleteEndpointMessage", { name: endpoint?.display_name || "" })}
              <br />
              <span className="text-destructive">{t("apiTests.cannotRecover")}</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("apiTests.deleting")}
                </>
              ) : (
                t("apiTests.confirmDelete")
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVcxbWVRPT06YmM4MjgxNTg=

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
