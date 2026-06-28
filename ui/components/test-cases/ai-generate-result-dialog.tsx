"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZscVV3PT06YjJlOGE3ZGI=

import * as React from "react";
import { ChevronRight, ChevronDown, ThumbsUp, ThumbsDown, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { TestCaseInfo } from "@/lib/api/types";
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZscVV3PT06YjJlOGE3ZGI=

interface Scenario {
  name: string;
  testCases: TestCaseInfo[];
  expanded: boolean;
}

interface AIGenerateResultDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prompt: string;
  folderId?: string | null;
  scenarios: Scenario[];
  onAddTestCases: () => void;
  onStartOver: () => void;
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZscVV3PT06YjJlOGE3ZGI=

export function AIGenerateResultDialog({
  open,
  onOpenChange,
  prompt,
  folderId,
  scenarios,
  onAddTestCases,
  onStartOver,
}: AIGenerateResultDialogProps) {
  const [expandedScenarios, setExpandedScenarios] = React.useState<Set<number>>(
    new Set(scenarios.map((_, i) => i))
  );
  const [feedback, setFeedback] = React.useState<"up" | "down" | null>(null);

  const totalTestCases = scenarios.reduce((sum, s) => sum + s.testCases.length, 0);
  const scenarioCount = scenarios.length;

  const toggleScenario = (index: number) => {
    const newExpanded = new Set(expandedScenarios);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedScenarios(newExpanded);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="h-5 w-5 text-primary" />
            使用 AI 生成测试用例
          </DialogTitle>
        </DialogHeader>

        {/* 提示词和文件夹 */}
        <div className="space-y-2 py-2">
          <p className="text-sm text-muted-foreground">{prompt}</p>
          {folderId && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">📁</span>
              <span>{folderId}</span>
            </div>
          )}
        </div>

        {/* 生成结果摘要 */}
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-3 text-sm">
          <Sparkles className="h-4 w-4 text-primary shrink-0" />
          <span className="text-blue-900">
            我们已生成 <strong>{totalTestCases} 个测试用例</strong>，涵盖{" "}
            <strong>{scenarioCount} 个场景</strong>。保存这些测试用例后，您可以生成步骤/结果。
          </span>
        </div>

        {/* 场景列表 */}
        <div className="flex-1 overflow-y-auto space-y-2 py-2">
          {scenarios.map((scenario, index) => (
            <div key={index} className="border rounded-lg">
              <button
                onClick={() => toggleScenario(index)}
                className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {expandedScenarios.has(index) ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="font-medium">{scenario.name}</span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {scenario.testCases.length} 个测试用例
                </span>
              </button>

              {expandedScenarios.has(index) && (
                <div className="border-t px-4 py-3 space-y-2 bg-muted/20">
                  {scenario.testCases.map((testCase, tcIndex) => (
                    <div
                      key={tcIndex}
                      className="flex items-start gap-3 p-3 bg-background rounded border"
                    >
                      <input type="checkbox" defaultChecked className="mt-1" />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{testCase.name}</p>
                        {testCase.description && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {testCase.description}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" className="h-7 text-xs">
                          查看
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs text-primary">
                          添加
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* 反馈和操作按钮 */}
        <DialogFooter className="flex items-center justify-between sm:justify-between border-t pt-4">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                "h-8 w-8",
                feedback === "up" && "bg-green-100 text-green-600 hover:bg-green-100"
              )}
              onClick={() => setFeedback(feedback === "up" ? null : "up")}
            >
              <ThumbsUp className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                "h-8 w-8",
                feedback === "down" && "bg-red-100 text-red-600 hover:bg-red-100"
              )}
              onClick={() => setFeedback(feedback === "down" ? null : "down")}
            >
              <ThumbsDown className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onStartOver}>
              重新开始
            </Button>
            <Button onClick={onAddTestCases} className="min-w-[160px]">
              添加 {totalTestCases} 个测试用例
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZscVV3PT06YjJlOGE3ZGI=

