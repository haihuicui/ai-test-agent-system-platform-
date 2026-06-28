/**
 * 创建/编辑 Web 功能对话框
 * 用于手工创建或编辑 Web Function
 */
"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkcxWVp3PT06MDIyMzMyY2Y=

import * as React from "react";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import type { WebFunction } from "@/lib/api/web-functions";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkcxWVp3PT06MDIyMzMyY2Y=

interface CreateWebFunctionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  folderId?: string | null;
  editingFunction?: WebFunction | null;
  onSuccess?: () => void;
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkcxWVp3PT06MDIyMzMyY2Y=

export function CreateWebFunctionDialog({
  open,
  onOpenChange,
  projectId,
  folderId,
  editingFunction,
  onSuccess,
}: CreateWebFunctionDialogProps) {
  const [submitting, setSubmitting] = useState(false);

  // 判断是否为编辑模式
  const isEditMode = !!editingFunction;

  // 表单数据
  const [displayName, setDisplayName] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [businessModule, setBusinessModule] = useState("");

  // 重置表单
  const resetForm = () => {
    setDisplayName("");
    setName("");
    setDescription("");
    setBaseUrl("");
    setBusinessModule("");
  };

  // 当对话框打开或编辑功能变化时，初始化表单
  React.useEffect(() => {
    if (open && editingFunction) {
      // 编辑模式：填充现有数据
      setDisplayName(editingFunction.display_name || "");
      setName(editingFunction.name || "");
      setDescription(editingFunction.description || "");
      setBaseUrl(editingFunction.base_url || "");
      setBusinessModule(editingFunction.business_module || "");
    } else if (open && !editingFunction) {
      // 创建模式：重置表单
      resetForm();
    }
  }, [open, editingFunction]);

  // 处理对话框关闭
  const handleOpenChange = (open: boolean) => {
    if (!open && !submitting) {
      resetForm();
    }
    onOpenChange(open);
  };

  // 处理保存
  const handleSave = async () => {
    // 验证必填字段
    if (!displayName.trim()) {
      toast.error("请输入显示名称");
      return;
    }
    if (!name.trim()) {
      toast.error("请输入英文名称");
      return;
    }

    // 验证英文名称格式（只允许字母、数字、连字符和下划线）
    const nameRegex = /^[a-zA-Z0-9-_]+$/;
    if (!nameRegex.test(name.trim())) {
      toast.error("英文名称只能包含字母、数字、连字符和下划线");
      return;
    }

    try {
      setSubmitting(true);

      const requestBody: any = {
        display_name: displayName.trim(),
        name: name.trim(),
      };

      // 添加所有非空的字段到请求中
      if (description.trim()) requestBody.description = description.trim();
      if (baseUrl.trim()) requestBody.base_url = baseUrl.trim();
      // business_module: 即使为空字符串也要发送，这样可以清空该字段
      requestBody.business_module = businessModule.trim();
      if (folderId) requestBody.folder_id = folderId;

      let response;
      if (isEditMode && editingFunction) {
        // 编辑模式：使用 PATCH 更新
        response = await fetch(
          `/api/v2/projects/${projectId}/web-functions/${editingFunction.id}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(requestBody),
          }
        );
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "更新 Web 功能失败");
        }
        toast.success("Web 功能更新成功");
      } else {
        // 创建模式：使用 POST 创建
        response = await fetch(
          `/api/v2/projects/${projectId}/web-functions`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(requestBody),
          }
        );
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "创建 Web 功能失败");
        }
        toast.success("Web 功能创建成功");
      }

      resetForm();
      onOpenChange(false);
      onSuccess?.();
    } catch (error: any) {
      console.error(isEditMode ? "更新 Web 功能失败:" : "创建 Web 功能失败:", error);
      toast.error(error.message || (isEditMode ? "更新 Web 功能失败" : "创建 Web 功能失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditMode ? "编辑 Web 功能" : "创建 Web 功能"}</DialogTitle>
          <DialogDescription>
            {isEditMode ? "编辑现有的 Web 功能配置" : "手工创建单个 Web 功能，填写功能的完整信息"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* 显示名称 */}
          <div className="space-y-2">
            <Label htmlFor="displayName">
              显示名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="例如：用户登录功能"
              disabled={submitting}
            />
            <p className="text-xs text-muted-foreground">
              功能的中文名称，用于界面显示
            </p>
          </div>

          {/* 英文名称 */}
          <div className="space-y-2">
            <Label htmlFor="name">
              英文名称 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：user-login"
              disabled={submitting}
            />
            <p className="text-xs text-muted-foreground">
              功能的英文标识符，只能包含字母、数字、连字符和下划线
            </p>
          </div>

          {/* 业务模块 */}
          <div className="space-y-2">
            <Label htmlFor="businessModule">业务模块</Label>
            <Input
              id="businessModule"
              value={businessModule}
              onChange={(e) => setBusinessModule(e.target.value)}
              placeholder="例如：用户管理、订单服务等"
              disabled={submitting}
            />
            <p className="text-xs text-muted-foreground">
              用于功能分类和模块化管理
            </p>
          </div>

          {/* 基础 URL */}
          <div className="space-y-2">
            <Label htmlFor="baseUrl">基础 URL</Label>
            <Input
              id="baseUrl"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="例如：https://example.com"
              disabled={submitting}
            />
            <p className="text-xs text-muted-foreground">
              功能测试的基础网址
            </p>
          </div>

          {/* 详细描述 */}
          <div className="space-y-2">
            <Label htmlFor="description">详细描述</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="详细描述功能的作用、测试要点等"
              className="min-h-[100px] resize-none"
              disabled={submitting}
            />
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
          <Button onClick={handleSave} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isEditMode ? "保存中..." : "创建中..."}
              </>
            ) : (
              isEditMode ? "保存更改" : "创建功能"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkcxWVp3PT06MDIyMzMyY2Y=
