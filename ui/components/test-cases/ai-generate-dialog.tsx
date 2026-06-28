"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhoRFlnPT06NDEyYjVkN2E=

import * as React from "react";
import { Sparkles, Loader2, X } from "lucide-react";
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
import { generateTestCasesFromPrompt } from "@/lib/api/ai";
import type { TestCaseInfo, TestCaseTemplate } from "@/lib/api/types";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhoRFlnPT06NDEyYjVkN2E=

interface AIGenerateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  folderId?: string | null;
  onSuccess?: (testCases: TestCaseInfo[]) => void;
  onOpenChat?: (prompt: string) => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhoRFlnPT06NDEyYjVkN2E=

export function AIGenerateDialog({
  open,
  onOpenChange,
  projectId,
  folderId,
  onSuccess,
  onOpenChat,
}: AIGenerateDialogProps) {
  const [prompt, setPrompt] = React.useState("");
  const [template, setTemplate] = React.useState<TestCaseTemplate>("test_case");
  const [generating, setGenerating] = React.useState(false);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      toast.error("请输入生成提示词");
      return;
    }

    // 如果提供了 onOpenChat 回调，使用聊天界面
    if (onOpenChat) {
      const chatPrompt = `请帮我生成测试用例。

需求描述：
${prompt.trim()}

模板类型：${template === "test_case" ? "标准测试用例" : template === "test_case_bdd" ? "BDD测试用例" : "其他"}
${folderId ? `目标文件夹ID：${folderId}` : ""}

请根据以上需求生成测试用例。`;

      onOpenChat(chatPrompt);
      setPrompt("");
      return;
    }

    // 否则使用原来的 API 方式
    try {
      setGenerating(true);
      const response = await generateTestCasesFromPrompt(projectId, {
        prompt: prompt.trim(),
        folder_id: folderId,
        template,
      });

      if (response.success && response.test_cases.length > 0) {
        toast.success(`成功生成 ${response.test_cases.length} 个测试用例`);
        onSuccess?.(response.test_cases);
        onOpenChange(false);
        setPrompt("");
      } else {
        toast.error(response.message || "生成测试用例失败");
      }
    } catch (error) {
      console.error("Failed to generate test cases:", error);
      toast.error("生成测试用例失败，请稍后重试");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="h-5 w-5 text-primary" />
            AI 生成测试用例
          </DialogTitle>
          <DialogDescription className="text-base">
            使用自然语言描述功能需求，AI 将自动生成完整的测试用例
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
          {/* 快捷建议 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">试试这些：</Label>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-auto py-2 px-3 text-xs"
                onClick={() => setPrompt("为用户登录功能生成测试用例，包括用户名密码验证、记住密码、忘记密码、第三方登录等场景")}
              >
                <Sparkles className="h-3 w-3 mr-1" />
                为用户登录生成测试用例
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-auto py-2 px-3 text-xs"
                onClick={() => setPrompt("为密码重置功能生成测试用例，包括邮箱验证、验证码验证、密码强度检查、重置成功后的登录等场景")}
              >
                <Sparkles className="h-3 w-3 mr-1" />
                为密码重置生成测试用例
              </Button>
            </div>
          </div>
          {/* 提示词输入 */}
          <div className="space-y-2">
            <Label htmlFor="prompt" className="text-sm font-medium">
              描述您想要测试的功能 <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="例如：用户登录功能，包括用户名密码验证、记住密码、忘记密码、第三方登录等场景..."
              rows={6}
              className="resize-none"
            />
            <p className="text-xs text-muted-foreground flex items-start gap-1">
              <span className="text-primary">💡</span>
              <span>描述越详细，生成的测试用例越准确。可以包含功能描述、业务场景、边界条件等信息。</span>
            </p>
          </div>

          {/* 配置选项 */}
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
            disabled={generating || !prompt.trim()}
            className="min-w-[140px]"
          >
            {generating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                AI 生成中...
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
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhoRFlnPT06NDEyYjVkN2E=

