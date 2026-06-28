/**
 * AI 生成 Web 功能对话框
 * 用于通过 AI 智能体生成 Web 功能和测试
 */
"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pOdlVBPT06MmE5ZGI0YWE=

import * as React from "react";
import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pOdlVBPT06MmE5ZGI0YWE=

interface AIGenerateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGenerate: (description: string) => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pOdlVBPT06MmE5ZGI0YWE=

export function AIGenerateDialog({
  open,
  onOpenChange,
  onGenerate,
}: AIGenerateDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const [description, setDescription] = useState("");

  // 重置表单
  const resetForm = () => {
    setDescription("");
  };

  // 处理对话框关闭
  const handleOpenChange = (open: boolean) => {
    if (!open && !submitting) {
      resetForm();
    }
    onOpenChange(open);
  };

  // 处理生成
  const handleGenerate = () => {
    // 验证必填字段
    if (!description.trim()) {
      toast.error("请输入功能描述信息");
      return;
    }

    const prompt = `请帮我创建一个Web功能并生成测试：${description.trim()}`;

    onGenerate(prompt);
    resetForm();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-500" />
            AI 生成 Web 功能测试
          </DialogTitle>
          <DialogDescription>
            描述您想要测试的 Web 功能，AI 将自动生成功能定义、测试计划、测试用例和测试脚本
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* 功能描述 */}
          <div className="space-y-2">
            <Label htmlFor="description">
              功能描述 <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="例如：用户登录功能，包含用户名密码登录、手机验证码登录、忘记密码等子功能。需要测试登录成功、失败、验证码错误等场景。"
              className="min-h-[150px] resize-none"
              disabled={submitting}
            />
            <p className="text-xs text-muted-foreground">
              请详细描述要测试的 Web 功能，包括主要功能点、业务场景、测试要求等
            </p>
          </div>

          {/* 示例提示 */}
          <div className="rounded-lg border border-muted bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground mb-2">
              💡 描述示例：
            </p>
            <p className="text-xs text-muted-foreground">
              产品管理功能，包括产品列表查看、产品搜索、产品添加、产品编辑、产品删除等子功能。
              需要测试权限控制、数据验证、分页显示、搜索过滤等功能。
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={submitting || !description.trim()}
            className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white border-0"
          >
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                开始生成
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pOdlVBPT06MmE5ZGI0YWE=
