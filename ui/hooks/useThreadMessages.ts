"use client";

import useSWRInfinite from "swr/infinite";
import { useCallback, useMemo } from "react";
import type { Client, Message } from "@langchain/langgraph-sdk";

interface ThreadMessagesResponse {
  messages: Message[];
  has_more: boolean;
  next_checkpoint_id: string | null;
}

interface MessagesKey {
  kind: "thread-messages";
  threadId: string;
  beforeCheckpointId?: string;
  limit: number;
}

const MESSAGES_PAGE_SIZE = 20;

export function useThreadMessages(
  client: Client | null,
  threadId: string | null | undefined,
  enabled: boolean = true
) {
  const getKey = useCallback(
    (
      pageIndex: number,
      previousPageData: ThreadMessagesResponse | null
    ): MessagesKey | null => {
      if (!enabled || !client || !threadId) return null;
      if (previousPageData && !previousPageData.has_more) return null;

      return {
        kind: "thread-messages",
        threadId,
        limit: MESSAGES_PAGE_SIZE,
        beforeCheckpointId: previousPageData?.next_checkpoint_id ?? undefined,
      };
    },
    [client, enabled, threadId]
  );

  const fetcher = async (key: MessagesKey): Promise<ThreadMessagesResponse> => {
    if (!client) throw new Error("missing client");

    const params: Record<string, string> = { limit: String(key.limit) };
    if (key.beforeCheckpointId) {
      params.before_checkpoint_id = key.beforeCheckpointId;
    }

    // SDK 尚未暴露 /messages 端点，通过底层 fetch 调用。
    // BaseClient.fetch 在运行时是存在的，只是类型声明为 protected。
    const result = await (client as any).fetch(
      `/threads/${key.threadId}/messages`,
      { params }
    );
    return result as ThreadMessagesResponse;
  };

  const swr = useSWRInfinite(getKey, fetcher, {
    initialSize: 1,
    revalidateOnMount: true,
    revalidateFirstPage: false,
    revalidateOnFocus: false,
  });

  const messages = useMemo(
    () => swr.data?.flatMap((page) => page.messages) ?? [],
    [swr.data]
  );

  const hasMore = useMemo(() => {
    if (!swr.data || swr.data.length === 0) return true;
    return swr.data[swr.data.length - 1].has_more;
  }, [swr.data]);

  const isLoadingMore =
    swr.isValidating && swr.data != null && swr.size > swr.data.length;

  return {
    messages,
    pages: swr.data,
    error: swr.error,
    isLoading: enabled && swr.isLoading && swr.data == null,
    isLoadingMore,
    hasMore,
    setSize: swr.setSize,
    mutate: swr.mutate,
    loadMore: () => swr.setSize((size) => size + 1),
  };
}
