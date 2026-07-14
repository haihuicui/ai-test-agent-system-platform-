"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtwa1dBPT06NmJhZDM0MjY=

import React, { useMemo, useState, useCallback } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubAgentIndicator } from "@/components/langgraph/SubAgentIndicator";
import { ToolCallBox } from "@/components/langgraph/ToolCallBox";
import { MarkdownContent } from "@/components/langgraph/MarkdownContent";
import { MultimodalPreview } from "@/components/langgraph/MultimodalPreview";
import {
  isImageUrlBlock,
  isFileBlock,
  type FileBlock,
  type ImageUrlBlock,
} from "@/lib/langgraph/multimodal";
import type {
  SubAgent,
  ToolCall,
  ActionRequest,
  ReviewConfig,
} from "@/lib/langgraph/types";
import { Message } from "@langchain/langgraph-sdk";
import {
  extractSubAgentContent,
  extractStringFromMessageContent,
} from "@/lib/langgraph/utils";
import { downloadAgentFile } from "@/lib/api/agentFiles";
import { cn } from "@/lib/utils";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtwa1dBPT06NmJhZDM0MjY=

interface ChatMessageProps {
  message: Message;
  toolCalls: ToolCall[];
  isLoading?: boolean;
  isStreaming?: boolean;
  isResumingInterrupt?: boolean;
  actionRequestsMap?: Map<string, ActionRequest>;
  reviewConfigsMap?: Map<string, ReviewConfig>;
  ui?: any[];
  stream?: any;
  onResumeInterrupt?: (value: any) => void;
  graphId?: string;
}

function areToolCallsEqual(prevToolCalls: ToolCall[], nextToolCalls: ToolCall[]) {
  if (prevToolCalls === nextToolCalls) return true;
  if (prevToolCalls.length !== nextToolCalls.length) return false;

  return prevToolCalls.every((toolCall, index) => {
    const nextToolCall = nextToolCalls[index];
    return (
      toolCall.id === nextToolCall.id &&
      toolCall.name === nextToolCall.name &&
      toolCall.status === nextToolCall.status &&
      toolCall.result === nextToolCall.result &&
      toolCall.args === nextToolCall.args
    );
  });
}

function areUiEntriesEqual(prevUi?: any[], nextUi?: any[]) {
  if (prevUi === nextUi) return true;
  if (!prevUi || !nextUi) return prevUi === nextUi;
  if (prevUi.length !== nextUi.length) return false;

  return prevUi.every((entry, index) => entry === nextUi[index]);
}

