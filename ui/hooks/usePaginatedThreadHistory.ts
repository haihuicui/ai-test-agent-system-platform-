"use client";

import useSWRInfinite from "swr/infinite";
import { useMemo } from "react";
import type { Client, Config, ThreadState } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// LangGraph 的 messages channel 是「只增（append-only）累积」的，因此最新（head）
// checkpoint 通常已经包含整段对话。但 DeltaChannel 以 delta 形式存储，部分场景下
// 仅拉 head 会导致旧消息缺失；同时直接按 checkpoint 分页又会把累积状态重复拉取。
//
// 这里采用「先 head、再按需回溯」的策略：
// - 首屏只拉 1 个 checkpoint，保证打开会话时立即渲染。
// - 用户向上滚动时，通过 before 参数逐页拉取更早的 checkpoint。
// - hasMore 不仅看是否还有 checkpoint，还会检查上一页是否带来了新消息；
//   对累积型 checkpoint 来说， older checkpoint 不会增加新消息，因此翻页会自然停止，
//   避免无意义请求。
const PAGE_SIZE = 1;

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
      previousPageData?.[previousPageData.length - 1]?.checkpoint?.checkpoint_id;
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
  enabled: boolean = true
) {
  const swr = useSWRInfinite(
    getKey(client, enabled, threadId),
    (key) => {
      if (!client) return Promise.reject(new Error("missing client"));
      return fetcher(client, key);
    },
    {
      revalidateOnFocus: false,
      revalidateFirstPage: false,
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

  return {
    data: flattened,
    pages: swr.data,
    error: swr.error,
    isLoading: enabled && swr.isLoading && swr.data == null,
    mutate: swr.mutate,
    // 正在拉取更多历史（size 已增加但对应页数据尚未返回）
    isLoadingMore:
      swr.isValidating && swr.data != null && swr.size > swr.data.length,
    setSize: swr.setSize,
    hasMore,
    loadMore: () => swr.setSize((size) => size + 1),
  };
}
