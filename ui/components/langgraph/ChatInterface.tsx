"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm5obVRnPT06Njg2NGJhMDY=

import React, {
  useState,
  useRef,
  useCallback,
  useMemo,
  useEffect,
  useLayoutEffect,
  FormEvent,
  Fragment,
} from "react";
import { Button } from "@/components/ui/button";
import {
  Square,
  ArrowUp,
  CheckCircle,
  Clock,
  Circle,
  FileIcon,
  Loader2,
  Plus,
  Download,
} from "lucide-react";
import { ChatMessage } from "@/components/langgraph/ChatMessage";
import { OutputFormatInterrupt } from "@/components/langgraph/OutputFormatInterrupt";
import { PhaseReviewInterrupt } from "@/components/langgraph/PhaseReviewInterrupt";
import { ReviewHistoryTimeline } from "@/components/langgraph/ReviewHistoryTimeline";
import type {
  TodoItem,
  ToolCall,
  ActionRequest,
  ReviewConfig,
} from "@/lib/langgraph/types";
import { Assistant, Message } from "@langchain/langgraph-sdk";
import { extractStringFromMessageContent } from "@/lib/langgraph/utils";
import { useChatContext } from "@/providers/ChatProvider";
import { cn } from "@/lib/utils";
import { useStickToBottom } from "use-stick-to-bottom";
import { FilesPopover } from "@/components/langgraph/TasksFilesSidebar";
import { useFileUpload } from "@/hooks/useFileUpload";
import { ContentBlocksPreview } from "@/components/langgraph/ContentBlocksPreview";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useLanguage } from "@/providers/LanguageProvider";
import { extractCreatedTestCaseIds } from "@/lib/langgraph/utils";
import {
  downloadTestCasesExcel,
} from "@/lib/api/testCases";

interface ChatInterfaceProps {
  assistant: Assistant | null;
  initialPrompt?: string;
  /** 当 save_test_* 工具调用完成时触发，用于刷新成果物面板 */
  onArtifactSaved?: () => void;
}
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm5obVRnPT06Njg2NGJhMDY=

const getStatusIcon = (status: TodoItem["status"], className?: string) => {
  switch (status) {
    case "completed":
      return (
        <CheckCircle
          size={16}
          className={cn("text-success/80", className)}
        />
      );
    case "in_progress":
      return (
        <Clock
          size={16}
          className={cn("text-warning/80", className)}
        />
      );
    default:
      return (
        <Circle
          size={16}
          className={cn("text-tertiary/70", className)}
        />
      );
  }
};
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm5obVRnPT06Njg2NGJhMDY=

