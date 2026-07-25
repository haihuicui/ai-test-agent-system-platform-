"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Play, XCircle, Edit3, MessageSquareMore, ShieldAlert, ShieldCheck, Info, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type RiskLevel = "low" | "medium" | "high";

interface ExecutionAlternative {
  key: string;
  label: string;
}

interface ExecutionInvitationInterruptProps {
  type?: "execution_invitation";
  mode?: "web" | "api";
  sub_function_id?: string;
  endpoint_id?: string;
  script_name?: string;
  test_count?: number;
  description?: string;
  alternatives?: ExecutionAlternative[];
  risk_level?: RiskLevel;
  risk_reason?: string;
  onResume: (value: { decision: string; comment?: string }) => void;
  isLoading?: boolean;
}

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  execute: Play,
  skip: XCircle,
  edit: Edit3,
  other: MessageSquareMore,
};

const DEFAULT_ALTERNATIVES: ExecutionAlternative[] = [
  { key: "execute", label: "立即执行" },
  { key: "skip", label: "暂不执行" },
  { key: "edit", label: "修改脚本" },
  { key: "other", label: "其他" },
];

/**
 * 执行邀约中断组件。
 *
 * 当 Agent 完成测试脚本生成后，渲染一键操作卡片，
 * 用户选择后通过 onResume 恢复 LangGraph 执行。
 */
const RISK_BADGE: Record<RiskLevel, { bg: string; text: string }> = {
  low:    { bg: "bg-green-100 dark:bg-green-900",  text: "text-green-700 dark:text-green-200" },
  medium: { bg: "bg-yellow-100 dark:bg-yellow-900", text: "text-yellow-700 dark:text-yellow-200" },
  high:   { bg: "bg-red-100 dark:bg-red-900",    text: "text-red-700 dark:text-red-200" },
};

const EXECUTE_BUTTON_COLOR: Record<RiskLevel, string> = {
  low:    "bg-green-600 hover:bg-green-700",
  medium: "bg-yellow-600 hover:bg-yellow-700",
  high:   "bg-blue-600 hover:bg-blue-700",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "低风险",
  medium: "建议确认",
  high: "需要确认",
};

const RISK_ICONS: Record<RiskLevel, React.ComponentType<{ className?: string; size?: number }>> = {
  low: ShieldCheck,
  medium: Info,
  high: ShieldAlert,
};

export function ExecutionInvitationInterrupt({
  mode,
  script_name,
  test_count,
  description,
  alternatives,
  risk_level,
  risk_reason,
  onResume,
  isLoading,
}: ExecutionInvitationInterruptProps) {
  const [lastClicked, setLastClicked] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [otherMode, setOtherMode] = useState(false);
  const [otherComment, setOtherComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const items = alternatives?.length ? alternatives : DEFAULT_ALTERNATIVES;
  const level = risk_level || "high";
  const badge = RISK_BADGE[level];
  const executeColor = EXECUTE_BUTTON_COLOR[level];
  const RiskIcon = RISK_ICONS[level];
  const riskLabel = RISK_LABELS[level];

  const isDisabled = isLoading || isSubmitting;

  const handleSelect = (key: string) => {
    if (key === "other") {
      setOtherMode(true);
      return;
    }
    setLastClicked(key);
    setIsSubmitting(true);
    onResume({ decision: key, comment: comment.trim() || undefined });
  };

  const handleOtherSubmit = () => {
    const text = otherComment.trim();
    if (!text) return;
    setLastClicked("other");
    setIsSubmitting(true);
    onResume({ decision: "other", comment: text });
  };

  const handleOtherCancel = () => {
    setOtherMode(false);
    setOtherComment("");
  };

  const title = mode === "api" ? "API 测试已生成" : "Web 测试已生成";

  // LOW 风险：简化面板，只显示执行+跳过
  const visibleItems = level === "low"
    ? items.filter((item) => item.key === "execute" || item.key === "skip")
    : level === "medium"
    ? items.filter((item) => item.key !== "edit")
    : items;

  return (
    <div className="w-full rounded-lg border-2 border-blue-300 bg-blue-50/80 p-4 dark:border-blue-700 dark:bg-blue-950/30">
      {/* 风险等级徽章 */}
      <div className="mb-3 flex items-center justify-between">
        <span className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
          badge.bg, badge.text,
        )}>
          <RiskIcon size={12} />
          {riskLabel}
        </span>
        {risk_reason && (
          <span className="text-xs text-muted-foreground">
            {risk_reason}
          </span>
        )}
      </div>

      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
          <Play size={18} className="text-blue-700 dark:text-blue-200" />
        </div>
        <div className="flex-1">
          <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">
            {title}
          </h3>
          {description && (
            <p className="mt-1 text-sm text-gray-700 dark:text-gray-200">
              {description}
            </p>
          )}
          {(script_name ?? test_count !== undefined) && (
            <p className="mt-1 text-xs text-muted-foreground">
              {script_name}
              {script_name && test_count !== undefined ? " · " : ""}
              {test_count !== undefined ? `${test_count} 个用例` : ""}
            </p>
          )}
        </div>
      </div>

      {!otherMode ? (
        <>
          <div className={cn(
            "grid gap-2",
            visibleItems.length <= 2 ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4",
          )}>
            {visibleItems.map((item) => {
              const Icon = ICONS[item.key] || Play;
              const isPrimary = item.key === "execute";
              return (
                <Button
                  key={item.key}
                  onClick={() => handleSelect(item.key)}
                  variant={isPrimary ? "default" : "outline"}
                  disabled={isDisabled}
                  className={cn(
                    "h-auto items-center justify-center gap-2 p-3 text-center",
                    isPrimary && cn(executeColor, "text-white"),
                  )}
                >
                  {isSubmitting && lastClicked === item.key ? (
                    <span className="inline-flex items-center gap-1">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      提交中...
                    </span>
                  ) : (
                    <>
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="text-sm font-medium">{item.label}</span>
                    </>
                  )}
                </Button>
              );
            })}
          </div>

          <div className="mt-3">
            <label
              htmlFor="execution-comment"
              className="mb-1.5 block text-xs font-medium text-gray-700 dark:text-gray-300"
            >
              补充说明（可选）
            </label>
            <Textarea
              id="execution-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="例如：使用默认环境执行，或先检查脚本"
              disabled={isDisabled}
              rows={level === "low" ? 1 : 2}
              className="resize-none bg-card text-sm"
            />
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <label
            htmlFor="execution-other-comment"
            className="block text-xs font-medium text-gray-700 dark:text-gray-300"
          >
            请说明你的需求
          </label>
          <Textarea
            id="execution-other-comment"
            value={otherComment}
            onChange={(e) => setOtherComment(e.target.value)}
            placeholder="例如：先把脚本改成使用 headless=false 再执行"
            disabled={isDisabled}
            rows={3}
            className="resize-none bg-card text-sm"
          />
          <div className="flex gap-2">
            <Button
              onClick={handleOtherSubmit}
              disabled={isDisabled || !otherComment.trim()}
              className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700"
            >
              提交
            </Button>
            <Button
              variant="outline"
              onClick={handleOtherCancel}
              disabled={isDisabled}
            >
              取消
            </Button>
          </div>
        </div>
      )}

      {(isLoading || isSubmitting) && lastClicked && (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-300">
          <Loader2 className="h-3 w-3 animate-spin" />
          已选择，正在继续...
        </p>
      )}
    </div>
  );
}
