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
import { useThreadMessages } from "./useThreadMessages";
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

  // 自定义消息级历史：前端 UI 直接显示的消息列表（由服务端合并去重）
  const threadMessages = useThreadMessages(
    client,
    thread ? null : threadId,
    fetchHistoryOnMount
  );

  // SDK useStream 的 thread prop 仍需要 ThreadState[] 类型数据，
  // 因此保留基于 /history 的分页数据，仅用于传入 useStream。
  const paginatedHistory = usePaginatedThreadHistory(
    client,
    thread ? null : threadId,
    fetchHistoryOnMount,
    false  // 关闭自动加载，避免与 threadMessages 双通道重复请求
  );

  // 兜底：首次挂载或切换 thread 时，如果当前 threadId 有效但历史数据尚未加载，
  // 主动触发一次重校验。注意：依赖项只放 threadId，不要放 messages / data 数组，
  // 否则数据变化会再次触发 mutate，形成无限重新验证循环，导致前端闪烁。
  const prevThreadIdRef = useRef<string | null | undefined>(threadId);
  useEffect(() => {
    const prev = prevThreadIdRef.current;
    prevThreadIdRef.current = threadId;
    if (!fetchHistoryOnMount) return;
    if (!threadId) return;
    if (prev === threadId) return;

    threadMessages.mutate();
    paginatedHistory.mutate();
  }, [
    fetchHistoryOnMount,
    threadId,
    threadMessages.mutate,
    paginatedHistory.mutate,
  ]);

  // 稳定传入 useStream 的 thread 对象，避免整个 paginatedHistory 对象每次渲染都重建
  // 导致 useStream 内部 history 引用频繁变化。
  const threadForStream: UseStreamThread<StateType> = useMemo(
    () => ({
      data: paginatedHistory.data,
      error: paginatedHistory.error,
      isLoading: paginatedHistory.isLoading,
      mutate: async (mutateId?: string) => {
        // SDK 在流正常结束后会 await history.mutate()，然后才进入 finally 重置
        // stream.isLoading。这里采用 fire-and-forget：立即返回当前缓存数据，同时
        // 触发后台重新验证，保证最新对话记录能被加载，且不阻塞 SDK 重置 isLoading。
        paginatedHistory.mutate().catch((err) => {
          if (process.env.NODE_ENV === "development") {
            // eslint-disable-next-line no-console
            console.error(
              "[useChat] background history revalidate failed",
              err
            );
          }
        });
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
    // 新 run 结束后刷新历史消息，使历史包含最新 checkpoint
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[useChat] handleFinish: revalidating thread messages + history");
    }
    threadMessages.mutate();
    paginatedHistory.mutate();
    onHistoryRevalidate?.();
    // 检测是否创建了测试用例（通过检查最后的消息中是否包含工具调用）
    onTestCaseCreated?.();
  }, [
    threadMessages.mutate,
    paginatedHistory.mutate,
    onHistoryRevalidate,
    onTestCaseCreated,
  ]);

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
    // SDK 订阅级节流：把"每个 SSE 事件触发一次渲染"降为"每 50ms 最多一次"，
    // 是流式卡顿治理的核心开关（此前每个 token 都穿透到 React 渲染树）。
    throttle: 50,
    // Revalidate thread list when stream finishes, errors, or creates new thread
    onFinish: handleFinish,
    onError: onHistoryRevalidate,
    onCreated: onHistoryRevalidate,
    ...(thread ? { thread } : { thread: threadForStream }),
  });

  // stream 对象随每个事件更换引用。通过 ref 访问最新 stream，
  // 让下方所有 submit 类回调保持引用稳定（useCallback 不依赖 stream），
  // 避免 ChatMessage memo / context 消费者被每事件的新回调引用击穿。
  const streamRef = useRef(stream);
  streamRef.current = stream;

  // 合并流式消息与历史消息（去重，按时间顺序排列）
  const mergedMessages = useMemo(() => {
    const streamIds = new Set(
      stream.messages.map((m) => m.id).filter((id): id is string => !!id)
    );

    // 历史消息中排除流式消息已包含的 id，避免重复。
    // threadMessages.messages 已经由服务端按时间顺序合并去重。
    const historical = threadMessages.messages.filter(
      (m) => m.id && !streamIds.has(m.id)
    );

    return [...historical, ...stream.messages];
  }, [stream.messages, threadMessages.messages]);

  // 当消息历史已经到达尽头时，不再自动加载。
  const isReachingEnd = !threadMessages.hasMore;

  const loadMoreHistory = useCallback(() => {
    threadMessages.loadMore();
  }, [threadMessages.loadMore]);

  // 注：SDK 层已做 50ms 订阅级节流（见上方 useStream 的 throttle 选项），
  // 此前这里的 33ms 手动节流（throttledMessages + 签名 + 定时器）已被取代并移除，
  // 直接使用 mergedMessages，由 ChatMessage 的 memo 承担未变消息的跳过渲染。

  // 从 assistant config 中提取并构建 Agent 运行时上下文
  const buildAgentContext = useCallback(
    (options?: {
      enable_rag?: boolean;
      auto_approve_threshold?: number;
      auto_execute_enabled?: boolean;
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
      options?: { enable_rag?: boolean; auto_approve_threshold?: number; auto_execute_enabled?: boolean }
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
      streamRef.current.submit(
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
    [buildRunConfig, buildAgentContext, onHistoryRevalidate]
  );

  const runSingleStep = useCallback(
    (
      messages: Message[],
      checkpoint?: Checkpoint,
      isRerunningSubagent?: boolean,
      optimisticMessages?: Message[]
    ) => {
      if (checkpoint) {
        streamRef.current.submit(undefined, {
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
        streamRef.current.submit(
          { messages },
          {
            config: buildRunConfig(),
            context: buildAgentContext(),
            interruptBefore: ["tools"],
          }
        );
      }
    },
    [buildRunConfig, buildAgentContext]
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
    (
      hasTaskToolCall?: boolean,
      options?: { enable_rag?: boolean; auto_approve_threshold?: number; auto_execute_enabled?: boolean }
    ) => {
      streamRef.current.submit(undefined, {
        config: buildRunConfig({ recursion_limit: 1000 }),
        context: buildAgentContext(options),
        ...(hasTaskToolCall
          ? { interruptAfter: ["tools"] }
          : { interruptBefore: ["tools"] }),
      });
      // Update thread list when continuing stream
      onHistoryRevalidate?.();
    },
    [buildRunConfig, buildAgentContext, onHistoryRevalidate]
  );

  const markCurrentThreadAsResolved = useCallback(() => {
    streamRef.current.submit(null, { command: { goto: "__end__", update: null } });
    // Update thread list when marking thread as resolved
    onHistoryRevalidate?.();
  }, [onHistoryRevalidate]);

  const stopStream = useCallback(() => {
    streamRef.current.stop();
  }, []);

  // 运行失败后的断点恢复：submit(undefined) 从线程最新 checkpoint 继续执行。
  // 与 continueStream 的区别：不携带 interruptBefore/After（那是单步调试用），
  // 用于 stream.error 后的「从断点继续」按钮。
  const retryFromError = useCallback(
    (options?: { enable_rag?: boolean; auto_approve_threshold?: number; auto_execute_enabled?: boolean }) => {
      streamRef.current.submit(undefined, {
        config: buildRunConfig({ recursion_limit: 1000 }),
        context: buildAgentContext(options),
      });
      onHistoryRevalidate?.();
    },
    [buildRunConfig, buildAgentContext, onHistoryRevalidate]
  );

  // 记录是否正在从 interrupt 恢复（点击评审卡片按钮后）。
  // stream.isLoading 在中断出现时仍保持 true，导致评审按钮被长期禁用，
  // 因此单独维护一个提交 resume 命令期间的本地 loading 状态。
  const [isResumingInterrupt, setIsResumingInterrupt] = useState(false);

  // 相同 payload 的重复 resume 去重窗口：SDK 会把所有 submit 串行排队
  // （不拒绝并发提交），双击或旧卡片未消失时的再次点击会被排队的下一个
  // pending interrupt 消费，造成"幽灵确认"。10s 窗口内相同 payload 直接忽略；
  // 正常流程中两个阶段的合法确认间隔以分钟计，不会误伤。
  const lastResumeRef = useRef<{ sig: string; at: number } | null>(null);

  const resumeInterrupt = useCallback(
    (
      value: any,
      options?: { enable_rag?: boolean; auto_approve_threshold?: number; auto_execute_enabled?: boolean }
    ) => {
      const sig = JSON.stringify(value) ?? "";
      const now = Date.now();
      if (
        lastResumeRef.current &&
        lastResumeRef.current.sig === sig &&
        now - lastResumeRef.current.at < 10_000
      ) {
        return;
      }
      lastResumeRef.current = { sig, at: now };
      setIsResumingInterrupt(true);
      streamRef.current.submit(null, {
        command: { resume: value },
        context: buildAgentContext(options),
      });
      // Update thread list when resuming from interrupt
      onHistoryRevalidate?.();
    },
    [buildAgentContext, onHistoryRevalidate]
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
    messages: mergedMessages,
    isLoading: stream.isLoading,
    isThreadLoading: stream.isThreadLoading || threadMessages.isLoading,
    interrupt: stream.interrupt,
    isResumingInterrupt,
    getMessagesMetadata: stream.getMessagesMetadata,
    sendMessage,
    runSingleStep,
    continueStream,
    stopStream,
    retryFromError,
    markCurrentThreadAsResolved,
    resumeInterrupt,
    isReachingEnd,
    // 历史分页
    loadMoreHistory,
    isLoadingMoreHistory: threadMessages.isLoadingMore,
    historyPages: threadMessages.pages,
    historyHasNewMessages: threadMessages.hasMore,
  };
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=
