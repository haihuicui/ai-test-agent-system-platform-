/**
 * 场景测试 AI 生成对话框
 *
 * 工作流程：
 * 1. 选择场景数据来源：
 *    - 选择接口：从项目中选择已有的接口
 *    - URL 链接：提供 OpenAPI 文档 URL
 *    - 上传文件：上传 OpenAPI/Swagger 文档
 * 2. 点击"AI 生成场景"后打开 AI 助手
 * 3. AI 自动分析并创建多接口测试场景
 * 4. 完成后通过回调刷新界面
 */
"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTBKSWJRPT06ZjQ3MjE5MGY=

import * as React from "react";
import { useState, useEffect } from "react";
import { Sparkles, Loader2, Link as LinkIcon, Upload, FileCode, Workflow, List } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { listAPIEndpoints, APIEndpoint } from "@/lib/api/api-endpoints";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTBKSWJRPT06ZjQ3MjE5MGY=

type SchemaSource = "interfaces" | "url" | "file";
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTBKSWJRPT06ZjQ3MjE5MGY=

interface AIGenerateScenarioDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectIdentifier: string;
  onOpenChat?: (prompt: string) => void;
}

export function AIGenerateScenarioDialog({
  open,
  onOpenChange,
  projectIdentifier,
  onOpenChat,
}: AIGenerateScenarioDialogProps) {
  const [schemaSource, setSchemaSource] = useState<SchemaSource>("interfaces");
  const [schemaUrl, setSchemaUrl] = useState("");
  const [schemaFile, setSchemaFile] = useState<File | null>(null);
  const [customRequirements, setCustomRequirements] = useState("");
  const [interfaces, setInterfaces] = useState<APIEndpoint[]>([]);
  const [selectedInterfaceIds, setSelectedInterfaceIds] = useState<Set<string>>(new Set());
  const [loadingInterfaces, setLoadingInterfaces] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // 加载接口列表
  useEffect(() => {
    if (open && projectIdentifier) {
      loadInterfaces();
    }
  }, [open, projectIdentifier]);

  const loadInterfaces = async () => {
    setLoadingInterfaces(true);
    try {
      const data = await listAPIEndpoints(projectIdentifier);
      setInterfaces(data);
    } catch (error) {
      console.error("Failed to load interfaces:", error);
      toast.error("加载接口列表失败");
    } finally {
      setLoadingInterfaces(false);
    }
  };

  // 全选/取消全选
  const handleToggleAll = (checked: boolean) => {
    if (checked) {
      setSelectedInterfaceIds(new Set(interfaces.map(i => i.id)));
    } else {
      setSelectedInterfaceIds(new Set());
    }
  };

  // 切换单个接口选择
  const handleToggleInterface = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedInterfaceIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedInterfaceIds(newSelected);
  };

  // 检查是否全部选中
  const isAllSelected = interfaces.length > 0 && selectedInterfaceIds.size === interfaces.length;
  const isSomeSelected = selectedInterfaceIds.size > 0 && selectedInterfaceIds.size < interfaces.length;

  // 过滤后的接口列表
  const filteredInterfaces = interfaces.filter((intf) =>
    searchQuery === "" ||
    intf.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    intf.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
    intf.method.toLowerCase().includes(searchQuery.toLowerCase()) ||
    intf.tag_group?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // 重置表单
  const resetForm = () => {
    setSchemaSource("interfaces");
    setSchemaUrl("");
    setSchemaFile(null);
    setCustomRequirements("");
    setSelectedInterfaceIds(new Set());
    setSearchQuery("");
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  // 处理 AI 生成场景
  const handleAIGenerate = async () => {
    if (schemaSource === "interfaces" && selectedInterfaceIds.size === 0) {
      toast.error("请至少选择一个接口");
      return;
    }
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
      let chatPrompt = "";

      if (schemaSource === "interfaces") {
        // 基于选中的接口生成场景
        const ids = Array.from(selectedInterfaceIds).join(", ");
        chatPrompt = `创建 API 场景测试

接口 ID: ${ids}

请基于这些接口分析业务关联性，使用场景测试技能（scenario）创建完整的测试场景。
创建完成后必须执行场景测试，根据执行结果自动修复数据依赖、断言或请求参数，确保场景可正常运行。`;
      } else {
        // 基于 OpenAPI 文档生成场景
        chatPrompt = `从 OpenAPI 文档创建 API 场景测试

文档来源: ${schemaSource === "url" ? schemaUrl : schemaFile?.name}

请解析文档中的接口，分析业务关联性，使用场景测试技能（scenario）创建完整的测试场景。
创建完成后必须执行场景测试，根据执行结果自动修复数据依赖、断言或请求参数，确保场景可正常运行。`;
      }

      // 如果用户提供了自定义要求，添加到提示词中
      if (customRequirements.trim()) {
        chatPrompt += `

---

自定义要求:
${customRequirements.trim()}`;
      }

      onOpenChat(chatPrompt);
      resetForm();
      onOpenChange(false);
    } else {
      toast.error("AI 助手未配置，无法生成场景");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="h-5 w-5 text-primary" />
            AI 生成测试场景
          </DialogTitle>
          <DialogDescription className="text-base">
            选择项目中的接口或上传 OpenAPI/Swagger 文档，AI 将自动分析并创建多接口测试场景
          </DialogDescription>

          {/* 安全提示 */}
          <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700 mt-3">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>您的数据是安全的，不会用于 AI 训练</span>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-6 py-4">
          {/* Schema 来源选择 */}
          <div className="space-y-3">
            <Label>场景数据来源</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={schemaSource === "interfaces" ? "default" : "outline"}
                onClick={() => setSchemaSource("interfaces")}
                className="flex-1"
              >
                <List className="mr-2 h-4 w-4" />
                选择接口
              </Button>
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
                上传文件
              </Button>
            </div>
          </div>

          {/* 选择接口 */}
          {schemaSource === "interfaces" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>
                  选择接口 <span className="text-destructive">*</span>
                </Label>
                <div className="flex items-center gap-2 text-sm">
                  <Checkbox
                    id="selectAll"
                    checked={isAllSelected}
                    onCheckedChange={handleToggleAll}
                  />
                  <label
                    htmlFor="selectAll"
                    className="cursor-pointer select-none"
                  >
                    全选 ({selectedInterfaceIds.size}/{interfaces.length})
                  </label>
                </div>
              </div>

              {/* 搜索框 */}
              <Input
                placeholder="搜索接口名称、路径、方法或标签..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="mb-2"
              />

              {/* 接口列表 */}
              <div className="border rounded-lg max-h-80 overflow-y-auto">
                {loadingInterfaces ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : filteredInterfaces.length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">
                    {searchQuery ? "未找到匹配的接口" : "暂无可用接口"}
                  </div>
                ) : (
                  <div className="divide-y">
                    {filteredInterfaces.map((intf) => (
                      <div
                        key={intf.id}
                        className="flex items-start gap-3 p-3 hover:bg-muted/50 transition-colors"
                      >
                        <Checkbox
                          id={`intf-${intf.id}`}
                          checked={selectedInterfaceIds.has(intf.id)}
                          onCheckedChange={(checked) =>
                            handleToggleInterface(intf.id, checked as boolean)
                          }
                          className="mt-1"
                        />
                        <label
                          htmlFor={`intf-${intf.id}`}
                          className="flex-1 cursor-pointer select-none"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                              intf.method === "GET" ? "bg-green-100 text-green-700" :
                              intf.method === "POST" ? "bg-blue-100 text-blue-700" :
                              intf.method === "PUT" ? "bg-yellow-100 text-yellow-700" :
                              intf.method === "DELETE" ? "bg-red-100 text-red-700" :
                              "bg-gray-100 text-gray-700"
                            }`}>
                              {intf.method}
                            </span>
                            <span className="font-medium text-sm">{intf.display_name}</span>
                          </div>
                          <div className="text-xs text-muted-foreground font-mono mb-1">
                            {intf.path}
                          </div>
                          {intf.summary && (
                            <div className="text-xs text-muted-foreground">
                              {intf.summary}
                            </div>
                          )}
                          {intf.tag_group && (
                            <div className="mt-1">
                              <span className="text-xs bg-muted px-2 py-0.5 rounded">
                                {intf.tag_group}
                              </span>
                            </div>
                          )}
                        </label>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <p className="text-xs text-muted-foreground">
                已选择 {selectedInterfaceIds.size} 个接口，AI 将基于这些接口创建测试场景
              </p>
            </div>
          )}

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
                        支持 JSON/YAML 格式，最大 10MB
                      </p>
                    </div>
                  </div>
                </label>
              </div>
            </div>
          )}

          {/* 自定义场景描述和要求 */}
          <div className="space-y-2">
            <Label htmlFor="customRequirements">
              自定义场景描述和要求
              <span className="text-xs font-normal text-muted-foreground ml-2">(可选)</span>
            </Label>
            <Textarea
              id="customRequirements"
              value={customRequirements}
              onChange={(e) => setCustomRequirements(e.target.value)}
              placeholder="请描述您希望创建的测试场景和特殊要求，例如：&#10;• 电商系统：创建用户注册、登录、浏览商品、加入购物车、下单、支付等完整流程场景&#10;• 需要包含正常流程和异常流程（如支付失败、库存不足等）&#10;• 每个场景需要包含数据依赖和断言验证"
              rows={5}
              className="resize-none"
            />
            <p className="text-xs text-muted-foreground">
              详细描述您的需求，AI 将根据您的要求生成更精准的测试场景
            </p>
          </div>

          {/* 说明 */}
          {schemaSource === "interfaces" ? (
            <div className="rounded-lg bg-blue-50 dark:bg-blue-950/20 p-4 text-sm text-blue-700 dark:text-blue-400">
              <div className="flex items-start gap-2">
                <Workflow className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium mb-1">AI 将基于选中的接口创建场景：</p>
                  <ul className="space-y-1 text-xs">
                    <li>• 分析选中接口的业务关联性</li>
                    <li>• 创建完整的业务流程场景（如：用户下单流程）</li>
                    <li>• 为每个场景配置多个步骤和接口调用顺序</li>
                    <li>• 自动设置请求参数、断言和数据依赖</li>
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-lg bg-purple-50 dark:bg-purple-950/20 p-4 text-sm text-purple-700 dark:text-purple-400">
              <div className="flex items-start gap-2">
                <Workflow className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium mb-1">AI 将自动创建以下内容：</p>
                  <ul className="space-y-1 text-xs">
                    <li>• 分析所有接口的业务关联性</li>
                    <li>• 创建完整的业务流程场景（如：用户下单流程）</li>
                    <li>• 为每个场景配置多个步骤和接口调用顺序</li>
                    <li>• 自动设置请求参数、断言和数据依赖</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 flex-shrink-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            onClick={handleAIGenerate}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            AI 生成场景
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTBKSWJRPT06ZjQ3MjE5MGY=
