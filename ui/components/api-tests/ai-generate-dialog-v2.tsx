/**
 * API 测试生成对话框（重构版）
 *
 * 工作流程：
 * 1. 上传并解析 OpenAPI 文件 -> 创建文件夹结构
 * 2. 显示解析结果 -> 用户可以查看和继续操作
 */
"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFwM2RRPT06ZGEyOTE5MjQ=

import * as React from "react";
import { useState } from "react";
import { Sparkles, Loader2, Link as LinkIcon, Upload, FileCode, CheckCircle2, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { uploadSchema } from "@/lib/api/api-tests";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFwM2RRPT06ZGEyOTE5MjQ=

type SchemaSource = "url" | "file";
type Step = "upload" | "success";
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFwM2RRPT06ZGEyOTE5MjQ=

interface AIGenerateAPITestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectIdentifier: string;
  onSuccess?: () => void;
  onOpenChat?: (prompt: string) => void;
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFwM2RRPT06ZGEyOTE5MjQ=

export function AIGenerateAPITestDialog({
  open,
  onOpenChange,
  projectIdentifier,
  onSuccess,
  onOpenChat,
}: AIGenerateAPITestDialogProps) {
  const [currentStep, setCurrentStep] = useState<Step>("upload");
  const [schemaSource, setSchemaSource] = useState<SchemaSource>("url");
  const [schemaUrl, setSchemaUrl] = useState("");
  const [schemaFile, setSchemaFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [parseResult, setParseResult] = useState<any>(null);

  // 重置表单
  const resetForm = () => {
    setCurrentStep("upload");
    setSchemaSource("url");
    setSchemaUrl("");
    setSchemaFile(null);
    setUploading(false);
    setParseResult(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  // 处理 OpenAPI 上传和解析
  const handleUploadAndParse = async () => {
    if (schemaSource === "url" && !schemaUrl.trim()) {
      toast.error("请输入 Schema URL");
      return;
    }
    if (schemaSource === "file" && !schemaFile) {
      toast.error("请选择 Schema 文件");
      return;
    }

    // 如果提供了 onOpenChat，使用聊天界面
    if (onOpenChat) {
      const chatPrompt = `请帮我解析这个 OpenAPI 文档并创建文件夹结构。

${schemaSource === "url" ? `Schema URL: ${schemaUrl}` : `已上传文件: ${schemaFile?.name}`}

请帮我：
1. 解析 OpenAPI 文档
2. 按标签分组创建父文件夹（如 "Activities"）
3. 为每个接口创建子文件夹（如 "GET-Activities", "POST-Activities"）
4. 提取完整的接口信息`;

      onOpenChat(chatPrompt);
      resetForm();
      return;
    }

    // 直接调用 API 解析
    setUploading(true);
    try {
      // 读取文件内容
      let fileContent: any = null;
      if (schemaSource === "file" && schemaFile) {
        const text = await schemaFile.text();
        fileContent = JSON.parse(text);
      }

      // 调用 upload-openapi API
      const response = await fetch(`/api/v2/upload-openapi`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_identifier: projectIdentifier,
          parent_folder_id: null,
          file_content: fileContent || { url: schemaUrl },
          create_structure: true
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '解析失败');
      }

      const result = await response.json();
      setParseResult(result);
      setCurrentStep("success");

      toast.success(result.summary?.message || "解析成功！");
      onSuccess?.();

    } catch (error: any) {
      console.error("解析 OpenAPI 失败:", error);
      toast.error(error.message || "解析 OpenAPI 文件失败，请稍后重试");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="h-5 w-5 text-primary" />
            {currentStep === "upload" ? "上传 OpenAPI 文档" : "解析成功！"}
          </DialogTitle>
          <DialogDescription className="text-base">
            {currentStep === "upload"
              ? "上传 OpenAPI/Swagger 文档，自动创建文件夹结构并提取接口信息"
              : "已成功创建文件夹结构，现在可以查看和生成测试"
            }
          </DialogDescription>

          {/* 安全提示 */}
          <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700 mt-3">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>您的数据是安全的，不会用于 AI 训练</span>
          </div>
        </DialogHeader>

        {currentStep === "upload" && (
          <div className="space-y-6 py-4">
            {/* Schema 来源选择 */}
            <div className="space-y-3">
              <Label>Schema 来源</Label>
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant={schemaSource === "url" ? "default" : "outline"}
                  onClick={() => setSchemaSource("url")}
                  className="flex-1"
                >
                  <LinkIcon className="mr-2 h-4 w-4" />
                  URL 链接
                </Button>
                <Button
                  type="button"
                  variant={schemaSource === "file" ? "default" : "outline"}
                  onClick={() => setSchemaSource("file")}
                  className="flex-1"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  上传 JSON 文件
                </Button>
              </div>
            </div>

            {/* URL 输入 */}
            {schemaSource === "url" && (
              <div className="space-y-2">
                <Label htmlFor="schemaUrl">
                  OpenAPI/Swagger URL <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="schemaUrl"
                  value={schemaUrl}
                  onChange={(e) => setSchemaUrl(e.target.value)}
                  placeholder="https://api.example.com/openapi.json"
                />
                <p className="text-xs text-muted-foreground">
                  支持公开的 OpenAPI/Swagger JSON URL
                </p>
              </div>
            )}

            {/* 文件上传 */}
            {schemaSource === "file" && (
              <div className="space-y-2">
                <Label>
                  JSON 文件 <span className="text-destructive">*</span>
                </Label>
                <div className="border-2 border-dashed rounded-lg p-8 text-center">
                  <input
                    type="file"
                    id="schemaFile"
                    accept=".json"
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
                          {schemaFile?.name || "点击选择 JSON 文件"}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          支持 JSON 格式，最大 10MB
                        </p>
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {/* 说明 */}
            <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-700">
              <div className="flex items-start gap-2">
                <FolderOpen className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium mb-1">将自动创建以下结构：</p>
                  <ul className="space-y-1 text-xs">
                    <li>• 按标签分组的父文件夹（如 "Activities"）</li>
                    <li>• 每个接口的子文件夹（如 "GET-Activities", "POST-Activities"）</li>
                    <li>• 提取完整的接口信息（参数、请求体、响应等）</li>
                    <li>• 可以在左侧文件夹树中查看所有接口</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === "success" && parseResult && (
          <div className="space-y-6 py-4">
            {/* 成功图标 */}
            <div className="flex justify-center">
              <div className="rounded-full bg-green-100 p-4">
                <CheckCircle2 className="h-12 w-12 text-green-600" />
              </div>
            </div>

            {/* 成功消息 */}
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold">{parseResult.summary?.message || "解析成功"}</h3>
              <p className="text-sm text-muted-foreground">
                {parseResult.summary?.structure || "文件夹结构已创建"}
              </p>
            </div>

            {/* 统计信息 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg border p-4 text-center">
                <div className="text-2xl font-bold text-primary">{parseResult.total_tags || 0}</div>
                <div className="text-xs text-muted-foreground mt-1">标签分组</div>
              </div>
              <div className="rounded-lg border p-4 text-center">
                <div className="text-2xl font-bold text-primary">{parseResult.total_endpoints || 0}</div>
                <div className="text-xs text-muted-foreground mt-1">接口总数</div>
              </div>
              <div className="rounded-lg border p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{parseResult.tag_folders?.length || 0}</div>
                <div className="text-xs text-muted-foreground mt-1">已创建文件夹</div>
              </div>
            </div>

            {/* 文件夹列表 */}
            {parseResult.tag_folders && parseResult.tag_folders.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">已创建的文件夹：</Label>
                <div className="rounded-lg border p-4 space-y-2 max-h-48 overflow-y-auto">
                  {parseResult.tag_folders.map((folder: any, index: number) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                      <FolderOpen className="h-4 w-4 text-primary" />
                      <span className="font-medium">{folder.folder_name}</span>
                      <span className="text-muted-foreground">({folder.endpoint_count} 个接口)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 下一步提示 */}
            <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-700">
              <div className="flex items-start gap-2">
                <Sparkles className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium mb-1">下一步操作：</p>
                  <ul className="space-y-1 text-xs">
                    <li>• 在左侧文件夹树中查看所有接口</li>
                    <li>• 点击接口查看详细信息</li>
                    <li>• 使用 AI 助手为特定接口生成测试</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === "upload" && uploading && (
          <div className="flex flex-col items-center justify-center py-16 space-y-6">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping" />
              <Loader2 className="relative h-16 w-16 animate-spin text-primary" />
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold">正在解析 OpenAPI 文档...</h3>
              <p className="text-sm text-muted-foreground">
                创建文件夹结构并提取接口信息
              </p>
            </div>
          </div>
        )}

        <DialogFooter className="gap-2">
          {currentStep === "upload" && (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={uploading}
              >
                取消
              </Button>
              <Button
                onClick={handleUploadAndParse}
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
                    解析并创建结构
                  </>
                )}
              </Button>
            </>
          )}

          {currentStep === "success" && (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  resetForm();
                }}
              >
                再解析一个
              </Button>
              <Button
                onClick={() => {
                  onOpenChange(false);
                  onSuccess?.();
                }}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                完成，查看接口
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
