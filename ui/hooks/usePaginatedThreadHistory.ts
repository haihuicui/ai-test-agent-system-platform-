"use client";

import useSWRInfinite from "swr/infinite";
import { useMemo } from "react";
import type { Client, Config, ThreadState } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// LangGraph 的 messages channel 是「只增（append-only）累积」的，最新（head）
// checkpoint 已经包含整段对话的全部消息。只有 DeltaChannel 等少数场景需要
// 回溯更早的 checkpoint。
//
// 策略：默认只拉 head checkpoint（快速 + 完整）。用户向上滚动时按需逐页回溯。
// 不自动预加载——累积型 checkpoint 每个都是全量快照，预加载会重复传输大量数据。
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
    // 上一页没有数据，已经到尽头
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
  // 当 threadId 在挂载时已有效（例如从 URL 恢复），直接初始化为 1 页，
  // 确保 SWR 立即发起首页历史请求。threadId 为 null 时保持 0，等待后续触发。
  const initialSize = threadId ? 1 : 0;
  const swr = useSWRInfinite(
    getKey(client, enabled, threadId),
    (key) => {
      if (!client) return Promise.reject(new Error("missing client"));
      return fetcher(client, key);
    },
    {
      initialSize,
      revalidateOnMount: true,
      revalidateFirstPage: false,
      revalidateOnFocus: false,
    }
  );

  const flattened = useMemo(() => swr.data?.flat() ?? [], [swr.data]);

  // 尽头判断：API 返回空 → 到尽头；最后一页非空 → 可能有更早 checkpoint。
  const hasMore = useMemo(() => {
    if (!swr.data || swr.data.length === 0) {
      return swr.isValidating || swr.size === 0;
    }
    if (swr.isValidating) return true;
    if (swr.size > swr.data.length) return false;
    const lastPage = swr.data[swr.data.length - 1];
    return lastPage != null && lastPage.length > 0;
  }, [swr.data, swr.isValidating, swr.size]);

  // 计算上一页是否带来了新的 message id（仅用于 UI 提示）。
  const hasNewMessages = useMemo(() => {
    if (!swr.data || swr.data.length <= 1) return true;
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

  return {
    data: flattened,
    pages: swr.data,
    error: swr.error,
    isLoading: enabled && swr.isLoading && swr.data == null,
    mutate: swr.mutate,
    isLoadingMore,
    setSize: swr.setSize,
    hasMore,
    hasNewMessages,
    // 用户向上滚动时按需加载更早的 checkpoint。
    loadMore: () => swr.setSize((size) => size + 1),
  };
}
