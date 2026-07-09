"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, Download, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { toast } from "sonner";

interface BodyMeta {
  original_size?: number;
  truncated?: boolean;
  storage_path?: string | null;
  storage_error?: string | null;
  preview_length?: number;
}

interface HttpTraceViewerProps {
  request: {
    method?: string;
    url?: string;
    headers?: Record<string, string> | null;
    params?: Record<string, any> | null;
    body?: any;
    body_meta?: BodyMeta;
  };
  response?: {
    status?: number;
    statusText?: string;
    headers?: Record<string, any> | null;
    body?: any;
    body_meta?: BodyMeta;
    timing?: number;
  } | null;
  resultId?: string;
}

export const getMethodColor = (method: string) => {
  const colors: Record<string, string> = {
    GET: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-300",
    POST: "bg-green-100 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300",
    PUT: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900 dark:text-orange-300",
    PATCH: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-300",
    DELETE: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300",
  };
  return colors[method?.toUpperCase()] || "bg-gray-100 text-gray-700 border-gray-200";
};

export const getStatusVariant = (status: number) => {
  if (status >= 200 && status < 300) return "success";
  if (status >= 300 && status < 400) return "warning";
  if (status >= 400 && status < 500) return "destructive";
  if (status >= 500) return "destructive";
  return "secondary";
};

const formatBody = (body: any): string => {
  if (body === undefined || body === null) return "";
  if (typeof body === "string") return body;
  try {
    return JSON.stringify(body, null, 2);
  } catch {
    return String(body);
  }
};

const formatBytes = (bytes?: number): string => {
  if (bytes === undefined || bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const isEmptyObject = (value: any): boolean =>
  value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0;

function CollapsibleSection({
  title,
  children,
  defaultExpanded = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  return (
    <div className="border rounded-md overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-muted/50 hover:bg-muted text-xs font-medium transition-colors"
      >
        <span>{title}</span>
        {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
      </button>
      {expanded && <div className="p-3">{children}</div>}
    </div>
  );
}

function KeyValueTable({
  data,
  emptyText = "无数据",
}: {
  data: Record<string, any> | null | undefined;
  emptyText?: string;
}) {
  if (!data || isEmptyObject(data)) {
    return <p className="text-xs text-muted-foreground">{emptyText}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <tbody>
          {Object.entries(data).map(([key, value]) => (
            <tr key={key} className="border-b last:border-b-0">
              <td className="py-1.5 pr-4 font-medium text-muted-foreground whitespace-nowrap align-top">
                {key}
              </td>
              <td className="py-1.5 break-all align-top font-mono">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CodeBlock({ code, language = "json" }: { code: string; language?: string }) {
  if (!code) {
    return <p className="text-xs text-muted-foreground">无数据</p>;
  }
  return (
    <SyntaxHighlighter
      language={language}
      style={oneDark}
      customStyle={{
        margin: 0,
        borderRadius: "0.375rem",
        fontSize: "0.75rem",
        maxHeight: "24rem",
      }}
      showLineNumbers
      wrapLines
    >
      {code}
    </SyntaxHighlighter>
  );
}

function BodySection({
  body,
  bodyMeta,
  resultId,
  label,
}: {
  body: any;
  bodyMeta?: BodyMeta;
  resultId?: string;
  label: string;
}) {
  const [downloading, setDownloading] = useState(false);
  const formatted = formatBody(body);
  const truncated = bodyMeta?.truncated;
  const storagePath = bodyMeta?.storage_path;
  const storageError = bodyMeta?.storage_error;

  const handleDownload = async () => {
    if (!resultId || !storagePath) return;
    setDownloading(true);
    try {
      const response = await fetch(`/api/v2/api-test-results/${resultId}/response-body`);
      if (!response.ok) {
        const errorText = await response.text().catch(() => "未知错误");
        toast.error(`下载完整${label}失败：${errorText}`);
        return;
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `response_body_${resultId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`完整${label}已下载`);
    } catch (error) {
      toast.error(`下载完整${label}失败`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <CollapsibleSection title={label} defaultExpanded={true}>
      {truncated && (
        <div className="mb-2 p-2 rounded bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p>
              {label}已截断，原始大小 {formatBytes(bodyMeta?.original_size)}，
              当前仅展示前 {bodyMeta?.preview_length || 2000} 字符。
            </p>
            {storageError && (
              <p className="text-red-600 mt-1">完整内容上传失败：{storageError}</p>
            )}
            {storagePath && resultId && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 h-7 text-xs gap-1"
                onClick={handleDownload}
                disabled={downloading}
              >
                <Download className="h-3.5 w-3.5" />
                {downloading ? "下载中..." : "下载完整内容"}
              </Button>
            )}
          </div>
        </div>
      )}
      <CodeBlock code={formatted} language="json" />
    </CollapsibleSection>
  );
}

export function HttpTraceViewer({ request, response, resultId }: HttpTraceViewerProps) {
  const method = request.method || "GET";
  const url = request.url || "—";

  const hasResponse = response && typeof response.status === "number";

  return (
    <Tabs defaultValue="request" className="w-full">
      <TabsList className="grid w-full grid-cols-2">
        <TabsTrigger value="request">请求</TabsTrigger>
        <TabsTrigger value="response">响应</TabsTrigger>
      </TabsList>

      <TabsContent value="request" className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={getMethodColor(method)}>
            {method.toUpperCase()}
          </Badge>
          <code className="text-xs break-all text-muted-foreground">{url}</code>
        </div>

        <CollapsibleSection title="Query Params" defaultExpanded={false}>
          <KeyValueTable data={request.params} emptyText="无查询参数" />
        </CollapsibleSection>

        <CollapsibleSection title="Headers" defaultExpanded={false}>
          <KeyValueTable data={request.headers} emptyText="无请求头" />
        </CollapsibleSection>

        <BodySection body={request.body} bodyMeta={request.body_meta} label="Body" />
      </TabsContent>

      <TabsContent value="response" className="space-y-3">
        {hasResponse ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={getStatusVariant(response.status!)}>
                {response.status}
                {response.statusText ? ` ${response.statusText}` : ""}
              </Badge>
              {typeof response.timing === "number" && (
                <span className="text-xs text-muted-foreground">{response.timing.toFixed(0)}ms</span>
              )}
            </div>

            <CollapsibleSection title="Headers" defaultExpanded={false}>
              <KeyValueTable data={response.headers} emptyText="无响应头" />
            </CollapsibleSection>

            <BodySection
              body={response.body}
              bodyMeta={response.body_meta}
              resultId={resultId}
              label="Body"
            />
          </>
        ) : (
          <div className="text-sm text-muted-foreground py-4">未收到响应或响应数据缺失</div>
        )}
      </TabsContent>
    </Tabs>
  );
}
