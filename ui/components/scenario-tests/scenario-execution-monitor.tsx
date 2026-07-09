/**
 * 场景执行监控面板
 * 实时显示场景执行状态和结果
 */
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VZNVdBPT06MDQyNmViMWE=

"use client";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VZNVdBPT06MDQyNmViMWE=

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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getScenario,
  listScenarioRuns,
  getStepResults,
} from "@/lib/api/scenarios";
import type { Scenario, ScenarioRun, StepResult } from "@/types/scenario";
import { HttpTraceViewer, getMethodColor, getStatusVariant } from "./http-trace-viewer";
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VZNVdBPT06MDQyNmViMWE=

interface ScenarioExecutionMonitorProps {
  scenarioId: string | null;
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0VZNVdBPT06MDQyNmViMWE=

export function ScenarioExecutionMonitor({
  scenarioId,
}: ScenarioExecutionMonitorProps) {
  const [scenario, setScenario] = React.useState<Scenario | null>(null);
  const [runs, setRuns] = React.useState<ScenarioRun[]>([]);
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [stepResults, setStepResults] = React.useState<StepResult[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [expandedSteps, setExpandedSteps] = React.useState<Set<string>>(new Set());

  // 加载数据
  React.useEffect(() => {
    if (scenarioId) {
      loadScenario();
      loadRuns();
    } else {
      setScenario(null);
      setRuns([]);
      setSelectedRunId(null);
      setStepResults([]);
    }
  }, [scenarioId]);

  // 加载步骤结果
  React.useEffect(() => {
    if (selectedRunId && scenarioId) {
      loadStepResults();
    }
  }, [selectedRunId, scenarioId]);

  const loadScenario = async () => {
    if (!scenarioId) return;

    try {
      const data = await getScenario(scenarioId);
      setScenario(data);
    } catch (error) {
      console.error("Failed to load scenario:", error);
    }
  };

  const loadRuns = async () => {
    if (!scenarioId) return;

    try {
      setLoading(true);
      const result = await listScenarioRuns(scenarioId, 1, 20);
      setRuns(result.items);

      // 自动选择最新的执行记录
      if (result.items.length > 0 && !selectedRunId) {
        setSelectedRunId(result.items[0].id);
      }
    } catch (error) {
      console.error("Failed to load runs:", error);
      toast.error("加载执行记录失败");
    } finally {
      setLoading(false);
    }
  };

  const loadStepResults = async () => {
    if (!selectedRunId || !scenarioId) return;

    try {
      const results = await getStepResults(scenarioId, selectedRunId);
      setStepResults(results);
    } catch (error) {
      console.error("Failed to load step results:", error);
      toast.error("加载步骤结果失败");
    }
  };

  const toggleExpand = (stepId: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "running":
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStepStatusBadge = (status: string) => {
    switch (status) {
      case "passed":
        return <Badge className="bg-green-100 text-green-700">通过</Badge>;
      case "failed":
        return <Badge className="bg-red-100 text-red-700">失败</Badge>;
      case "skipped":
        return <Badge variant="secondary">跳过</Badge>;
      case "error":
        return <Badge variant="destructive">错误</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  function CollapsibleErrorStack({ stack }: { stack: string }) {
    const [expanded, setExpanded] = React.useState(false);
    return (
      <div className="border rounded-md overflow-hidden">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-3 py-2 bg-red-50 hover:bg-red-100 dark:bg-red-950 dark:hover:bg-red-900 text-xs font-medium text-red-700 dark:text-red-300 transition-colors"
        >
          <span>查看堆栈</span>
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>
        {expanded && (
          <pre className="text-xs bg-muted p-3 overflow-x-auto max-h-80">{stack}</pre>
        )}
      </div>
    );
  }

  if (!scenarioId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <Play className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">请先选择一个场景</h3>
          <p className="text-sm text-muted-foreground">
            从左侧列表选择场景后，可以执行场景并查看执行结果
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 顶部操作栏 */}
      <Card>
        <CardContent className="p-6">
          {/* 场景信息 */}
          <div>
            <h3 className="font-semibold text-lg mb-1">
              {scenario?.name || "加载中..."}
            </h3>
            <p className="text-sm text-muted-foreground">
              {scenario?.total_steps || 0} 个步骤 · 最近执行:{" "}
              {scenario?.last_run_at
                ? new Date(scenario.last_run_at).toLocaleString()
                : "未执行"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 执行历史和步骤结果 */}
      <div className="grid grid-cols-3 gap-6">
        {/* 左侧：执行历史 */}
        <div className="col-span-1 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">执行历史</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  加载中...
                </div>
              ) : runs.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  暂无执行记录
                </div>
              ) : (
                <div className="divide-y max-h-[500px] overflow-y-auto">
                  {runs.map((run) => (
                    <div
                      key={run.id}
                      className={`p-3 cursor-pointer hover:bg-muted/50 transition-colors ${
                        selectedRunId === run.id ? "bg-muted" : ""
                      }`}
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {getStatusIcon(run.status)}
                        <span className="text-xs font-mono">
                          {run.identifier}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(run.created_at).toLocaleString()}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs">
                        <span className="text-green-600">
                          通过 {run.passed_steps}
                        </span>
                        {run.failed_steps > 0 && (
                          <span className="text-red-600">
                            失败 {run.failed_steps}
                          </span>
                        )}
                        {run.duration_ms && (
                          <span className="text-muted-foreground">
                            {run.duration_ms}ms
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

        {/* 右侧：步骤结果详情 */}
        <div className="col-span-2 space-y-4">
          {selectedRunId ? (
            <>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">步骤结果</CardTitle>
                </CardHeader>
                <CardContent>
                  {stepResults.length === 0 ? (
                    <div className="text-center py-8 text-sm text-muted-foreground">
                      暂无步骤结果
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {stepResults.map((result) => (
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
                                <span className="text-sm font-semibold">
                                  步骤 {result.step_order}
                                  {result.step_name ? ` · ${result.step_name}` : ""}
                                </span>
                                {result.request_data?.method && (
                                  <Badge variant="outline" className={getMethodColor(result.request_data.method)}>
                                    {result.request_data.method.toUpperCase()}
                                  </Badge>
                                )}
                                {typeof result.response_data?.status === "number" && (
                                  <Badge variant={getStatusVariant(result.response_data.status)}>
                                    {result.response_data.status}
                                  </Badge>
                                )}
                                {getStepStatusBadge(result.status)}
                                {result.duration_ms && (
                                  <span className="text-xs text-muted-foreground">
                                    {result.duration_ms}ms
                                  </span>
                                )}
                              </div>
                              {(result.full_url || result.request_data?.url) && (
                                <code className="text-xs text-muted-foreground block truncate">
                                  {result.full_url || result.request_data?.url}
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
                              {expandedSteps.has(result.id) ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </Button>
                          </div>

                          {/* 展开的详细信息 */}
                          {expandedSteps.has(result.id) && (
                            <div className="mt-4 pt-4 border-t space-y-3">
                              <HttpTraceViewer
                                request={{
                                  method: result.request_data?.method,
                                  url: result.full_url || result.request_data?.url,
                                  headers: result.request_data?.headers,
                                  params: result.request_data?.params,
                                  body: result.request_data?.body,
                                }}
                                response={result.response_data}
                              />

                              {/* 错误堆栈 */}
                              {result.error_stack && (
                                <CollapsibleErrorStack stack={result.error_stack} />
                              )}

                              {/* 提取的数据 */}
                              {Object.keys(result.extracted_data || {}).length > 0 && (
                                <div>
                                  <h5 className="text-xs font-semibold mb-2">提取的数据</h5>
                                  <div className="space-y-1">
                                    {Object.entries(result.extracted_data).map(
                                      ([key, value]) => (
                                        <div
                                          key={key}
                                          className="text-xs bg-muted/50 px-2 py-1 rounded flex items-center gap-2"
                                        >
                                          <code className="text-primary">{key}</code>
                                          <span className="text-muted-foreground">=</span>
                                          <code className="text-muted-foreground">
                                            {JSON.stringify(value)}
                                          </code>
                                        </div>
                                      )
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* 断言结果 */}
                              {result.assertion_results && result.assertion_results.length > 0 && (
                                <div>
                                  <h5 className="text-xs font-semibold mb-2">断言结果</h5>
                                  <div className="space-y-1">
                                    {result.assertion_results.map(
                                      (assertion: any, idx: number) => (
                                        <div
                                          key={idx}
                                          className={`text-xs px-2 py-1 rounded flex items-center gap-2 ${
                                            assertion.passed
                                              ? "bg-green-50 text-green-700"
                                              : "bg-red-50 text-red-700"
                                          }`}
                                        >
                                          {assertion.passed ? (
                                            <CheckCircle2 className="h-3 w-3" />
                                          ) : (
                                            <XCircle className="h-3 w-3" />
                                          )}
                                          <span>{assertion.message || assertion.assertion.type}</span>
                                        </div>
                                      )
                                    )}
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
            </>
          ) : (
            <Card>
              <CardContent className="p-12">
                <div className="text-center">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">选择执行记录</h3>
                  <p className="text-sm text-muted-foreground">
                    从左侧列表选择一个执行记录查看详细结果
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