export const ChatInterface = React.memo<ChatInterfaceProps>(({ assistant, initialPrompt, onArtifactSaved }) => {
  const { t } = useLanguage();
  const [metaOpen, setMetaOpen] = useState<"tasks" | "files" | null>(null);
  const tasksContainerRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const [input, setInput] = useState("");
  const [enableRag, setEnableRag] = useState(true);
  const [autoApproveEnabled, setAutoApproveEnabled] = useState(() => {
    if (typeof window === "undefined") return false;
    const raw = window.localStorage.getItem("chat_auto_approve_enabled");
    return raw === "true";
  });
  const [autoApproveThreshold, setAutoApproveThreshold] = useState(() => {
    if (typeof window === "undefined") return 80;
    const raw = window.localStorage.getItem("chat_auto_approve_threshold");
    const num = raw ? parseInt(raw, 10) : 80;
    return Number.isNaN(num) ? 80 : Math.max(0, Math.min(100, num));
  });
  const [exportingExcel, setExportingExcel] = useState(false);
  const {
    contentBlocks,
    handleFileUpload,
    handlePaste,
    dropRef,
    removeBlock,
    resetBlocks,
    dragOver,
  } = useFileUpload();
  const { scrollRef, contentRef } = useStickToBottom();
  const initialPromptSentRef = useRef(false);
  const sendMessageRef = useRef<((content: string) => void) | null>(null);
  const isMountedRef = useRef(true);
  const lastScrollTopRef = useRef(0);
  const scrollTopBeforeLoadRef = useRef(0);

  const {
    stream,
    messages,
    todos,
    files,
    ui,
    setFiles,
    isLoading,
    isThreadLoading,
    interrupt,
    isResumingInterrupt,
    sendMessage,
    stopStream,
    resumeInterrupt,
    loadMoreHistory,
    isLoadingMoreHistory,
    isReachingEnd,
    historyPages,
  } = useChatContext();

  // 保持 sendMessage 的最新引用，并自动带上当前 RAG / 自动审批设置
  React.useEffect(() => {
    sendMessageRef.current = (content: string) => {
      sendMessage(content, [], {
        enable_rag: enableRag,
        auto_approve_threshold: autoApproveEnabled ? autoApproveThreshold : 100,
      });
    };
  }, [sendMessage, enableRag, autoApproveEnabled, autoApproveThreshold]);

  // 组件挂载/卸载标记
  React.useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // 持久化自动审批阈值设置
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      "chat_auto_approve_enabled",
      String(autoApproveEnabled)
    );
  }, [autoApproveEnabled]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("chat_auto_approve_threshold", String(autoApproveThreshold));
  }, [autoApproveThreshold]);

  const submitDisabled = isLoading || !assistant;

  const handleSubmit = useCallback(
    (e?: FormEvent) => {
      if (e) {
        e.preventDefault();
      }
      const messageText = input.trim();
      if (
        (!messageText && contentBlocks.length === 0) ||
        isLoading ||
        submitDisabled
      )
        return;
      sendMessage(messageText, contentBlocks, {
        enable_rag: enableRag,
        auto_approve_threshold: autoApproveEnabled ? autoApproveThreshold : 100,
      });
      setInput("");
      resetBlocks();
    },
    [
      input,
      contentBlocks,
      isLoading,
      sendMessage,
      setInput,
      submitDisabled,
      enableRag,
      autoApproveEnabled,
      autoApproveThreshold,
      resetBlocks,
    ]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (submitDisabled) return;
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, submitDisabled]
  );

  // 当 initialPrompt 改变时重置标记
  React.useEffect(() => {
    initialPromptSentRef.current = false;
  }, [initialPrompt]);

  // 自动发送初始提示词
  React.useEffect(() => {
    if (
      initialPrompt &&
      !isLoading &&
      !isThreadLoading &&
      assistant &&
      messages.length === 0 &&
      !initialPromptSentRef.current
    ) {
      // 使用 setTimeout 确保组件完全初始化
      const timer = setTimeout(() => {
        // 检查组件是否仍然挂载，且 sendMessage 已准备好
        if (isMountedRef.current && sendMessageRef.current) {
          // 真正发送前才标记为已发送，避免上一条 effect 被清理后
          // ref 被提前置为 true，导致重渲染后不再发送。
          initialPromptSentRef.current = true;
          sendMessageRef.current(initialPrompt);
        }
      }, 100);

      return () => {
        clearTimeout(timer);
      };
    }
  }, [initialPrompt, isLoading, isThreadLoading, assistant, messages.length]);

  // 向上滚动到顶部附近时加载更多历史消息
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const onScroll = () => {
      const currentScrollTop = container.scrollTop;
      const isScrollingUp = currentScrollTop < lastScrollTopRef.current;
      lastScrollTopRef.current = currentScrollTop;

      if (!isScrollingUp) return;
      if (isThreadLoading || isLoadingMoreHistory || isReachingEnd) return;
      // 只在接近顶部时触发，给用户留出一段可滚动查看已加载历史的空间
      if (currentScrollTop > 100) return;

      scrollTopBeforeLoadRef.current = currentScrollTop;
      loadMoreHistory();
    };

    container.addEventListener("scroll", onScroll);
    return () => container.removeEventListener("scroll", onScroll);
  }, [
    scrollRef,
    isThreadLoading,
    isLoadingMoreHistory,
    isReachingEnd,
    loadMoreHistory,
  ]);

  // 鼠标滚轮在顶部继续往上滚时也能连续加载，不需要先往下滚再往上滚
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const onWheel = (e: WheelEvent) => {
      if (isThreadLoading || isLoadingMoreHistory || isReachingEnd) return;
      // deltaY < 0 表示向上滚动
      if (e.deltaY >= 0) return;
      // 只在到达或贴近顶部时触发
      if (container.scrollTop > 10) return;

      scrollTopBeforeLoadRef.current = container.scrollTop;
      loadMoreHistory();
    };

    container.addEventListener("wheel", onWheel);
    return () => container.removeEventListener("wheel", onWheel);
  }, [
    scrollRef,
    isThreadLoading,
    isLoadingMoreHistory,
    isReachingEnd,
    loadMoreHistory,
  ]);

  // 历史加载完成后，把滚动位置保持在顶部，让刚加载出来的历史消息直接可见
  useLayoutEffect(() => {
    if (isLoadingMoreHistory) return;
    if (scrollTopBeforeLoadRef.current === -1) return;

    const container = scrollRef.current;
    if (!container) {
      scrollTopBeforeLoadRef.current = -1;
      return;
    }

    // 只有原本就在顶部附近才强制回到顶部，避免影响用户在中部/底部的阅读位置
    if (scrollTopBeforeLoadRef.current <= 100) {
      // 先同步更新参考值，避免设置 scrollTop 触发的 scroll 事件被误判为向上滚动
      lastScrollTopRef.current = 0;
      container.scrollTop = 0;
    }
    scrollTopBeforeLoadRef.current = -1;
  }, [isLoadingMoreHistory, messages.length, scrollRef]);

  // 缓存 message UI 映射，避免每次渲染都 O(n*m) filter
  const messageUiMap = useMemo(() => {
    const nextMap = new Map<string, any[]>();

    if (!ui) {
      return nextMap;
    }

    ui.forEach((item: any) => {
      const messageId = item.metadata?.message_id;
      if (!messageId) {
        return;
      }

      const existing = nextMap.get(messageId);
      if (existing) {
        existing.push(item);
      } else {
        nextMap.set(messageId, [item]);
      }
    });

    return nextMap;
  }, [ui]);

  const processedMessages = useMemo(() => {
    const messageMap = new Map<
      string,
      { message: Message; toolCalls: ToolCall[] }
    >();
    // toolCallId -> 拥有该 tool call 的消息 key，用于 O(1) 配对 tool 结果，
    // 避免对每条 tool 消息都线性扫描整个 messageMap（原先是 O(N²)）。
    const toolCallOwner = new Map<string, string>();

    messages.forEach((message: Message) => {
      if (message.type === "ai") {
        const toolCallsInMessage: Array<{
          id?: string;
          function?: { name?: string; arguments?: unknown };
          name?: string;
          type?: string;
          args?: unknown;
          input?: unknown;
        }> = [];

        if (
          message.additional_kwargs?.tool_calls &&
          Array.isArray(message.additional_kwargs.tool_calls)
        ) {
          toolCallsInMessage.push(...message.additional_kwargs.tool_calls);
        } else if (message.tool_calls && Array.isArray(message.tool_calls)) {
          toolCallsInMessage.push(
            ...message.tool_calls.filter(
              (toolCall: { name?: string }) => toolCall.name !== ""
            )
          );
        } else if (Array.isArray(message.content)) {
          const toolUseBlocks = message.content.filter(
            (block: { type?: string }) => block.type === "tool_use"
          );
          toolCallsInMessage.push(...toolUseBlocks);
        }

        const toolCallsWithStatus = toolCallsInMessage.map(
          (
            toolCall: {
              id?: string;
              function?: { name?: string; arguments?: unknown };
              name?: string;
              type?: string;
              args?: unknown;
              input?: unknown;
            },
            toolCallIndex: number
          ) => {
            const name =
              toolCall.function?.name ||
              toolCall.name ||
              toolCall.type ||
              "unknown";
            const args =
              toolCall.function?.arguments ||
              toolCall.args ||
              toolCall.input ||
              {};
            return {
              id: toolCall.id || `tool-${message.id}-${toolCallIndex}`,
              name,
              args,
              status: interrupt ? "interrupted" : ("pending" as const),
            } as ToolCall;
          }
        );

        messageMap.set(message.id!, {
          message,
          toolCalls: toolCallsWithStatus,
        });
        // 记录每个 tool call 归属的消息，供 tool 结果 O(1) 配对
        for (const tc of toolCallsWithStatus) {
          toolCallOwner.set(tc.id, message.id!);
        }
      } else if (message.type === "tool") {
        const toolCallId = message.tool_call_id;
        if (!toolCallId) {
          return;
        }

        const ownerKey = toolCallOwner.get(toolCallId);
        if (!ownerKey) {
          return;
        }
        const data = messageMap.get(ownerKey);
        if (!data) {
          return;
        }
        const toolCallIndex = data.toolCalls.findIndex(
          (tc: ToolCall) => tc.id === toolCallId
        );
        if (toolCallIndex === -1) {
          return;
        }
        data.toolCalls[toolCallIndex] = {
          ...data.toolCalls[toolCallIndex],
          status: "completed" as const,
          result: extractStringFromMessageContent(message),
        };
      } else if (message.type === "human") {
        messageMap.set(message.id!, {
          message,
          toolCalls: [],
        });
      }
    });

    const processedArray = Array.from(messageMap.values());
    return processedArray.map((data, index) => {
      const prevMessage = index > 0 ? processedArray[index - 1].message : null;
      return {
        ...data,
        showAvatar: data.message.type !== prevMessage?.type,
      };
    });
  }, [messages, interrupt]);

  const generatedTestCaseIds = useMemo(() => {
    const allToolCalls = processedMessages.flatMap((m) => m.toolCalls);
    return extractCreatedTestCaseIds(allToolCalls);
  }, [processedMessages]);

  // =========================================================================
  // 检测 save_test_* 工具调用完成，自动触发成果物面板刷新
  // =========================================================================
  const lastArtifactSaveCountRef = useRef(0);
  const artifactSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const SAVE_ARTIFACT_TOOLS = ["save_test_plan", "save_test_cases", "save_test_script"];

  useEffect(() => {
    // 统计已完成 (status === "completed") 的 save_test_* 工具调用数
    const allToolCalls = processedMessages.flatMap((m) => m.toolCalls);
    const completedSaveCount = allToolCalls.filter(
      (tc) =>
        SAVE_ARTIFACT_TOOLS.includes(tc.name) &&
        tc.status === "completed"
    ).length;

    // 首次检测不触发（初始历史加载），仅在增量变化时触发
    if (lastArtifactSaveCountRef.current === 0) {
      lastArtifactSaveCountRef.current = completedSaveCount;
      return;
    }

    if (completedSaveCount > lastArtifactSaveCountRef.current) {
      lastArtifactSaveCountRef.current = completedSaveCount;

      // 防抖：短时间内多次 save 调用只触发一次刷新
      if (artifactSaveTimerRef.current) {
        clearTimeout(artifactSaveTimerRef.current);
      }
      artifactSaveTimerRef.current = setTimeout(() => {
        onArtifactSaved?.();
      }, 300);
    }

    // 新对话开始时重置计数
    if (completedSaveCount === 0 && lastArtifactSaveCountRef.current > 0) {
      lastArtifactSaveCountRef.current = 0;
    }
  }, [processedMessages, onArtifactSaved]);

  // 清理防抖定时器
  useEffect(() => {
    return () => {
      if (artifactSaveTimerRef.current) {
        clearTimeout(artifactSaveTimerRef.current);
      }
    };
  }, []);

  const handleDownloadExcel = useCallback(async () => {
    const projectId = assistant?.config?.configurable
      ?.project_identifier as string | undefined;
    if (!projectId) {
      toast.error(t("testCases.exportExcelMissingProject"));
      return;
    }

    if (generatedTestCaseIds.length === 0) {
      toast.error(t("testCases.exportExcelNoScope"));
      return;
    }

    try {
      setExportingExcel(true);
      await downloadTestCasesExcel(
        projectId,
        { test_case_ids: generatedTestCaseIds },
        {
          onCompleted: () => {
            toast.success(t("testCases.exportExcelSuccess"));
          },
          onFailed: (message) => {
            toast.error(message || t("testCases.exportExcelFailed"));
          },
        }
      );
    } catch (error) {
      console.error("Export excel failed:", error);
      toast.error(t("testCases.exportExcelFailed"));
    } finally {
      setExportingExcel(false);
    }
  }, [
    assistant?.config?.configurable?.project_identifier,
    generatedTestCaseIds,
    t,
  ]);

  const groupedTodos = {
    in_progress: todos.filter((t) => t.status === "in_progress"),
    pending: todos.filter((t) => t.status === "pending"),
    completed: todos.filter((t) => t.status === "completed"),
  };

  const hasTasks = todos.length > 0;
  const hasFiles = Object.keys(files).length > 0;

  // Parse out any action requests or review configs from the interrupt
  const actionRequestsMap: Map<string, ActionRequest> | null = useMemo(() => {
    const actionRequests =
      interrupt?.value && (interrupt.value as any)["action_requests"];
    if (!actionRequests) return new Map<string, ActionRequest>();
    return new Map(actionRequests.map((ar: ActionRequest) => [ar.name, ar]));
  }, [interrupt]);

  const reviewConfigsMap: Map<string, ReviewConfig> | null = useMemo(() => {
    const reviewConfigs =
      interrupt?.value && (interrupt.value as any)["review_configs"];
    if (!reviewConfigs) return new Map<string, ReviewConfig>();
    return new Map(
      reviewConfigs.map((rc: ReviewConfig) => [rc.actionName, rc])
    );
  }, [interrupt]);

  // 阶段评审中断：存在 interrupt 但当前中断不是针对最后一条消息里工具调用的
  const isPhaseReviewInterrupt = useMemo(() => {
    if (!interrupt || !actionRequestsMap || actionRequestsMap.size === 0) {
      return false;
    }
    const lastMessage = processedMessages[processedMessages.length - 1];
    if (!lastMessage) return true;
    return !lastMessage.toolCalls.some((tc) => actionRequestsMap.has(tc.name));
  }, [interrupt, actionRequestsMap, processedMessages]);

  // 输出格式选择中断
  const isFormatSelectionInterrupt = useMemo(() => {
    return (interrupt?.value as any)?.type === "format_selection";
  }, [interrupt]);

  // 从历史消息中提取评审轮次元数据
  const reviewRounds = useMemo(() => {
    const rounds: any[] = [];
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
          timestamp: reviewRound.timestamp ? String(reviewRound.timestamp) : undefined,
        });
      }
    }
    return rounds;
  }, [messages]);

  // 当前阶段评审历史（传给 PhaseReviewInterrupt 显示上一轮意见）
  const currentPhaseReviewRounds = useMemo(() => {
    if (!isPhaseReviewInterrupt || !actionRequestsMap) return [];
    const actionRequest = Array.from(actionRequestsMap.values())[0];
    const phase = actionRequest?.args?.phase as string;
    if (!phase) return [];
    return reviewRounds.filter((r) => r.phase === phase);
  }, [isPhaseReviewInterrupt, actionRequestsMap, reviewRounds]);

  // 滚动完全交由 useStickToBottom 处理（初次加载/发送/流式输出会自动滚到底部，
  // 用户主动上滑查看历史时停止跟随）。
  // 原先这里有一段手动 scrollTo({behavior: isLoading?"auto":"smooth"}) 的 effect：
  // 生成结束(isLoading=false)后它用 "smooth" 触发原生平滑滚动动画，该动画会和
  // 用户的鼠标滚轮抢夺滚动权；当上层因连接重试等原因频繁重渲染时，effect 被反复
  // 触发，平滑动画持续重启，表现为"完全滚不动"。故移除，交给库统一管理。

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div
        className="flex-1 overflow-y-auto overflow-x-hidden overscroll-contain"
        ref={scrollRef}
      >
        <div
          className="mx-auto w-full max-w-[1024px] px-6 pb-6 pt-4"
          ref={contentRef}
        >
          {isThreadLoading ? (
            <div className="flex items-center justify-center p-8">
              <p className="text-muted-foreground">加载中...</p>
            </div>
          ) : (
            <>
              {isLoadingMoreHistory && (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-sm text-muted-foreground">
                    加载历史消息...
                  </span>
                </div>
              )}
              {((historyPages?.length ?? 0) > 0) && !isReachingEnd && !isLoadingMoreHistory && (
                <div className="flex items-center justify-center py-2">
                  <span className="text-xs text-muted-foreground">
                    向上滚动加载更多历史消息
                  </span>
                </div>
              )}
              {isReachingEnd && messages.length > 0 && (
                <div className="flex items-center justify-center py-4">
                  <span className="text-xs text-muted-foreground">
                    没有更多消息了
                  </span>
                </div>
              )}
              {processedMessages.map((data, index) => {
                const messageUi = messageUiMap.get(data.message.id ?? "");
                const isLastMessage = index === processedMessages.length - 1;
                return (
                  <ChatMessage
                    key={data.message.id}
                    message={data.message}
                    toolCalls={data.toolCalls}
                    isLoading={isLoading}
                    isStreaming={isLastMessage && isLoading}
                    isResumingInterrupt={isResumingInterrupt}
                    actionRequestsMap={
                      isLastMessage ? actionRequestsMap : undefined
                    }
                    reviewConfigsMap={
                      isLastMessage ? reviewConfigsMap : undefined
                    }
                    ui={messageUi}
                    stream={isLastMessage ? stream : undefined}
                    onResumeInterrupt={
                      isLastMessage ? resumeInterrupt : undefined
                    }
                    graphId={isLastMessage ? assistant?.graph_id : undefined}
                  />
                );
              })}
              {isFormatSelectionInterrupt && interrupt && (
                <div className="mt-4">
                  <OutputFormatInterrupt
                    formats={(interrupt.value as any).formats || []}
                    description={(interrupt.value as any).description}
                    onResume={resumeInterrupt}
                    isLoading={isResumingInterrupt}
                  />
                </div>
              )}
              {isPhaseReviewInterrupt && interrupt && (
                <div className="mt-4">
                  <PhaseReviewInterrupt
                    actionRequest={Array.from(actionRequestsMap!.values())[0]}
                    reviewConfig={Array.from(reviewConfigsMap!.values())[0]}
                    reviewRounds={currentPhaseReviewRounds}
                    onResume={resumeInterrupt}
                    isLoading={isResumingInterrupt}
                  />
                </div>
              )}
              <ReviewHistoryTimeline messages={messages} />
            </>
          )}
        </div>
      </div>

      <div className="flex-shrink-0 bg-background">
        <div
          ref={dropRef}
          className={cn(
            "mx-4 mb-6 flex flex-shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-background",
            "mx-auto w-[calc(100%-32px)] max-w-[1024px] transition-colors duration-200 ease-in-out",
            dragOver && "border-primary border-2 border-dashed"
          )}
        >
          {(hasTasks || hasFiles) && (
            <div className="flex max-h-72 flex-col overflow-y-auto border-b border-border bg-muted empty:hidden">
              {!metaOpen && (
                <>
                  {(() => {
                    const activeTask = todos.find(
                      (t) => t.status === "in_progress"
                    );

                    const totalTasks = todos.length;
                    const remainingTasks =
                      totalTasks - groupedTodos.pending.length;
                    const isCompleted = totalTasks === remainingTasks;

                    const tasksTrigger = (() => {
                      if (!hasTasks) return null;
                      return (
                        <button
                          type="button"
                          onClick={() =>
                            setMetaOpen((prev) =>
                              prev === "tasks" ? null : "tasks"
                            )
                          }
                          className="grid w-full cursor-pointer grid-cols-[auto_auto_1fr] items-center gap-3 px-[18px] py-3 text-left"
                          aria-expanded={metaOpen === "tasks"}
                        >
                          {(() => {
                            if (isCompleted) {
                              return [
                                <CheckCircle
                                  key="icon"
                                  size={16}
                                  className="text-success/80"
                                />,
                                <span
                                  key="label"
                                  className="ml-[1px] min-w-0 truncate text-sm"
                                >
                                  所有任务已完成
                                </span>,
                              ];
                            }

                            if (activeTask != null) {
                              return [
                                <div key="icon">
                                  {getStatusIcon(activeTask.status)}
                                </div>,
                                <span
                                  key="label"
                                  className="ml-[1px] min-w-0 truncate text-sm"
                                >
                                  任务{" "}
                                  {totalTasks - groupedTodos.pending.length} / {" "}
                                  {totalTasks}
                                </span>,
                                <span
                                  key="content"
                                  className="min-w-0 gap-2 truncate text-sm text-muted-foreground"
                                >
                                  {activeTask.content}
                                </span>,
                              ];
                            }

                            return [
                              <Circle
                                key="icon"
                                size={16}
                                className="text-tertiary/70"
                              />,
                              <span
                                key="label"
                                className="ml-[1px] min-w-0 truncate text-sm"
                              >
                                任务 {totalTasks - groupedTodos.pending.length}{" "}
                                / {totalTasks}
                              </span>,
                            ];
                          })()}
                        </button>
                      );
                    })();

                    const filesTrigger = (() => {
                      if (!hasFiles) return null;
                      return (
                        <button
                          type="button"
                          onClick={() =>
                            setMetaOpen((prev) =>
                              prev === "files" ? null : "files"
                            )
                          }
                          className="flex flex-shrink-0 cursor-pointer items-center gap-2 px-[18px] py-3 text-left text-sm"
                          aria-expanded={metaOpen === "files"}
                        >
                          <FileIcon size={16} />
                          文件 (状态)
                          <span className="h-4 min-w-4 rounded-full bg-[#2F6868] px-0.5 text-center text-[10px] leading-[16px] text-white">
                            {Object.keys(files).length}
                          </span>
                        </button>
                      );
                    })();

                    return (
                      <div className="grid grid-cols-[1fr_auto_auto] items-center">
                        {tasksTrigger}
                        {filesTrigger}
                      </div>
                    );
                  })()}
                </>
              )}

              {metaOpen && (
                <>
                  <div className="sticky top-0 flex items-stretch bg-muted text-sm">
                    {hasTasks && (
                      <button
                        type="button"
                        className="py-3 pr-4 first:pl-[18px] aria-expanded:font-semibold"
                        onClick={() =>
                          setMetaOpen((prev) =>
                            prev === "tasks" ? null : "tasks"
                          )
                        }
                        aria-expanded={metaOpen === "tasks"}
                      >
                        任务
                      </button>
                    )}
                    {hasFiles && (
                      <button
                        type="button"
                        className="inline-flex items-center gap-2 py-3 pr-4 first:pl-[18px] aria-expanded:font-semibold"
                        onClick={() =>
                          setMetaOpen((prev) =>
                            prev === "files" ? null : "files"
                          )
                        }
                        aria-expanded={metaOpen === "files"}
                      >
                        文件 (状态)
                        <span className="h-4 min-w-4 rounded-full bg-[#2F6868] px-0.5 text-center text-[10px] leading-[16px] text-white">
                          {Object.keys(files).length}
                        </span>
                      </button>
                    )}
                    <button
                      aria-label="Close"
                      className="flex-1"
                      onClick={() => setMetaOpen(null)}
                    />
                  </div>
                  <div
                    ref={tasksContainerRef}
                    className="px-[18px]"
                  >
                    {metaOpen === "tasks" &&
                      Object.entries(groupedTodos)
                        .filter(([_, todos]) => todos.length > 0)
                        .map(([status, todos]) => (
                          <div
                            key={status}
                            className="mb-4"
                          >
                            <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-tertiary">
                              {
                                {
                                  pending: "待处理",
                                  in_progress: "进行中",
                                  completed: "已完成",
                                }[status]
                              }
                            </h3>
                            <div className="grid grid-cols-[auto_1fr] gap-3 rounded-sm p-1 pl-0 text-sm">
                              {todos.map((todo, index) => (
                                <Fragment key={`${status}_${todo.id}_${index}`}>
                                  {getStatusIcon(todo.status, "mt-0.5")}
                                  <span className="break-words text-inherit">
                                    {todo.content}
                                  </span>
                                </Fragment>
                              ))}
                            </div>
                          </div>
                        ))}

                    {metaOpen === "files" && (
                      <div className="mb-6">
                        <FilesPopover
                          files={files}
                          setFiles={setFiles}
                          editDisabled={
                            isLoading === true || interrupt !== undefined
                          }
                        />
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
          {generatedTestCaseIds.length > 0 && !isLoading && (
            <div className="flex items-center justify-between gap-2 border-b border-border bg-muted px-4 py-2 text-sm">
              <span className="text-muted-foreground">
                {t("testCases.generatedTestCasesCount", {
                  count: generatedTestCaseIds.length.toString(),
                })}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleDownloadExcel}
                disabled={exportingExcel}
              >
                {exportingExcel ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {t("testCases.downloadExcel")}
              </Button>
            </div>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col">
            <ContentBlocksPreview
              blocks={contentBlocks}
              onRemove={removeBlock}
              size="md"
            />
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={isLoading ? "运行中..." : "输入您的消息，或上传 PDF / 图片..."}
              className="font-inherit field-sizing-content flex-1 resize-none border-0 bg-transparent px-[18px] pb-[13px] pt-[14px] text-sm leading-7 text-primary outline-none placeholder:text-tertiary"
              rows={1}
            />
            <div className="flex items-center justify-between gap-2 p-3">
              <div className="flex items-center gap-4">
                <Label
                  htmlFor="chat-file-input"
                  className="flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-primary"
                >
                  <Plus className="h-4 w-4" />
                  <span>上传 PDF 或图片</span>
                </Label>
                <input
                  id="chat-file-input"
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <div className="flex items-center gap-2">
                  <Switch
                    id="rag-switch"
                    checked={enableRag}
                    onCheckedChange={setEnableRag}
                    disabled={isLoading}
                  />
                  <Label
                    htmlFor="rag-switch"
                    className="cursor-pointer text-sm text-muted-foreground"
                  >
                    开启 RAG
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="auto-approve-switch"
                    checked={autoApproveEnabled}
                    onCheckedChange={setAutoApproveEnabled}
                    disabled={isLoading}
                  />
                  <Label
                    htmlFor="auto-approve-switch"
                    className="cursor-pointer text-sm text-muted-foreground"
                  >
                    自动审批
                  </Label>
                  {autoApproveEnabled && (
                    <div className="flex items-center gap-1">
                      <Input
                        id="auto-approve-threshold"
                        type="number"
                        min={0}
                        max={100}
                        value={autoApproveThreshold}
                        onChange={(e) => {
                          const num = parseInt(e.target.value, 10);
                          if (!Number.isNaN(num)) {
                            setAutoApproveThreshold(Math.max(0, Math.min(100, num)));
                          }
                        }}
                        disabled={isLoading}
                        className="h-6 w-14 px-1 text-xs"
                      />
                      <Label
                        htmlFor="auto-approve-threshold"
                        className="cursor-pointer text-xs text-muted-foreground"
                      >
                        分
                      </Label>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type={isLoading ? "button" : "submit"}
                  variant={isLoading ? "destructive" : "default"}
                  onClick={isLoading ? stopStream : handleSubmit}
                  disabled={
                    !isLoading &&
                    (submitDisabled ||
                      (!input.trim() && contentBlocks.length === 0))
                  }
                >
                  {isLoading ? (
                    <>
                      <Square size={14} />
                      <span>停止</span>
                    </>
                  ) : (
                    <>
                      <ArrowUp size={18} />
                      <span>发送</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
});
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Tm5obVRnPT06Njg2NGJhMDY=

ChatInterface.displayName = "ChatInterface";
