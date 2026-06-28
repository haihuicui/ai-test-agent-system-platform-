/**
 * 场景步骤创建对话框
 *
 * 功能：
 * - 创建新步骤
 * - 选择 API 端点
 * - 配置请求参数
 * - 管理数据提取器
 * - 管理断言
 * - 配置执行选项
 */
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldSVk5nPT06ZTAxMjNiM2I=

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
  Loader2,
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
import { addScenarioStep, listScenarioSteps, addDataMapping } from "@/lib/api/scenarios";
import { listAPIEndpoints } from "@/lib/api/api-endpoints";
import type { StepExtractor, StepAssertion } from "@/types/scenario";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldSVk5nPT06ZTAxMjNiM2I=

interface StepCreateDialogProps {
  scenarioId: string;
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldSVk5nPT06ZTAxMjNiM2I=

export function StepCreateDialog({
  scenarioId,
  projectId,
  open,
  onOpenChange,
  onSave,
}: StepCreateDialogProps) {
  const [endpoints, setEndpoints] = React.useState<any[]>([]);
  const [allSteps, setAllSteps] = React.useState<any[]>([]);
  const [loadingEndpoints, setLoadingEndpoints] = React.useState(false);
  const [saving, setSaving] = React.useState(false);

  // 表单状态
  const [selectedEndpointId, setSelectedEndpointId] = React.useState("");
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

  // UI 状态
  const [expandedSections, setExpandedSections] = React.useState<Set<string>>(
    new Set(["basic", "endpoint", "request", "extractors", "mappings", "assertions", "execution"])
  );

  // 加载 API 端点列表
  React.useEffect(() => {
    if (open) {
      loadEndpoints();
      loadSteps();
    }
  }, [open]);

  const loadEndpoints = async () => {
    try {
      setLoadingEndpoints(true);
      const data = await listAPIEndpoints(projectId, {});
      setEndpoints(data);
    } catch (error) {
      console.error("Failed to load endpoints:", error);
      toast.error("加载接口列表失败");
    } finally {
      setLoadingEndpoints(false);
    }
  };

  const loadSteps = async () => {
    try {
      const steps = await listScenarioSteps(scenarioId);
      setAllSteps(steps);
    } catch (error) {
      console.error("Failed to load steps:", error);
    }
  };

  const handleSave = async () => {
    // 验证
    if (!name.trim()) {
      toast.error("请输入步骤名称");
      return;
    }

    if (!selectedEndpointId) {
      toast.error("请选择 API 端点");
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

      // 计算步骤顺序
      const stepOrder = allSteps.length + 1;

      // 1. 先创建步骤
      const newStep = await addScenarioStep(scenarioId, {
        endpoint_id: selectedEndpointId,
        name: name.trim(),
        description: description.trim() || undefined,
        step_order: stepOrder,
        request_override: JSON.parse(requestOverride),
        headers_override: JSON.parse(headersOverride),
        condition_expression: conditionExpression.trim() || undefined,
        continue_on_failure: continueOnFailure,
        delay_ms: delayMs,
        retry_count: retryCount,
        extractors: extractors,
        assertions: assertions,
      });

      // 2. 添加数据映射
      for (const mapping of dataMappings) {
        // 只有当映射配置完整时才添加
        if (mapping.target_path && mapping.source_type) {
          await addDataMapping(scenarioId, newStep.id, {
            source_type: mapping.source_type,
            source_step_id: mapping.source_step_id,
            source_path: mapping.source_path,
            target_path: mapping.target_path,
            transform_expression: mapping.transform_expression,
            description: mapping.description,
          });
        }
      }

      toast.success("步骤已创建");
      resetForm();
      onSave();
    } catch (error: any) {
      console.error("Failed to create step:", error);
      toast.error(error.message || "创建步骤失败");
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setSelectedEndpointId("");
    setName("");
    setDescription("");
    setRequestOverride("{}");
    setHeadersOverride("{}");
    setConditionExpression("");
    setContinueOnFailure(false);
    setDelayMs(0);
    setRetryCount(0);
    setExtractors([]);
    setAssertions([]);
    setDataMappings([]);
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
    setAssertions([...assertions, { type: "status", expected: 200 }]);
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

  // 添加数据映射
  const addDataMappingRow = () => {
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

  const selectedEndpoint = endpoints.find((e) => e.id === selectedEndpointId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Plus className="h-5 w-5 text-primary" />
            添加步骤
          </DialogTitle>
          <DialogDescription>
            {selectedEndpoint && (
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline">{selectedEndpoint.method}</Badge>
                <code className="text-sm">{selectedEndpoint.path}</code>
              </div>
            )}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 min-h-0 px-6 py-4">
          {loadingEndpoints ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
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

              {/* 选择 API 端点 */}
              <CollapsibleSection
                title="API 端点"
                icon={<Code className="h-4 w-4" />}
                expanded={expandedSections.has("endpoint")}
                onToggle={() => toggleSection("endpoint")}
              >
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="endpoint-select">
                      选择 API 端点 <span className="text-destructive">*</span>
                    </Label>
                    <Select value={selectedEndpointId} onValueChange={setSelectedEndpointId}>
                      <SelectTrigger id="endpoint-select">
                        <SelectValue placeholder="选择要调用的 API 端点" />
                      </SelectTrigger>
                      <SelectContent>
                        {endpoints.map((endpoint) => (
                          <SelectItem key={endpoint.id} value={endpoint.id}>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-xs">
                                {endpoint.method}
                              </Badge>
                              <span className="font-mono text-xs">{endpoint.path}</span>
                              <span className="text-muted-foreground">{endpoint.display_name}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedEndpoint && (
                      <div className="mt-2 p-3 bg-muted/50 rounded-lg space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground">接口名称：</span>
                          <span className="text-sm font-medium">{selectedEndpoint.display_name}</span>
                        </div>
                        {selectedEndpoint.description && (
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">描述：</span>
                            <span className="text-sm">{selectedEndpoint.description}</span>
                          </div>
                        )}
                      </div>
                    )}
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
                      <div key={index} className="rounded-lg border p-3 space-y-2">
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
                              onChange={(e) => updateExtractor(index, "name", e.target.value)}
                              placeholder="变量名"
                              className="h-8 text-sm"
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">类型</Label>
                            <Select
                              value={extractor.type || "jsonpath"}
                              onValueChange={(value) => updateExtractor(index, "type", value)}
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
                              onChange={(e) => updateExtractor(index, "path", e.target.value)}
                              placeholder="$.data.id"
                              className="h-8 text-sm font-mono"
                            />
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                  <Button variant="outline" size="sm" onClick={addExtractor} className="w-full gap-1">
                    <Plus className="h-3 w-3" />
                    添加提取器
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
                      <div key={index} className="rounded-lg border p-3 space-y-2">
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
                              onValueChange={(value) => updateDataMapping(index, "source_type", value)}
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
                                onValueChange={(value) => updateDataMapping(index, "source_step_id", value)}
                              >
                                <SelectTrigger className="h-8 text-sm">
                                  <SelectValue placeholder="选择源步骤" />
                                </SelectTrigger>
                                <SelectContent>
                                  {allSteps.map((s) => (
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
                              onChange={(e) => updateDataMapping(index, "source_path", e.target.value)}
                              placeholder={mapping.source_type === "variable" ? "变量名" : "$.data.token"}
                              className="h-8 text-sm font-mono"
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">目标路径</Label>
                            <Input
                              value={mapping.target_path || ""}
                              onChange={(e) => updateDataMapping(index, "target_path", e.target.value)}
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
                            onChange={(e) => updateDataMapping(index, "description", e.target.value)}
                            placeholder="描述这个数据映射的作用"
                            className="h-8 text-sm"
                          />
                        </div>
                      </div>
                    ))
                  )}
                  <Button variant="outline" size="sm" onClick={addDataMappingRow} className="w-full gap-1">
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
                    <div className="text-center py-4 text-sm text-muted-foreground">暂无断言</div>
                  ) : (
                    assertions.map((assertion, index) => (
                      <div key={index} className="rounded-lg border p-3 space-y-2">
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
                              onValueChange={(value) => updateAssertion(index, "type", value)}
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
                                onChange={(e) => updateAssertion(index, "path", e.target.value)}
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
                              value={assertion.operator || "equals"}
                              onValueChange={(value) => updateAssertion(index, "operator", value)}
                            >
                              <SelectTrigger className="h-8 text-sm">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="equals">等于</SelectItem>
                                <SelectItem value="not_equals">不等于</SelectItem>
                                <SelectItem value="contains">包含</SelectItem>
                                <SelectItem value="greater_than">大于</SelectItem>
                                <SelectItem value="less_than">小于</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                  <Button variant="outline" size="sm" onClick={addAssertion} className="w-full gap-1">
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
                          onCheckedChange={(checked) => setContinueOnFailure(checked as boolean)}
                        />
                        <Label htmlFor="continue-on-failure" className="text-sm cursor-pointer">
                          失败时继续
                        </Label>
                      </div>
                    </div>
                  </div>
                </div>
              </CollapsibleSection>
            </div>
          )}
        </ScrollArea>

        <DialogFooter className="gap-2 border-t px-6 py-4 shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving} className="gap-1">
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                创建中...
              </>
            ) : (
              <>
                <Plus className="h-4 w-4" />
                创建步骤
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

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
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {icon}
        <span className="font-semibold text-sm">{title}</span>
      </button>
      {expanded && <div className="pl-6">{children}</div>}
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldSVk5nPT06ZTAxMjNiM2I=
