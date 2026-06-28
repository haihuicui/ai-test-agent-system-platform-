"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1dSaWR3PT06ZDQzZGE2ZTQ=

import * as React from "react";
import { Upload, FileText, Image as ImageIcon, Loader2, X, Sparkles } from "lucide-react";
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
import { toast } from "sonner";
import { generateTestCasesFromDocument } from "@/lib/api/ai";
import type { TestCaseInfo, TestCaseTemplate } from "@/lib/api/types";
import { cn } from "@/lib/utils";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1dSaWR3PT06ZDQzZGE2ZTQ=

interface AIGenerateFromDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  folderId?: string | null;
  onSuccess?: (testCases: TestCaseInfo[]) => void;
  onOpenChat?: (prompt: string) => void;
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1dSaWR3PT06ZDQzZGE2ZTQ=

export function AIGenerateFromDocumentDialog({
  open,
  onOpenChange,
  projectId,
  folderId,
  onSuccess,
  onOpenChat,
}: AIGenerateFromDocumentDialogProps) {
  const [file, setFile] = React.useState<File | null>(null);
  const [additionalPrompt, setAdditionalPrompt] = React.useState("");
  const [template, setTemplate] = React.useState<TestCaseTemplate>("test_case");
  const [generating, setGenerating] = React.useState(false);
  const [dragActive, setDragActive] = React.useState(false);
  const [jiraLinks, setJiraLinks] = React.useState<string[]>([]);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (selectedFile: File) => {
    // 验证文件类型
    const validTypes = [
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
      "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/plain",
    ];

    if (!validTypes.includes(selectedFile.type)) {
      toast.error("不支持的文件类型，请上传图片、PDF 或文档文件");
      return;
    }

    // 验证文件非空（避免上传 0 字节文件导致后续解析失败）
    if (selectedFile.size === 0) {
      toast.error("该文件为空（0 字节），请选择有效的文件");
      return;
    }

    // 验证文件大小（最大10MB）
    if (selectedFile.size > 10 * 1024 * 1024) {
      toast.error("文件大小不能超过 10MB");
      return;
    }

    setFile(selectedFile);
  };

  const handleGenerate = async () => {
    if (!file) {
      toast.error("请先上传文件");
      return;
    }

    // 如果提供了 onOpenChat 回调，使用聊天界面
    if (onOpenChat) {
      try {
        // 先上传文件到 MinIO
        toast.info("正在上传文件...");
        const { uploadDocument } = await import("@/lib/api/documents");
        const uploadResult = await uploadDocument(file);

        if (!uploadResult.success) {
          toast.error("文件上传失败");
          return;
        }

        // 校验后端实际接收到的大小，0 字节直接拦截
        if (!uploadResult.data.file_size) {
          toast.error("上传后检测到文件内容为空（0 字节），请确认文件有效后重试");
          return;
        }

        const fileUrl = uploadResult.data.url;
        const fileName = uploadResult.data.file_name;
        const fileType = uploadResult.data.content_type;

        // 构建提示词，包含文件URL（让智能体自己调用工具解析）
        const chatPrompt = `请帮我从文档中生成测试用例。

文档信息：
- 文件名：${fileName}
- 文件类型：${fileType}
- 文件大小：${(uploadResult.data.file_size / 1024).toFixed(2)} KB
- 文件URL：${fileUrl}

${additionalPrompt.trim() ? `补充说明：\n${additionalPrompt.trim()}\n\n` : ""}模板类型：${template === "test_case" ? "标准测试用例" : template === "test_case_bdd" ? "BDD测试用例" : "其他"}
${folderId ? `目标文件夹ID：${folderId}` : ""}

请先使用 parse_document_from_url 工具解析文档内容，然后根据解析结果生成相应的测试用例。`;

        // 打开聊天对话框
        onOpenChat(chatPrompt);
        setFile(null);
        setAdditionalPrompt("");
        toast.success("文件上传成功");
      } catch (error) {
        console.error("Failed to upload document:", error);
        toast.error(error instanceof Error ? error.message : "文件上传失败");
      }
      return;
    }

    // 否则使用原来的 API 方式
    try {
      setGenerating(true);
      const response = await generateTestCasesFromDocument(projectId, {
        file,
        folder_id: folderId,
        additional_prompt: additionalPrompt.trim() || undefined,
        template,
      });

      if (response.success && response.test_cases.length > 0) {
        toast.success(`成功生成 ${response.test_cases.length} 个测试用例`);
        onSuccess?.(response.test_cases);
        onOpenChange(false);
        setFile(null);
        setAdditionalPrompt("");
      } else {
        toast.error(response.message || "生成测试用例失败");
      }
    } catch (error) {
      console.error("Failed to generate test cases from document:", error);
      toast.error("生成测试用例失败，请稍后重试");
    } finally {
      setGenerating(false);
    }
  };

  const getFileIcon = () => {
    if (!file) return <Upload className="h-8 w-8" />;
    if (file.type.startsWith("image/")) return <ImageIcon className="h-8 w-8" />;
    return <FileText className="h-8 w-8" />;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="h-5 w-5 text-primary" />
            从文档/图片生成测试用例
          </DialogTitle>
          <DialogDescription className="text-base">
            上传需求文档、规格说明或界面截图，AI 将自动分析内容并生成相应的测试用例
          </DialogDescription>

          {/* 安全提示 */}
          <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700 mt-3">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>您的数据是安全的，不会用于 AI 训练</span>
          </div>
        </DialogHeader>

        <div className="space-y-5 py-4">
          {/* 文件上传区域 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">
              上传文件 <span className="text-destructive">*</span>
            </Label>
            <div
              className={cn(
                "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-all cursor-pointer",
                dragActive
                  ? "border-primary bg-primary/10 scale-[1.01]"
                  : file
                  ? "border-primary/50 bg-primary/5"
                  : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30"
              )}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => !file && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept="image/*,.pdf,.doc,.docx,.txt"
                onChange={handleFileChange}
              />

              {file ? (
                <div className="flex w-full items-center justify-between gap-4">
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
                      {getFileIcon()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate text-base">{file.name}</p>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                    }}
                    className="h-9 w-9 shrink-0 hover:bg-destructive/10 hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="text-center">
                  <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                    <Upload className="h-8 w-8 text-primary" />
                  </div>
                  <p className="mb-2 text-base font-medium">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        fileInputRef.current?.click();
                      }}
                      className="text-primary hover:text-primary/80 hover:underline font-semibold"
                    >
                      点击上传文件
                    </button>
                    <span className="text-muted-foreground"> 或拖拽文件到此处</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    支持图片 (JPG, PNG, GIF, WebP)、文档 (PDF, Word, TXT)
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1">
                    文件大小限制：10MB
                  </p>
                  <p className="text-xs text-primary mt-2">
                    试用示例文件：
                    <button
                      type="button"
                      className="ml-1 hover:underline font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        toast.info("示例文件功能开发中");
                      }}
                    >
                      WhatsApp-Delete.pdf
                    </button>
                    {" , "}
                    <button
                      type="button"
                      className="hover:underline font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        toast.info("示例文件功能开发中");
                      }}
                    >
                      Zoom-Guide.pdf
                    </button>
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* JIRA 链接 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">
                添加 JIRA 需求 <span className="text-muted-foreground font-normal">(可选)</span>
              </Label>
            </div>
            <div className="space-y-2">
              {jiraLinks.map((link, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={link}
                    onChange={(e) => {
                      const newLinks = [...jiraLinks];
                      newLinks[index] = e.target.value;
                      setJiraLinks(newLinks);
                    }}
                    placeholder="输入 JIRA 链接"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      setJiraLinks(jiraLinks.filter((_, i) => i !== index));
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setJiraLinks([...jiraLinks, ""])}
                className="w-full"
              >
                + 添加链接
              </Button>
            </div>
          </div>

          {/* 附加提示 */}
          <div className="space-y-2">
            <Label htmlFor="additional-prompt" className="text-sm font-medium">
              附加说明 <span className="text-muted-foreground font-normal">(可选)</span>
            </Label>
            <Textarea
              id="additional-prompt"
              value={additionalPrompt}
              onChange={(e) => setAdditionalPrompt(e.target.value)}
              placeholder="例如：重点关注边界条件测试、需要包含性能测试用例、关注安全性测试等..."
              rows={3}
              className="resize-none"
            />
            <p className="text-xs text-muted-foreground">
              提供额外的上下文信息，帮助 AI 更好地理解您的需求
            </p>
          </div>

          {/* 模板选择 */}
          <div className="space-y-2">
            <Label htmlFor="template" className="text-sm font-medium">测试用例模板</Label>
            <Select
              value={template}
              onValueChange={(v) => setTemplate(v as TestCaseTemplate)}
            >
              <SelectTrigger id="template" className="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="test_case">
                  <div className="flex flex-col items-start">
                    <span className="font-medium">测试步骤模板</span>
                    <span className="text-xs text-muted-foreground">传统的步骤-预期结果格式</span>
                  </div>
                </SelectItem>
                <SelectItem value="test_case_bdd">
                  <div className="flex flex-col items-start">
                    <span className="font-medium">BDD 模板</span>
                    <span className="text-xs text-muted-foreground">Given-When-Then 格式</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={generating}
            className="min-w-[100px]"
          >
            取消
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={generating || !file}
            className="min-w-[140px]"
          >
            {generating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                AI 分析生成中...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                生成测试用例
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1dSaWR3PT06ZDQzZGE2ZTQ=
