"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AlertCircle, Layers, Plus, Eye, Zap, FolderOpen, CheckCircle2, Loader2, Play } from "lucide-react";
import { cn } from "@/lib/utils";

interface WebIntentFunction {
  id: string;
  identifier: string;
  display_name: string;
  base_url?: string;
}

interface WebIntentAlternative {
  key: string;
  label: string;
}

/** 候选功能（多候选场景） */
interface CandidateFunction {
  id: string;
  identifier: string;
  display_name: string;
  folder_name?: string;
  sub_function_count?: number;
  test_case_count?: number;
  status?: string;
  match_score?: string;
}

interface IntentConfirmationInterruptProps {
  recommendation?: string;
  reason?: string;
  description?: string;
  existing_function?: WebIntentFunction;
  alternatives?: WebIntentAlternative[];
  /** 多个候选功能列表（推荐项通过 recommendation 字段指向其 key） */
  candidates?: CandidateFunction[];
  onResume: (value: any) => void;
  isLoading?: boolean;
}

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  expand: Layers,
  new: Plus,
  view_details: Eye,
  execute: Play,
};

/**
 * Web 测试意图确认中断组件。
 *
 * 当 Agent 检测到已有匹配 Web 功能时，渲染推荐卡片与一键操作按钮，
 * 用户选择后通过 onResume 恢复 LangGraph 执行。
 */
