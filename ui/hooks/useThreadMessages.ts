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
      if (!enabled || !client || !threadId) {
        if (process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.debug(
            "[useThreadMessages] getKey returns null",
            JSON.stringify({ enabled, hasClient: !!client, threadId, pageIndex })
          );
        }
        return null;
      }
      if (previousPageData && !previousPageData.has_more) return null;

      const key = {
        kind: "thread-messages" as const,
        threadId,
        limit: MESSAGES_PAGE_SIZE,
        beforeCheckpointId: previousPageData?.next_checkpoint_id ?? undefined,
      };
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[useThreadMessages] getKey", key);
      }
      return key;
    },
    [client, enabled, threadId]
  );

  const fetcher = async (key: MessagesKey): Promise<ThreadMessagesResponse> => {
    if (!client) throw new Error("missing client");

    const params: Record<string, string> = { limit: String(key.limit) };
    if (key.beforeCheckpointId) {
      params.before_checkpoint_id = key.beforeCheckpointId;
    }

    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[useThreadMessages] fetching", `/threads/${key.threadId}/messages`, params);
    }

    try {
      // SDK 尚未暴露 /messages 端点，通过底层 fetch 调用。
      // 直接用浏览器 fetch，绕过 SDK 的 AsyncCaller 重试/队列，便于在 Network 面板定位请求。
      const apiUrl =
        (client as any).apiUrl || process.env.NEXT_PUBLIC_LANGGRAPH_API_URL;
      // apiUrl 在生产环境可能带 /langgraph 子路径（如 http://ip/langgraph），
      // new URL 的 path 以 / 开头会忽略 base 的子路径，因此用相对路径并补全斜杠。
      const base = apiUrl.endsWith("/") ? apiUrl : `${apiUrl}/`;
      const url = new URL(`threads/${key.threadId}/messages`, base);
      url.searchParams.set("limit", String(key.limit));
      if (key.beforeCheckpointId) {
        url.searchParams.set("before_checkpoint_id", key.beforeCheckpointId);
      }

      const response = await fetch(url.toString(), {
        headers: (client as any).defaultHeaders || {},
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
      const result = await response.json();

      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[useThreadMessages] response", result);
      }

      return result as ThreadMessagesResponse;
    } catch (err) {
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.error("[useThreadMessages] fetch error", err);
      }
      throw err;
    }
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
