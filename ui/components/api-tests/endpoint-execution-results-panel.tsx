"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Play,
  RefreshCw,
  Eye,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  getEndpointTestRuns,
  getEndpointRunResults,
} from "@/lib/api/api-endpoints";
import type { APITestResult } from "@/lib/api/api-tests";
import {
  HttpTraceViewer,
  getMethodColor,
  getStatusVariant,
} from "@/components/scenario-tests/http-trace-viewer";
import { useLanguage } from "@/providers/LanguageProvider";

interface EndpointExecutionResultsPanelProps {
  endpointId: string;
  projectId: string;
  refreshTrigger?: number;
}

interface TestRun {
  id: string;
  api_test_id: string;
  status: string;
  total_scenarios: number;
  passed_scenarios: number;
  failed_scenarios: number;
  skipped_scenarios: number;
  duration?: number | null;
  report_path?: string | null;
  report_attachment_id?: string | null;
  created_at: string;
}

export function EndpointExecutionResultsPanel({
  endpointId,
  projectId,
  refreshTrigger,
}: EndpointExecutionResultsPanelProps) {
  const { t } = useLanguage();
  const [runs, setRuns] = React.useState<TestRun[]>([]);
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [results, setResults] = React.useState<APITestResult[]>([]);
  const [loadingRuns, setLoadingRuns] = React.useState(false);
  const [loadingResults, setLoadingResults] = React.useState(false);
  const [expandedResults, setExpandedResults] = React.useState<Set<string>>(new Set());

  // endpoint 切换时重置执行历史与选中运行，避免旧 run_id 被带到新 endpoint 上
  // 造成 404: 测试运行不属于该 endpoint
  React.useEffect(() => {
    setSelectedRunId(null);
    setRuns([]);
    setResults([]);
    setExpandedResults(new Set());
  }, [endpointId]);

  const loadRuns = React.useCallback(async () => {
    if (!endpointId) return;
    try {
      setLoadingRuns(true);
      const data = await getEndpointTestRuns(endpointId, 20);
      setRuns(data.test_runs);
      if (data.test_runs.length > 0) {
        setSelectedRunId(data.test_runs[0].id);
      }
    } catch (error) {
      console.error("Failed to load test runs:", error);
      toast.error(t("apiTests.loadRunsFailed") || "加载执行记录失败");
    } finally {
      setLoadingRuns(false);
    }
  }, [endpointId, t]);

  const loadResults = React.useCallback(async () => {
    if (!selectedRunId || !endpointId) return;
    const selectedRun = runs.find((r) => r.id === selectedRunId);
    // 防御：只请求确实属于当前 endpoint 运行列表的 run，避免脏 state 触发无效请求
    if (!selectedRun) return;
    try {
      setLoadingResults(true);
      const data = await getEndpointRunResults(
        endpointId,
        selectedRunId,
        selectedRun.api_test_id,
        { page: 1, page_size: 100 }
      );
      setResults(data.items);
    } catch (error) {
      console.error("Failed to load run results:", error);
      toast.error(t("apiTests.loadResultsFailed") || "加载执行结果失败");
    } finally {
      setLoadingResults(false);
    }
  }, [endpointId, selectedRunId, runs, t]);

  React.useEffect(() => {
    loadRuns();
  }, [loadRuns, refreshTrigger]);

  React.useEffect(() => {
    loadResults();
  }, [loadResults]);

  const toggleExpand = (resultId: string) => {
    setExpandedResults((prev) => {
      const next = new Set(prev);
      if (next.has(resultId)) {
        next.delete(resultId);
      } else {
        next.add(resultId);
      }
      return next;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
      case "passed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "running":
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getResultStatusBadge = (status: string) => {
    switch (status) {
      case "passed":
        return <Badge className="bg-green-100 text-green-700">通过</Badge>;
      case "failed":
        return <Badge className="bg-red-100 text-red-700">失败</Badge>;
      case "skipped":
        return <Badge variant="secondary">跳过</Badge>;
      case "blocked":
        return <Badge variant="destructive">阻塞</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const selectedRun = runs.find((r) => r.id === selectedRunId);

  const handleViewReport = async (attachmentId?: string | null) => {
    if (!attachmentId) {
      toast.info(t("apiTests.noReportAvailable") || "暂无报告");
      return;
    }
    try {
      const response = await fetch(`/api/v2/attachments/${attachmentId}/report-viewer`);
      if (!response.ok) {
        toast.error(t("apiTests.openReportFailed") || "无法打开测试报告");
        return;
      }
      const data = await response.json();
      window.open(data.index_url, "_blank");
    } catch (error) {
      console.error("Failed to open report:", error);
      toast.error(t("apiTests.openReportFailed") || "打开报告失败");
    }
  };

  const handleDownloadReport = (attachmentId?: string | null) => {
    if (!attachmentId) {
      toast.info(t("apiTests.noReportAvailable") || "暂无报告");
      return;
    }
    window.open(`/api/v2/projects/${projectId}/attachments/${attachmentId}/download`, "_blank");
  };

  const formatAssertionValue = (value: unknown): string => {
    if (value === undefined) return "undefined";
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  if (!endpointId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <Play className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">
            {t("apiTests.selectEndpoint") || "请选择一个接口"}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("apiTests.selectEndpointToViewResults") || "从左侧列表或上方接口列表选择接口后查看执行结果"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        {/* 左侧：执行历史 */}
        <div className="col-span-1 space-y-4 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="pb-3 shrink-0">
              <CardTitle className="text-base">
                {t("apiTests.executionHistory") || "执行历史"}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 flex-1 min-h-0 overflow-auto">
              {loadingRuns ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {t("common.loading") || "加载中..."}
                </div>
              ) : runs.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {t("apiTests.noExecutionHistory") || "暂无执行记录"}
                </div>
              ) : (
                <div className="divide-y">
                  {runs.map((run) => (
                    <div
                      key={run.id}
                      className={cn(
                        "p-3 cursor-pointer hover:bg-muted/50 transition-colors",
                        selectedRunId === run.id && "bg-muted"
                      )}
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {getStatusIcon(run.status)}
                        <span className="text-xs font-mono">{run.id.slice(0, 8)}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(run.created_at).toLocaleString()}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs">
                        <span className="text-green-600">
                          通过 {run.passed_scenarios}
                        </span>
                        {run.failed_scenarios > 0 && (
                          <span className="text-red-600">
                            失败 {run.failed_scenarios}
                          </span>
                        )}
                        {run.duration !== null && run.duration !== undefined && (
                          <span className="text-muted-foreground">
                            {run.duration.toFixed(2)}s
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 右侧：用例结果详情 */}
        <div className="col-span-2 space-y-4 flex flex-col min-h-0">
          {selectedRunId ? (
            <Card className="flex-1 flex flex-col min-h-0">
              <CardHeader className="pb-3 shrink-0 flex flex-row items-center justify-between">
                <CardTitle className="text-base">
                  {t("apiTests.testResults") || "用例结果"}
                </CardTitle>
                {selectedRun?.report_attachment_id && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 gap-1"
                      onClick={() => handleViewReport(selectedRun.report_attachment_id)}
                    >
                      <Eye className="h-4 w-4" />
                      <span className="text-xs">{t("apiTests.viewReport") || "查看报告"}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 gap-1"
                      onClick={() => handleDownloadReport(selectedRun.report_attachment_id)}
                    >
                      <Download className="h-4 w-4" />
                      <span className="text-xs">{t("apiTests.downloadZip") || "下载 ZIP"}</span>
                    </Button>
                  </div>
                )}
              </CardHeader>
              <CardContent className="flex-1 min-h-0 overflow-auto">
                {loadingResults ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">
                    {t("common.loading") || "加载中..."}
                  </div>
                ) : results.length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">
                    {t("apiTests.noResults") || "暂无执行结果"}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {results.map((result) => (
                      <div
                        key={result.id}
                        className="border rounded-lg p-4 hover:bg-muted/50 transition-colors"
                      >
                        <div
                          className="flex items-start justify-between cursor-pointer gap-3"
                          onClick={() => toggleExpand(result.id)}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex flex-wrap items-center gap-2 mb-1">
                              <span className="text-sm font-semibold truncate">
                                {result.scenario_name}
                              </span>
                              {result.request_data?.method && (
                                <Badge
                                  variant="outline"
                                  className={getMethodColor(result.request_data.method)}
                                >
                                  {result.request_data.method.toUpperCase()}
                                </Badge>
                              )}
                              {typeof result.response_data?.status === "number" && (
                                <Badge variant={getStatusVariant(result.response_data.status)}>
                                  {result.response_data.status}
                                </Badge>
                              )}
                              {getResultStatusBadge(result.status)}
                              {result.duration_ms && (
                                <span className="text-xs text-muted-foreground">
                                  {result.duration_ms}ms
                                </span>
                              )}
                            </div>
                            {result.request_data?.url && (
                              <code className="text-xs text-muted-foreground block truncate">
                                {result.request_data.url}
                              </code>
                            )}
                            {result.error_message && (
                              <div className="text-xs text-red-600 mt-1 line-clamp-2">
                                {result.error_message}
                              </div>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 shrink-0"
                          >
                            {expandedResults.has(result.id) ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </Button>
                        </div>

                        {/* 展开的详细信息 */}
                        {expandedResults.has(result.id) && (
                          <div className="mt-4 pt-4 border-t space-y-3">
                            {(result.request_data || result.response_data) ? (
                              <HttpTraceViewer
                                resultId={result.id}
                                request={{
                                  method: result.request_data?.method,
                                  url: result.request_data?.url,
                                  headers: result.request_data?.headers as Record<string, string> | null | undefined,
                                  params: result.request_data?.params,
                                  body: result.request_data?.body,
                                  body_meta: result.request_data?.body_meta,
                                }}
                                response={result.response_data ? {
                                  status: result.response_data.status,
                                  statusText: result.response_data.statusText,
                                  headers: result.response_data.headers as Record<string, string> | null | undefined,
                                  body: result.response_data.body,
                                  body_meta: result.response_data.body_meta,
                                  timing: result.response_data.timing,
                                } : null}
                              />
                            ) : (
                              <div className="text-sm text-muted-foreground py-4 flex items-center gap-2">
                                <AlertCircle className="h-4 w-4" />
                                {t("apiTests.noTraceData") || "未捕获到请求/响应明细（可能是旧数据或脚本未使用 trace helper）"}
                              </div>
                            )}

                            {/* 断言结果 */}
                            {result.assertion_results && result.assertion_results.length > 0 && (
                              <div>
                                <h5 className="text-xs font-semibold mb-2">
                                  {t("apiTests.assertionResults") || "断言结果"}
                                </h5>
                                <div className="overflow-x-auto rounded border">
                                  <table className="w-full text-xs border-collapse">
                                    <thead>
                                      <tr className="bg-muted/60 text-muted-foreground border-b">
                                        <th className="text-left px-2 py-1.5 font-medium">{t("apiTests.assertionResult") || "结果"}</th>
                                        <th className="text-left px-2 py-1.5 font-medium">{t("apiTests.assertionType") || "类型"}</th>
                                        <th className="text-left px-2 py-1.5 font-medium">{t("apiTests.assertionExpected") || "预期"}</th>
                                        <th className="text-left px-2 py-1.5 font-medium">{t("apiTests.assertionActual") || "实际"}</th>
                                        <th className="text-left px-2 py-1.5 font-medium">{t("apiTests.assertionMessage") || "消息"}</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {result.assertion_results.map((assertion, idx) => {
                                        const expectedText = formatAssertionValue(assertion.expected);
                                        const actualText = formatAssertionValue(assertion.actual);
                                        const assertionConfig = assertion.assertion as Record<string, unknown>;
                                        return (
                                          <tr
                                            key={idx}
                                            className={cn(
                                              assertion.passed
                                                ? "bg-green-50 text-green-700"
                                                : "bg-red-50 text-red-700",
                                              idx > 0 && "border-t border-border/40"
                                            )}
                                          >
                                            <td className="px-2 py-1.5 whitespace-nowrap align-top">
                                              {assertion.passed ? (
                                                <span className="inline-flex items-center gap-1">
                                                  <CheckCircle2 className="h-3 w-3" /> {t("apiTests.assertionPassed") || "通过"}
                                                </span>
                                              ) : (
                                                <span className="inline-flex items-center gap-1">
                                                  <XCircle className="h-3 w-3" /> {t("apiTests.assertionFailed") || "失败"}
                                                </span>
                                              )}
                                            </td>
                                            <td className="px-2 py-1.5 align-top">
                                              <span className="capitalize">{String(assertionConfig.type || "")}</span>
                                              {typeof assertionConfig.path === "string" && assertionConfig.path && (
                                                <code className="block text-[10px] opacity-80 truncate max-w-[120px]">
                                                  {assertionConfig.path}
                                                </code>
                                              )}
                                            </td>
                                            <td
                                              className="px-2 py-1.5 align-top truncate max-w-[120px]"
                                              title={expectedText}
                                            >
                                              <code>{expectedText}</code>
                                            </td>
                                            <td
                                              className="px-2 py-1.5 align-top truncate max-w-[120px]"
                                              title={actualText}
                                            >
                                              <code>{actualText}</code>
                                            </td>
                                            <td className="px-2 py-1.5 align-top">
                                              {assertion.message || "-"}
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="flex-1 flex flex-col min-h-0">
              <CardContent className="p-12 flex-1 flex items-center justify-center">
                <div className="text-center">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">
                    {t("apiTests.selectRun") || "选择执行记录"}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {t("apiTests.selectRunToViewDetails") || "从左侧列表选择一个执行记录查看详细结果"}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
