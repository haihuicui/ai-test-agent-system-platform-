"use client";

import useSWRInfinite from "swr/infinite";
import { useMemo } from "react";
import type { Client, ThreadState, Config } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// 每页固定拉 1 个 checkpoint，用户可无限向上滚动加载。
const PAGE_SIZE = 1;

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
      revalidateFirstPage: false,
      revalidateOnFocus: false,
    }
  );

  const flattened = useMemo(() => swr.data?.flat() ?? [], [swr.data]);
  const isLoadingMore = swr.size > 0 && swr.data?.[swr.size - 1] == null;

  return {
    data: flattened,
    pages: swr.data,
    error: swr.error,
    isLoading: swr.isLoading && swr.data == null,
    mutate: swr.mutate,
    isLoadingMore,
    setSize: swr.setSize,
  };
}