function MessageFileDownloads({ content }: { content: string }) {
  const paths = useMemo(() => {
    const matches = content.match(/\/[^\s]+\.xlsx/gi) ?? [];
    return Array.from(new Set(matches));
  }, [content]);

  if (paths.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {paths.map((path) => (
        <Button
          key={path}
          variant="outline"
          size="sm"
          onClick={() => downloadAgentFile(path)}
          className="gap-1.5"
        >
          <Download size={14} />
          <span>下载 Excel</span>
        </Button>
      ))}
    </div>
  );
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtwa1dBPT06NmJhZDM0MjY=

export const ChatMessage = React.memo<ChatMessageProps>(
  ({
    message,
    toolCalls,
    isLoading,
    isStreaming,
    isResumingInterrupt,
    actionRequestsMap,
    reviewConfigsMap,
    ui,
    stream,
    onResumeInterrupt,
    graphId,
  }) => {
    const isUser = message.type === "human";
    const messageContent = extractStringFromMessageContent(message);
    const hasContent = messageContent && messageContent.trim() !== "";
    const hasToolCalls = toolCalls.length > 0;

    // 用户上传的附件：图片以 image_url 块存在 content 中，PDF 放在 additional_kwargs.attachments
    const imageUrlBlocks: ImageUrlBlock[] = Array.isArray(message.content)
      ? (message.content as unknown[]).filter(isImageUrlBlock)
      : [];
    const rawAttachments = (message.additional_kwargs as Record<string, unknown>)?.attachments;
    const pdfBlocks: FileBlock[] = Array.isArray(rawAttachments)
      ? (rawAttachments as unknown[]).filter(isFileBlock)
      : [];
    const hasAttachments = imageUrlBlocks.length > 0 || pdfBlocks.length > 0;

    const subAgents = useMemo(
      () =>
        toolCalls
          .filter(
            (tc: ToolCall) =>
              tc.name === "task" &&
              tc.args["subagent_type"] &&
              tc.args["subagent_type"] !== "" &&
              tc.args["subagent_type"] !== null
          )
          .map((tc: ToolCall) => ({
            id: tc.id,
            name: tc.name,
            subAgentName: (tc.args as Record<string, unknown>)["subagent_type"] as string,
            input: tc.args,
            output: tc.result ? { result: tc.result } : undefined,
            status: tc.status,
          } as SubAgent)),
      [toolCalls]
    );

    const [expandedSubAgents, setExpandedSubAgents] = useState<Record<string, boolean>>({});
    const isSubAgentExpanded = useCallback(
      (id: string) => expandedSubAgents[id] ?? true,
      [expandedSubAgents]
    );
    const toggleSubAgent = useCallback((id: string) => {
      setExpandedSubAgents((prev) => ({
        ...prev,
        [id]: prev[id] === undefined ? false : !prev[id],
      }));
    }, []);

    return (
      <div
        className={cn("flex w-full max-w-full overflow-x-hidden", isUser && "flex-row-reverse")}
        style={{ contentVisibility: "auto", containIntrinsicSize: "200px" }}
      >
        <div className={cn("min-w-0 max-w-full", isUser ? "max-w-[70%]" : "w-full")}>
          {(hasContent || hasAttachments) && (
            <div className={cn("relative flex items-end gap-0")}>
              {isUser ? (
                /* 用户消息：先显示附件，再显示文本气泡 */
                <div className="mt-4 flex flex-col items-end gap-2">
                  {hasAttachments && (
                    <div className="flex flex-wrap justify-end gap-2">
                      {imageUrlBlocks.map((block, idx) => (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={`img-${idx}`}
                          src={block.image_url.url}
                          alt={`uploaded image ${idx + 1}`}
                          className="h-16 w-16 rounded-md object-cover"
                        />
                      ))}
                      {pdfBlocks.map((block, idx) => (
                        <MultimodalPreview
                          key={`pdf-${idx}`}
                          block={block}
                          size="md"
                        />
                      ))}
                    </div>
                  )}
                  {hasContent && (
                    <div
                      className="overflow-hidden break-words rounded-xl rounded-br-none border border-border px-3 py-2 text-sm font-normal leading-[150%] text-foreground"
                      style={{
                        backgroundColor: "var(--color-user-message-bg)",
                      }}
                    >
                      <p className="m-0 whitespace-pre-wrap break-words text-sm leading-relaxed">
                        {messageContent}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div
                  className={cn(
                    "mt-4 overflow-hidden break-words text-sm font-normal leading-[150%] text-primary"
                  )}
                >
                  <MarkdownContent content={messageContent} streaming={isStreaming} />
                  {!isStreaming && <MessageFileDownloads content={messageContent} />}
                </div>
              )}
            </div>
          )}
          {hasToolCalls && (
            <div className="mt-4 flex w-full flex-col">
              {toolCalls.map((toolCall: ToolCall) => {
                if (toolCall.name === "task") return null;
                const toolCallGenUiComponent =
                  ui && ui.length > 0
                    ? ui.find((u) => u.metadata?.tool_call_id === toolCall.id)
                    : undefined;
                const actionRequest = actionRequestsMap?.get(toolCall.name);
                const reviewConfig = reviewConfigsMap?.get(toolCall.name);
                return (
                  <ToolCallBox
                    key={toolCall.id}
                    toolCall={toolCall}
                    uiComponent={toolCallGenUiComponent}
                    stream={stream}
                    graphId={graphId}
                    actionRequest={actionRequest}
                    reviewConfig={reviewConfig}
                    onResume={onResumeInterrupt}
                    isLoading={isLoading}
                    isResumingInterrupt={isResumingInterrupt}
                  />
                );
              })}
            </div>
          )}
          {!isUser && subAgents.length > 0 && (
            <div className="flex w-fit max-w-full flex-col gap-4">
              {subAgents.map((subAgent) => (
                <div key={subAgent.id} className="flex w-full flex-col gap-2">
                  <div className="flex items-end gap-2">
                    <div className="w-[calc(100%-100px)]">
                      <SubAgentIndicator
                        subAgent={subAgent}
                        onClick={() => toggleSubAgent(subAgent.id)}
                        isExpanded={isSubAgentExpanded(subAgent.id)}
                      />
                    </div>
                  </div>
                  {isSubAgentExpanded(subAgent.id) && (
                    <div className="w-full max-w-full">
                      <div className="bg-surface border-border-light rounded-md border p-4">
                        <h4 className="text-primary/70 mb-2 text-xs font-semibold uppercase tracking-wider">
                          输入
                        </h4>
                        <div className="mb-4">
                          <MarkdownContent content={extractSubAgentContent(subAgent.input)} />
                        </div>
                        {subAgent.output && (
                          <>
                            <h4 className="text-primary/70 mb-2 text-xs font-semibold uppercase tracking-wider">
                              输出
                            </h4>
                            <MarkdownContent content={extractSubAgentContent(subAgent.output)} />
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    const isSameMessage = prevProps.message === nextProps.message;
    const isSameToolCalls = areToolCallsEqual(
      prevProps.toolCalls,
      nextProps.toolCalls
    );
    const isSameUi = areUiEntriesEqual(prevProps.ui, nextProps.ui);
    const isSameInterruptMaps =
      prevProps.actionRequestsMap === nextProps.actionRequestsMap &&
      prevProps.reviewConfigsMap === nextProps.reviewConfigsMap;

    const isSameLastMessageState =
      prevProps.stream === nextProps.stream &&
      prevProps.onResumeInterrupt === nextProps.onResumeInterrupt &&
      prevProps.graphId === nextProps.graphId &&
      prevProps.isLoading === nextProps.isLoading &&
      prevProps.isStreaming === nextProps.isStreaming &&
      prevProps.isResumingInterrupt === nextProps.isResumingInterrupt;

    return (
      isSameMessage &&
      isSameToolCalls &&
      isSameUi &&
      isSameInterruptMaps &&
      isSameLastMessageState
    );
  }
);

ChatMessage.displayName = "ChatMessage";
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtwa1dBPT06NmJhZDM0MjY=
