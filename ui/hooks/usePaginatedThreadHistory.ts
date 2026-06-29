"use client";

import useSWRInfinite from "swr/infinite";
import { useMemo, useCallback } from "react";
import type { Client, ThreadState, Config } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// 每页固定拉 10 个 checkpoint，减少加载次数，一次能看到更多历史。
const PAGE_SIZE = 10;

interface HistoryKey {
  kind: "thread-history";
  threadId: string;
  before?: Config;
}

function getKey(threadId: string | null | undefined) {
  return (
    pageIndex: number,
    previousPageData: ThreadState<StateType>[] | null
  ): HistoryKey | null => {
    if (!threadId) return null;
    if (previousPageData && previousPageData.length === 0) return null;

    const before =
      previousPageData && previousPageData.length > 0
        ? {
            configurable: {
              checkpoint_id:
                previousPageData[previousPageData.length - 1].checkpoint
                  .checkpoint_id,
            },
          }
        : undefined;

    return { kind: "thread-history", threadId, before };
  };
}

async function fetcher(
  client: Client,
  key: HistoryKey
): Promise<ThreadState<StateType>[]> {
  return client.threads.getHistory<StateType>(key.threadId, {
    limit: PAGE_SIZE,
    ...(key.before ? { before: key.before } : {}),
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
      initialSize: 0,
      revalidateFirstPage: false,
      revalidateOnFocus: false,
    }
  );

  const flattened = useMemo(() => swr.data?.flat() ?? [], [swr.data]);

  // 更 robust 的尽头判断：
  // - 校验中先假设还有更多；
  // - 请求的页数比实际返回的多，说明有 key 返回了 null（已到尽头）；
  // - 数据为空且没有正在校验、且已经请求过页面，说明返回了空页（已到尽头）；
  // - 最后一页数量不足 PAGE_SIZE，也代表已到尽头。
  const hasMore = useMemo(() => {
    if (!swr.data || swr.data.length === 0) {
      return swr.isValidating || swr.size === 0;
    }
    if (swr.isValidating) return true;
    if (swr.size > swr.data.length) return false;
    const lastPage = swr.data[swr.data.length - 1];
    return lastPage.length >= PAGE_SIZE;
  }, [swr.data, swr.isValidating, swr.size]);

  const isLoadingMore = swr.size > (swr.data?.length ?? 0) && hasMore;

  const loadMore = useCallback(() => {
    if (!threadId || !hasMore || isLoadingMore) return;
    swr.setSize((size) => size + 1);
  }, [threadId, hasMore, isLoadingMore, swr.setSize]);

  return {
    data: flattened,
    pages: swr.data,
    error: swr.error,
    isLoading: swr.isLoading && swr.data == null,
    mutate: swr.mutate,
    isLoadingMore,
    setSize: swr.setSize,
    hasMore,
    loadMore,
  };
}
