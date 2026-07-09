"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjNObFR3PT06ZTM4ZjQxMzQ=

import * as React from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import {
  Plus,
  Zap,
  List,
  Workflow,
  Activity,
  Clock,
  Sparkles,
} from "lucide-react";
import { MainLayout } from "@/components/layout";
import { useLanguage } from "@/providers/LanguageProvider";
import { useProjectEnvironment } from "@/providers/ProjectEnvironmentProvider";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScenarioListPanel } from "@/components/scenario-tests/scenario-list-panel";
import { ScenarioOrchestrationView } from "@/components/scenario-tests/scenario-orchestration-view";
import { ScenarioExecutionMonitor } from "@/components/scenario-tests/scenario-execution-monitor";
import { ScenarioCreateDialog } from "@/components/scenario-tests/scenario-create-dialog";
import { ScenarioDetailSidebar } from "@/components/scenario-tests/scenario-detail-sidebar";
import { EnvironmentSelector } from "@/components/api-tests/environment-selector";
import { EnvironmentSheet } from "@/components/api-tests/environment-sheet";
import { executeScenario } from "@/lib/api/scenarios";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjNObFR3PT06ZTM4ZjQxMzQ=

type ViewMode = "list" | "orchestrate" | "monitor";
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjNObFR3PT06ZTM4ZjQxMzQ=

