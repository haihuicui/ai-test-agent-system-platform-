"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhobFp3PT06MWViNmY4MWI=

import * as React from "react";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { X, Minimize2, Maximize2 } from "lucide-react";
import { ClientProvider } from "@/providers/ClientProvider";
import { ChatProvider } from "@/providers/ChatProvider";
import { ChatInterface } from "@/components/langgraph";
import { Assistant } from "@langchain/langgraph-sdk";
import { cn } from "@/lib/utils";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhobFp3PT06MWViNmY4MWI=

interface AIChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialPrompt?: string;
  projectId?: string;
  folderId?: string | null;
  templateType?: string;
  assistantId?: string;
  title?: string;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhobFp3PT06MWViNmY4MWI=

export function AIChatDialog({
  open,
  onOpenChange,
  initialPrompt,
  projectId,
  folderId,
  templateType = "test_case",
  assistantId,
  title = "生成测试用例 - AI 助手",
}: AIChatDialogProps) {
  const [assistant, setAssistant] = React.useState<Assistant | null>(null);
  const [isMinimized, setIsMinimized] = React.useState(false);
  const [threadId, setThreadId] = React.useState<string | null>(null);

  // 初始化 Assistant
  React.useEffect(() => {
    const defaultAssistantId = process.env.NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID || "testcase_generator_agent";
    const finalAssistantId = assistantId || defaultAssistantId;

    setAssistant({
      assistant_id: finalAssistantId,
      graph_id: finalAssistantId,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      config: {
        configurable: {
          // 添加上下文信息，供智能体使用
          project_identifier: projectId || "",
          folder_id: folderId || "",
          template_type: templateType,
        }
      },
      metadata: {},
      version: 1,
      name: templateType === "api_test" ? "API 测试生成助手" : "测试用例生成助手",
      context: {},
    });
  }, [projectId, folderId, templateType, assistantId]); // 当参数变化时重新初始化

  // 每次打开对话框时创建新线程
  React.useEffect(() => {
    if (open) {
      setThreadId(null); // 重置线程ID，创建新线程
      setIsMinimized(false); // 重置最小化状态
    }
  }, [open]);

  const deploymentUrl =
    process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || "http://localhost:2025";
  const apiKey = process.env.NEXT_PUBLIC_LANGSMITH_API_KEY || "";

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        direction="right"
        showCloseButton={false}
        className={cn(
          "w-full sm:max-w-4xl transition-all duration-300 p-0",
          isMinimized ? "sm:max-w-md" : "sm:max-w-4xl"
        )}
        onPointerDownOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between border-b px-6 py-4 bg-background">
          <h2 className="text-lg font-semibold">{title}</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsMinimized(!isMinimized)}
              className="h-8 w-8"
              title={isMinimized ? "展开" : "收起"}
            >
              {isMinimized ? (
                <Maximize2 className="h-4 w-4" />
              ) : (
                <Minimize2 className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onOpenChange(false)}
              className="h-8 w-8"
              title="关闭"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* 聊天界面 */}
        {!isMinimized && assistant && (
          <div className="flex-1 overflow-hidden">
            <ClientProvider deploymentUrl={deploymentUrl} apiKey={apiKey}>
              <ChatProvider activeAssistant={assistant}>
                <ChatInterface
                  assistant={assistant}
                  initialPrompt={initialPrompt}
                  key={threadId || "new"} // 使用 key 强制重新渲染
                />
              </ChatProvider>
            </ClientProvider>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}

// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhobFp3PT06MWViNmY4MWI=
