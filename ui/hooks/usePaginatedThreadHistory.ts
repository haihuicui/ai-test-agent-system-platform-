"use client";

import useSWRInfinite from "swr/infinite";
import { useMemo } from "react";
import type { Client, ThreadState } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// LangGraph 的 messages channel 是「只增（append-only）累积」的：最新（head）
// checkpoint 已经包含了整段对话的全部消息。以前按 checkpoint 分页会把几乎完全
// 相同的整段消息数组重复拉取 N 次（10 个 checkpoint ≈ 10 份全量快照），一个
// 200+ 消息的会话就能到 40MB+ / 60s，直接把「加载历史对话」卡死；而这些旧
// checkpoint 只是消息更少的子集，翻页永远拿不到任何新消息。
//
// 因此这里只拉最新的 1 个 checkpoint（limit=1），它即为完整对话。既避免了
// 冗余传输，也在打开会话时立即加载出历史（initialSize:1），不再依赖用户向上
// 滚动才触发首次加载。
const PAGE_SIZE = 1;

interface HistoryKey {
  kind: "thread-history";
  threadId: string;
}

function getKey(threadId: string | null | undefined) {
  return (pageIndex: number): HistoryKey | null => {
    if (!threadId) return null;
    // 只加载最新 checkpoint（已含全部消息），不再翻页。
    if (pageIndex > 0) return null;
    return { kind: "thread-history", threadId };
  };
}

async function fetcher(
  client: Client,
  key: HistoryKey
): Promise<ThreadState<StateType>[]> {
  return client.threads.getHistory<StateType>(key.threadId, {
    limit: PAGE_SIZE,
  });
}

export function usePaginatedThreadHistory(
  client: Client | null,
  threadId: string | null | undefined
) {
  const swr = useSWRInfinite(
    getKey(threadId),
    (key) => (client ? fetcher(client, key) : Promise.resolve([])),
    {
      // 打开会话时立即加载最新 checkpoint（其中已含整段对话）。
      initialSize: 1,
      revalidateFirstPage: false,
      revalidateOnFocus: false,
    }
  );

  const flattened = useMemo(() => swr.data?.flat() ?? [], [swr.data]);

  return {
    data: flattened,
    pages: swr.data,
    error: swr.error,
    isLoading: swr.isLoading && swr.data == null,
    mutate: swr.mutate,
    // 最新 checkpoint 即完整对话，没有可继续加载的更早消息。
    isLoadingMore: false,
    setSize: swr.setSize,
    hasMore: false,
    loadMore: () => {},
  };
}
