"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm1SNU1BPT06ZWVkNmNmYjM=

import * as React from "react";
import { Plus, Trash2, GripVertical, Folder, Sparkles, Settings2, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { AttachmentUpload } from "./attachment-upload";
import { toast } from "sonner";
import { aiAssistField } from "@/lib/api/ai";
import type {
  TestCaseInfo,
  TestCaseCreate,
  TestStepCreate,
  Priority,
  TestCaseState,
  TestCaseType,
  TestCaseTemplate,
  AutomationStatus,
} from "@/lib/api/types";

interface TestCaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  testCase?: TestCaseInfo | null;
  onSubmit: (data: TestCaseCreate) => Promise<void>;
  submitting?: boolean;
  folderName?: string;
  projectId?: string;
}
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm1SNU1BPT06ZWVkNmNmYjM=

const defaultFormData: TestCaseCreate = {
  name: "",
  description: "",
  preconditions: "",
  priority: "medium",
  status: "new",
  case_type: "other",
  template: "test_case",
  test_case_steps: [],
  tags: [],
  module: "",
  test_data: "",
  case_number: "",
};
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm1SNU1BPT06ZWVkNmNmYjM=

export function TestCaseDialog({
  open,
  onOpenChange,
  testCase,
  onSubmit,
  submitting,
  folderName,
  projectId,
}: TestCaseDialogProps) {
  const [formData, setFormData] = React.useState<TestCaseCreate>(defaultFormData);
  const [steps, setSteps] = React.useState<TestStepCreate[]>([{ step: "", result: "" }]);
  const [template, setTemplate] = React.useState<TestCaseTemplate>("test_case");
  const [createAnother, setCreateAnother] = React.useState(false);
  const [automationStatus, setAutomationStatus] = React.useState<AutomationStatus>("not_automated");
  const [owner, setOwner] = React.useState("Myself");
  const [aiAssisting, setAiAssisting] = React.useState<string | null>(null);
  const [attachmentFiles, setAttachmentFiles] = React.useState<File[]>([]);

  // 初始化表单数据
  React.useEffect(() => {
    if (testCase) {
      setFormData({
        name: testCase.name,
        description: testCase.description || "",
        preconditions: testCase.preconditions || "",
        priority: testCase.priority,
        status: testCase.status,
        case_type: testCase.case_type,
        template: testCase.template,
        tags: testCase.tags || [],
        feature: testCase.feature || "",
        scenario: testCase.scenario || "",
        background: testCase.background || "",
        module: testCase.module || "",
        case_number: testCase.case_number || "",
        test_data: testCase.test_data
          ? typeof testCase.test_data === "string"
            ? testCase.test_data
            : JSON.stringify(testCase.test_data, null, 2)
          : "",
      });
      setSteps(
        testCase.test_case_steps?.map((s) => ({
          step: s.step,
          result: s.result || "",
        })) || [{ step: "", result: "" }]
      );
      setTemplate(testCase.template);
    } else {
      setFormData(defaultFormData);
      setSteps([{ step: "", result: "" }]);
      setTemplate("test_case");
    }
  }, [testCase, open]);

  // 添加步骤
  const addStep = () => {
    setSteps([...steps, { step: "", result: "" }]);
  };

  // 删除步骤
  const removeStep = (index: number) => {
    if (steps.length > 1) {
      setSteps(steps.filter((_, i) => i !== index));
    }
  };

  // 更新步骤
  const updateStep = (
    index: number,
    field: keyof TestStepCreate,
    value: string
  ) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    setSteps(newSteps);
  };

  // AI辅助填充字段
  const handleAIAssist = async (field: "description" | "preconditions" | "steps") => {
    if (!projectId) {
      toast.error("项目ID未提供");
      return;
    }

    if (!formData.name.trim()) {
      toast.error("请先输入测试用例标题");
      return;
    }

    try {
      setAiAssisting(field);
      const response = await aiAssistField(projectId, {
        field,
        context: {
          title: formData.name,
          description: formData.description,
          preconditions: formData.preconditions,
          existing_steps: steps,
        },
      });

      if (response.success) {
        if (field === "description") {
          setFormData({ ...formData, description: response.content as string });
          toast.success("AI 已生成描述内容");
        } else if (field === "preconditions") {
          setFormData({ ...formData, preconditions: response.content as string });
          toast.success("AI 已生成前置条件");
        } else if (field === "steps") {
          const generatedSteps = response.content as Array<{ step: string; result: string }>;
          setSteps(generatedSteps.length > 0 ? generatedSteps : [{ step: "", result: "" }]);
          toast.success("AI 已生成测试步骤");
        }
      } else {
        toast.error(response.message || "AI 辅助失败");
      }
    } catch (error) {
      console.error("AI assist failed:", error);
      toast.error("AI 辅助失败，请稍后重试");
    } finally {
      setAiAssisting(null);
    }
  };

  // 提交表单
  const handleSubmit = async () => {
    let parsedTestData: Record<string, unknown> | undefined = undefined;
    if (typeof formData.test_data === "string" && formData.test_data.trim()) {
      try {
        parsedTestData = JSON.parse(formData.test_data);
      } catch {
        toast.error("测试数据不是合法的 JSON");
        return;
      }
    }

    const data: TestCaseCreate = {
      ...formData,
      template,
      owner: owner === "Myself" ? undefined : owner,
      automation_status: automationStatus,
      test_case_steps: template === "test_case" ? steps.filter(s => s.step.trim()) : undefined,
      test_data: parsedTestData,
      module: formData.module?.trim() || undefined,
      case_number: formData.case_number?.trim() || undefined,
    };
    await onSubmit(data);
    if (createAnother && !testCase) {
      setFormData(defaultFormData);
      setSteps([{ step: "", result: "" }]);
    }
  };

  const isEdit = !!testCase;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-7xl max-h-[90vh] p-0 gap-0">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold">
            {isEdit ? "编辑测试用例" : "创建测试用例"}
          </h2>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => onOpenChange(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* 主体内容 */}
        <div className="flex flex-1 overflow-hidden">
          {/* 左侧表单区域 */}
          <div className="flex-1 overflow-hidden">
            <ScrollArea className="h-[calc(90vh-140px)]">
              <div className="space-y-6 p-6">
                {/* 标题和模板 */}
                <div className="flex gap-4">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="name">
                      标题 <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="name"
                      value={formData.name}
                      onChange={(e) =>
                        setFormData({ ...formData, name: e.target.value })
                      }
                      placeholder="输入测试用例名称"
                    />
                  </div>
                  <div className="w-48 space-y-2">
                    <Label>模板</Label>
                    <Select
                      value={template}
                      onValueChange={(v) => {
                        setTemplate(v as TestCaseTemplate);
                        setFormData({ ...formData, template: v as TestCaseTemplate });
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="test_case">测试步骤</SelectItem>
                        <SelectItem value="test_case_bdd">BDD 测试用例</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* 所在目录 */}
                {folderName && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Folder className="h-4 w-4" />
                    <span>{folderName}</span>
                  </div>
                )}

                {/* 描述 */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="description">描述</Label>
                    {projectId && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                        onClick={() => handleAIAssist("description")}
                        disabled={aiAssisting === "description" || !formData.name.trim()}
                      >
                        {aiAssisting === "description" ? (
                          <>
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span>AI 生成中...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="h-3 w-3" />
                            <span>AI 辅助</span>
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                  <RichTextEditor
                    id="description"
                    value={formData.description || ""}
                    onChange={(value) =>
                      setFormData({ ...formData, description: value })
                    }
                    placeholder="简要描述测试内容"
                    rows={3}
                  />
                </div>

                {/* 前置条件 */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="preconditions">前置条件</Label>
                    {projectId && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                        onClick={() => handleAIAssist("preconditions")}
                        disabled={aiAssisting === "preconditions" || !formData.name.trim()}
                      >
                        {aiAssisting === "preconditions" ? (
                          <>
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span>AI 生成中...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="h-3 w-3" />
                            <span>AI 辅助</span>
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                  <RichTextEditor
                    id="preconditions"
                    value={formData.preconditions || ""}
                    onChange={(value) =>
                      setFormData({ ...formData, preconditions: value })
                    }
                    placeholder="定义测试的前置条件"
                    rows={2}
                  />
                </div>

                {/* 测试步骤和预期结果 - 只在标准模板下显示 */}
                {template === "test_case" && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label>测试步骤和预期结果</Label>
                      {projectId && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                          onClick={() => handleAIAssist("steps")}
                          disabled={aiAssisting === "steps" || !formData.name.trim()}
                        >
                          {aiAssisting === "steps" ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin" />
                              <span>AI 生成中...</span>
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-3 w-3" />
                              <span>AI 生成步骤</span>
                            </>
                          )}
                        </Button>
                      )}
                    </div>

                    {/* 测试数据 */}
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">测试数据</Label>
                      <Textarea
                        value={typeof formData.test_data === "string" ? formData.test_data : ""}
                        onChange={(e) => setFormData({ ...formData, test_data: e.target.value })}
                        placeholder='{"username": "test", "password": "123456"}'
                        className="min-h-[80px] resize-none font-mono text-xs"
                      />
                    </div>

                    {steps.map((step, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <div className="flex items-center gap-2 pt-8">
                          <GripVertical className="h-4 w-4 cursor-grab text-muted-foreground" />
                          <span className="w-4 text-center text-sm text-muted-foreground">
                            {index + 1}
                          </span>
                        </div>
                        <div className="grid flex-1 grid-cols-2 gap-2">
                          <div className="space-y-1">
                            {index === 0 && (
                              <Label className="text-xs text-muted-foreground">Step</Label>
                            )}
                            <RichTextEditor
                              value={step.step}
                              onChange={(value) => updateStep(index, "step", value)}
                              placeholder="步骤详情"
                              rows={2}
                            />
                          </div>
                          <div className="space-y-1">
                            {index === 0 && (
                              <Label className="text-xs text-muted-foreground">Result</Label>
                            )}
                            <RichTextEditor
                              value={step.result || ""}
                              onChange={(value) => updateStep(index, "result", value)}
                              placeholder="预期结果"
                              rows={2}
                            />
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="mt-8 text-muted-foreground hover:text-destructive"
                          onClick={() => removeStep(index)}
                          disabled={steps.length <= 1}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={addStep}
                      className="text-primary"
                    >
                      <Plus className="mr-1 h-4 w-4" />
                      添加步骤
                    </Button>
                  </div>
                )}

                {/* BDD 模板 */}
                {template === "test_case_bdd" && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="background">背景</Label>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs text-muted-foreground hover:text-primary"
                          onClick={() => {
                            const template = "Given [前置条件]\nAnd [其他前置条件]";
                            setFormData({
                              ...formData,
                              background: formData.background
                                ? formData.background + "\n" + template
                                : template
                            });
                          }}
                        >
                          + 创建
                        </Button>
                      </div>
                      <RichTextEditor
                        id="background"
                        value={formData.background || ""}
                        onChange={(value) =>
                          setFormData({ ...formData, background: value })
                        }
                        placeholder="Given [前置条件]"
                        rows={3}
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="feature">功能</Label>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs text-muted-foreground hover:text-primary"
                          onClick={() => {
                            const template = "Feature: [功能名称]\n  作为 [角色]\n  我想要 [功能]\n  以便 [价值]";
                            setFormData({
                              ...formData,
                              feature: formData.feature
                                ? formData.feature + "\n\n" + template
                                : template
                            });
                          }}
                        >
                          + 创建
                        </Button>
                      </div>
                      <RichTextEditor
                        id="feature"
                        value={formData.feature || ""}
                        onChange={(value) =>
                          setFormData({ ...formData, feature: value })
                        }
                        placeholder="Feature: [功能名称]"
                        rows={3}
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="scenario">场景</Label>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs text-muted-foreground hover:text-primary"
                          onClick={() => {
                            const template = "Scenario: [场景名称]\n  Given [前置条件]\n  When [操作]\n  Then [预期结果]";
                            setFormData({
                              ...formData,
                              scenario: formData.scenario
                                ? formData.scenario + "\n\n" + template
                                : template
                            });
                          }}
                        >
                          + 创建
                        </Button>
                      </div>
                      <RichTextEditor
                        id="scenario"
                        value={formData.scenario || ""}
                        onChange={(value) =>
                          setFormData({ ...formData, scenario: value })
                        }
                        placeholder="Scenario: [场景名称]"
                        rows={6}
                      />
                    </div>
                  </div>
                )}

                {/* 附件上传 - 只在标准模板下显示 */}
                {template === "test_case" && (
                  <AttachmentUpload
                    testCaseId={testCase?.id}
                    testCaseIdentifier={testCase?.identifier}
                    projectIdentifier={projectId}
                    onFilesChange={setAttachmentFiles}
                    autoUpload={!!testCase} // 编辑模式自动上传
                    maxFiles={10}
                    maxSize={50}
                  />
                )}
              </div>
            </ScrollArea>
          </div>

          {/* 右侧字段面板 */}
          <div className="w-64 shrink-0 border-l bg-muted/30">
            <ScrollArea className="h-[calc(90vh-140px)]">
              <div className="p-4">
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-sm font-medium">测试用例字段</span>
                  <Button variant="link" size="sm" className="h-auto p-0 text-primary">
                    <Settings2 className="mr-1 h-3 w-3" />
                    配置
                  </Button>
                </div>

                <div className="space-y-4">
                  {/* Owner */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      Owner <span className="text-destructive">*</span>
                    </Label>
                    <Select value={owner} onValueChange={setOwner}>
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Myself">Myself</SelectItem>
                        <SelectItem value="Unassigned">未分配</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* State */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      状态 <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={formData.status}
                      onValueChange={(value: TestCaseState) =>
                        setFormData({ ...formData, status: value })
                      }
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {/* 设计阶段 */}
                        <SelectItem value="new">🆕 新建</SelectItem>
                        <SelectItem value="review_pending">⏳ 待评审</SelectItem>
                        <SelectItem value="reviewed">✅ 已评审</SelectItem>
                        {/* 执行阶段 */}
                        <SelectItem value="not_run">⚪ 未执行</SelectItem>
                        <SelectItem value="passed">✅ 通过</SelectItem>
                        <SelectItem value="failed">❌ 失败</SelectItem>
                        <SelectItem value="blocked">🚫 阻塞</SelectItem>
                        <SelectItem value="skipped">⏭️ 跳过</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Priority */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      优先级 <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={formData.priority}
                      onValueChange={(value: Priority) =>
                        setFormData({ ...formData, priority: value })
                      }
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="critical">🔴 紧急</SelectItem>
                        <SelectItem value="high">🟠 高</SelectItem>
                        <SelectItem value="medium">🟡 中</SelectItem>
                        <SelectItem value="low">🟢 低</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Type of Test Case */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      用例类型 <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={formData.case_type}
                      onValueChange={(value: TestCaseType) =>
                        setFormData({ ...formData, case_type: value })
                      }
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="functional">功能测试</SelectItem>
                        <SelectItem value="smoke_sanity">冒烟测试</SelectItem>
                        <SelectItem value="regression">回归测试</SelectItem>
                        <SelectItem value="security">安全测试</SelectItem>
                        <SelectItem value="performance">性能测试</SelectItem>
                        <SelectItem value="usability">可用性测试</SelectItem>
                        <SelectItem value="acceptance">验收测试</SelectItem>
                        <SelectItem value="integration">集成测试</SelectItem>
                        <SelectItem value="exploratory">探索性测试</SelectItem>
                        <SelectItem value="other">其他</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Automation Status */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      自动化状态 <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={automationStatus}
                      onValueChange={(value) => setAutomationStatus(value as AutomationStatus)}
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="not_automated">未自动化</SelectItem>
                        <SelectItem value="automated">已自动化</SelectItem>
                        <SelectItem value="in_progress">自动化进行中</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* 用例编号 */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">用例编号</Label>
                    <Input
                      placeholder="如 TC-2025-001"
                      value={formData.case_number || ""}
                      onChange={(e) =>
                        setFormData({ ...formData, case_number: e.target.value })
                      }
                      className="h-9"
                    />
                  </div>

                  {/* 所属模块 */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">所属模块</Label>
                    <Input
                      placeholder="如 用户管理"
                      value={formData.module || ""}
                      onChange={(e) =>
                        setFormData({ ...formData, module: e.target.value })
                      }
                      className="h-9"
                    />
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        </div>

        {/* 底部操作栏 */}
        <div className="flex items-center justify-between border-t px-6 py-4">
          <div className="flex items-center gap-2">
            <Checkbox
              id="createAnother"
              checked={createAnother}
              onCheckedChange={(checked) => setCreateAnother(checked as boolean)}
            />
            <Label htmlFor="createAnother" className="text-sm font-normal">
              继续创建下一个
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={submitting || !formData.name.trim()}>
              {submitting ? "保存中..." : isEdit ? "保存" : "创建"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm1SNU1BPT06ZWVkNmNmYjM=
