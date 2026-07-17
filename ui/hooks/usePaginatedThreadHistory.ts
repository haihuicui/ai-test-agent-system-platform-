"use client";

import useSWRInfinite from "swr/infinite";
import { useEffect, useMemo, useRef } from "react";
import type { Client, Config, ThreadState } from "@langchain/langgraph-sdk";
import type { StateType } from "./useChat";

// LangGraph 的 messages channel 是「只增（append-only）累积」的，因此最新（head）
// checkpoint 通常已经包含整段对话。但 DeltaChannel 以 delta 形式存储，部分场景下
// 仅拉 head 会导致旧消息缺失；同时直接按 checkpoint 分页又会把累积状态重复拉取。
//
// 这里采用「先 head、再按需回溯」的策略：
// - 首屏只拉 1 个 checkpoint，保证打开会话时立即渲染。
// - 组件挂载后在后台自动继续拉取更早的 checkpoint，直到 API 返回空页或到达安全上限；
//   用户无需手动滚动即可看到完整历史。
// - 用户向上滚动时，也会通过 before 参数逐页拉取更早的 checkpoint。
// - hasMore 看的是 API 是否还有更早 checkpoint（最后一页是否非空）。
//   对累积型 checkpoint 来说，older checkpoint 不会增加新消息，但去重由 useChat 负责；
//   这里宁可多请求几页，也要保证 DeltaChannel / summarization 等场景下的历史完整。
// - 自动加载额外受 MAX_AUTO_LOAD_PAGES 限制，防止极端 checkpoint 数量导致无限请求。
// 首页：仅拉取最新的 1 个 head checkpoint，确保首屏立即渲染。
// head checkpoint 在 LangGraph 标准模式下已包含全部消息（cumulative channel），
// 仅 DeltaChannel / summarization 等特殊场景需要回溯更早的 checkpoint。
const PAGE_SIZE = 1;
// 后续页：批量拉取剩余所有更早的 checkpoint，将原先 N 次串行请求合并为 1 次，
// 根除逐页自动加载链条因竞态/网络波动中断导致「对话记录展示不全」的问题。
const BULK_FETCH_SIZE = 100;
// 自动加载历史时的安全上限。因 bulk fetch 一页即可覆盖绝大多数场景，大幅降低该值。
const MAX_AUTO_LOAD_PAGES = 4;

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
    // 首页仅取 head checkpoint（快速首屏），后续页批量拉取剩余所有 checkpoint。
    const limit = pageIndex === 0 ? PAGE_SIZE : BULK_FETCH_SIZE;
    return { kind: "thread-history", threadId, limit, before };
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
  // 确保 SWR 立即发起首页历史请求，不再依赖自动加载 effect 的异步触发。
  // 当 threadId 为 null 时保持 initialSize: 0，由自动加载 effect 在
  // threadId 变为有效值后触发首屏拉取。
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

  // 更 robust 的尽头判断：
  // - 校验中先假设还有更多；
  // - 请求的页数比实际返回的多，说明有 key 返回了 null（已到尽头）；
  // - 数据为空且没有正在校验、且已经请求过页面，说明返回了空页（已到尽头）；
  // - 最后一页数量非空，代表可能还有更早的 checkpoint。
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

  // 挂载或切换 thread 后，在后台自动加载更早的 checkpoint，直到历史完整或到达安全上限。
  // 这样关闭并重新打开 AI 助手时，无需用户手动滚动即可看到全部历史对话。
  //
  // 使用 requestAnimationFrame 而非 setTimeout(…, 0)：
  // - setTimeout(0) 在微任务中触发，可能在 React 批处理完成前就执行，
  //   导致 cleanup 取消掉待执行的 setSize → 链条静默断裂。
  // - rAF 在下一帧（~16ms）触发，保证所有 React 状态更新已提交完毕，
  //   配合 ref 门控防止 Strict Mode 双击。
  const autoLoadRafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || !autoLoadAll || !threadId) return;
    // 首页数据尚未到达，不触发自动加载，避免 setSize 在 SWR 未就绪时被调用
    if (!swr.data || swr.data.length === 0) return;
    if (!hasMore) return;
    if (isLoadingMore) return;
    if ((swr.data?.length ?? 0) >= MAX_AUTO_LOAD_PAGES) return;
    // rAF 已在等待中，防止 Strict Mode 双击导致 size 被重复递增
    if (autoLoadRafRef.current != null) return;

    autoLoadRafRef.current = requestAnimationFrame(() => {
      autoLoadRafRef.current = null;
      swr.setSize((size) => size + 1);
    });

    return () => {
      if (autoLoadRafRef.current != null) {
        cancelAnimationFrame(autoLoadRafRef.current);
        autoLoadRafRef.current = null;
      }
    };
  }, [
    enabled,
    autoLoadAll,
    threadId,
    hasMore,
    isLoadingMore,
    swr.data,
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
    hasNewMessages,
    loadMore: () => swr.setSize((size) => size + 1),
  };
}
