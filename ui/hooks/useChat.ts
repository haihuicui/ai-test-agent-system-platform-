"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=

import React, { useCallback, useEffect, useRef, useState } from "react";
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
  };
};
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=

export function useChat({
  activeAssistant,
  onHistoryRevalidate,
  thread,
  onTestCaseCreated,
}: {
  activeAssistant: Assistant | null;
  onHistoryRevalidate?: () => void;
  thread?: UseStreamThread<StateType>;
  onTestCaseCreated?: () => void;
}) {
  const [threadId, setThreadId] = useQueryState("threadId");
  const [assistantId, setAssistantId] = useQueryState("assistantId");
  const client = useClient();

  // 同步 assistantId 到 URL
  React.useEffect(() => {
    if (activeAssistant?.assistant_id && assistantId !== activeAssistant.assistant_id) {
      setAssistantId(activeAssistant.assistant_id);
    }
  }, [activeAssistant?.assistant_id, assistantId, setAssistantId]);

  // 处理流完成事件
  const handleFinish = useCallback(() => {
    onHistoryRevalidate?.();
    // 检测是否创建了测试用例（通过检查最后的消息中是否包含工具调用）
    onTestCaseCreated?.();
  }, [onHistoryRevalidate, onTestCaseCreated]);

  const stream = useStream<StateType>({
    assistantId: activeAssistant?.assistant_id || "",
    client: client ?? undefined,
    reconnectOnMount: true,
    threadId: threadId ?? null,
    onThreadId: setThreadId,
    defaultHeaders: { "x-auth-scheme": "langsmith" },
    fetchStateHistory: { limit: 1 },
    // Revalidate thread list when stream finishes, errors, or creates new thread
    onFinish: handleFinish,
    onError: onHistoryRevalidate,
    onCreated: onHistoryRevalidate,
    ...(thread ? { thread } : {}),
  });

  // 流式渲染节流：逐 token 推送时，把"每个 token 触发一次渲染"降为"每 ~33ms 一次"，
  // 大幅减少长对话流式过程中的重复渲染。新消息（计数变化）和流结束时立即同步，
  // 保证用户发送的消息即时显示、且不丢失最终内容；仅对最后一条消息的 token 增长做节流。
  const STREAM_THROTTLE_MS = 33;
  const [throttledMessages, setThrottledMessages] = useState<Message[]>(
    stream.messages
  );
  const latestMessagesRef = useRef<Message[]>(stream.messages);
  const flushedLenRef = useRef<number>(stream.messages.length);
  const lastSigRef = useRef<string>("");
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 轻量签名：条数 + 末条 id + 末条内容长度。stream.messages 每次渲染都是新引用，
  // 用签名判断是否“真的变了”，避免无意义的 setState 造成无限更新循环。
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
    const msgs = stream.messages;
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
  }, [stream.messages, stream.isLoading]);

  // 卸载时清理定时器
  useEffect(
    () => () => {
      if (throttleTimerRef.current) clearTimeout(throttleTimerRef.current);
    },
    []
  );

  const sendMessage = useCallback(
    (content: string) => {
      const newMessage: Message = { id: uuidv4(), type: "human", content };

      // 从 assistant config 中提取 context 信息
      const context = activeAssistant?.config?.configurable || {};

      // 构建 context 对象
      const agentContext: Record<string, any> = {
        project_identifier: context.project_identifier || "",
        folder_id: context.folder_id || "",
        template_type: context.template_type || "test_case",
      };

      stream.submit(
        {
          messages: [newMessage],
          // 将 context 信息传递给后端智能体
          context: agentContext
        },
        {
          optimisticValues: (prev) => ({
            messages: [...(prev.messages ?? []), newMessage],
          }),
          config: { ...(activeAssistant?.config ?? {}), recursion_limit: 1000 },
        }
      );
      // Update thread list immediately when sending a message
      onHistoryRevalidate?.();
    },
    [stream, activeAssistant?.config, onHistoryRevalidate]
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
          config: activeAssistant?.config,
          checkpoint: checkpoint,
          ...(isRerunningSubagent
            ? { interruptAfter: ["tools"] }
            : { interruptBefore: ["tools"] }),
        });
      } else {
        stream.submit(
          { messages },
          { config: activeAssistant?.config, interruptBefore: ["tools"] }
        );
      }
    },
    [stream, activeAssistant?.config]
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
        config: {
          ...(activeAssistant?.config || {}),
          recursion_limit: 1000,
        },
        ...(hasTaskToolCall
          ? { interruptAfter: ["tools"] }
          : { interruptBefore: ["tools"] }),
      });
      // Update thread list when continuing stream
      onHistoryRevalidate?.();
    },
    [stream, activeAssistant?.config, onHistoryRevalidate]
  );

  const markCurrentThreadAsResolved = useCallback(() => {
    stream.submit(null, { command: { goto: "__end__", update: null } });
    // Update thread list when marking thread as resolved
    onHistoryRevalidate?.();
  }, [stream, onHistoryRevalidate]);

  const resumeInterrupt = useCallback(
    (value: any) => {
      stream.submit(null, { command: { resume: value } });
      // Update thread list when resuming from interrupt
      onHistoryRevalidate?.();
    },
    [stream, onHistoryRevalidate]
  );

  const stopStream = useCallback(() => {
    stream.stop();
  }, [stream]);

  return {
    stream,
    todos: stream.values.todos ?? [],
    files: stream.values.files ?? {},
    email: stream.values.email,
    ui: stream.values.ui,
    setFiles,
    messages: throttledMessages,
    isLoading: stream.isLoading,
    isThreadLoading: stream.isThreadLoading,
    interrupt: stream.interrupt,
    getMessagesMetadata: stream.getMessagesMetadata,
    sendMessage,
    runSingleStep,
    continueStream,
    stopStream,
    markCurrentThreadAsResolved,
    resumeInterrupt,
  };
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFsNVp3PT06NmUwNGM4MzQ=
