"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AlertCircle, Layers, Plus, Eye } from "lucide-react";
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

interface IntentConfirmationInterruptProps {
  recommendation?: string;
  reason?: string;
  description?: string;
  existing_function?: WebIntentFunction;
  alternatives?: WebIntentAlternative[];
  onResume: (value: any) => void;
  isLoading?: boolean;
}

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  expand: Layers,
  new: Plus,
  view_details: Eye,
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
  onResume,
  isLoading,
}: IntentConfirmationInterruptProps) {
  const [lastClicked, setLastClicked] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const handleSelect = (key: string) => {
    setLastClicked(key);
    onResume({ decision: key, comment: comment.trim() || undefined });
  };

  const items = alternatives?.length
    ? alternatives
    : [
        { key: "expand", label: "扩展已有功能" },
        { key: "new", label: "新建功能" },
        { key: "view_details", label: "先查看详情" },
      ];

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
            需要确认意图
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
          {existing_function && (
            <p className="mt-1 text-xs text-purple-700 dark:text-purple-300">
              {existing_function.identifier} · {existing_function.display_name}
              {existing_function.base_url && ` · ${existing_function.base_url}`}
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {items.map((item) => {
          const Icon = ICONS[item.key] || AlertCircle;
          const isRecommended = item.key === recommendation;
          return (
            <Button
              key={item.key}
              onClick={() => handleSelect(item.key)}
              variant={isRecommended ? "default" : "outline"}
              disabled={isLoading}
              className={cn(
                "h-auto items-center justify-start gap-2 p-3 text-left",
                isRecommended &&
                  "bg-purple-600 text-white hover:bg-purple-700 dark:bg-purple-600 dark:hover:bg-purple-700"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <div className="flex flex-col">
                <span className="text-sm font-medium">{item.label}</span>
                {isRecommended && (
                  <span className="text-[10px] opacity-80">系统推荐</span>
                )}
              </div>
            </Button>
          );
        })}
      </div>

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
          disabled={isLoading}
          rows={2}
          className="resize-none bg-card text-sm"
        />
      </div>

      {isLoading && lastClicked && (
        <p className="mt-3 text-xs text-purple-600 dark:text-purple-300">
          已选择，正在继续...
        </p>
      )}
    </div>
  );
}
