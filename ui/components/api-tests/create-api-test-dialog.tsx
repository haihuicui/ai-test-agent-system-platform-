/**
 * 创建 API 测试对话框
 */
"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGMWRRPT06YmNmOWUzMGE=

import * as React from "react";
import { useState } from "react";
import { Upload, Link, Sparkles, Loader2, FileCode, Check, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { uploadSchema, createAPITest, generateFromSchema } from "@/lib/api/api-tests";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGMWRRPT06YmNmOWUzMGE=

interface CreateAPITestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectIdentifier: string;
  onSuccess?: () => void;
}

type SchemaSource = "url" | "file";
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGMWRRPT06YmNmOWUzMGE=

type Step = "basic" | "schema" | "generating" | "preview";
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJGMWRRPT06YmNmOWUzMGE=

export function CreateAPITestDialog({
  open,
  onOpenChange,
  projectIdentifier,
  onSuccess,
}: CreateAPITestDialogProps) {
  const [currentStep, setCurrentStep] = useState<Step>("basic");
  const [schemaSource, setSchemaSource] = useState<SchemaSource>("url");

  // 表单数据
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [schemaUrl, setSchemaUrl] = useState("");
  const [schemaFile, setSchemaFile] = useState<File | null>(null);
  const [scriptFormat, setScriptFormat] = useState("playwright");
  const [scriptLanguage, setScriptLanguage] = useState("typescript");

  // 上传和生成状态
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [schemaPath, setSchemaPath] = useState("");
  const [generatedScript, setGeneratedScript] = useState("");
  const [generationInfo, setGenerationInfo] = useState<any>(null);

  // 重置表单
  const resetForm = () => {
    setCurrentStep("basic");
    setSchemaSource("url");
    setName("");
    setDescription("");
    setSchemaUrl("");
    setSchemaFile(null);
    setScriptFormat("playwright");
    setScriptLanguage("typescript");
    setUploading(false);
    setGenerating(false);
    setSchemaPath("");
    setGeneratedScript("");
    setGenerationInfo(null);
  };

  // 处理对话框关闭
  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  // 验证基本信息步骤
  const validateBasicStep = () => {
    if (!name.trim()) {
      toast.error("请输入测试名称");
      return false;
    }
    return true;
  };

  // 验证 Schema 步骤
  const validateSchemaStep = () => {
    if (schemaSource === "url" && !schemaUrl.trim()) {
      toast.error("请输入 Schema URL");
      return false;
    }
    if (schemaSource === "file" && !schemaFile) {
      toast.error("请选择 Schema 文件");
      return false;
    }
    return true;
  };

  // 处理 Schema 上传
  const handleSchemaUpload = async () => {
    if (!validateSchemaStep()) return;

    setUploading(true);
    try {
      let uploadResult;

      if (schemaSource === "file" && schemaFile) {
        // 上传文件
        uploadResult = await uploadSchema(projectIdentifier, schemaFile);
      } else {
        // 从 URL 获取（暂时将 URL 保存为 schema_url）
        uploadResult = {
          schema_path: "",
          schema_url: schemaUrl,
        };
      }

      setSchemaPath(uploadResult.schema_path);

      // 进入生成步骤
      setCurrentStep("generating");

      // 模拟 AI 生成过程（实际应该调用 api_agent）
      await simulateAIGeneration(uploadResult);

    } catch (error: any) {
      console.error("上传 Schema 失败:", error);
      toast.error(error.message || "上传 Schema 失败");
    } finally {
      setUploading(false);
    }
  };

  // 调用 AI 生成（使用真实的 api_agent）
  const simulateAIGeneration = async (uploadResult: any) => {
    setGenerating(true);

    try {
      // 调用后端 API 触发 AI 生成
      const result = await generateFromSchema(projectIdentifier, {
        schema_url: schemaSource === "url" ? schemaUrl : undefined,
        schema_path: schemaSource === "file" ? uploadResult.schema_path : undefined,
        script_format: scriptFormat,
        script_language: scriptLanguage,
        include_auth: true,
        include_security: false,
        include_error_handling: true,
      });

      // 设置生成的内容
      setGeneratedScript(result.test_script);
      setGenerationInfo({
        total_endpoints: result.statistics.total_endpoints,
        total_scenarios: result.statistics.total_scenarios,
        estimated_duration: `${Math.ceil(result.statistics.total_scenarios / 5)}-${Math.ceil(result.statistics.total_scenarios / 3)} 分钟`,
      });

      setCurrentStep("preview");

    } catch (error: any) {
      console.error("AI 生成失败:", error);
      toast.error(error.message || "AI 生成失败，请稍后重试");
      setCurrentStep("schema");
    } finally {
      setGenerating(false);
    }
  };

  // 处理最终创建
  const handleCreate = async () => {
    try {
      // 生成脚本路径
      const scriptPath = `api-test-scripts/${projectIdentifier}/${Date.now()}.spec.ts`;

      await createAPITest(projectIdentifier, {
        name,
        description: description || undefined,
        schema_path: schemaPath || "",
        script_path: scriptPath,
        script_format: scriptFormat,
        script_language: scriptLanguage,
        schema_url: schemaSource === "url" ? schemaUrl : undefined,
        total_endpoints: generationInfo?.total_endpoints || 0,
        total_scenarios: generationInfo?.total_scenarios || 0,
      });

      toast.success("API 测试创建成功");
      resetForm();
      onOpenChange(false);
      onSuccess?.();

    } catch (error: any) {
      console.error("创建 API 测试失败:", error);
      toast.error(error.message || "创建失败");
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case "basic":
        return (
          <div className="space-y-6 py-6">
            <div>
              <h3 className="text-lg font-semibold mb-4">基本信息</h3>
              <p className="text-sm text-muted-foreground mb-6">
                填写 API 测试的基本信息
              </p>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">
                  测试名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如: 用户管理 API 测试"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && validateBasicStep()) {
                      setCurrentStep("schema");
                    }
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">描述</Label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="简要描述此 API 测试的目的和范围"
                  className="w-full min-h-[100px] px-3 py-2 text-sm rounded-md border border-input bg-background"
                />
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <Button
                onClick={() => {
                  if (validateBasicStep()) {
                    setCurrentStep("schema");
                  }
                }}
              >
                下一步
              </Button>
            </div>
          </div>
        );

      case "schema":
        return (
          <div className="space-y-6 py-6">
            <div>
              <h3 className="text-lg font-semibold mb-4">API Schema</h3>
              <p className="text-sm text-muted-foreground mb-6">
                上传或提供 OpenAPI/Swagger Schema 文件，AI 将根据 Schema 自动生成测试脚本
              </p>
            </div>

            {/* Schema 来源选择 */}
            <div className="space-y-4">
              <Label>Schema 来源</Label>
              <div className="flex gap-4">
                <Button
                  type="button"
                  variant={schemaSource === "url" ? "default" : "outline"}
                  onClick={() => setSchemaSource("url")}
                  className="flex-1"
                >
                  <Link className="mr-2 h-4 w-4" />
                  URL 链接
                </Button>
                <Button
                  type="button"
                  variant={schemaSource === "file" ? "default" : "outline"}
                  onClick={() => setSchemaSource("file")}
                  className="flex-1"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  上传文件
                </Button>
              </div>
            </div>

            {/* URL 输入 */}
            {schemaSource === "url" && (
              <div className="space-y-2">
                <Label htmlFor="schemaUrl">
                  Schema URL <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="schemaUrl"
                  value={schemaUrl}
                  onChange={(e) => setSchemaUrl(e.target.value)}
                  placeholder="https://api.example.com/openapi.json"
                />
                <p className="text-xs text-muted-foreground">
                  支持公开的 OpenAPI/Swagger JSON 或 YAML URL
                </p>
              </div>
            )}

            {/* 文件上传 */}
            {schemaSource === "file" && (
              <div className="space-y-2">
                <Label>
                  Schema 文件 <span className="text-destructive">*</span>
                </Label>
                <div className="border-2 border-dashed rounded-lg p-8 text-center">
                  <input
                    type="file"
                    id="schemaFile"
                    accept=".json,.yaml,.yml"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        setSchemaFile(file);
                      }
                    }}
                  />
                  <label htmlFor="schemaFile" className="cursor-pointer">
                    <div className="flex flex-col items-center gap-3">
                      <FileCode className="h-10 w-10 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">
                          {schemaFile?.name || "点击选择文件"}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          支持 JSON, YAML 格式，最大 10MB
                        </p>
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {/* 脚本格式 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>脚本格式</Label>
                <Select value={scriptFormat} onValueChange={setScriptFormat}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="playwright">Playwright</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>脚本语言</Label>
                <Select value={scriptLanguage} onValueChange={setScriptLanguage}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="typescript">TypeScript</SelectItem>
                    <SelectItem value="javascript">JavaScript</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <Button
                variant="outline"
                onClick={() => setCurrentStep("basic")}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                上一步
              </Button>
              <Button
                onClick={handleSchemaUpload}
                disabled={uploading}
              >
                {uploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    处理中...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    使用 AI 生成测试
                  </>
                )}
              </Button>
            </div>
          </div>
        );

      case "generating":
        return (
          <div className="flex flex-col items-center justify-center py-16 space-y-6">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping" />
              <Loader2 className="relative h-16 w-16 animate-spin text-primary" />
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold">AI 正在生成测试脚本</h3>
              <p className="text-sm text-muted-foreground">
                分析 API Schema，生成测试场景和断言...
              </p>
            </div>
          </div>
        );

      case "preview":
        return (
          <div className="space-y-6 py-6">
            <div>
              <h3 className="text-lg font-semibold mb-2">生成完成</h3>
              <p className="text-sm text-muted-foreground">
                AI 已为您的 API 生成测试脚本，请预览并确认
              </p>
            </div>

            {/* 统计信息 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-muted/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-primary">
                  {generationInfo?.total_endpoints || 0}
                </div>
                <div className="text-xs text-muted-foreground mt-1">API 端点</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-primary">
                  {generationInfo?.total_scenarios || 0}
                </div>
                <div className="text-xs text-muted-foreground mt-1">测试场景</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-primary">
                  {generationInfo?.estimated_duration || "-"}
                </div>
                <div className="text-xs text-muted-foreground mt-1">预计时长</div>
              </div>
            </div>

            {/* 脚本预览 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>生成的测试脚本</Label>
                <Badge variant="outline">{scriptLanguage}</Badge>
              </div>
              <ScrollArea className="h-[300px] w-full rounded-md border p-4">
                <pre className="text-xs font-mono whitespace-pre-wrap">
                  {generatedScript}
                </pre>
              </ScrollArea>
            </div>

            <div className="flex justify-between pt-4">
              <Button
                variant="outline"
                onClick={() => setCurrentStep("schema")}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回修改
              </Button>
              <Button onClick={handleCreate}>
                <Check className="mr-2 h-4 w-4" />
                确认创建
              </Button>
            </div>
          </div>
        );
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <DialogTitle className="text-lg font-semibold">创建 API 测试</DialogTitle>
            {currentStep !== "basic" && (
              <p className="text-sm text-muted-foreground mt-1">
                {name}
              </p>
            )}
          </div>
        </div>

        {/* 进度指示器 */}
        {currentStep !== "generating" && (
          <div className="flex items-center justify-center gap-2 px-6 py-4 border-b">
            <div
              className={`flex items-center gap-2 text-sm ${
                currentStep === "basic" ? "text-primary font-medium" : "text-muted-foreground"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  currentStep === "basic" || currentStep === "schema" || currentStep === "preview"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                1
              </div>
              基本信息
            </div>
            <div className="w-8 h-px bg-border" />
            <div
              className={`flex items-center gap-2 text-sm ${
                currentStep === "schema" ? "text-primary font-medium" : "text-muted-foreground"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  currentStep === "schema" || currentStep === "preview"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                2
              </div>
              Schema
            </div>
            <div className="w-8 h-px bg-border" />
            <div
              className={`flex items-center gap-2 text-sm ${
                currentStep === "preview" ? "text-primary font-medium" : "text-muted-foreground"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  currentStep === "preview" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                3
              </div>
              预览
            </div>
          </div>
        )}

        {/* 内容 */}
        <ScrollArea className="h-[600px]">
          <div className="px-6">
            {renderStep()}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
