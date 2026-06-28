/**
 * API 解析对话框（增强版）
 *
 * 支持两种方式：
 * 1. 输入 OpenAPI 文档的 URL
 * 2. 上传本地 JSON 文件
 */
"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhBM1J3PT06ZGVhNWQ4OGM=

import * as React from "react";
import { useState } from "react";
import { Upload, FileCode, Loader2, CheckCircle2, FolderOpen, Link as LinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhBM1J3PT06ZGVhNWQ4OGM=

interface APIParseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectIdentifier: string;
  onSuccess?: () => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhBM1J3PT06ZGVhNWQ4OGM=

type SourceType = "url" | "file";
type Step = "input" | "parsing" | "success";
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhBM1J3PT06ZGVhNWQ4OGM=

export function APIParseDialog({
  open,
  onOpenChange,
  projectIdentifier,
  onSuccess,
}: APIParseDialogProps) {
  const [currentStep, setCurrentStep] = useState<Step>("input");
  const [sourceType, setSourceType] = useState<SourceType>("file");
  const [url, setUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseResult, setParseResult] = useState<any>(null);

  // 重置表单
  const resetForm = () => {
    setCurrentStep("input");
    setSourceType("file");
    setUrl("");
    setSelectedFile(null);
    setParsing(false);
    setParseResult(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  // 选择文件
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.json')) {
        toast.error("请选择 JSON 格式的文件");
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error("文件大小不能超过 10MB");
        return;
      }
      setSelectedFile(file);
    }
  };

  // 解析 OpenAPI 文件
  const handleParse = async () => {
    // 验证输入
    if (sourceType === "url" && !url.trim()) {
      toast.error("请输入 URL 地址");
      return;
    }
    if (sourceType === "file" && !selectedFile) {
      toast.error("请选择文件");
      return;
    }

    setParsing(true);
    setCurrentStep("parsing");

    try {
      let fileContent: any;

      if (sourceType === "file") {
        // 从文件读取
        const text = await selectedFile!.text();
        fileContent = JSON.parse(text);
      } else {
        // 从 URL 获取（后端会处理远程获取）
        fileContent = { url: url.trim() };
      }

      // 调用后端 API
      const response = await fetch('/api/v2/upload-openapi', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_identifier: projectIdentifier,
          parent_folder_id: null,
          file_content: fileContent,
          create_structure: true,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '解析失败');
      }

      const result = await response.json();
      setParseResult(result);
      setCurrentStep("success");

      // 触发成功回调
      onSuccess?.();
      toast.success("OpenAPI 文档解析成功！");

    } catch (error: any) {
      console.error("解析 OpenAPI 失败:", error);
      toast.error(error.message || "解析 OpenAPI 文件失败，请检查文件格式或 URL 是否可访问");
      setCurrentStep("input");
    } finally {
      setParsing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <FileCode className="h-5 w-5 text-primary" />
            {currentStep === "input" && "API 文档解析"}
            {currentStep === "parsing" && "正在解析..."}
            {currentStep === "success" && "解析成功！"}
          </DialogTitle>
          <DialogDescription className="text-base">
            {currentStep === "input" &&
              "支持输入 URL 或上传 JSON 文件，自动创建文件夹结构并提取接口信息"
            }
            {currentStep === "parsing" &&
              "正在解析文档并创建文件夹结构，请稍候..."
            }
            {currentStep === "success" &&
              "文档解析成功，文件夹结构已创建！"
            }
          </DialogDescription>

          {/* 安全提示 */}
          {currentStep === "input" && (
            <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700 mt-3">
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>您的数据是安全的，不会用于 AI 训练</span>
            </div>
          )}
        </DialogHeader>

        {/* 输入步骤 */}
        {currentStep === "input" && (
          <div className="space-y-6 py-4">
            {/* 来源选择 */}
            <div className="space-y-3">
              <Label>选择来源方式</Label>
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant={sourceType === "url" ? "default" : "outline"}
                  onClick={() => setSourceType("url")}
                  className="flex-1"
                >
                  <LinkIcon className="mr-2 h-4 w-4" />
                  URL 地址
                </Button>
                <Button
                  type="button"
                  variant={sourceType === "file" ? "default" : "outline"}
                  onClick={() => setSourceType("file")}
                  className="flex-1"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  上传文件
                </Button>
              </div>
            </div>

            {/* URL 输入 */}
            {sourceType === "url" && (
              <div className="space-y-2">
                <Label htmlFor="apiUrl">
                  OpenAPI/Swagger URL <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="apiUrl"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://api.example.com/openapi.json"
                />
                <p className="text-xs text-muted-foreground">
                  支持公开的 OpenAPI/Swagger JSON URL
                </p>
              </div>
            )}

            {/* 文件上传 */}
            {sourceType === "file" && (
              <div className="space-y-2">
                <Label>
                  选择 JSON 文件 <span className="text-destructive">*</span>
                </Label>
                <div className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary transition-colors">
                  <input
                    type="file"
                    id="openapiFile"
                    accept=".json"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                  <label htmlFor="openapiFile" className="cursor-pointer">
                    <div className="flex flex-col items-center gap-3">
                      {selectedFile ? (
                        <>
                          <FileCode className="h-12 w-12 text-primary" />
                          <div>
                            <p className="text-sm font-medium">{selectedFile.name}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {(selectedFile.size / 1024).toFixed(2)} KB
                            </p>
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.preventDefault();
                              setSelectedFile(null);
                            }}
                          >
                            重新选择
                          </Button>
                        </>
                      ) : (
                        <>
                          <Upload className="h-12 w-12 text-muted-foreground" />
                          <div>
                            <p className="text-sm font-medium">点击选择文件</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              支持 JSON 格式，最大 10MB
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                  </label>
                </div>
              </div>
            )}

            {/* 说明信息 */}
            <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-700">
              <div className="flex items-start gap-2">
                <FolderOpen className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium mb-2">将自动创建以下结构：</p>
                  <ul className="space-y-1 text-xs">
                    <li>✓ 按标签分组的父文件夹（如 "Activities"）</li>
                    <li>✓ 每个接口的子文件夹（如 "GET-Activities", "POST-Activities"）</li>
                    <li>✓ 提取完整的接口信息（参数、请求体、响应等）</li>
                    <li>✓ 在左侧文件夹树中查看所有接口</li>
                    <li>✓ 点击接口查看详情并生成测试</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* 支持格式说明 */}
            <div className="rounded-lg border p-4 text-sm">
              <p className="font-medium mb-2">支持的文件格式：</p>
              <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                <div>• OpenAPI 3.0.x (JSON)</div>
                <div>• OpenAPI 3.1.x (JSON)</div>
                <div>• Swagger 2.0 (JSON)</div>
              </div>
            </div>
          </div>
        )}

        {/* 解析中步骤 */}
        {currentStep === "parsing" && (
          <div className="flex flex-col items-center justify-center py-16 space-y-6">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping" />
              <Loader2 className="relative h-16 w-16 animate-spin text-primary" />
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold">正在解析 OpenAPI 文档...</h3>
              <p className="text-sm text-muted-foreground">
                {sourceType === "url" ? "从 URL 获取并" : ""}创建文件夹结构并提取接口信息
              </p>
            </div>
          </div>
        )}

        {/* 成功步骤 */}
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
              <h3 className="text-lg font-semibold">解析成功！</h3>
              <p className="text-sm text-muted-foreground">
                OpenAPI 文档已成功解析，文件夹结构已创建
              </p>
            </div>

            {/* 统计信息 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg border p-4 text-center">
                <div className="text-2xl font-bold text-primary">
                  {parseResult.total_tags || parseResult.tag_folders?.length || 0}
                </div>
                <div className="text-xs text-muted-foreground mt-1">标签分组</div>
              </div>
              <div className="rounded-lg border p-4 text-center">
                <div className="text-2xl font-bold text-primary">
                  {parseResult.total_endpoints || 0}
                </div>
                <div className="text-xs text-muted-foreground mt-1">接口总数</div>
              </div>
              <div className="rounded-lg border p-4 text-center">
                <div className="text-2xl font-bold text-green-600">
                  {parseResult.tag_folders?.length || 0}
                </div>
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
                <FolderOpen className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium mb-1">下一步操作：</p>
                  <ul className="space-y-1 text-xs">
                    <li>1. 在左侧文件夹树中查看所有接口</li>
                    <li>2. 点击接口节点查看详细信息</li>
                    <li>3. 使用"AI 生成测试"按钮生成测试用例</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 底部按钮 */}
        <DialogFooter className="gap-2">
          {currentStep === "input" && (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={parsing}
              >
                取消
              </Button>
              <Button
                onClick={handleParse}
                disabled={(!url && sourceType === "url") || (!selectedFile && sourceType === "file") || parsing}
              >
                {parsing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    解析中...
                  </>
                ) : (
                  <>
                    <FileCode className="mr-2 h-4 w-4" />
                    开始解析
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
