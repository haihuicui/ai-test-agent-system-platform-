"use client";

import useSWRInfinite from "swr/infinite";
import { useEffect, useMemo } from "react";
import type { Client, Config, ThreadState } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// LangGraph 的 messages channel 是「只增（append-only）累积」的，因此最新（head）
// checkpoint 通常已经包含整段对话。但 DeltaChannel 以 delta 形式存储，部分场景下
// 仅拉 head 会导致旧消息缺失；同时直接按 checkpoint 分页又会把累积状态重复拉取。
//
// 这里采用「先 head、再按需回溯」的策略：
// - 首屏只拉 1 个 checkpoint，保证打开会话时立即渲染。
// - 组件挂载后在后台自动继续拉取更早的 checkpoint，直到没有新消息或到达安全上限；
//   用户无需手动滚动即可看到完整历史。
// - 用户向上滚动时，也会通过 before 参数逐页拉取更早的 checkpoint。
// - hasMore 不仅看是否还有 checkpoint，还会检查上一页是否带来了新消息；
//   对累积型 checkpoint 来说， older checkpoint 不会增加新消息，因此翻页会自然停止，
//   避免无意义请求。
const PAGE_SIZE = 1;
// 自动加载历史时的安全上限，防止极端 checkpoint 数量导致无限请求
const MAX_AUTO_LOAD_PAGES = 50;

interface HistoryKey {
  kind: "thread-history";
  threadId: string;
  limit: number;
  before?: string;
}

function getKey(
  client: Client | null,
  enabled: boolean,
  threadId: string | null | undefined
) {
  return (
    pageIndex: number,
    previousPageData: ThreadState<StateType>[] | null
  ): HistoryKey | null => {
    if (!enabled || !client || !threadId) return null;
    // 上一页没有数据，说明已经到尽头
    if (previousPageData && previousPageData.length === 0) return null;
    const before =
      previousPageData?.[previousPageData.length - 1]?.checkpoint?.checkpoint_id ??
      undefined;
    return { kind: "thread-history", threadId, limit: PAGE_SIZE, before };
  };
}

async function fetcher(
  client: Client,
  key: HistoryKey
): Promise<ThreadState<StateType>[]> {
  const params: { limit: number; before?: Config } = { limit: key.limit };
  if (key.before) {
    // LangGraph /history 接口要求 before 是 RunnableConfig 格式，
    // 只传 checkpoint_id 字符串会报 422。
    params.before = {
      configurable: {
        thread_id: key.threadId,
        checkpoint_id: key.before,
      },
    };
  }
  return client.threads.getHistory<StateType>(key.threadId, params);
}

export function usePaginatedThreadHistory(
  client: Client | null,
  threadId: string | null | undefined,
  enabled: boolean = true,
  autoLoadAll: boolean = true
) {
  const swr = useSWRInfinite(
    getKey(client, enabled, threadId),
    (key) => {
      if (!client) return Promise.reject(new Error("missing client"));
      return fetcher(client, key);
    },
    {
      initialSize: 1,
      revalidateOnMount: true,
      revalidateOnFocus: false,
    }
  );

  const flattened = useMemo(() => swr.data?.flat() ?? [], [swr.data]);

  // 计算 hasMore：
  // 1. 没有任何页 → false
  // 2. 最后一页为空 → false
  // 3. 最后一页带来了新的 message id → true
  // 4. 最后一页没有新消息（累积型 checkpoint 常见）→ false
  const hasMore = useMemo(() => {
    if (!swr.data || swr.data.length === 0) return false;
    const lastPage = swr.data[swr.data.length - 1];
    if (!lastPage || lastPage.length === 0) return false;

    const seen = new Set<string>();
    for (let i = 0; i < swr.data.length - 1; i++) {
      for (const state of swr.data[i]) {
        for (const msg of state.values?.messages ?? []) {
          if (msg.id) seen.add(msg.id);
        }
      }
    }
    for (const state of lastPage) {
      for (const msg of state.values?.messages ?? []) {
        if (msg.id && !seen.has(msg.id)) return true;
      }
    }
    return false;
  }, [swr.data]);

  // 正在拉取更多历史（size 已增加但对应页数据尚未返回）
  const isLoadingMore =
    swr.isValidating && swr.data != null && swr.size > swr.data.length;

  // 挂载或切换 thread 后，在后台自动加载更早的 checkpoint，直到历史完整或到达安全上限。
  // 这样关闭并重新打开 AI 助手时，无需用户手动滚动即可看到全部历史对话。
  useEffect(() => {
    if (!enabled || !autoLoadAll || !threadId) return;
    if (!hasMore) return;
    if (isLoadingMore) return;
    if ((swr.data?.length ?? 0) >= MAX_AUTO_LOAD_PAGES) return;

    const timer = setTimeout(() => {
      swr.setSize((size) => size + 1);
    }, 0);
    return () => clearTimeout(timer);
  }, [
    enabled,
    autoLoadAll,
    threadId,
    hasMore,
    isLoadingMore,
    swr.data?.length,
    swr.setSize,
  ]);

  return {
    data: flattened,
    pages: swr.data,
    error: swr.error,
    isLoading: enabled && swr.isLoading && swr.data == null,
    mutate: swr.mutate,
    isLoadingMore,
    setSize: swr.setSize,
    hasMore,
    loadMore: () => swr.setSize((size) => size + 1),
  };
}
