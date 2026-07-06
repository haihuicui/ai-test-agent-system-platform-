"use client";
// NOTE  MC8zOmFIVnBZMlhsdEpUbXRiZm92b3ZTZVhBPT06NzFmNzQ0Yzk=

import { useMemo, useState } from "react";
import { Message } from "@langchain/langgraph-sdk";
import { ChevronDown, ChevronUp, History, CheckCircle2, XCircle, SkipForward, RotateCcw, Target } from "lucide-react";
import { cn } from "@/lib/utils";
// NOTE  MS8zOmFIVnBZMlhsdEpUbXRiZm92b3ZTZVhBPT06NzFmNzQ0Yzk=

interface ReviewRound {
  phase: string;
  round: number;
  decision: string;
  comment?: string;
  checklist?: Record<string, boolean>;
  timestamp?: string;
}
// FIXME  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b3ZTZVhBPT06NzFmNzQ0Yzk=

interface ReviewHistoryTimelineProps {
  messages: Message[];
}
// TODO  My8zOmFIVnBZMlhsdEpUbXRiZm92b3ZTZVhBPT06NzFmNzQ0Yzk=

const PHASE_DISPLAY_NAMES: Record<string, string> = {
  "requirement-analysis": "需求分析",
  "test-strategy": "测试策略",
  "test-case-generation": "测试用例生成",
  "quality-review": "质量评审",
};

function extractReviewRounds(messages: Message[]): ReviewRound[] {
  const rounds: ReviewRound[] = [];
  for (const msg of messages) {
    if (msg.type !== "human") continue;
    const ak = (msg.additional_kwargs as Record<string, any>) || {};
    const reviewRound = ak._review_round;
    if (reviewRound && typeof reviewRound === "object") {
      rounds.push({
        phase: String(reviewRound.phase || ""),
        round: Number(reviewRound.round || 1),
        decision: String(reviewRound.decision || ""),
        comment: reviewRound.comment ? String(reviewRound.comment) : undefined,
        checklist:
          reviewRound.checklist && typeof reviewRound.checklist === "object"
            ? reviewRound.checklist
            : undefined,
        timestamp: reviewRound.timestamp
          ? String(reviewRound.timestamp)
          : undefined,
      });
    }
  }
  return rounds;
}

function formatTimestamp(iso?: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function DecisionBadge({ decision }: { decision: string }) {
  const configs: Record<
    string,
    { label: string; icon: React.ComponentType<{ size?: number | string; className?: string }>; className: string }
  > = {
    approve: {
      label: "通过",
      icon: CheckCircle2,
      className: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    },
    request_changes: {
      label: "要求修改",
      icon: XCircle,
      className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    },
    regenerate: {
      label: "重新生成",
      icon: RotateCcw,
      className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    },
    skip: {
      label: "跳过",
      icon: SkipForward,
      className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    },
    narrow_scope: {
      label: "缩小范围",
      icon: Target,
      className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    },
  };

  const config = configs[decision] || {
    label: decision,
    icon: CheckCircle2,
    className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
  };
  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        config.className
      )}
    >
      <Icon size={12} />
      {config.label}
    </span>
  );
}

export function ReviewHistoryTimeline({ messages }: ReviewHistoryTimelineProps) {
  const [expanded, setExpanded] = useState(false);
  const rounds = useMemo(() => extractReviewRounds(messages), [messages]);

  // 按 phase 分组（必须位于所有 hooks 之后、任何提前 return 之前）
  const grouped = useMemo(() => {
    const map = new Map<string, ReviewRound[]>();
    for (const r of rounds) {
      const list = map.get(r.phase) || [];
      list.push(r);
      map.set(r.phase, list);
    }
    return map;
  }, [rounds]);

  if (rounds.length === 0) return null;

  return (
    <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between text-left"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <History size={16} className="text-muted-foreground" />
          评审历史
          <span className="text-xs text-muted-foreground">（共 {rounds.length} 轮）</span>
        </div>
        {expanded ? (
          <ChevronUp size={16} className="text-muted-foreground" />
        ) : (
          <ChevronDown size={16} className="text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="mt-3 space-y-4">
          {Array.from(grouped.entries()).map(([phase, phaseRounds]) => (
            <div key={phase}>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {PHASE_DISPLAY_NAMES[phase] || phase}
              </h4>
              <div className="space-y-2">
                {phaseRounds.map((r, idx) => (
                  <div
                    key={idx}
                    className="rounded-md border border-border bg-card p-3 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-foreground">
                        第 {r.round} 轮
                      </span>
                      <DecisionBadge decision={r.decision} />
                    </div>
                    {r.comment && (
                      <p className="mt-2 text-muted-foreground">{r.comment}</p>
                    )}
                    {r.checklist && Object.keys(r.checklist).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(r.checklist).map(([key, checked]) => (
                          <span
                            key={key}
                            className={cn(
                              "rounded px-1.5 py-0.5 text-xs",
                              checked
                                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                            )}
                          >
                            {key}: {checked ? "通过" : "未通过"}
                          </span>
                        ))}
                      </div>
                    )}
                    {r.timestamp && (
                      <p className="mt-2 text-xs text-muted-foreground">
                        {formatTimestamp(r.timestamp)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
// NOTE  My8zOmFIVnBZMlhsdEpUbXRiZm92b3ZTZVhBPT06NzFmNzQ0Yzk=
