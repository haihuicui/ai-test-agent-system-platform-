/**
 * API 接口详情侧边栏
 *
 * 显示单个 API 接口的完整信息
 * 包括：基本信息、参数、请求体、响应、关联信息等
 */
"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjFadmFBPT06OGVjNjg4NTc=

import * as React from "react";
import { useState, useEffect } from "react";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  FileText,
  Key,
  Layers,
  CheckCircle,
  Sparkles,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjFadmFBPT06OGVjNjg4NTc=

interface APIEndpointDetail {
  id: string;
  display_name: string;
  method: string;
  path: string;
  summary?: string;
  description?: string;
  tag_group?: string;
  parameters?: any[];
  request_body?: any;
  responses?: any;
  security?: any[];
  tags?: string[];
  custom_config?: {
    resource_name?: string;
    folder_name?: string;
    deprecated?: boolean;
  };
  total_test_cases?: number;
  total_test_runs?: number;
  last_run_status?: string;
}

interface APIEndpointSidebarProps {
  projectIdentifier: string;
  endpoint: APIEndpointDetail | null;
  onClose?: () => void;
  onGenerateTest?: (endpointId: string, prompt: string) => void;
}

export function APIEndpointSidebar({
  projectIdentifier,
  endpoint,
  onClose,
  onGenerateTest,
}: APIEndpointSidebarProps) {
  const [loading, setLoading] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  if (!endpoint) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground p-8">
        <div className="text-center space-y-3">
          <FileText className="h-12 w-12 mx-auto opacity-50" />
          <p>选择一个接口查看详细信息</p>
        </div>
      </div>
    );
  }

  const methodColors: Record<string, string> = {
    GET: "bg-green-100 text-green-700 border-green-300",
    POST: "bg-blue-100 text-blue-700 border-blue-300",
    PUT: "bg-orange-100 text-orange-700 border-orange-300",
    PATCH: "bg-yellow-100 text-yellow-700 border-yellow-300",
    DELETE: "bg-red-100 text-red-700 border-red-300",
  };

  const handleGenerateTest = () => {
    const prompt = `请为接口 ${endpoint.display_name} 生成测试用例。

接口信息：
- 方法: ${endpoint.method}
- 路径: ${endpoint.path}
- 描述: ${endpoint.summary || endpoint.description || "无"}

请生成：
1. 完整的测试用例
2. 测试脚本
3. 包含正常场景、边界条件、异常处理`;

    if (onGenerateTest) {
      onGenerateTest(endpoint.id, prompt);
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 头部 - 接口基本信息 */}
      <div className="border-b p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <Badge className={methodColors[endpoint.method] || "bg-gray-100"}>
                {endpoint.method}
              </Badge>
              {endpoint.custom_config?.deprecated && (
                <Badge variant="outline" className="text-orange-600">
                  已弃用
                </Badge>
              )}
              {endpoint.tag_group && (
                <Badge variant="outline">{endpoint.tag_group}</Badge>
              )}
            </div>
            <h3 className="text-lg font-semibold">{endpoint.display_name}</h3>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              ✕
            </Button>
          )}
        </div>

        {endpoint.summary && (
          <p className="text-sm text-muted-foreground">{endpoint.summary}</p>
        )}

        {/* 统计信息 */}
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-1">
            <FileText className="h-4 w-4" />
            <span>测试用例: {endpoint.total_test_cases || 0}</span>
          </div>
          <div className="flex items-center gap-1">
            <Layers className="h-4 w-4" />
            <span>测试运行: {endpoint.total_test_runs || 0}</span>
          </div>
          {endpoint.last_run_status && (
            <div className="flex items-center gap-1">
              <CheckCircle className="h-4 w-4" />
              <span>{endpoint.last_run_status}</span>
            </div>
          )}
        </div>

        {/* AI 生成按钮 */}
        <Button
          onClick={handleGenerateTest}
          className="w-full"
          size="sm"
        >
          <Sparkles className="mr-2 h-4 w-4" />
          AI 生成测试用例
        </Button>
      </div>

      {/* 内容区 - 可滚动 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* 路径信息 */}
        <Section
          title="接口路径"
          icon={<ArrowRight className="h-4 w-4" />}
          defaultOpen
        >
          <code className="block w-full rounded-lg bg-muted px-3 py-2 text-sm">
            {endpoint.path}
          </code>
        </Section>

        {/* 参数 */}
        {endpoint.parameters && endpoint.parameters.length > 0 && (
          <Section
            title={`参数 (${endpoint.parameters.length})`}
            icon={<Key className="h-4 w-4" />}
          >
            <div className="space-y-2">
              {endpoint.parameters.map((param: any, index: number) => (
                <div
                  key={index}
                  className="rounded-lg border p-3 space-y-1"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{param.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {param.in}
                    </Badge>
                    {param.required && (
                      <Badge variant="destructive" className="text-xs">
                        必填
                      </Badge>
                    )}
                  </div>
                  {param.description && (
                    <p className="text-xs text-muted-foreground">
                      {param.description}
                    </p>
                  )}
                  {param.schema && (
                    <code className="text-xs bg-muted px-2 py-1 rounded">
                      {JSON.stringify(param.schema)}
                    </code>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* 请求体 */}
        {endpoint.request_body && (
          <Section
            title="请求体"
            icon={<Layers className="h-4 w-4" />}
          >
            <pre className="text-xs bg-muted p-3 rounded-lg overflow-x-auto">
              {JSON.stringify(endpoint.request_body, null, 2)}
            </pre>
          </Section>
        )}

        {/* 响应 */}
        {endpoint.responses && Object.keys(endpoint.responses).length > 0 && (
          <Section
            title={`响应 (${Object.keys(endpoint.responses).length})`}
            icon={<CheckCircle className="h-4 w-4" />}
          >
            <div className="space-y-2">
              {Object.entries(endpoint.responses).map(([statusCode, response]: [string, any]) => (
                <div
                  key={statusCode}
                  className="rounded-lg border p-3 space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={statusCode.startsWith("2") ? "default" : "destructive"}
                    >
                      {statusCode}
                    </Badge>
                    <span className="text-sm font-medium">
                      {(response as any).description || "无描述"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* 安全配置 */}
        {endpoint.security && endpoint.security.length > 0 && (
          <Section
            title="安全认证"
            icon={<Key className="h-4 w-4" />}
          >
            <pre className="text-xs bg-muted p-3 rounded-lg overflow-x-auto">
              {JSON.stringify(endpoint.security, null, 2)}
            </pre>
          </Section>
        )}

        {/* 标签 */}
        {endpoint.tags && endpoint.tags.length > 0 && (
          <Section
            title="标签"
            icon={<Layers className="h-4 w-4" />}
          >
            <div className="flex flex-wrap gap-2">
              {endpoint.tags.map((tag: string, index: number) => (
                <Badge key={index} variant="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjFadmFBPT06OGVjNjg4NTc=

// 可折叠的分组组件
interface SectionProps {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function Section({ title, icon, children, defaultOpen = false }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium text-sm">{title}</span>
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjFadmFBPT06OGVjNjg4NTc=