export default function ScenarioTestsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { t } = useLanguage();
  const { selectedEnvironmentId } = useProjectEnvironment();

  const [viewMode, setViewMode] = React.useState<ViewMode>("list");
  const [selectedScenarioId, setSelectedScenarioId] = React.useState<string | null>(null);
  const [showDetailSidebar, setShowDetailSidebar] = React.useState(false);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const [detailSidebarEditing, setDetailSidebarEditing] = React.useState(false);
  const [detailEditTrigger, setDetailEditTrigger] = React.useState(0);
  const [environmentSheetOpen, setEnvironmentSheetOpen] = React.useState(false);
  const [running, setRunning] = React.useState(false);

  const handleScenarioCreated = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setViewMode("orchestrate");
    setCreateDialogOpen(false);
    setRefreshTrigger((prev) => prev + 1);
    toast.success(t("apiTests.scenarioCreated"));
  };

  const handleSelectScenario = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setShowDetailSidebar(true);
    setDetailSidebarEditing(false);
    setViewMode("orchestrate");
  };

  const handleEditScenario = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setShowDetailSidebar(true);
    setDetailSidebarEditing(true);
    setDetailEditTrigger((prev) => prev + 1);
    setViewMode("orchestrate");
  };

  const handleRunScenario = async () => {
    if (!selectedScenarioId) return;
    setRunning(true);
    try {
      const result = await executeScenario(selectedScenarioId, {
        environment_id: selectedEnvironmentId || undefined,
      });
      if (result.status === "completed") {
        toast.success(t("apiTests.scenarioRunSuccess") || "场景执行成功");
      } else {
        toast.warning(result.message || "场景执行完成");
      }
      setRefreshTrigger((prev) => prev + 1);
      setViewMode("monitor");
    } catch (error) {
      console.error("Failed to run scenario:", error);
      toast.error(t("apiTests.scenarioRunFailed") || "场景执行失败");
    } finally {
      setRunning(false);
    }
  };

  return (
    <MainLayout title={t("scenarioTests.title")}>
      <div className="flex h-[calc(100vh-8rem)] rounded-lg border bg-card overflow-hidden">
        {/* 左侧栏 - 场景列表 */}
        <div className="w-80 shrink-0 border-r bg-muted/20 flex flex-col min-h-0">
          <div className="p-4 border-b bg-background shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">{t("apiTests.testScenarios")}</h2>
              <Button
                size="sm"
                onClick={() => setCreateDialogOpen(true)}
                className="gap-2"
              >
                <Plus className="h-4 w-4" />
                {t("common.create")}
              </Button>
            </div>

            {/* 场景筛选器 */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs"
                onClick={() => setRefreshTrigger((prev) => prev + 1)}
              >
                {t("apiTests.all")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="flex-1 text-xs"
              >
                {t("apiTests.draft")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="flex-1 text-xs"
              >
                {t("apiTests.active")}
              </Button>
            </div>
          </div>

          {/* 场景列表 */}
          <div className="flex-1 overflow-hidden min-h-0">
            <ScenarioListPanel
              key={refreshTrigger}
              projectId={projectId}
              selectedScenarioId={selectedScenarioId}
              onSelectScenario={handleSelectScenario}
              onEditScenario={handleEditScenario}
              onViewExecutionHistory={(scenarioId) => {
                setSelectedScenarioId(scenarioId);
                setViewMode("monitor");
              }}
            />
          </div>
        </div>

        {/* 中间主内容区 */}
        <div className="flex-1 flex flex-col min-h-0 bg-background">
          {/* 顶部工具栏 - 视图切换 */}
          <div className="flex items-center justify-between border-b p-4 bg-muted/20">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => {/* TODO: 打开 AI 生成场景对话框 */}}
              >
                <Sparkles className="h-4 w-4" />
                AI 生成场景
              </Button>
              <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as ViewMode)}>
                <TabsList>
                  <TabsTrigger value="list" className="gap-2">
                    <List className="h-4 w-4" />
                    {t("apiTests.scenarioList")}
                  </TabsTrigger>
                  <TabsTrigger value="orchestrate" className="gap-2">
                    <Workflow className="h-4 w-4" />
                    {t("apiTests.scenarioOrchestration")}
                  </TabsTrigger>
                  <TabsTrigger value="monitor" className="gap-2">
                    <Activity className="h-4 w-4" />
                    {t("apiTests.executionMonitor")}
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            <div className="flex items-center gap-2">
              <EnvironmentSelector onManage={() => setEnvironmentSheetOpen(true)} />
              {selectedScenarioId && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => setViewMode("monitor")}
                  >
                    <Clock className="h-4 w-4" />
                    {t("apiTests.executionHistory")}
                  </Button>
                  <Button
                    size="sm"
                    className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600"
                    onClick={handleRunScenario}
                    disabled={running}
                  >
                    <Zap className="h-4 w-4" />
                    {running ? t("common.running") : t("apiTests.runScenario")}
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* 视图内容区 */}
          <div className="flex-1 overflow-y-auto p-6">
            {viewMode === "list" && (
              <ScenarioListView
                projectId={projectId}
                onSelectScenario={handleSelectScenario}
                refreshTrigger={refreshTrigger}
              />
            )}
            {viewMode === "orchestrate" && (
              <ScenarioOrchestrationView
                projectId={projectId}
                scenarioId={selectedScenarioId}
                selectedEnvironmentId={selectedEnvironmentId}
                onScenarioUpdate={() => setRefreshTrigger((prev) => prev + 1)}
                onOpenSidebar={() => setShowDetailSidebar(true)}
              />
            )}
            {viewMode === "monitor" && (
              <ScenarioExecutionMonitor
                scenarioId={selectedScenarioId}
              />
            )}
          </div>
        </div>

        {/* 右侧详情栏（可隐藏） */}
        {showDetailSidebar && selectedScenarioId && (
          <div className="w-[500px] shrink-0 border-l bg-background shadow-lg">
            <ScenarioDetailSidebar
              scenarioId={selectedScenarioId}
              projectId={projectId}
              selectedEnvironmentId={selectedEnvironmentId}
              defaultEditing={detailSidebarEditing}
              editTrigger={detailEditTrigger}
              onClose={() => {
                setShowDetailSidebar(false);
                setDetailSidebarEditing(false);
              }}
              onScenarioUpdated={() => {
                setRefreshTrigger((prev) => prev + 1);
                setDetailSidebarEditing(false);
              }}
              onOpenAIChat={() => {}}
              onSwitchToMonitor={() => {
                setViewMode("monitor");
              }}
            />
          </div>
        )}
      </div>

      {/* 环境配置 Sheet */}
      <EnvironmentSheet
        projectId={projectId}
        open={environmentSheetOpen}
        onOpenChange={setEnvironmentSheetOpen}
      />

      {/* 场景创建对话框 */}
      <ScenarioCreateDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        projectId={projectId}
        onSuccess={handleScenarioCreated}
      />
    </MainLayout>
  );
}

// 场景列表视图（占位符，实际使用 ScenarioListPanel）
function ScenarioListView({
  projectId,
  onSelectScenario,
  refreshTrigger,
}: {
  projectId: string;
  onSelectScenario: (scenarioId: string) => void;
  refreshTrigger: number;
}) {
  const { t } = useLanguage();
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <Workflow className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
        <p className="text-lg font-medium mb-2">{t("apiTests.switchToOrchestration")}</p>
        <p className="text-sm text-muted-foreground">
          {t("apiTests.orchestrationViewDesc")}
        </p>
      </div>
    </div>
  );
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UjNObFR3PT06ZTM4ZjQxMzQ=
