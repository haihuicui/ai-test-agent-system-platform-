"use client";

import { createContext, useContext, useMemo, ReactNode } from "react";
import { Client } from "@langchain/langgraph-sdk";
import { resolveDeploymentUrl } from "@/lib/langgraph/client";

interface ClientContextValue {
  client: Client;
}
// NOTE  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U0dSa1pnPT06NDIxNTM0YzQ=

/**
 * 关闭 SDK 的 SSE 空闲看门狗（idleReconnectStream，auto 模式）。
 *
 * 背景：服务端每 5s 发心跳，SDK 看门狗测出节奏后 15s（3×心跳间隔）无字节
 * 即主动断开重连；服务端主事件循环在长工具调用 / 大 checkpoint 序列化期间
 * 短暂阻塞导致心跳断流，看门狗会反复误杀连接。而 streamWithRetry 的重连
 * 计数全程累计、重连成功也不复位（上限 5 次），长任务（Web Agent 生成阶段
 * 约 18 分钟）必然耗尽并抛 "Exceeded maximum SSE reconnection attempts (5)"，
 * UI 误报「运行已中断」（此时服务端 run 实际仍在正常执行）。
 *
 * 服务端已有心跳保活，看门狗的半开检测价值低。置 0 仅关闭空闲看门狗，
 * 网络错误触发的重连（streamWithRetry）不受影响。
 *
 * react 层 useStream 不透传该选项（SDK 1.9.31 仍未支持），只能在此对
 * client.runs 的 stream / joinStream 做实例级包装强制注入。
 */
function disableSseIdleWatchdog(client: Client): void {
  const runs = client.runs;

  const originalStream = runs.stream.bind(runs);
  runs.stream = ((
    threadId: string | null,
    assistantId: string,
    payload?: Record<string, unknown>
  ) =>
    (originalStream as (...args: unknown[]) => unknown)(
      threadId,
      assistantId,
      { ...payload, streamIdleReconnect: 0 }
    )) as typeof runs.stream;

  const originalJoinStream = runs.joinStream.bind(runs);
  runs.joinStream = ((
    threadId: string | null | undefined,
    runId: string,
    options?: Record<string, unknown> | AbortSignal
  ) =>
    originalJoinStream(
      threadId,
      runId,
      options != null && !(options instanceof AbortSignal)
        ? { ...options, streamIdleReconnect: 0 }
        : options
    )) as typeof runs.joinStream;
}

const ClientContext = createContext<ClientContextValue | null>(null);

interface ClientProviderProps {
  children: ReactNode;
  deploymentUrl: string;
  apiKey: string;
}
// eslint-disable  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U0dSa1pnPT06NDIxNTM0YzQ=

export function ClientProvider({
  children,
  deploymentUrl,
  apiKey,
}: ClientProviderProps) {
  const client = useMemo(() => {
    const instance = new Client({
      apiUrl: resolveDeploymentUrl(deploymentUrl),
      defaultHeaders: {
        "Content-Type": "application/json",
        "X-Api-Key": apiKey,
      },
    });
    disableSseIdleWatchdog(instance);
    return instance;
  }, [deploymentUrl, apiKey]);

  const value = useMemo(() => ({ client }), [client]);

  return (
    <ClientContext.Provider value={value}>{children}</ClientContext.Provider>
  );
}

export function useClient(): Client {
  const context = useContext(ClientContext);

  if (!context) {
    throw new Error("useClient must be used within a ClientProvider");
  }
  return context.client;
}