export function IntentConfirmationInterrupt({
  recommendation,
  reason,
  description,
  existing_function,
  alternatives,
  candidates,
  onResume,
  isLoading,
}: IntentConfirmationInterruptProps) {
  const [lastClicked, setLastClicked] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSelect = (key: string) => {
    setLastClicked(key);
    setIsSubmitting(true);
    onResume({ decision: key, comment: comment.trim() || undefined });
  };

  const isDisabled = isLoading || isSubmitting;

  const items = alternatives?.length
    ? alternatives
    : [
        { key: "expand", label: "扩展已有功能" },
        { key: "new", label: "新建功能" },
        { key: "view_details", label: "先查看详情" },
      ];

  const hasCandidates = candidates && candidates.length > 1;

  return (
    <div className="w-full rounded-lg border-2 border-purple-300 bg-purple-50/80 p-4 dark:border-purple-700 dark:bg-purple-950/30">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-900">
          <AlertCircle
            size={18}
            className="text-purple-700 dark:text-purple-200"
          />
        </div>
        <div className="flex-1">
          <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">
            {hasCandidates ? "检测到已有匹配功能" : "需要确认意图"}
          </h3>
          {reason && (
            <p className="mt-1 text-sm text-gray-700 dark:text-gray-200">
              {reason}
            </p>
          )}
          {description && (
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {description}
            </p>
          )}
          {!hasCandidates && existing_function && (
            <p className="mt-1 text-xs text-purple-700 dark:text-purple-300">
              {existing_function.identifier} · {existing_function.display_name}
              {existing_function.base_url && ` · ${existing_function.base_url}`}
            </p>
          )}
        </div>
      </div>

      {/* ──── 多候选功能对比卡片 ──── */}
      {hasCandidates ? (
        <div className="space-y-2">
          {candidates!.map((candidate) => {
            const isRecommended = candidate.id === recommendation;
            const isPassed = candidate.status === "passed" || candidate.status?.includes("通过");
            return (
              <div
                key={candidate.id}
                className={cn(
                  "rounded-lg border p-3 transition-all",
                  isRecommended
                    ? "border-purple-400 bg-purple-100/70 ring-1 ring-purple-300 dark:border-purple-500 dark:bg-purple-900/40 dark:ring-purple-600"
                    : "border-border bg-card hover:border-purple-200 dark:hover:border-purple-700"
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                        {candidate.identifier}
                      </span>
                      <span className="truncate text-sm text-muted-foreground">
                        {candidate.display_name}
                      </span>
                      {isRecommended && (
                        <span className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-purple-200 px-2 py-0.5 text-[10px] font-medium text-purple-800 dark:bg-purple-800 dark:text-purple-200">
                          <Zap className="h-2.5 w-2.5" />
                          系统推荐
                        </span>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                      {candidate.folder_name && (
                        <span className="inline-flex items-center gap-1">
                          <FolderOpen className="h-3 w-3" />
                          {candidate.folder_name}
                        </span>
                      )}
                      {(candidate.sub_function_count ?? 0) > 0 && (
                        <span>{candidate.sub_function_count} 子功能</span>
                      )}
                      {(candidate.test_case_count ?? 0) > 0 && (
                        <span>{candidate.test_case_count} 用例</span>
                      )}
                      {candidate.status && (
                        <span
                          className={cn(
                            "inline-flex items-center gap-0.5 font-medium",
                            isPassed
                              ? "text-green-700 dark:text-green-400"
                              : "text-amber-700 dark:text-amber-400"
                          )}
                        >
                          {isPassed && <CheckCircle2 className="h-3 w-3" />}
                          {candidate.status}
                        </span>
                      )}
                      {candidate.match_score && (
                        <span className="text-purple-600 dark:text-purple-300">
                          匹配度: {candidate.match_score}
                        </span>
                      )}
                    </div>
                  </div>
                  <Button
                    onClick={() => handleSelect(`candidate:${candidate.id}`)}
                    variant={isRecommended ? "default" : "outline"}
                    size="sm"
                    disabled={isDisabled}
                    className={cn(
                      "shrink-0 min-w-[90px]",
                      isRecommended &&
                        "bg-purple-600 text-white hover:bg-purple-700 dark:bg-purple-600 dark:hover:bg-purple-700"
                    )}
                  >
                    {isSubmitting && lastClicked === `candidate:${candidate.id}` ? (
                      <span className="inline-flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        提交中
                      </span>
                    ) : isRecommended ? (
                      "直接用这个"
                    ) : (
                      "选择"
                    )}
                  </Button>
                </div>
              </div>
            );
          })}

          {/* 底部：新建功能备选 */}
          <button
            type="button"
            onClick={() => handleSelect("new")}
            disabled={isDisabled}
            className="flex w-full items-center justify-center gap-1.5 rounded-md py-2 text-sm text-muted-foreground transition-colors hover:bg-purple-100/50 hover:text-purple-700 dark:hover:bg-purple-900/30 dark:hover:text-purple-300"
          >
            <Plus className="h-3.5 w-3.5" />
            不选择已有功能，新建一个
          </button>
        </div>
      ) : (
        /* ──── 单候选模式（保持兼容） ──── */
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {items.map((item) => {
            const Icon = ICONS[item.key] || AlertCircle;
            const isRecommended = item.key === recommendation;
            return (
              <Button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                variant={isRecommended ? "default" : "outline"}
                disabled={isDisabled}
                className={cn(
                  "h-auto items-center justify-start gap-2 p-3 text-left",
                  isRecommended &&
                    "bg-purple-600 text-white hover:bg-purple-700 dark:bg-purple-600 dark:hover:bg-purple-700"
                )}
              >
                {isSubmitting && lastClicked === item.key ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                ) : (
                  <Icon className="h-4 w-4 shrink-0" />
                )}
                <div className="flex flex-col">
                  <span className="text-sm font-medium">
                    {isSubmitting && lastClicked === item.key ? "提交中..." : item.label}
                  </span>
                  {isRecommended && !isSubmitting && (
                    <span className="text-[10px] opacity-80">系统推荐</span>
                  )}
                </div>
              </Button>
            );
          })}
        </div>
      )}

      <div className="mt-3">
        <label
          htmlFor="intent-comment"
          className="mb-1.5 block text-xs font-medium text-gray-700 dark:text-gray-300"
        >
          补充说明（可选）
        </label>
        <Textarea
          id="intent-comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="例如：只扩展登录相关用例，不包含购物车"
          disabled={isDisabled}
          rows={2}
          className="resize-none bg-card text-sm"
        />
      </div>

      {isSubmitting && lastClicked && (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-purple-600 dark:text-purple-300">
          <Loader2 className="h-3 w-3 animate-spin" />
          已选择，正在继续...
        </p>
      )}
    </div>
  );
}
