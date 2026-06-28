/**
 * 场景编排器 - 可视化编辑业务流场景
 *
 * 功能：
 * - 步骤拖拽排序
 * - 数据依赖配置
 * - 变量管理
 * - 实时预览
 */
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhacU9BPT06ZTY1NjFiM2Q=

"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  GripVertical,
  Plus,
  Trash2,
  Edit,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  CheckCircle2,
  Clock,
  Settings,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  listScenarioSteps,
  deleteScenarioStep,
  reorderScenarioSteps,
} from "@/lib/api/scenarios";
import type { ScenarioStep } from "@/types/scenario";
import { StepEditDialog } from "./step-edit-dialog";
import { StepCreateDialog } from "./step-create-dialog";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhacU9BPT06ZTY1NjFiM2Q=

interface ScenarioOrchestrationViewProps {
  projectId: string;
  scenarioId: string | null;
  onScenarioUpdate: () => void;
  onOpenSidebar?: () => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhacU9BPT06ZTY1NjFiM2Q=

export function ScenarioOrchestrationView({
  projectId,
  scenarioId,
  onScenarioUpdate,
  onOpenSidebar,
}: ScenarioOrchestrationViewProps) {
  const [steps, setSteps] = React.useState<ScenarioStep[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [selectedStepId, setSelectedStepId] = React.useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = React.useState<Set<string>>(new Set());
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);

  // 拖拽传感器
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // 加载场景步骤
  React.useEffect(() => {
    if (scenarioId) {
      loadSteps();
    } else {
      setSteps([]);
    }
  }, [scenarioId]);

  const loadSteps = async () => {
    if (!scenarioId) return;

    try {
      setLoading(true);
      const data = await listScenarioSteps(scenarioId);
      setSteps(data);
    } catch (error) {
      console.error("Failed to load steps:", error);
      toast.error("加载步骤失败");
    } finally {
      setLoading(false);
    }
  };

  // 拖拽结束处理
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = steps.findIndex((item) => item.id === active.id);
      const newIndex = steps.findIndex((item) => item.id === over.id);

      const newSteps = arrayMove(steps, oldIndex, newIndex);

      // 更新步骤顺序
      newSteps.forEach((item, index) => {
        item.step_order = index + 1;
      });

      setSteps(newSteps);

      // 保存新顺序到后端
      try {
        const stepOrders = newSteps.reduce(
          (acc, step) => {
            acc[step.id] = step.step_order;
            return acc;
          },
          {} as Record<string, number>
        );
        await reorderScenarioSteps(scenarioId!, stepOrders);
        onScenarioUpdate();
        toast.success("步骤顺序已更新");
      } catch (error) {
        console.error("Failed to save step order:", error);
        toast.error("保存步骤顺序失败");
        // 恢复原顺序
        setSteps(steps);
      }
    }
  };

  // 添加步骤
  const handleAddStep = () => {
    setCreateDialogOpen(true);
  };

  // 删除步骤
  const handleDeleteStep = async (stepId: string) => {
    if (!scenarioId) return;

    try {
      await deleteScenarioStep(scenarioId, stepId);
      setSteps(steps.filter((s) => s.id !== stepId));
      toast.success("步骤已删除");
      onScenarioUpdate();
    } catch (error) {
      console.error("Failed to delete step:", error);
      toast.error("删除步骤失败");
    }
  };

  // 切换展开状态
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

  if (!scenarioId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <Settings className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">请先选择一个场景</h3>
          <p className="text-sm text-muted-foreground">
            从左侧列表选择场景，或创建新场景开始编排
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-sm text-muted-foreground">加载中...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 顶部：场景概览 */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <div className="text-sm text-muted-foreground">步骤数量</div>
                <div className="text-2xl font-bold">{steps.length}</div>
              </div>
              <div className="h-10 w-px bg-border" />
              <div>
                <div className="text-sm text-muted-foreground">数据依赖</div>
                <div className="text-2xl font-bold">
                  {steps.reduce((acc, s) => acc + (s.data_mappings?.length || 0), 0)}
                </div>
              </div>
              <div className="h-10 w-px bg-border" />
              <div>
                <div className="text-sm text-muted-foreground">断言</div>
                <div className="text-2xl font-bold">
                  {steps.reduce((acc, s) => acc + (s.assertions?.length || 0), 0)}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={handleAddStep} variant="outline" size="sm" className="gap-2">
                <Plus className="h-4 w-4" />
                添加步骤
              </Button>
              {onOpenSidebar && (
                <Button onClick={onOpenSidebar} variant="outline" size="sm" className="gap-2">
                  <Play className="h-4 w-4" />
                  执行场景
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 步骤列表（可拖拽） */}
      {steps.length === 0 ? (
        <Card>
          <CardContent className="p-12">
            <div className="text-center">
              <Clock className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">暂无步骤</h3>
              <p className="text-sm text-muted-foreground mb-4">
                点击"添加步骤"按钮或使用 AI 助手来添加步骤
              </p>
              <Button onClick={handleAddStep} className="gap-2">
                <Plus className="h-4 w-4" />
                添加第一个步骤
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={steps.map((s) => s.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-3">
              {steps.map((step, index) => (
                <SortableStepItem
                  key={step.id}
                  step={step}
                  index={index}
                  isExpanded={expandedSteps.has(step.id)}
                  onToggleExpand={() => toggleExpand(step.id)}
                  onDelete={() => handleDeleteStep(step.id)}
                  onEdit={() => {
                    setSelectedStepId(step.id);
                    setEditDialogOpen(true);
                  }}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* 步骤编辑对话框 */}
      {selectedStepId && editDialogOpen && (
        <StepEditDialog
          stepId={selectedStepId}
          scenarioId={scenarioId!}
          projectId={projectId}
          open={editDialogOpen}
          onOpenChange={(open: boolean) => {
            setEditDialogOpen(open);
            if (!open) setSelectedStepId(null);
          }}
          onSave={() => {
            loadSteps();
            setEditDialogOpen(false);
            setSelectedStepId(null);
            onScenarioUpdate();
          }}
        />
      )}

      {/* 步骤创建对话框 */}
      <StepCreateDialog
        scenarioId={scenarioId!}
        projectId={projectId}
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSave={() => {
          loadSteps();
          setCreateDialogOpen(false);
          onScenarioUpdate();
        }}
      />
    </div>
  );
}

// 可排序步骤项组件
function SortableStepItem({
  step,
  index,
  isExpanded,
  onToggleExpand,
  onDelete,
  onEdit,
}: {
  step: ScenarioStep;
  index: number;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onDelete: () => void;
  onEdit: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const getMethodColor = (method: string) => {
    const colors: Record<string, string> = {
      GET: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400",
      POST: "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400",
      PUT: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400",
      DELETE: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400",
      PATCH: "bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400",
    };
    return colors[method] || "bg-gray-100 text-gray-700";
  };

  return (
    <div ref={setNodeRef} style={style} className="relative z-10">
      <Card className={isDragging ? "shadow-lg" : ""}>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            {/* 拖拽手柄 */}
            <button
              className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground flex-shrink-0"
              {...attributes}
              {...listeners}
            >
              <GripVertical className="h-5 w-5" />
            </button>

            {/* 步骤序号 */}
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
              {index + 1}
            </div>

            {/* 步骤内容 */}
            <div className="flex-1 min-w-0 overflow-hidden">
              <div className="flex items-center gap-2 mb-1">
                {step.endpoint && (
                  <Badge className={`${getMethodColor(step.endpoint.method)} flex-shrink-0`}>
                    {step.endpoint.method}
                  </Badge>
                )}
                <h4 className="font-semibold truncate">{step.name}</h4>
              </div>

              {step.endpoint && (
                <code className="text-xs text-muted-foreground font-mono block truncate">
                  {step.endpoint.path}
                </code>
              )}

              {/* 数据依赖指示器 */}
              {step.data_mappings && step.data_mappings.length > 0 && (
                <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                  <ArrowRight className="h-3 w-3 flex-shrink-0" />
                  <span className="truncate">{step.data_mappings.length} 个数据依赖</span>
                </div>
              )}

              {/* 断言数量 */}
              {step.assertions && step.assertions.length > 0 && (
                <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                  <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
                  <span className="truncate">{step.assertions.length} 个断言</span>
                </div>
              )}
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-1 flex-shrink-0 relative z-20 ml-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggleExpand}
                className="h-8 w-8 p-0"
                title="展开/收起"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onEdit}
                className="h-8 w-8 p-0"
                title="编辑步骤"
              >
                <Edit className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onDelete}
                className="h-8 w-8 p-0 hover:text-destructive"
                title="删除步骤"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* 展开的详细信息 */}
          {isExpanded && (
            <div className="mt-4 pt-4 border-t space-y-3">
              {/* 数据提取器 */}
              {step.extractors && step.extractors.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium mb-2">数据提取器</h5>
                  <div className="space-y-1">
                    {step.extractors.map((extractor, idx) => (
                      <div
                        key={idx}
                        className="text-xs bg-muted/50 px-2 py-1 rounded flex items-center gap-2"
                      >
                        <code className="text-primary">{extractor.name}</code>
                        <span className="text-muted-foreground">←</span>
                        <code className="text-muted-foreground">{extractor.path}</code>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 断言 */}
              {step.assertions && step.assertions.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium mb-2">断言</h5>
                  <div className="space-y-1">
                    {step.assertions.map((assertion, idx) => (
                      <div
                        key={idx}
                        className="text-xs bg-muted/50 px-2 py-1 rounded flex items-center gap-2"
                      >
                        <CheckCircle2 className="h-3 w-3 text-green-500" />
                        <span>{assertion.type}: {JSON.stringify(assertion.expected)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 数据映射 */}
              {step.data_mappings && step.data_mappings.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium mb-2">数据依赖</h5>
                  <div className="space-y-1">
                    {step.data_mappings.map((mapping) => (
                      <div
                        key={mapping.id}
                        className="text-xs bg-muted/50 px-2 py-1 rounded"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">源:</span>
                          <code className="text-primary">{mapping.source_path || "静态值"}</code>
                          <span className="text-muted-foreground">→</span>
                          <span className="text-muted-foreground">目标:</span>
                          <code className="text-primary">{mapping.target_path}</code>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhacU9BPT06ZTY1NjFiM2Q=
