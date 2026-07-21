/**
 * 场景步骤编辑对话框
 *
 * 功能：
 * - 编辑步骤基本信息
 * - 配置请求参数覆盖
 * - 管理数据提取器
 * - 管理断言
 * - 配置执行选项
 */
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTNKcFdnPT06MTdhZTQ4OWU=

"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  Save,
  X,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Code,
  GitBranch,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  getScenarioStep,
  updateScenarioStep,
  listScenarioSteps,
  addDataMapping as addDataMappingAPI,
  deleteDataMapping as deleteDataMappingAPI,
} from "@/lib/api/scenarios";
import { OPERATOR_LABELS, normalizeAssertions, normalizeOperator } from "@/lib/assertion-utils";
import type { ScenarioStep, StepExtractor, StepAssertion, StepVariableExport } from "@/types/scenario";
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTNKcFdnPT06MTdhZTQ4OWU=

interface StepEditDialogProps {
  stepId: string;
  scenarioId: string;
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTNKcFdnPT06MTdhZTQ4OWU=

export function StepEditDialog({
  stepId,
  scenarioId,
  open,
  onOpenChange,
  onSave,
}: StepEditDialogProps) {
  const [step, setStep] = React.useState<ScenarioStep | null>(null);
  const [allSteps, setAllSteps] = React.useState<ScenarioStep[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);

  // 表单状态
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [requestOverride, setRequestOverride] = React.useState("{}");
  const [headersOverride, setHeadersOverride] = React.useState("{}");
  const [conditionExpression, setConditionExpression] = React.useState("");
  const [continueOnFailure, setContinueOnFailure] = React.useState(false);
  const [delayMs, setDelayMs] = React.useState(0);
  const [retryCount, setRetryCount] = React.useState(0);

  // 提取器、断言和数据映射
  const [extractors, setExtractors] = React.useState<StepExtractor[]>([]);
  const [assertions, setAssertions] = React.useState<StepAssertion[]>([]);
  const [dataMappings, setDataMappings] = React.useState<any[]>([]);
  const [variableExports, setVariableExports] = React.useState<StepVariableExport[]>([]);

  // UI 状态
  const [expandedSections, setExpandedSections] = React.useState<Set<string>>(
    new Set(["basic", "request", "extractors", "variable_exports", "mappings", "assertions", "execution"])
  );

  // 加载步骤详情
  React.useEffect(() => {
    if (open && stepId) {
      loadStep();
    }
  }, [open, stepId]);

  const loadStep = async () => {
    try {
      setLoading(true);
      const data = await getScenarioStep(stepId);
      setStep(data);

      // 加载场景的所有步骤（用于数据映射的源步骤选择）
      const steps = await listScenarioSteps(scenarioId);
      setAllSteps(steps);

      // 填充表单
      setName(data.name || "");
      setDescription(data.description || "");
      setRequestOverride(JSON.stringify(data.request_override || {}, null, 2));
      setHeadersOverride(JSON.stringify(data.headers_override || {}, null, 2));
      setConditionExpression(data.condition_expression || "");
      setContinueOnFailure(data.continue_on_failure || false);
      setDelayMs(data.delay_ms || 0);
      setRetryCount(data.retry_count || 0);
      setExtractors(data.extractors || []);
      setAssertions(normalizeAssertions(data.assertions || []));
      setDataMappings(data.data_mappings || []);
      setVariableExports(
        (data.variable_exports || []).map((e) => ({ ...e, type: e.type || "jsonpath" }))
      );
    } catch (error) {
      console.error("Failed to load step:", error);
      toast.error("加载步骤详情失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!step) return;

    // 验证
    if (!name.trim()) {
      toast.error("请输入步骤名称");
      return;
    }

    // 验证 JSON 格式
    try {
      JSON.parse(requestOverride);
    } catch {
      toast.error("请求参数覆盖不是有效的 JSON 格式");
      return;
    }

    try {
      JSON.parse(headersOverride);
    } catch {
      toast.error("请求头覆盖不是有效的 JSON 格式");
      return;
    }

    try {
      setSaving(true);

      // 1. 先保存步骤的基本信息（不包含 data_mappings）
      await updateScenarioStep(scenarioId, stepId, {
        name: name.trim(),
        description: description.trim() || undefined,
        request_override: JSON.parse(requestOverride),
        headers_override: JSON.parse(headersOverride),
        condition_expression: conditionExpression.trim() || undefined,
        continue_on_failure: continueOnFailure,
        delay_ms: delayMs,
        retry_count: retryCount,
        extractors: extractors,
        assertions: assertions,
        variable_exports: variableExports,
      });

      // 2. 处理数据映射的更新
      // 先删除所有现有的数据映射
      const existingMappings = step.data_mappings || [];
      for (const mapping of existingMappings) {
        await deleteDataMappingAPI(scenarioId, stepId, mapping.id);
      }

      // 3. 重新添加用户编辑后的数据映射
      for (const mapping of dataMappings) {
        // 只有当映射配置完整时才添加
        if (mapping.target_path && mapping.source_type) {
          await addDataMappingAPI(scenarioId, stepId, {
            source_type: mapping.source_type,
            source_step_id: mapping.source_step_id,
            source_path: mapping.source_path,
            target_path: mapping.target_path,
            transform_expression: mapping.transform_expression,
            description: mapping.description,
          });
        }
      }

      toast.success("步骤已更新");
      onSave();
    } catch (error: any) {
      console.error("Failed to update step:", error);
      toast.error(error.message || "更新步骤失败");
    } finally {
      setSaving(false);
    }
  };

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

  // 添加提取器
  const addExtractor = () => {
    setExtractors([
      ...extractors,
      { name: `extractor_${extractors.length + 1}`, path: "", type: "jsonpath" },
    ]);
  };

  // 更新提取器
  const updateExtractor = (index: number, field: keyof StepExtractor, value: string) => {
    const newExtractors = [...extractors];
    newExtractors[index] = { ...newExtractors[index], [field]: value };
    setExtractors(newExtractors);
  };

  // 删除提取器
  const removeExtractor = (index: number) => {
    setExtractors(extractors.filter((_, i) => i !== index));
  };

  // 添加断言
  const addAssertion = () => {
    setAssertions([...assertions, { type: "status", expected: 200, operator: "eq" }]);
  };

  // 更新断言
  const updateAssertion = (index: number, field: keyof StepAssertion, value: any) => {
    const newAssertions = [...assertions];
    newAssertions[index] = { ...newAssertions[index], [field]: value };
    setAssertions(newAssertions);
  };

  // 删除断言
  const removeAssertion = (index: number) => {
    setAssertions(assertions.filter((_, i) => i !== index));
  };

  // 添加变量导出
  const addVariableExport = () => {
    setVariableExports([
      ...variableExports,
      { name: `var_${variableExports.length + 1}`, source: "request", path: "", type: "jsonpath" },
    ]);
  };

  // 更新变量导出
  const updateVariableExport = (index: number, field: keyof StepVariableExport, value: string) => {
    const newExports = [...variableExports];
    newExports[index] = { ...newExports[index], [field]: value };
    setVariableExports(newExports);
  };

  // 删除变量导出
  const removeVariableExport = (index: number) => {
    setVariableExports(variableExports.filter((_, i) => i !== index));
  };

  // 添加数据映射
  const addDataMapping = () => {
    setDataMappings([
      ...dataMappings,
      {
        source_type: "previous_response",
        source_step_id: "",
        source_path: "",
        target_path: "",
        transform_expression: "",
        description: "",
      },
    ]);
  };

  // 更新数据映射
  const updateDataMapping = (index: number, field: string, value: any) => {
    const newMappings = [...dataMappings];
    newMappings[index] = { ...newMappings[index], [field]: value };
    setDataMappings(newMappings);
  };

  // 删除数据映射
  const removeDataMapping = (index: number) => {
    setDataMappings(dataMappings.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl h-[85vh] p-0 flex flex-col">
          <DialogTitle className="sr-only">编辑步骤</DialogTitle>
          <div className="flex items-center justify-center py-12">
            <p className="text-sm text-muted-foreground">加载中...</p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Code className="h-5 w-5 text-primary" />
            编辑步骤
          </DialogTitle>
          <DialogDescription>
            {step?.endpoint && (
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline">{step.endpoint.method}</Badge>
                <code className="text-sm">{step.endpoint.path}</code>
              </div>
            )}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 min-h-0 px-6 py-4">
          <div className="space-y-4 pr-4">
            {/* 基本信息 */}
            <CollapsibleSection
              title="基本信息"
              icon={<GitBranch className="h-4 w-4" />}
              expanded={expandedSections.has("basic")}
              onToggle={() => toggleSection("basic")}
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="step-name">
                    步骤名称 <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="step-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="例如：用户登录"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="step-description">步骤描述</Label>
                  <Textarea
                    id="step-description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="描述这个步骤的作用..."
                    rows={3}
                  />
                </div>
              </div>
            </CollapsibleSection>

            <Separator />

            {/* 请求配置 */}
            <CollapsibleSection
              title="请求配置"
              icon={<Code className="h-4 w-4" />}
              expanded={expandedSections.has("request")}
              onToggle={() => toggleSection("request")}
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="request-override">请求参数覆盖 (JSON)</Label>
                  <Textarea
                    id="request-override"
                    value={requestOverride}
                    onChange={(e) => setRequestOverride(e.target.value)}
                    placeholder='{"username": "test", "password": "123456"}'
                    rows={5}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    覆盖接口默认的请求参数，格式为 JSON
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="headers-override">请求头覆盖 (JSON)</Label>
                  <Textarea
                    id="headers-override"
                    value={headersOverride}
                    onChange={(e) => setHeadersOverride(e.target.value)}
                    placeholder='{"Authorization": "Bearer token"}'
                    rows={3}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    覆盖接口默认的请求头，格式为 JSON
                  </p>
                </div>
              </div>
            </CollapsibleSection>

            <Separator />

            {/* 数据提取器 */}
            <CollapsibleSection
              title="数据提取器"
              icon={<GitBranch className="h-4 w-4" />}
              expanded={expandedSections.has("extractors")}
              onToggle={() => toggleSection("extractors")}
            >
              <div className="space-y-3">
                {extractors.length === 0 ? (
                  <div className="text-center py-4 text-sm text-muted-foreground">
                    暂无数据提取器
                  </div>
                ) : (
                  extractors.map((extractor, index) => (
                    <div
                      key={index}
                      className="rounded-lg border p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">提取器 #{index + 1}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeExtractor(index)}
                          className="h-7 w-7 p-0 hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">名称</Label>
                          <Input
                            value={extractor.name}
                            onChange={(e) =>
                              updateExtractor(index, "name", e.target.value)
                            }
                            placeholder="变量名"
                            className="h-8 text-sm"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">类型</Label>
                          <Select
                            value={extractor.type || "jsonpath"}
                            onValueChange={(value) =>
                              updateExtractor(index, "type", value)
                            }
                          >
                            <SelectTrigger className="h-8 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="jsonpath">JSONPath</SelectItem>
                              <SelectItem value="regex">正则表达式</SelectItem>
                              <SelectItem value="header">Header</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">路径</Label>
                          <Input
                            value={extractor.path}
                            onChange={(e) =>
                              updateExtractor(index, "path", e.target.value)
                            }
                            placeholder="$.data.id"
                            className="h-8 text-sm font-mono"
                          />
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addExtractor}
                  className="w-full gap-1"
                >
                  <Plus className="h-3 w-3" />
                  添加提取器
                </Button>
              </div>
            </CollapsibleSection>

            <Separator />

            {/* 变量导出 */}
            <CollapsibleSection
              title="变量导出"
              icon={<GitBranch className="h-4 w-4" />}
              expanded={expandedSections.has("variable_exports")}
              onToggle={() => toggleSection("variable_exports")}
            >
              <div className="space-y-3">
                {variableExports.length === 0 ? (
                  <div className="text-center py-4 text-sm text-muted-foreground">
                    暂无变量导出
                  </div>
                ) : (
                  variableExports.map((exportItem, index) => (
                    <div key={index} className="rounded-lg border p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">变量导出 #{index + 1}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeVariableExport(index)}
                          className="h-7 w-7 p-0 hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">变量名</Label>
                          <Input
                            value={exportItem.name}
                            onChange={(e) => updateVariableExport(index, "name", e.target.value)}
                            placeholder="siteName"
                            className="h-8 text-sm"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">来源</Label>
                          <Select
                            value={exportItem.source}
                            onValueChange={(value) => updateVariableExport(index, "source", value)}
                          >
                            <SelectTrigger className="h-8 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="request">请求</SelectItem>
                              <SelectItem value="response">响应</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">路径</Label>
                          <Input
                            value={exportItem.path}
                            onChange={(e) => updateVariableExport(index, "path", e.target.value)}
                            placeholder="$.body.name"
                            className="h-8 text-sm font-mono"
                          />
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <Button variant="outline" size="sm" onClick={addVariableExport} className="w-full gap-1">
                  <Plus className="h-3 w-3" />
                  添加变量导出
                </Button>
              </div>
            </CollapsibleSection>

            <Separator />

            {/* 数据依赖 */}
            <CollapsibleSection
              title="数据依赖"
              icon={<GitBranch className="h-4 w-4" />}
              expanded={expandedSections.has("mappings")}
              onToggle={() => toggleSection("mappings")}
            >
              <div className="space-y-3">
                {dataMappings.length === 0 ? (
                  <div className="text-center py-4 text-sm text-muted-foreground">
                    暂无数据依赖
                  </div>
                ) : (
                  dataMappings.map((mapping, index) => (
                    <div
                      key={index}
                      className="rounded-lg border p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">数据映射 #{index + 1}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeDataMapping(index)}
                          className="h-7 w-7 p-0 hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">数据源类型</Label>
                          <Select
                            value={mapping.source_type || "previous_response"}
                            onValueChange={(value) =>
                              updateDataMapping(index, "source_type", value)
                            }
                          >
                            <SelectTrigger className="h-8 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="previous_response">前一步骤响应</SelectItem>
                              <SelectItem value="variable">场景变量</SelectItem>
                              <SelectItem value="static">静态值</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {mapping.source_type === "previous_response" && (
                          <div className="space-y-1">
                            <Label className="text-xs">源步骤</Label>
                            <Select
                              value={mapping.source_step_id || ""}
                              onValueChange={(value) =>
                                updateDataMapping(index, "source_step_id", value)
                              }
                            >
                              <SelectTrigger className="h-8 text-sm">
                                <SelectValue placeholder="选择源步骤" />
                              </SelectTrigger>
                              <SelectContent>
                                {allSteps
                                  .filter((s) => s.id !== stepId) // 排除当前步骤
                                  .map((s) => (
                                    <SelectItem key={s.id} value={s.id}>
                                      步骤 {s.step_order}: {s.name}
                                    </SelectItem>
                                  ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}
                        <div className="space-y-1">
                          <Label className="text-xs">
                            {mapping.source_type === "variable" ? "变量名" : "源路径"}
                          </Label>
                          <Input
                            value={mapping.source_path || ""}
                            onChange={(e) =>
                              updateDataMapping(index, "source_path", e.target.value)
                            }
                            placeholder={
                              mapping.source_type === "variable"
                                ? "变量名"
                                : "$.data.token"
                            }
                            className="h-8 text-sm font-mono"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">目标路径</Label>
                          <Input
                            value={mapping.target_path || ""}
                            onChange={(e) =>
                              updateDataMapping(index, "target_path", e.target.value)
                            }
                            placeholder="headers.Authorization"
                            className="h-8 text-sm font-mono"
                          />
                        </div>
                        <div className="col-span-2 space-y-1">
                          <Label className="text-xs">转换表达式（可选）</Label>
                          <Input
                            value={mapping.transform_expression || ""}
                            onChange={(e) =>
                              updateDataMapping(index, "transform_expression", e.target.value)
                            }
                            placeholder="'Bearer ' + value"
                            className="h-8 text-sm font-mono"
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">描述</Label>
                        <Input
                          value={mapping.description || ""}
                          onChange={(e) =>
                            updateDataMapping(index, "description", e.target.value)
                          }
                          placeholder="描述这个数据映射的作用"
                          className="h-8 text-sm"
                        />
                      </div>
                    </div>
                  ))
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addDataMapping}
                  className="w-full gap-1"
                >
                  <Plus className="h-3 w-3" />
                  添加数据依赖
                </Button>
              </div>
            </CollapsibleSection>

            <Separator />

            {/* 断言 */}
            <CollapsibleSection
              title="断言"
              icon={<CheckCircle2 className="h-4 w-4" />}
              expanded={expandedSections.has("assertions")}
              onToggle={() => toggleSection("assertions")}
            >
              <div className="space-y-3">
                {assertions.length === 0 ? (
                  <div className="text-center py-4 text-sm text-muted-foreground">
                    暂无断言
                  </div>
                ) : (
                  assertions.map((assertion, index) => (
                    <div
                      key={index}
                      className="rounded-lg border p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">断言 #{index + 1}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeAssertion(index)}
                          className="h-7 w-7 p-0 hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-4 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">类型</Label>
                          <Select
                            value={assertion.type}
                            onValueChange={(value) =>
                              updateAssertion(index, "type", value)
                            }
                          >
                            <SelectTrigger className="h-8 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="status">状态码</SelectItem>
                              <SelectItem value="jsonpath">JSONPath</SelectItem>
                              <SelectItem value="header">Header</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {assertion.type !== "status" && (
                          <div className="space-y-1">
                            <Label className="text-xs">路径</Label>
                            <Input
                              value={assertion.path || ""}
                              onChange={(e) =>
                                updateAssertion(index, "path", e.target.value)
                              }
                              placeholder="$.data.code"
                              className="h-8 text-sm font-mono"
                            />
                          </div>
                        )}
                        <div className="space-y-1">
                          <Label className="text-xs">期望值</Label>
                          <Input
                            value={
                              typeof assertion.expected === "object"
                                ? JSON.stringify(assertion.expected)
                                : String(assertion.expected)
                            }
                            onChange={(e) => {
                              let value: any = e.target.value;
                              if (value === "true") value = true;
                              else if (value === "false") value = false;
                              else if (!isNaN(Number(value))) value = Number(value);
                              updateAssertion(index, "expected", value);
                            }}
                            placeholder="200"
                            className="h-8 text-sm font-mono"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">操作符</Label>
                          <Select
                            value={normalizeOperator(assertion.operator)}
                            onValueChange={(value) =>
                              updateAssertion(index, "operator", value)
                            }
                          >
                            <SelectTrigger className="h-8 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {Object.entries(OPERATOR_LABELS).map(([value, label]) => (
                                <SelectItem key={value} value={value}>{label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addAssertion}
                  className="w-full gap-1"
                >
                  <Plus className="h-3 w-3" />
                  添加断言
                </Button>
              </div>
            </CollapsibleSection>

            <Separator />

            {/* 执行配置 */}
            <CollapsibleSection
              title="执行配置"
              icon={<Clock className="h-4 w-4" />}
              expanded={expandedSections.has("execution")}
              onToggle={() => toggleSection("execution")}
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="condition-expression">条件表达式</Label>
                  <Input
                    id="condition-expression"
                    value={conditionExpression}
                    onChange={(e) => setConditionExpression(e.target.value)}
                    placeholder="{{ previous_step.status == 'success' }}"
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    只有满足条件时才执行此步骤，支持变量引用
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="delay-ms">延迟 (毫秒)</Label>
                    <Input
                      id="delay-ms"
                      type="number"
                      value={delayMs}
                      onChange={(e) => setDelayMs(Number(e.target.value))}
                      min={0}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="retry-count">重试次数</Label>
                    <Input
                      id="retry-count"
                      type="number"
                      value={retryCount}
                      onChange={(e) => setRetryCount(Number(e.target.value))}
                      min={0}
                      max={10}
                    />
                  </div>
                  <div className="flex items-end">
                    <div className="flex items-center space-x-2 pb-2">
                      <Checkbox
                        id="continue-on-failure"
                        checked={continueOnFailure}
                        onCheckedChange={(checked) =>
                          setContinueOnFailure(checked as boolean)
                        }
                      />
                      <Label
                        htmlFor="continue-on-failure"
                        className="text-sm cursor-pointer"
                      >
                        失败时继续
                      </Label>
                    </div>
                  </div>
                </div>
              </div>
            </CollapsibleSection>
          </div>
        </ScrollArea>

        <DialogFooter className="gap-2 border-t px-6 py-4 shrink-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving} className="gap-1">
            {saving ? (
              <>
                <Clock className="h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                保存更改
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTNKcFdnPT06MTdhZTQ4OWU=

// 可折叠区块组件
function CollapsibleSection({
  title,
  icon,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 w-full text-left hover:text-primary transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        {icon}
        <span className="font-semibold text-sm">{title}</span>
      </button>
      {expanded && <div className="pl-6">{children}</div>}
    </div>
  );
}
