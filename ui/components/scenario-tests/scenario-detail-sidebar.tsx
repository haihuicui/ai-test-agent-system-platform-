/**
 * 场景详情侧边栏
 * 显示场景的详细信息、配置项和快速操作
 */
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVVkbFN3PT06MWVmMGUyNjM=

"use client";
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVVkbFN3PT06MWVmMGUyNjM=

import * as React from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import {
  X,
  Edit,
  Settings,
  Zap,
  Play,
  Clock,
  FileText,
  Save,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  getScenario,
  updateScenario,
  executeScenario,
} from "@/lib/api/scenarios";
import { MessageSquare } from "lucide-react";
import type { Scenario } from "@/types/scenario";
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVVkbFN3PT06MWVmMGUyNjM=

interface ScenarioDetailSidebarProps {
  scenarioId: string;
  projectId: string;
  onClose: () => void;
  onScenarioUpdated: () => void;
  onOpenAIChat?: (prompt: string) => void;
  onSwitchToMonitor?: () => void;
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVVkbFN3PT06MWVmMGUyNjM=

export function ScenarioDetailSidebar({
  scenarioId,
  projectId,
  onClose,
  onScenarioUpdated,
  onOpenAIChat,
  onSwitchToMonitor,
}: ScenarioDetailSidebarProps) {
  const [scenario, setScenario] = React.useState<Scenario | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [editing, setEditing] = React.useState(false);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [executing, setExecuting] = React.useState(false);
  const [customRequirements, setCustomRequirements] = React.useState("");

  // 加载场景详情
  React.useEffect(() => {
    loadScenario();
  }, [scenarioId]);

  const loadScenario = async () => {
    try {
      setLoading(true);
      const data = await getScenario(scenarioId);
      setScenario(data);
      setName(data.name);
      setDescription(data.description || "");
    } catch (error) {
      console.error("Failed to load scenario:", error);
      toast.error("加载场景详情失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!scenario) return;

    if (!name.trim()) {
      toast.error("请输入场景名称");
      return;
    }

    try {
      setSaving(true);
      await updateScenario(scenarioId, {
        name: name.trim(),
        description: description.trim() || undefined,
      });

      await loadScenario();
      setEditing(false);
      onScenarioUpdated();
      toast.success("场景已更新");
    } catch (error) {
      console.error("Failed to update scenario:", error);
      toast.error("更新场景失败");
    } finally {
      setSaving(false);
    }
  };

  const handleExecute = async () => {
    // 如果提供了 onOpenAIChat，使用 AI 助手来执行场景
    if (onOpenAIChat && typeof onOpenAIChat === 'function') {
      const prompt = `请帮我执行这个测试场景：

场景名称：${scenario?.name}
场景描述：${scenario?.description || '无'}

场景配置：
- 步骤总数：${scenario?.total_steps}
- 并行执行：${scenario?.parallel_execution ? '开启' : '关闭'}
- 重试次数：${scenario?.retry_count}
- 超时时间：${scenario?.timeout_seconds} 秒

全局变量：
${Object.entries(scenario?.global_variables || {}).map(([key, value]) => `- ${key}: ${JSON.stringify(value)}`).join('\n')}

${customRequirements.trim() ? `用户自定义执行要求：
${customRequirements.trim()}

` : ''}请帮我：
1. 执行这个场景
2. 如果场景执行出现问题，请检查场景的配置是否合理
3. 如果需要，帮我调整配置参数
4. 分析执行结果并给出建议`;

      onOpenAIChat(prompt);
      return;
    }

    // 原有的直接执行逻辑
    try {
      setExecuting(true);
      const result = await executeScenario(scenarioId, {
        variables: {},
        base_url: "",
        async_mode: false,
        custom_requirements: customRequirements.trim() || undefined,
      });

      if (result.status === "completed") {
        toast.success(`场景执行成功！通过 ${result.result?.passed_steps} 个步骤`);
      } else {
        toast.warning(`场景执行完成：${result.message}`);
      }

      onScenarioUpdated();
    } catch (error) {
      console.error("Failed to execute scenario:", error);
      toast.error("执行场景失败");
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-background">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">场景详情</h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-muted-foreground">加载中...</p>
        </div>
      </div>
    );
  }

  if (!scenario) {
    return (
      <div className="flex flex-col h-full bg-background">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">场景详情</h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-muted-foreground">未找到场景信息</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* 头部 */}
      <div className="flex items-center justify-between border-b px-6 py-4 bg-gradient-to-r from-blue-50 via-purple-50 to-pink-50 dark:from-blue-950/30 dark:via-purple-950/30 dark:to-pink-950/30">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-muted-foreground">
              {scenario.identifier}
            </span>
            <Badge variant="secondary">{scenario.status}</Badge>
          </div>
          <h3 className="text-lg font-bold truncate bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            {scenario.name}
          </h3>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0"
          onClick={onClose}
        >
          <X className="h-5 w-5" />
        </Button>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {/* 统计卡片 */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg border bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-3">
            <div className="text-xs text-muted-foreground mb-1">步骤数</div>
            <div className="text-2xl font-bold text-blue-600">
              {scenario.total_steps}
            </div>
          </div>
          <div className="rounded-lg border bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20 p-3">
            <div className="text-xs text-muted-foreground mb-1">超时</div>
            <div className="text-lg font-bold text-green-600">
              {scenario.timeout_seconds}s
            </div>
          </div>
          <div className="rounded-lg border bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-950/20 dark:to-pink-950/20 p-3">
            <div className="text-xs text-muted-foreground mb-1">重试</div>
            <div className="text-lg font-bold text-purple-600">
              {scenario.retry_count}
            </div>
          </div>
        </div>

        <Separator />

        {/* 基本信息 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold flex items-center gap-2">
              <FileText className="h-4 w-4" />
              基本信息
            </h4>
            {!editing && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(true)}
                className="h-8 gap-1"
              >
                <Edit className="h-3 w-3" />
                编辑
              </Button>
            )}
          </div>

          {editing ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="edit-name">场景名称</Label>
                <Input
                  id="edit-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={saving}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-description">场景描述</Label>
                <Textarea
                  id="edit-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={saving}
                  rows={3}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={saving}
                  className="gap-1"
                >
                  <Save className="h-3 w-3" />
                  {saving ? "保存中..." : "保存"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditing(false);
                    setName(scenario.name);
                    setDescription(scenario.description || "");
                  }}
                  disabled={saving}
                >
                  取消
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">场景描述</div>
                  <p className="text-sm">
                    {scenario.description || (
                      <span className="text-muted-foreground italic">暂无描述</span>
                    )}
                  </p>
                </div>
                {scenario.last_run_at && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">上次执行</div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm">
                        {new Date(scenario.last_run_at).toLocaleString()}
                      </span>
                      {scenario.last_run_status && (
                        <Badge
                          variant={
                            scenario.last_run_status === "completed"
                              ? "default"
                              : "destructive"
                          }
                        >
                          {scenario.last_run_status}
                        </Badge>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <Separator />

        {/* 全局变量 */}
        {Object.keys(scenario.global_variables || {}).length > 0 && (
          <>
            <div className="space-y-3">
              <h4 className="font-semibold flex items-center gap-2">
                <Settings className="h-4 w-4" />
                全局变量
              </h4>
              <div className="space-y-2">
                {Object.entries(scenario.global_variables).map(([key, value]) => (
                  <div
                    key={key}
                    className="rounded-lg border bg-muted/20 p-3 text-sm"
                  >
                    <code className="text-primary font-semibold">{key}</code>
                    <span className="mx-2 text-muted-foreground">=</span>
                    <code className="text-muted-foreground">
                      {JSON.stringify(value)}
                    </code>
                  </div>
                ))}
              </div>
            </div>
            <Separator />
          </>
        )}

        {/* 执行配置 */}
        <div className="space-y-3">
          <h4 className="font-semibold flex items-center gap-2">
            <Settings className="h-4 w-4" />
            执行配置
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">并行执行</span>
              <Badge variant={scenario.parallel_execution ? "default" : "secondary"}>
                {scenario.parallel_execution ? "开启" : "关闭"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">重试次数</span>
              <span>{scenario.retry_count}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">超时时间</span>
              <span>{scenario.timeout_seconds} 秒</span>
            </div>
          </div>
        </div>

        <Separator />

        {/* 执行要求 */}
        <div className="space-y-3">
          <h4 className="font-semibold flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            执行要求
          </h4>
          <div className="space-y-2">
            <Label htmlFor="custom-requirements" className="text-xs text-muted-foreground">
              添加自定义执行要求（可选）
            </Label>
            <Textarea
              id="custom-requirements"
              placeholder="例如：使用测试环境账号执行，验证订单创建流程..."
              value={customRequirements}
              onChange={(e) => setCustomRequirements(e.target.value)}
              rows={3}
              disabled={executing}
              className="text-sm resize-none"
            />
            <p className="text-xs text-muted-foreground">
              这些要求将在执行场景时一起发送
            </p>
          </div>
        </div>
      </div>

      {/* 底部操作栏 */}
      <div className="border-t p-4 bg-muted/20">
        <div className="flex gap-2">
          <Button
            className="flex-1 gap-2 bg-gradient-to-r from-blue-600 to-purple-600"
            onClick={handleExecute}
            disabled={executing || scenario.total_steps === 0}
          >
            {executing ? (
              <>
                <Play className="h-4 w-4 animate-pulse" />
                执行中...
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" />
                执行场景
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
