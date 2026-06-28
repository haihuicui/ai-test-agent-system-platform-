"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjJ0M1RnPT06Yzc1ZDAyN2I=

import * as React from "react";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { toast } from "sonner";
import type { APITest, CreateAPITestRequest } from "@/lib/api/api-tests";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjJ0M1RnPT06Yzc1ZDAyN2I=

interface APITestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiTest?: APITest | null;
  onSubmit: (data: CreateAPITestRequest) => Promise<void>;
  submitting?: boolean;
  folderName?: string;
  projectId?: string;
}

type ScriptFormat = "playwright" | "postman" | "rest_assured" | "other";
type ScriptLanguage = "typescript" | "javascript" | "python" | "java" | "other";
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjJ0M1RnPT06Yzc1ZDAyN2I=

const defaultFormData: CreateAPITestRequest = {
  name: "",
  schema_path: "",
  script_path: "",
  script_format: "playwright",
  script_language: "typescript",
  schema_url: "",
  description: "",
  test_config: {},
};

export function APITestDialog({
  open,
  onOpenChange,
  apiTest,
  onSubmit,
  submitting,
  folderName,
  projectId,
}: APITestDialogProps) {
  const [formData, setFormData] = React.useState<CreateAPITestRequest>(defaultFormData);
  const [createAnother, setCreateAnother] = React.useState(false);

  // 初始化表单数据
  React.useEffect(() => {
    if (apiTest) {
      setFormData({
        name: apiTest.name,
        description: apiTest.description || "",
        schema_path: apiTest.schema_path || "",
        script_path: apiTest.script_path,
        script_format: apiTest.script_format as ScriptFormat,
        script_language: apiTest.script_language as ScriptLanguage,
        schema_url: apiTest.schema_url || "",
        test_config: apiTest.test_config || {},
      });
    } else {
      setFormData(defaultFormData);
    }
  }, [apiTest, open]);

  // 提交表单
  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      toast.error("请输入API测试名称");
      return;
    }
    if (!formData.schema_path.trim()) {
      toast.error("请输入Schema路径");
      return;
    }
    if (!formData.script_path.trim()) {
      toast.error("请输入脚本路径");
      return;
    }

    await onSubmit(formData);
    if (createAnother && !apiTest) {
      setFormData(defaultFormData);
    }
  };

  const isEdit = !!apiTest;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] p-0 gap-0">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold">
            {isEdit ? "编辑API测试" : "创建API测试"}
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
                {/* 名称 */}
                <div className="space-y-2">
                  <Label htmlFor="name">
                    名称 <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    placeholder="输入API测试名称"
                  />
                </div>

                {/* 描述 */}
                <div className="space-y-2">
                  <Label htmlFor="description">描述</Label>
                  <RichTextEditor
                    id="description"
                    value={formData.description || ""}
                    onChange={(value) =>
                      setFormData({ ...formData, description: value })
                    }
                    placeholder="简要描述API测试内容"
                    rows={3}
                  />
                </div>

                {/* Schema URL */}
                <div className="space-y-2">
                  <Label htmlFor="schema_url">Schema URL</Label>
                  <Input
                    id="schema_url"
                    value={formData.schema_url || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, schema_url: e.target.value })
                    }
                    placeholder="https://api.example.com/openapi.json"
                  />
                  <p className="text-xs text-muted-foreground">
                    可选：提供OpenAPI/Swagger schema的URL
                  </p>
                </div>

                {/* Schema Path */}
                <div className="space-y-2">
                  <Label htmlFor="schema_path">
                    Schema路径 <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="schema_path"
                    value={formData.schema_path || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, schema_path: e.target.value })
                    }
                    placeholder="/path/to/schema.yaml"
                  />
                  <p className="text-xs text-muted-foreground">
                    OpenAPI/Swagger schema文件路径
                  </p>
                </div>

                {/* Script Path */}
                <div className="space-y-2">
                  <Label htmlFor="script_path">
                    脚本路径 <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="script_path"
                    value={formData.script_path}
                    onChange={(e) =>
                      setFormData({ ...formData, script_path: e.target.value })
                    }
                    placeholder="/path/to/test-script.spec.ts"
                  />
                  <p className="text-xs text-muted-foreground">
                    测试脚本文件路径
                  </p>
                </div>
              </div>
            </ScrollArea>
          </div>

          {/* 右侧字段面板 */}
          <div className="w-64 shrink-0 border-l bg-muted/30">
            <ScrollArea className="h-[calc(90vh-140px)]">
              <div className="p-4">
                <div className="mb-4">
                  <span className="text-sm font-medium">测试配置</span>
                </div>

                <div className="space-y-4">
                  {/* Script Format */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      脚本格式 <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={formData.script_format}
                      onValueChange={(value: ScriptFormat) =>
                        setFormData({ ...formData, script_format: value })
                      }
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="playwright">Playwright</SelectItem>
                        <SelectItem value="postman">Postman</SelectItem>
                        <SelectItem value="rest_assured">REST Assured</SelectItem>
                        <SelectItem value="other">其他</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Script Language */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">
                      脚本语言 <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={formData.script_language}
                      onValueChange={(value: ScriptLanguage) =>
                        setFormData({ ...formData, script_language: value })
                      }
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="typescript">TypeScript</SelectItem>
                        <SelectItem value="javascript">JavaScript</SelectItem>
                        <SelectItem value="python">Python</SelectItem>
                        <SelectItem value="java">Java</SelectItem>
                        <SelectItem value="other">其他</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Test Config Info */}
                  <div className="rounded-md border border-muted bg-background p-3">
                    <p className="mb-2 text-xs font-medium">测试配置提示</p>
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      <li>• 脚本格式决定生成的测试框架</li>
                      <li>• 脚本语言决定编程语言</li>
                      <li>• Schema路径支持本地或远程</li>
                    </ul>
                  </div>

                  {/* Advanced Config */}
                  <div className="space-y-1.5">
                    <Label className="text-sm">高级配置</Label>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="includeAuth"
                          className="h-4 w-4 rounded border-gray-300"
                          defaultChecked={true}
                        />
                        <Label htmlFor="includeAuth" className="text-xs font-normal">
                          包含认证测试
                        </Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="includeSecurity"
                          className="h-4 w-4 rounded border-gray-300"
                        />
                        <Label htmlFor="includeSecurity" className="text-xs font-normal">
                          包含安全测试
                        </Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="includeErrorHandling"
                          className="h-4 w-4 rounded border-gray-300"
                          defaultChecked={true}
                        />
                        <Label htmlFor="includeErrorHandling" className="text-xs font-normal">
                          包含错误处理测试
                        </Label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        </div>

        {/* 底部操作栏 */}
        <div className="flex items-center justify-between border-t px-6 py-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="createAnother"
              className="h-4 w-4 rounded border-gray-300"
              checked={createAnother}
              onChange={(e) => setCreateAnother(e.target.checked)}
            />
            <Label htmlFor="createAnother" className="text-sm font-normal cursor-pointer">
              继续创建下一个
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting || !formData.name.trim() || !formData.schema_path.trim() || !formData.script_path.trim()}
            >
              {submitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  保存中...
                </>
              ) : isEdit ? (
                "保存"
              ) : (
                "创建"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjJ0M1RnPT06Yzc1ZDAyN2I=
