"use client";
// NOTE  MC8zOmFIVnBZMlhsdEpUbXRiZm92b3FzUm1jZz09OjZhYjY1ZjQy

import { useState, useMemo, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  CheckCircle,
  MessageSquareWarning,
  AlertCircle,
  RotateCcw,
  SkipForward,
  Target,
  ChevronDown,
  ChevronRight,
  FileText,
} from "lucide-react";
import type { ActionRequest, ReviewConfig } from "@/lib/langgraph/types";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "@/components/langgraph/MarkdownContent";
// NOTE  MS8zOmFIVnBZMlhsdEpUbXRiZm92b3FzUm1jZz09OjZhYjY1ZjQy

interface PhaseReviewInterruptProps {
  actionRequest: ActionRequest;
  reviewConfig?: ReviewConfig;
  reviewRounds?: ReviewRound[];
  onResume: (value: any) => void;
  isLoading?: boolean;
}
// FIXME  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b3FzUm1jZz09OjZhYjY1ZjQy

interface ChecklistItem {
  key: string;
  label: string;
}
// TODO  My8zOmFIVnBZMlhsdEpUbXRiZm92b3FzUm1jZz09OjZhYjY1ZjQy

interface ReviewRound {
  phase: string;
  round: number;
  decision: string;
  comment?: string;
  timestamp?: string;
}
// NOTE  My8zOmFIVnBZMlhsdEpUbXRiZm92b3FzUm1jZz09OjZhYjY1ZjQy

