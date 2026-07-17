"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import {
  type Message,
  type Assistant,
  type Checkpoint,
} from "@langchain/langgraph-sdk";
import { v4 as uuidv4 } from "uuid";
import type { UseStreamThread } from "@langchain/langgraph-sdk/react";
import type { TodoItem } from "@/lib/langgraph/types";
import { useClient } from "@/providers/ClientProvider";
import { useQueryState } from "nuqs";
import { usePaginatedThreadHistory } from "./usePaginatedThreadHistory";
import {
  type ChatAttachmentBlock,
  isImageBlock,
  isFileBlock,
  type ImageUrlBlock,
} from "@/lib/langgraph/multimodal";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=

export type StateType = {
  messages: Message[];
  todos: TodoItem[];
  files: Record<string, string>;
  email?: {
    id?: string;
    subject?: string;
    page_content?: string;
  };
  ui?: any;
  context?: {
    project_identifier?: string;
    folder_id?: string;
    template_type?: string;
    environment_id?: string;
    enable_rag?: boolean;
  };
};
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=

export function useChat({
  activeAssistant,
  onHistoryRevalidate,
  thread,
  onTestCaseCreated,
  reconnectOnMount = true,
  fetchHistoryOnMount = true,
}: {
  activeAssistant: Assistant | null;
  onHistoryRevalidate?: () => void;
  thread?: UseStreamThread<StateType>;
  onTestCaseCreated?: () => void;
  reconnectOnMount?: boolean;
  fetchHistoryOnMount?: boolean;
}) {
  const [threadId, setThreadId] = useQueryState("threadId");
  const [assistantId, setAssistantId] = useQueryState("assistantId");
  const client = useClient();

  // 同步 assistantId 到 URL；当 URL 中残留的 assistantId 与当前助手不一致时，
  // 说明是从其它页面/其它助手带过来的状态，需要清空 threadId 以避免跨页面污染。
  React.useEffect(() => {
    if (!activeAssistant?.assistant_id) return;
    if (assistantId !== activeAssistant.assistant_id) {
      if (assistantId) {
        setThreadId(null);
      }
      setAssistantId(activeAssistant.assistant_id);
    }
  }, [activeAssistant?.assistant_id, assistantId, setAssistantId, setThreadId]);

  // 自定义分页历史：当外部传入 thread 或明确禁用历史加载时不启用内部分页
  const paginatedHistory = usePaginatedThreadHistory(
    client,
    thread ? null : threadId,
    fetchHistoryOnMount,
    fetchHistoryOnMount
  );

  // 兜底：首次挂载时 threadId 可能为 null（nuqs 水合或异步选中），key 变为有效值后
  // SWRInfinite 不一定会自动拉取首屏历史，导致重新打开 AI 助手后对话记录空白。
  // 在 threadId 首次变为有效且历史尚未加载时主动触发一次重校验。
  //
  // 注意：prevThreadIdRef 在挂载时初始化为 threadId，重新挂载时 threadId 可能已从 URL
  // 恢复为有效值。此前仅判断 if (prev) return 会错误地跳过重新挂载场景，因为 prev 的
  // 初始值就是当前 threadId（非 null）。现在改为：仅当 threadId 未变化且历史数据已
  // 存在时才跳过，其余情况（包括挂载时 threadId 有效但数据尚未拉取）均触发 mutate。
  const prevThreadIdRef = useRef<string | null | undefined>(threadId);
  useEffect(() => {
    const prev = prevThreadIdRef.current;
    prevThreadIdRef.current = threadId;
    if (!fetchHistoryOnMount) return;
    if (!threadId) return;
    // threadId 未变且已有历史数据 → 无需重复拉取
    if (prev === threadId && paginatedHistory.data && paginatedHistory.data.length > 0) return;
    paginatedHistory.mutate();
  }, [fetchHistoryOnMount, threadId, paginatedHistory.data, paginatedHistory.mutate]);

  // 稳定传入 useStream 的 thread 对象，避免整个 paginatedHistory 对象每次渲染都重建
  // 导致 useStream 内部 history 引用频繁变化。
  const threadForStream: UseStreamThread<StateType> = useMemo(
    () => ({
      data: paginatedHistory.data,
      error: paginatedHistory.error,
      isLoading: paginatedHistory.isLoading,
      mutate: async (mutateId?: string) => {
        await paginatedHistory.mutate();
        return paginatedHistory.data;
      },
    }),
    [
      paginatedHistory.data,
      paginatedHistory.error,
      paginatedHistory.isLoading,
      paginatedHistory.mutate,
    ]
  );

  // 处理流完成事件
  const handleFinish = useCallback(() => {
    // 新 run 结束后刷新历史第一页，使历史包含最新 checkpoint
    paginatedHistory.mutate();
    onHistoryRevalidate?.();
    // 检测是否创建了测试用例（通过检查最后的消息中是否包含工具调用）
    onTestCaseCreated?.();
  }, [paginatedHistory.mutate, onHistoryRevalidate, onTestCaseCreated]);

  // 包装 onThreadId：stream 在创建新 thread 后回调该函数。
  // 如果用户在此期间已经手动切换到别的历史对话，忽略这次覆盖，防止 URL 被跳回。
  const setThreadIdFromStream = useCallback(
    (newThreadId: string | null) => {
      if (newThreadId && threadId && newThreadId !== threadId) {
        return;
      }
      setThreadId(newThreadId);
    },
    [threadId, setThreadId]
  );

  const stream = useStream<StateType>({
    assistantId: activeAssistant?.assistant_id || "",
    client: client ?? undefined,
    reconnectOnMount,
    threadId: threadId ?? null,
    onThreadId: setThreadIdFromStream,
    defaultHeaders: { "x-auth-scheme": "langsmith" },
    fetchStateHistory: false,
    // Revalidate thread list when stream finishes, errors, or creates new thread
    onFinish: handleFinish,
    onError: onHistoryRevalidate,
    onCreated: onHistoryRevalidate,
    ...(thread ? { thread } : { thread: threadForStream }),
  });

  // 合并流式消息与分页历史消息（去重，按时间顺序排列）
  const mergedMessages = useMemo(() => {
    const streamIds = new Set(
      stream.messages.map((m) => m.id).filter((id): id is string => !!id)
    );
    const seen = new Set<string>(streamIds);

    // 辅助：计算消息内容的近似长度，用于同一 id 多版本时择优。
    const contentLength = (msg: Message): number => {
      const c = msg.content;
      if (typeof c === "string") return c.length;
      if (Array.isArray(c)) {
        // 直接序列化后比较长度，避免 MessageContent 联合类型推断问题。
        return JSON.stringify(c).length;
      }
      return 0;
    };

    // checkpoints 按 newest-first 返回；checkpoint 内部消息按时间顺序排列。
    // 这里从最新 checkpoint 的末尾开始遍历，保证最后反转为 chronological order 时
    // 消息顺序正确。对于同一 message id 的多个版本（例如 DeltaChannel 重放、
    // summarization / compaction 把旧工具结果改写为 pointer），优先保留内容更完整的
    // 版本，避免 head checkpoint 中已被压缩的消息覆盖掉 older checkpoint 里的完整内容。
    const newestFirst: Message[] = [];
    const indexById = new Map<string, number>();

    for (const state of paginatedHistory.data) {
      const stateMessages = state.values?.messages ?? [];
      for (let i = stateMessages.length - 1; i >= 0; i--) {
        const msg = stateMessages[i];
        if (!msg.id) {
          // 没有 id 的消息无法去重，直接保留；通常不应出现。
          newestFirst.push(msg);
          continue;
        }
        if (seen.has(msg.id)) continue;
        const existingIndex = indexById.get(msg.id);
        if (existingIndex == null) {
          indexById.set(msg.id, newestFirst.length);
          newestFirst.push(msg);
        } else if (contentLength(msg) > contentLength(newestFirst[existingIndex])) {
          newestFirst[existingIndex] = msg;
        }
      }
    }

    const older = newestFirst.reverse();
    return [...older, ...stream.messages];
  }, [stream.messages, paginatedHistory.data]);

  // 追踪连续空加载次数：当向上滚动拉取的 checkpoint 没有带回任何新消息时递增。
  // 累积型 channel 的更早 checkpoint 只是消息子集，连续 2 次空加载即视为有效尽头，
  // 避免陷入"向上滚动→加载→无新消息→又提示向上滚动"的死循环。
  const [consecutiveEmptyLoads, setConsecutiveEmptyLoads] = useState(0);
  useEffect(() => {
    const pagesLen = paginatedHistory.pages?.length ?? 0;
    if (pagesLen <= 1) {
      setConsecutiveEmptyLoads(0);
      return;
    }
    if (paginatedHistory.hasNewMessages) {
      setConsecutiveEmptyLoads(0);
    } else {
      setConsecutiveEmptyLoads((n) => n + 1);
    }
  }, [paginatedHistory.hasNewMessages, paginatedHistory.pages?.length]);
  // 切换对话时重置计数
  useEffect(() => {
    setConsecutiveEmptyLoads(0);
  }, [threadId]);

  // 历史已到尽头：API 无更多 checkpoint，或连续空加载达到阈值。
  const EMPTY_LOAD_LIMIT = 2;
  const isReachingEnd = !paginatedHistory.hasMore || consecutiveEmptyLoads >= EMPTY_LOAD_LIMIT;

  const loadMoreHistory = useCallback(() => {
    paginatedHistory.loadMore();
  }, [paginatedHistory.loadMore]);

  // 流式渲染节流：逐 token 推送时，把"每个 token 触发一次渲染"降为"每 ~33ms 一次"，
  // 大幅减少长对话流式过程中的重复渲染。新消息（计数变化）和流结束时立即同步，
  // 保证用户发送的消息即时显示、且不丢失最终内容；仅对最后一条消息的 token 增长做节流。
  const STREAM_THROTTLE_MS = 33;
  const [throttledMessages, setThrottledMessages] = useState<Message[]>(
    mergedMessages
  );
  const latestMessagesRef = useRef<Message[]>(mergedMessages);
  const flushedLenRef = useRef<number>(mergedMessages.length);
  const lastSigRef = useRef<string>("");
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 轻量签名：条数 + 末条 id + 末条内容长度。mergedMessages 每次渲染都是新引用，
  // 用签名判断是否"真的变了"，避免无意义的 setState 造成无限更新循环。
  const messagesSignature = (msgs: Message[]): string => {
    const n = msgs.length;
    if (n === 0) return "0";
    const last = msgs[n - 1] as { id?: string; content?: unknown };
    const c = last?.content;
    const clen =
      typeof c === "string" ? c.length : Array.isArray(c) ? c.length : 0;
    return `${n}:${last?.id ?? ""}:${clen}`;
  };

  useEffect(() => {
    const msgs = mergedMessages;
    const sig = messagesSignature(msgs);
    // 无实质变化（仅引用变了）→ 直接跳过，杜绝无限循环
    if (sig === lastSigRef.current) return;
    latestMessagesRef.current = msgs;

    const flush = () => {
      const latest = latestMessagesRef.current;
      lastSigRef.current = messagesSignature(latest);
      flushedLenRef.current = latest.length;
      setThrottledMessages(latest);
    };

    // 非流式（加载历史/结束）或消息条数变化（新消息）→ 立即刷新
    if (!stream.isLoading || msgs.length !== flushedLenRef.current) {
      if (throttleTimerRef.current) {
        clearTimeout(throttleTimerRef.current);
        throttleTimerRef.current = null;
      }
      flush();
      return;
    }

    // 流式中且仅最后一条内容增长 → 节流（尾随刷新）
    if (throttleTimerRef.current) return;
    throttleTimerRef.current = setTimeout(() => {
      throttleTimerRef.current = null;
      flush();
    }, STREAM_THROTTLE_MS);
  }, [mergedMessages, stream.isLoading]);

  // 卸载时清理定时器
  useEffect(
    () => () => {
      if (throttleTimerRef.current) clearTimeout(throttleTimerRef.current);
    },
    []
  );

  // 从 assistant config 中提取并构建 Agent 运行时上下文
  const buildAgentContext = useCallback(
    (options?: {
      enable_rag?: boolean;
      auto_approve_threshold?: number;
    }): Record<string, any> => {
      const context = activeAssistant?.config?.configurable || {};
      return {
        project_identifier: context.project_identifier || "",
        folder_id: context.folder_id || "",
        template_type: context.template_type || "test_case",
        environment_id: context.environment_id || "",
        enable_rag: options?.enable_rag ?? true,
        auto_approve_threshold: options?.auto_approve_threshold ?? 100,
      };
    },
    [activeAssistant?.config]
  );

  // 构建提交 run 时使用的 config：移除 configurable，避免与 context 同时传递。
  // LangGraph API 禁止 config.configurable 与 context 并存。
  const buildRunConfig = useCallback(
    (extra?: Record<string, any>) => {
      const config = activeAssistant?.config ? { ...activeAssistant.config } : {};
      delete config.configurable;
      return { ...config, ...extra };
    },
    [activeAssistant?.config]
  );

  const sendMessage = useCallback(
    (
      content: string,
      contentBlocks?: ChatAttachmentBlock[],
      options?: { enable_rag?: boolean; auto_approve_threshold?: number }
    ) => {
      const imageBlocks = contentBlocks?.filter(isImageBlock) ?? [];
      const pdfBlocks = contentBlocks?.filter(isFileBlock) ?? [];

      // 图片转换为 OpenAI / Doubao 兼容的 image_url 格式
      const imageUrlBlocks: ImageUrlBlock[] = imageBlocks.map((b) => ({
        type: "image_url",
        image_url: { url: `data:${b.mimeType};base64,${b.data}` },
      }));

      const messageContent: Message["content"] =
        imageUrlBlocks.length > 0
          ? ([
              ...(content.trim().length > 0
                ? [{ type: "text" as const, text: content.trim() }]
                : []),
              ...imageUrlBlocks,
            ] as Message["content"])
          : content.trim();

      const newMessage: Message = {
        id: uuidv4(),
        type: "human",
        content: messageContent,
        additional_kwargs: {
          ...(pdfBlocks.length > 0 ? { attachments: pdfBlocks } : {}),
          enable_rag: options?.enable_rag ?? true,
          auto_approve_threshold: options?.auto_approve_threshold ?? 100,
        },
      };

      // 运行时上下文必须通过 submit 的 options.context 传递给 LangGraph，
      // 不能放在 input 中；否则 request.runtime.context 会保持为空，
      // 导致 project_identifier 为空而创建失败。
      stream.submit(
        { messages: [newMessage] },
        {
          optimisticValues: (prev) => ({
            messages: [...(prev.messages ?? []), newMessage],
          }),
          config: buildRunConfig({ recursion_limit: 1000 }),
          context: buildAgentContext(options),
        }
      );
      // Update thread list immediately when sending a message
      onHistoryRevalidate?.();
    },
    [stream, buildRunConfig, buildAgentContext, onHistoryRevalidate]
  );

  const runSingleStep = useCallback(
    (
      messages: Message[],
      checkpoint?: Checkpoint,
      isRerunningSubagent?: boolean,
      optimisticMessages?: Message[]
    ) => {
      if (checkpoint) {
        stream.submit(undefined, {
          ...(optimisticMessages
            ? { optimisticValues: { messages: optimisticMessages } }
            : {}),
          config: buildRunConfig(),
          context: buildAgentContext(),
          checkpoint: checkpoint,
          ...(isRerunningSubagent
            ? { interruptAfter: ["tools"] }
            : { interruptBefore: ["tools"] }),
        });
      } else {
        stream.submit(
          { messages },
          {
            config: buildRunConfig(),
            context: buildAgentContext(),
            interruptBefore: ["tools"],
          }
        );
      }
    },
    [stream, buildRunConfig, buildAgentContext]
  );

  const setFiles = useCallback(
    async (files: Record<string, string>) => {
      if (!threadId) return;
      // TODO: missing a way how to revalidate the internal state
      // I think we do want to have the ability to externally manage the state
      await client.threads.updateState(threadId, { values: { files } });
    },
    [client, threadId]
  );

  const continueStream = useCallback(
    (hasTaskToolCall?: boolean) => {
      stream.submit(undefined, {
        config: buildRunConfig({ recursion_limit: 1000 }),
        context: buildAgentContext(),
        ...(hasTaskToolCall
          ? { interruptAfter: ["tools"] }
          : { interruptBefore: ["tools"] }),
      });
      // Update thread list when continuing stream
      onHistoryRevalidate?.();
    },
    [stream, buildRunConfig, buildAgentContext, onHistoryRevalidate]
  );

  const markCurrentThreadAsResolved = useCallback(() => {
    stream.submit(null, { command: { goto: "__end__", update: null } });
    // Update thread list when marking thread as resolved
    onHistoryRevalidate?.();
  }, [stream, onHistoryRevalidate]);

  const stopStream = useCallback(() => {
    stream.stop();
  }, [stream]);

  // 记录是否正在从 interrupt 恢复（点击评审卡片按钮后）。
  // stream.isLoading 在中断出现时仍保持 true，导致评审按钮被长期禁用，
  // 因此单独维护一个提交 resume 命令期间的本地 loading 状态。
  const [isResumingInterrupt, setIsResumingInterrupt] = useState(false);

  const resumeInterrupt = useCallback(
    (value: any) => {
      setIsResumingInterrupt(true);
      stream.submit(null, {
        command: { resume: value },
        context: buildAgentContext(),
      });
      // Update thread list when resuming from interrupt
      onHistoryRevalidate?.();
    },
    [stream, buildAgentContext, onHistoryRevalidate]
  );

  // 恢复状态重置：resumeInterrupt 调用 stream.submit 后，interrupt 不会立即变化——
  // SDK 先检查 values.__interrupt__（旧值），之后才检查 stream.isLoading。
  // 当服务端开始处理（stream.isLoading → true）时说明 resume 已被消费；
  // 当 interrupt 变化/消失/报错时也说明处理完成。三者任一变化都应重置，
  // 否则按钮会永久卡死在"提交中..."。
  useEffect(() => {
    setIsResumingInterrupt(false);
  }, [stream.isLoading, stream.interrupt, stream.error]);

  return {
    stream,
    todos: stream.values.todos ?? [],
    files: stream.values.files ?? {},
    email: stream.values.email,
    ui: stream.values.ui,
    setFiles,
    messages: throttledMessages,
    isLoading: stream.isLoading,
    isThreadLoading: stream.isThreadLoading || paginatedHistory.isLoading,
    interrupt: stream.interrupt,
    isResumingInterrupt,
    getMessagesMetadata: stream.getMessagesMetadata,
    sendMessage,
    runSingleStep,
    continueStream,
    stopStream,
    markCurrentThreadAsResolved,
    resumeInterrupt,
    isReachingEnd,
    // 历史分页
    loadMoreHistory,
    isLoadingMoreHistory: paginatedHistory.isLoadingMore,
    historyPages: paginatedHistory.pages,
    historyHasNewMessages: paginatedHistory.hasNewMessages,
  };
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=
