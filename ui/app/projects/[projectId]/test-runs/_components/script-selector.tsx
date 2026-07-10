"use client";

import * as React from "react";
import {
  Code,
  Layers,
  Globe,
  Search,
  CheckSquare,
  Square,
  Filter,
  XCircle,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { listAPITests, type APITest } from "@/lib/api/api-tests";
import { listWebTests, type WebTest } from "@/lib/api/web-tests";
import { listScenarios } from "@/lib/api/scenarios";
import type { Scenario } from "@/types/scenario";
import { type ScriptSelection, type ScriptType } from "@/lib/api";

interface UnifiedScript {
  id: string;
  type: ScriptType;
  identifier: string;
  name: string;
  description?: string;
  typeLabel: string;
  typeIcon: React.ReactNode;
  meta: { label: string; value: string }[];
  createdAt: string;
}

interface ScriptSelectorProps {
  projectId: string;
  scripts: ScriptSelection[];
  onScriptsChange: (scripts: ScriptSelection[]) => void;
  disabled?: boolean;
}

export function ScriptSelector({
  projectId,
  scripts,
  onScriptsChange,
  disabled,
}: ScriptSelectorProps) {
  const [scriptTab, setScriptTab] = React.useState<ScriptType | "all">("all");
  const [scriptSearch, setScriptSearch] = React.useState("");
  const [apiTests, setApiTests] = React.useState<APITest[]>([]);
  const [scenarios, setScenarios] = React.useState<Scenario[]>([]);
  const [webTests, setWebTests] = React.useState<WebTest[]>([]);
  const [scriptsLoading, setScriptsLoading] = React.useState(false);

  const loadScripts = React.useCallback(async () => {
    if (!projectId) return;
    setScriptsLoading(true);
    try {
      const [apiRes, scenarioRes, webRes] = await Promise.allSettled([
        listAPITests(projectId, { page: 1, page_size: 300 }),
        listScenarios(projectId, { page: 1, page_size: 300 }),
        listWebTests(projectId, { page: 1, page_size: 300 }),
      ]);

      if (apiRes.status === "fulfilled") {
        setApiTests(apiRes.value.items || []);
      } else {
        // eslint-disable-next-line no-console
        console.error("[ScriptSelector] listAPITests failed:", apiRes.reason);
      }
      if (scenarioRes.status === "fulfilled") {
        setScenarios(scenarioRes.value.items || []);
      } else {
        // eslint-disable-next-line no-console
        console.error(
          "[ScriptSelector] listScenarios failed:",
          scenarioRes.reason
        );
      }
      if (webRes.status === "fulfilled") {
        setWebTests(webRes.value.items || []);
      } else {
        // eslint-disable-next-line no-console
        console.error("[ScriptSelector] listWebTests failed:", webRes.reason);
      }
    } finally {
      setScriptsLoading(false);
    }
  }, [projectId]);

  React.useEffect(() => {
    loadScripts();
  }, [loadScripts]);

  const allScriptItems = React.useMemo<UnifiedScript[]>(() => {
    const items: UnifiedScript[] = [];

    apiTests.forEach((t) => {
      items.push({
        id: t.id,
        type: "api_test",
        identifier: t.identifier,
        name: t.name,
        description: t.description ?? undefined,
        typeLabel: "API 测试",
        typeIcon: <Code className="h-3.5 w-3.5" />,
        meta: [
          { label: "端点", value: String(t.total_endpoints ?? 0) },
          { label: "场景", value: String(t.total_scenarios ?? 0) },
          { label: "格式", value: t.script_format || "playwright" },
        ],
        createdAt: t.created_at,
      });
    });

    scenarios.forEach((s) => {
      items.push({
        id: s.id,
        type: "scenario",
        identifier: s.identifier,
        name: s.name,
        description: s.description ?? undefined,
        typeLabel: "场景测试",
        typeIcon: <Layers className="h-3.5 w-3.5" />,
        meta: [
          { label: "步骤", value: String(s.total_steps ?? 0) },
          ...(s.last_run_status
            ? [{ label: "上次", value: s.last_run_status }]
            : []),
        ],
        createdAt: s.created_at,
      });
    });

    webTests.forEach((t) => {
      items.push({
        id: t.id,
        type: "web_test",
        identifier: t.identifier,
        name: t.name,
        description: t.description ?? undefined,
        typeLabel: "Web 测试",
        typeIcon: <Globe className="h-3.5 w-3.5" />,
        meta: [
          { label: "页面", value: String(t.total_pages ?? 0) },
          { label: "流程", value: String(t.total_flows ?? 0) },
          { label: "格式", value: t.script_format || "playwright" },
        ],
        createdAt: t.created_at,
      });
    });

    return items;
  }, [apiTests, scenarios, webTests]);

  const filteredScripts = React.useMemo(() => {
    let result = allScriptItems;

    if (scriptTab !== "all") {
      result = result.filter((s) => s.type === scriptTab);
    }

    if (scriptSearch.trim()) {
      const q = scriptSearch.trim().toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.identifier.toLowerCase().includes(q)
      );
    }

    return result;
  }, [allScriptItems, scriptTab, scriptSearch]);

  const selectedCountByType = React.useMemo(() => {
    const counts: Record<string, number> = {};
    scripts?.forEach((s) => {
      counts[s.script_type] = (counts[s.script_type] || 0) + 1;
    });
    return counts;
  }, [scripts]);

  const isScriptSelected = (type: ScriptType, id: string) => {
    return (
      scripts?.some((s) => s.script_type === type && s.script_id === id) ??
      false
    );
  };

  const toggleScriptSelection = (script: UnifiedScript) => {
    const exists = scripts.some(
      (s) => s.script_type === script.type && s.script_id === script.id
    );

    if (exists) {
      onScriptsChange(
        scripts.filter(
          (s) => !(s.script_type === script.type && s.script_id === script.id)
        )
      );
    } else {
      onScriptsChange([
        ...scripts,
        {
          script_type: script.type,
          script_id: script.id,
          script_identifier: script.identifier,
          script_name: script.name,
        },
      ]);
    }
  };

  const formatScriptDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("zh-CN");
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-base font-medium">选择执行脚本</Label>
        <div className="flex items-center gap-3 text-sm">
          {selectedCountByType["api_test"] ? (
            <span className="flex items-center gap-1 text-blue-600">
              <Code className="h-3.5 w-3.5" />
              API {selectedCountByType["api_test"]}
            </span>
          ) : null}
          {selectedCountByType["scenario"] ? (
            <span className="flex items-center gap-1 text-amber-600">
              <Layers className="h-3.5 w-3.5" />
              场景 {selectedCountByType["scenario"]}
            </span>
          ) : null}
          {selectedCountByType["web_test"] ? (
            <span className="flex items-center gap-1 text-green-600">
              <Globe className="h-3.5 w-3.5" />
              Web {selectedCountByType["web_test"]}
            </span>
          ) : null}
          {!scripts?.length ? (
            <span className="text-muted-foreground">未选择脚本</span>
          ) : (
            <span className="font-medium">共 {scripts.length} 个</span>
          )}
        </div>
      </div>

      {/* 工具栏 */}
      <div className="flex flex-wrap items-center gap-2">
        <Tabs
          value={scriptTab}
          onValueChange={(v) => setScriptTab(v as ScriptType | "all")}
        >
          <TabsList>
            <TabsTrigger value="all">
              全部
              {allScriptItems.length > 0 && (
                <span className="ml-1 text-xs text-muted-foreground">
                  ({allScriptItems.length})
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="api_test">
              <Code className="mr-1 h-3.5 w-3.5" />
              API
            </TabsTrigger>
            <TabsTrigger value="scenario">
              <Layers className="mr-1 h-3.5 w-3.5" />
              场景
            </TabsTrigger>
            <TabsTrigger value="web_test">
              <Globe className="mr-1 h-3.5 w-3.5" />
              Web
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索标识符或名称..."
            value={scriptSearch}
            onChange={(e) => setScriptSearch(e.target.value)}
            className="pl-9"
            disabled={disabled}
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => {
            const newSelections = filteredScripts
              .filter((item) => !isScriptSelected(item.type, item.id))
              .map((item) => ({
                script_type: item.type,
                script_id: item.id,
                script_identifier: item.identifier,
                script_name: item.name,
              }));
            onScriptsChange([...scripts, ...newSelections]);
          }}
        >
          <CheckSquare className="mr-1 h-3.5 w-3.5" />
          全选
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => {
            const visibleIds = new Set(filteredScripts.map((i) => i.id));
            onScriptsChange(
              scripts.filter((s) => !visibleIds.has(s.script_id))
            );
          }}
        >
          <Square className="mr-1 h-3.5 w-3.5" />
          取消全选
        </Button>
      </div>

      {/* 脚本表格 */}
      <Card>
        <CardContent className="p-0">
          <ScrollArea className="h-[340px]">
            {/* 表头 */}
            <div className="sticky top-0 z-10 grid grid-cols-[44px_1.2fr_0.8fr_1fr_90px_80px] gap-2 border-b bg-muted/60 px-3 py-2 text-xs font-medium text-muted-foreground backdrop-blur-sm">
              <div>选择</div>
              <div>标识符 / 名称</div>
              <div>类型</div>
              <div>元数据</div>
              <div>创建时间</div>
              <div>状态</div>
            </div>

            {scriptsLoading ? (
              <div className="flex h-40 items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载脚本中...
              </div>
            ) : filteredScripts.length === 0 ? (
              <div className="flex h-40 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
                <Filter className="h-8 w-8 opacity-40" />
                <span>
                  {allScriptItems.length === 0
                    ? "暂无可用脚本，请先创建 API 测试、场景或 Web 测试"
                    : "没有匹配当前筛选条件的脚本"}
                </span>
              </div>
            ) : (
              filteredScripts.map((item) => {
                const selected = isScriptSelected(item.type, item.id);
                return (
                  <div
                    key={`${item.type}-${item.id}`}
                    className="grid grid-cols-[44px_1.2fr_0.8fr_1fr_90px_80px] gap-2 border-b px-3 py-2.5 text-sm items-center transition-colors hover:bg-muted/40 last:border-b-0"
                  >
                    <Checkbox
                      checked={selected}
                      disabled={disabled}
                      onCheckedChange={() => toggleScriptSelection(item)}
                    />
                    <div className="min-w-0">
                      <div className="truncate font-medium">{item.name}</div>
                      <div className="truncate text-xs text-muted-foreground font-mono">
                        {item.identifier}
                      </div>
                      {item.description && (
                        <div className="truncate text-xs text-muted-foreground mt-0.5">
                          {item.description}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground">
                        {item.typeIcon}
                      </span>
                      <Badge
                        variant="outline"
                        className="text-xs font-normal"
                      >
                        {item.typeLabel}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                      {item.meta.map((m) => (
                        <span key={m.label}>
                          <span className="text-muted-foreground/60">
                            {m.label}
                          </span>{" "}
                          {m.value}
                        </span>
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatScriptDate(item.createdAt)}
                    </div>
                    <div>
                      {selected ? (
                        <Badge className="bg-primary/10 text-primary hover:bg-primary/20 text-xs font-normal gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          已选
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground/50">
                          -
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* 已选脚本摘要 */}
      {scripts && scripts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {scripts.map((s, idx) => (
            <Badge
              key={idx}
              variant="secondary"
              className="text-xs gap-1 pr-1"
            >
              {s.script_name || s.script_identifier || s.script_id}
              <button
                type="button"
                className="ml-0.5 rounded-full hover:bg-destructive/20 hover:text-destructive transition-colors disabled:opacity-50"
                disabled={disabled}
                onClick={() => {
                  onScriptsChange(scripts.filter((_, i) => i !== idx));
                }}
              >
                <XCircle className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
