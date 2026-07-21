"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Play, XCircle, Edit3, MessageSquareMore } from "lucide-react";
import { cn } from "@/lib/utils";

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
export function ExecutionInvitationInterrupt({
  mode,
  script_name,
  test_count,
  description,
  alternatives,
  onResume,
  isLoading,
}: ExecutionInvitationInterruptProps) {
  const [lastClicked, setLastClicked] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [otherMode, setOtherMode] = useState(false);
  const [otherComment, setOtherComment] = useState("");

  const items = alternatives?.length ? alternatives : DEFAULT_ALTERNATIVES;

  const handleSelect = (key: string) => {
    if (key === "other") {
      setOtherMode(true);
      return;
    }
    setLastClicked(key);
    onResume({ decision: key, comment: comment.trim() || undefined });
  };

  const handleOtherSubmit = () => {
    const text = otherComment.trim();
    if (!text) return;
    setLastClicked("other");
    onResume({ decision: "other", comment: text });
  };

  const handleOtherCancel = () => {
    setOtherMode(false);
    setOtherComment("");
  };

  const title = mode === "api" ? "API 测试已生成" : "Web 测试已生成";

  return (
    <div className="w-full rounded-lg border-2 border-blue-300 bg-blue-50/80 p-4 dark:border-blue-700 dark:bg-blue-950/30">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
          <Play
            size={18}
            className="text-blue-700 dark:text-blue-200"
          />
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
            <p className="mt-1 text-xs text-blue-700 dark:text-blue-300">
              {script_name}
              {script_name && test_count !== undefined ? " · " : ""}
              {test_count !== undefined ? `${test_count} 个用例` : ""}
            </p>
          )}
        </div>
      </div>

      {!otherMode ? (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {items.map((item) => {
              const Icon = ICONS[item.key] || Play;
              const isPrimary = item.key === "execute";
              return (
                <Button
                  key={item.key}
                  onClick={() => handleSelect(item.key)}
                  variant={isPrimary ? "default" : "outline"}
                  disabled={isLoading}
                  className={cn(
                    "h-auto items-center justify-center gap-2 p-3 text-center",
                    isPrimary &&
                      "bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-sm font-medium">{item.label}</span>
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
              disabled={isLoading}
              rows={2}
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
            disabled={isLoading}
            rows={3}
            className="resize-none bg-card text-sm"
          />
          <div className="flex gap-2">
            <Button
              onClick={handleOtherSubmit}
              disabled={isLoading || !otherComment.trim()}
              className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700"
            >
              提交
            </Button>
            <Button
              variant="outline"
              onClick={handleOtherCancel}
              disabled={isLoading}
            >
              取消
            </Button>
          </div>
        </div>
      )}

      {isLoading && lastClicked && (
        <p className="mt-3 text-xs text-blue-600 dark:text-blue-300">
          已选择，正在继续...
        </p>
      )}
    </div>
  );
}
