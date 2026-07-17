"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGxWb1NBPT06NDQ4MzJhOGE=

import React, { useState, useCallback, useEffect, useRef } from "react";
import { useQueryState } from "nuqs";
import { Button } from "@/components/ui/button";
import { Assistant } from "@langchain/langgraph-sdk";
import { MessagesSquare, SquarePen, X } from "lucide-react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { ThreadList } from "./ThreadList";
import { ChatProvider } from "@/providers/ChatProvider";
import { ChatInterface } from "./ChatInterface";
import { useThreads } from "@/hooks/useThreads";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGxWb1NBPT06NDQ4MzJhOGE=

interface AIChatContainerProps {
  assistant: Assistant;
  initialPrompt?: string;
  onClose?: () => void;
  createNewThread?: boolean;
  onTestCaseCreated?: () => void; // 测试用例创建后的回调（已废弃）
  onTestCreated?: () => void; // 通用回调：测试创建后调用
  /** 当 save_test_* 工具调用完成时触发，用于实时刷新成果物面板 */
  onArtifactSaved?: () => void;
  reconnectOnMount?: boolean;
  fetchHistoryOnMount?: boolean;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGxWb1NBPT06NDQ4MzJhOGE=

export function AIChatContainer({
  assistant,
  initialPrompt,
  onClose,
  createNewThread = false,
  onTestCaseCreated,
  onTestCreated,
  onArtifactSaved,
  reconnectOnMount,
  fetchHistoryOnMount,
}: AIChatContainerProps) {
  const [threadId, setThreadId] = useQueryState("threadId");
  const [sidebar, setSidebar] = useQueryState("sidebar");
  const [mutateThreads, setMutateThreads] = useState<(() => void) | null>(null);
  const [interruptCount, setInterruptCount] = useState(0);

  // 打开 AI 助手且当前没有 threadId 时，自动选中最近一条对话，避免右侧空白。
  const threads = useThreads({
    assistantId: assistant.assistant_id,
    limit: 1,
  });
  const autoSelectedRef = useRef(false);
  useEffect(() => {
    // 明确要新建对话时，不自动选中历史对话
    if (createNewThread) return;
    if (autoSelectedRef.current) return;
    if (threadId) {
      autoSelectedRef.current = true;
      return;
    }
    const firstPage = threads.data?.[0];
    if (firstPage && firstPage.length > 0) {
      setThreadId(firstPage[0].id);
      autoSelectedRef.current = true;
    }
  }, [createNewThread, threadId, threads.data, setThreadId]);

  // 合并回调函数
  const handleTestCreated = useCallback(() => {
    onTestCaseCreated?.();
    onTestCreated?.();
  }, [onTestCaseCreated, onTestCreated]);

  // 如果需要创建新对话，清除 threadId。
  // 只在 createNewThread 从 false 变为 true 时执行一次，避免 aiChatKey > 0
  // 后每次重新挂载都清空 threadId，导致历史对话丢失。
  // 使用 useLayoutEffect 确保在子组件（ChatInterface）的自动发送 effect 运行前
  // 就已经清空 URL 中的 threadId，避免子组件因看到旧线程而提前标记“已发送”。
  const prevCreateNewThreadRef = React.useRef(false);
  React.useLayoutEffect(() => {
    if (createNewThread && !prevCreateNewThreadRef.current) {
      setThreadId(null);
    }
    prevCreateNewThreadRef.current = createNewThread;
  }, [createNewThread, setThreadId]);

  return (
    <div className="flex h-full flex-col">
      {/* 标题栏 */}
      <header className="flex h-14 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-4">
          <h1 className="text-base font-semibold">AI 测试用例生成</h1>
          {!sidebar && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebar("1")}
              className="rounded-md border border-border bg-card p-2 text-foreground hover:bg-accent"
            >
              <MessagesSquare className="mr-2 h-4 w-4" />
              对话列表
              {interruptCount > 0 && (
                <span className="ml-2 inline-flex min-h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] text-destructive-foreground">
                  {interruptCount}
                </span>
              )}
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/*<div className="text-xs text-muted-foreground">*/}
          {/*  <span className="font-medium">助手:</span> {assistant.assistant_id}*/}
          {/*</div>*/}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setThreadId(null)}
            disabled={!threadId}
            className="border-[#2F6868] bg-[#2F6868] text-white hover:bg-[#2F6868]/80"
          >
            <SquarePen className="mr-2 h-4 w-4" />
            新建对话
          </Button>
          {onClose && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-hidden">
        <ResizablePanelGroup
          orientation="horizontal"
        >
          {sidebar && (
            <>
              <ResizablePanel
                defaultSize={30}
                minSize={30}
                className="relative"
              >
                <ThreadList
                  assistantId={assistant.assistant_id}
                  onThreadSelect={async (id) => {
                    await setThreadId(id);
                  }}
                  onMutateReady={(fn) => setMutateThreads(() => fn)}
                  onClose={() => setSidebar(null)}
                  onInterruptCountChange={setInterruptCount}
                />
              </ResizablePanel>
              <ResizableHandle withHandle className="w-1 bg-border hover:bg-primary/20" />
            </>
          )}

          <ResizablePanel
            defaultSize={70}
            className="relative flex flex-col"
          >
            <ChatProvider
              activeAssistant={assistant}
              onHistoryRevalidate={() => mutateThreads?.()}
              onTestCaseCreated={handleTestCreated}
              reconnectOnMount={reconnectOnMount}
              fetchHistoryOnMount={fetchHistoryOnMount}
            >
              <ChatInterface
                assistant={assistant}
                initialPrompt={initialPrompt}
                onArtifactSaved={onArtifactSaved}
              />
            </ChatProvider>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGxWb1NBPT06NDQ4MzJhOGE=

