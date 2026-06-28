/**
 * 创建 API 接口对话框
 * 用于手工创建单个 API Endpoint
 */
"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzBnMFZ3PT06MWVlNjcxMjE=

import * as React from "react";
import { useState } from "react";
import { Loader2, FileCode, ChevronDown, ChevronUp } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzBnMFZ3PT06MWVlNjcxMjE=

interface CreateEndpointDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  folderId?: string | null;
  onSuccess?: () => void;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzBnMFZ3PT06MWVlNjcxMjE=

export function CreateEndpointDialog({
  open,
  onOpenChange,
  projectId,
  folderId,
  onSuccess,
}: CreateEndpointDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 表单数据
  const [method, setMethod] = useState("GET");
  const [path, setPath] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");
  const [tagGroup, setTagGroup] = useState("");
  const [parameters, setParameters] = useState("");
  const [requestBody, setRequestBody] = useState("");
  const [responses, setResponses] = useState("");

  // 重置表单
  const resetForm = () => {
    setMethod("GET");
    setPath("");
    setDisplayName("");
    setSummary("");
    setDescription("");
    setTagGroup("");
    setParameters("");
    setRequestBody("");
    setResponses("");
    setShowAdvanced(false);
  };

  // 处理对话框关闭
  const handleOpenChange = (open: boolean) => {
    if (!open && !submitting) {
      resetForm();
    }
    onOpenChange(open);
  };

  // JSON 解析辅助函数
  const parseJSON = (jsonStr: string): any => {
    if (!jsonStr || jsonStr.trim() === "") return null;
    try {
      return JSON.parse(jsonStr);
    } catch (error) {
      throw new Error("JSON 格式错误");
    }
  };

  // 处理保存
  const handleSave = async () => {
    // 验证必填字段
    if (!path.trim()) {
      toast.error("请输入请求路径");
      return;
    }
    if (!path.startsWith("/")) {
      toast.error("请求路径必须以 / 开头");
      return;
    }

    try {
      setSubmitting(true);

      // 自动生成 display_name
      const finalDisplayName = displayName.trim() || `${method} ${path}`;

      // 解析 JSON 字段
      let parsedParameters = null;
      let parsedRequestBody = null;
      let parsedResponses = null;

      if (parameters.trim()) {
        try {
          parsedParameters = parseJSON(parameters);
        } catch (error) {
          toast.error("Parameters JSON 格式错误");
          setSubmitting(false);
          return;
        }
      }

      if (requestBody.trim()) {
        try {
          parsedRequestBody = parseJSON(requestBody);
        } catch (error) {
          toast.error("Request Body JSON 格式错误");
          setSubmitting(false);
          return;
        }
      }

      if (responses.trim()) {
        try {
          parsedResponses = parseJSON(responses);
        } catch (error) {
          toast.error("Responses JSON 格式错误");
          setSubmitting(false);
          return;
        }
      }

      const response = await fetch("/api/v2/api-endpoints", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          project_identifier: projectId,
          folder_id: folderId || undefined,
          method,
          path,
          display_name: finalDisplayName,
          summary: summary.trim() || undefined,
          description: description.trim() || undefined,
          tag_group: tagGroup.trim() || undefined,
          parameters: parsedParameters,
          request_body: parsedRequestBody,
          responses: parsedResponses,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "创建接口失败");
      }

      toast.success("接口创建成功");
      resetForm();
      onOpenChange(false);
      onSuccess?.();
    } catch (error: any) {
      console.error("创建接口失败:", error);
      toast.error(error.message || "创建接口失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>创建 API 接口</DialogTitle>
          <DialogDescription>
            手工创建单个 API 接口，填写接口的完整信息
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* 基本信息 */}
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="method">
                  请求方法 <span className="text-destructive">*</span>
                </Label>
                <Select value={method} onValueChange={setMethod} disabled={submitting}>
                  <SelectTrigger id="method">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="PUT">PUT</SelectItem>
                    <SelectItem value="DELETE">DELETE</SelectItem>
                    <SelectItem value="PATCH">PATCH</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="col-span-2 space-y-2">
                <Label htmlFor="path">
                  请求路径 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="path"
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  placeholder="/api/v1/users"
                  disabled={submitting}
                />
              </div>
            </div>

            {/* 接口名称 */}
            <div className="space-y-2">
              <Label htmlFor="displayName">接口名称</Label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="留空自动生成（例如：GET /api/v1/users）"
                disabled={submitting}
              />
              <p className="text-xs text-muted-foreground">
                接口的显示名称，如果不填写将自动生成
              </p>
            </div>

            {/* 标签分组 */}
            <div className="space-y-2">
              <Label htmlFor="tagGroup">标签分组</Label>
              <Input
                id="tagGroup"
                value={tagGroup}
                onChange={(e) => setTagGroup(e.target.value)}
                placeholder="用户管理、订单服务等"
                disabled={submitting}
              />
              <p className="text-xs text-muted-foreground">
                用于接口分类和分组管理
              </p>
            </div>

            {/* 摘要 */}
            <div className="space-y-2">
              <Label htmlFor="summary">摘要</Label>
              <Input
                id="summary"
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="简短描述接口功能"
                disabled={submitting}
              />
            </div>

            {/* 详细描述 */}
            <div className="space-y-2">
              <Label htmlFor="description">详细描述</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="详细描述接口的功能、参数说明等"
                className="min-h-[80px] resize-none"
                disabled={submitting}
              />
            </div>
          </div>

          {/* 高级选项切换 */}
          <div className="border-t pt-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full justify-between px-2"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <span className="flex items-center gap-2">
                <FileCode className="h-4 w-4" />
                <span className="font-medium">高级选项</span>
              </span>
              {showAdvanced ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>

            {showAdvanced && (
              <div className="mt-4 space-y-4 p-4 rounded-lg border-2 border-orange-200 bg-gradient-to-br from-orange-50/50 to-amber-50/50 dark:from-orange-950/20 dark:to-amber-950/20">
                <div className="flex items-center gap-2 mb-3">
                  <FileCode className="h-4 w-4 text-orange-500" />
                  <span className="font-semibold text-sm">高级定义（JSON 格式）</span>
                </div>

                {/* Parameters */}
                <div className="space-y-2">
                  <Label htmlFor="parameters">Parameters (参数定义)</Label>
                  <Textarea
                    id="parameters"
                    value={parameters}
                    onChange={(e) => setParameters(e.target.value)}
                    placeholder='[{"name": "id", "in": "path", "required": true, "schema": {"type": "string"}}]'
                    className="min-h-[100px] resize-none font-mono text-xs"
                    disabled={submitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    定义接口的路径参数、查询参数、请求头等
                  </p>
                </div>

                {/* Request Body */}
                <div className="space-y-2">
                  <Label htmlFor="requestBody">Request Body (请求体)</Label>
                  <Textarea
                    id="requestBody"
                    value={requestBody}
                    onChange={(e) => setRequestBody(e.target.value)}
                    placeholder='{"content": {"application/json": {"schema": {"type": "object"}}}}'
                    className="min-h-[100px] resize-none font-mono text-xs"
                    disabled={submitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    定义请求体的 schema
                  </p>
                </div>

                {/* Responses */}
                <div className="space-y-2">
                  <Label htmlFor="responses">Responses (响应定义)</Label>
                  <Textarea
                    id="responses"
                    value={responses}
                    onChange={(e) => setResponses(e.target.value)}
                    placeholder='{"200": {"description": "成功", "content": {"application/json": {"schema": {"type": "object"}}}}}'
                    className="min-h-[100px] resize-none font-mono text-xs"
                    disabled={submitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    定义不同状态码的响应
                  </p>
                </div>
              </div>
            )}
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
                创建中...
              </>
            ) : (
              "创建接口"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzBnMFZ3PT06MWVlNjcxMjE=