export function PhaseReviewInterrupt({
  actionRequest,
  reviewRounds,
  onResume,
  isLoading,
}: PhaseReviewInterruptProps) {
  const [comment, setComment] = useState("");
  const [lastClicked, setLastClicked] = useState<
    "approve" | "request_changes" | "regenerate" | "skip" | "narrow_scope" | null
  >(null);

  const checklistItems = useMemo<ChecklistItem[]>(() => {
    const raw = actionRequest.args?.checklist;
    if (Array.isArray(raw)) {
      return raw.map((item: any) => ({
        key: String(item.key ?? item.value ?? ""),
        label: String(item.label ?? item.name ?? ""),
      }));
    }
    return [];
  }, [actionRequest.args?.checklist]);

  const defaultChecklist = useMemo(() => {
    const map: Record<string, boolean> = {};
    checklistItems.forEach((item) => {
      map[item.key] = true;
    });
    return map;
  }, [checklistItems]);

  const [checklist, setChecklist] = useState<Record<string, boolean>>(defaultChecklist);

  // 当 actionRequest 变化（切换到不同阶段的评审）时，同步更新 checklist 状态。
  // useState 只在 mount 时使用默认值，之后 defaultChecklist 变化不会自动同步，
  // 会导致切换阶段后 checklist 仍保持上一阶段的勾选状态。
  useEffect(() => {
    setChecklist(defaultChecklist);
  }, [defaultChecklist]);

  const phaseName = (actionRequest.args?.phase_name as string) || "阶段报告";
  const description =
    actionRequest.description || `已完成 ${phaseName}，请审阅并决定下一步。`;

  // 后端传入的报告预览（头 8000 + 尾 2000 字符截断）。此前版本从未渲染它，
  // 用户只能上翻对话找报告原文——现在直接在卡片内展示。
  const reportPreview = (actionRequest.args?.preview as string) || "";
  const [showReport, setShowReport] = useState(true);

  // 低分返工确认模式：后端在评分低于红线时传入 rework 标记，
  // 卡片切换为 [开始返工] / [跳过返工（风险自负）] 两个决策按钮。
  const rework = actionRequest.args?.rework as
    | { score: number; threshold: number; round: number; max_rounds: number }
    | undefined;

  const uncheckedItems = useMemo(
    () => checklistItems.filter((item) => !checklist[item.key]),
    [checklistItems, checklist]
  );

  const currentRound = useMemo(() => {
    if (!reviewRounds || reviewRounds.length === 0) return 1;
    return Math.max(...reviewRounds.map((r) => r.round), 0) + 1;
  }, [reviewRounds]);

  const previousRound = useMemo(() => {
    if (!reviewRounds || reviewRounds.length === 0) return null;
    return reviewRounds[reviewRounds.length - 1];
  }, [reviewRounds]);

  const sendDecision = (decision: string) => {
    onResume({
      decision,
      message: comment.trim(),
      checklist,
    });
    setLastClicked(decision as any);
  };

  const handleApprove = () => sendDecision("approve");
  const handleRequestChanges = () => sendDecision("request_changes");
  const handleRegenerate = () => sendDecision("regenerate");
  const handleSkip = () => sendDecision("skip");
  const handleNarrowScope = () => sendDecision("narrow_scope");

  const toggleChecklist = (key: string) => {
    setChecklist((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div
      className={cn(
        "w-full rounded-lg border-2 p-4",
        rework
          ? "border-red-300 bg-red-50/80 dark:border-red-800 dark:bg-red-950/30"
          : "border-orange-300 bg-orange-50/80 dark:border-orange-700 dark:bg-orange-950/30"
      )}
    >
      {/* 头部 */}
      <div className="mb-4 flex items-start gap-3">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
            rework
              ? "bg-red-100 dark:bg-red-900"
              : "bg-orange-100 dark:bg-orange-900"
          )}
        >
          <AlertCircle
            size={18}
            className={cn(
              rework
                ? "text-red-700 dark:text-red-200"
                : "text-orange-700 dark:text-orange-200"
            )}
          />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">
              {rework
                ? `质量评审未达标：${rework.score} 分（红线 ${rework.threshold} 分）`
                : `需要人工评审：${phaseName}`}
            </h3>
            <span
              className={cn(
                "rounded-md px-2 py-0.5 text-xs font-medium",
                rework
                  ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                  : "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
              )}
            >
              第 {currentRound} 轮
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-700 dark:text-gray-200">
            {description}
          </p>
          {!reportPreview && (
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              报告内容已在上方对话中展示，可直接在此给出评审意见。
            </p>
          )}

          {previousRound?.comment && (
            <div className="mt-2 rounded-md border border-orange-200 bg-orange-100/50 p-2 dark:border-orange-800 dark:bg-orange-900/30">
              <p className="text-xs font-medium text-orange-800 dark:text-orange-200">
                上一轮（第 {previousRound.round} 轮）意见：
              </p>
              <p className="mt-0.5 text-xs text-orange-700 dark:text-orange-300">
                {previousRound.comment}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 报告内容展示区（可折叠，默认展开） */}
      {reportPreview && (
        <div className="mb-4 rounded-md border border-orange-200 bg-white/60 dark:border-orange-800 dark:bg-black/20">
          <button
            type="button"
            onClick={() => setShowReport((v) => !v)}
            className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-gray-100"
          >
            {showReport ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <FileText size={14} />
            报告内容{showReport ? "（点击收起）" : "（点击展开）"}
          </button>
          {showReport && (
            <div className="max-h-[480px] overflow-y-auto border-t border-orange-200 px-3 py-2 dark:border-orange-800">
              <MarkdownContent content={reportPreview} streaming={false} />
            </div>
          )}
        </div>
      )}

      {/* 评审维度清单（返工确认模式下隐藏——决策只有两个：返工或跳过） */}
      {checklistItems.length > 0 && !rework && (
        <div className="mb-4 rounded-md border border-orange-200 bg-white/60 p-3 dark:border-orange-800 dark:bg-black/20">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300">
            评审维度（取消未通过的项）
          </h4>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {checklistItems.map((item) => (
              <label
                key={item.key}
                className="flex cursor-pointer items-center gap-2 text-sm text-gray-800 dark:text-gray-200"
              >
                <Checkbox
                  checked={checklist[item.key] ?? true}
                  onCheckedChange={() => toggleChecklist(item.key)}
                  disabled={isLoading}
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* 快捷操作（返工确认模式下隐藏） */}
      {!rework && (
      <div className="mb-4">
        <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300"
        >
          快捷操作
        </h4>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={handleRegenerate}
            variant="outline"
            size="sm"
            disabled={isLoading}
            className="gap-1.5"
          >
            <RotateCcw size={14} />
            <span>重新生成</span>
          </Button>
          <Button
            onClick={handleNarrowScope}
            variant="outline"
            size="sm"
            disabled={isLoading}
            className="gap-1.5"
          >
            <Target size={14} />
            <span>缩小范围</span>
          </Button>
          <Button
            onClick={handleSkip}
            variant="outline"
            size="sm"
            disabled={isLoading}
            className="gap-1.5"
          >
            <SkipForward size={14} />
            <span>跳过本阶段</span>
          </Button>
        </div>
      </div>
      )}

      {/* 评审意见输入 */}
      <div className="mb-4">
        <label className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300"
        >
          <MessageSquareWarning size={14} />
          {rework ? "返工补充意见（可选）" : "评审意见（可选）"}
        </label>
        <Textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder={
            rework
              ? "如：重点修复状态机矛盾和订单号耦合问题，其余次要问题可不处理..."
              : "如：整体方向 OK，但请补充边界值场景和安全测试用例..."
          }
          className="min-h-[80px] bg-card text-sm"
          disabled={isLoading}
        />
      </div>

      {/* 主操作按钮 */}
      <div className="flex flex-wrap gap-2">
        {rework ? (
          <>
            <Button
              onClick={handleRequestChanges}
              size="sm"
              disabled={isLoading}
              className="gap-1.5 bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700"
            >
              <RotateCcw size={14} />
              <span className="font-semibold">
                {isLoading && lastClicked === "request_changes"
                  ? "提交中..."
                  : "开始返工"}
              </span>
            </Button>
            <Button
              onClick={handleSkip}
              variant="outline"
              size="sm"
              disabled={isLoading}
              className={cn(
                "gap-1.5 border-red-500 text-red-600 hover:bg-red-50 hover:text-red-700",
                "dark:hover:bg-red-950"
              )}
            >
              <SkipForward size={14} />
              <span className="font-semibold">
                {isLoading && lastClicked === "skip"
                  ? "提交中..."
                  : "跳过返工（风险自负）"}
              </span>
            </Button>
          </>
        ) : (
          <>
            <Button
              onClick={handleRequestChanges}
              variant="outline"
              size="sm"
              disabled={isLoading}
              className={cn(
                "border-red-500 text-red-600 hover:bg-red-50 hover:text-red-700",
                "dark:hover:bg-red-950"
              )}
            >
              <MessageSquareWarning size={14} />
              <span className="font-semibold">
                {isLoading && lastClicked === "request_changes"
                  ? "提交中..."
                  : "要求修改"}
              </span>
            </Button>

            <Button
              onClick={handleApprove}
              size="sm"
              disabled={isLoading}
              className="bg-green-600 text-white hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-700"
            >
              <CheckCircle size={14} />
              <span className="font-semibold">
                {isLoading && lastClicked === "approve" ? "提交中..." : "通过"}
              </span>
            </Button>
          </>
        )}
      </div>

      {uncheckedItems.length > 0 && !rework && (
        <p className="mt-3 text-xs text-orange-700 dark:text-orange-300">
          已取消 {uncheckedItems.map((i) => i.label).join("、")}，点击"通过"时会自动要求补充。
        </p>
      )}
    </div>
  );
}
// TODO  My8zOmFIVnBZMlhsdEpUbXRiZm92b3FzUm1jZz09OjZhYjY1ZjQy
