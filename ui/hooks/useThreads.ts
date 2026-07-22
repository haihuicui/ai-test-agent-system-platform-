import useSWRInfinite from "swr/infinite";
import type { Thread } from "@langchain/langgraph-sdk";
import { Client } from "@langchain/langgraph-sdk";
import { getConfig } from "@/lib/langgraph/config";
import { resolveDeploymentUrl } from "@/lib/langgraph/client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVc5bk9RPT06OWQ0NzJiN2E=

export interface ThreadItem {
  id: string;
  updatedAt: Date;
  status: Thread["status"];
  title: string;
  description: string;
  assistantId?: string;
}
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVc5bk9RPT06OWQ0NzJiN2E=

const DEFAULT_PAGE_SIZE = 20;
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVc5bk9RPT06OWQ0NzJiN2E=

export function useThreads(props: {
  status?: Thread["status"];
  limit?: number;
  assistantId?: string;
}) {
  const pageSize = props.limit || DEFAULT_PAGE_SIZE;

  return useSWRInfinite(
    (pageIndex: number, previousPageData: ThreadItem[] | null) => {
      const config = getConfig();
      const apiKey =
        config?.langsmithApiKey ||
        process.env.NEXT_PUBLIC_LANGSMITH_API_KEY ||
        "";
      const assistantId = props.assistantId ?? config?.assistantId;

      if (!config) {
        return null;
      }

      // If the previous page returned no items, we've reached the end
      if (previousPageData && previousPageData.length === 0) {
        return null;
      }

      return {
        kind: "threads" as const,
        pageIndex,
        pageSize,
        deploymentUrl: config.deploymentUrl,
        assistantId,
        apiKey,
        status: props?.status,
      };
    },
    async ({
      deploymentUrl,
      assistantId,
      apiKey,
      status,
      pageIndex,
      pageSize,
    }: {
      kind: "threads";
      pageIndex: number;
      pageSize: number;
      deploymentUrl: string;
      assistantId: string;
      apiKey: string;
      status?: Thread["status"];
    }) => {
      const client = new Client({
        apiUrl: resolveDeploymentUrl(deploymentUrl),
        defaultHeaders: apiKey ? { "X-Api-Key": apiKey } : {},
      });

      // Check if assistantId is a UUID (deployed) or graph name (local)
      const isUUID =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          assistantId
        );

      const threads = await client.threads.search({
        limit: pageSize,
        offset: pageIndex * pageSize,
        sortBy: "updated_at" as const,
        sortOrder: "desc" as const,
        status,
        // 已部署的 assistant 使用 UUID，LangGraph 会把 assistant_id 写入 metadata；
        // 本地 dev graph 使用 graph name，metadata 中对应的是 graph_id。
        ...(isUUID
          ? { metadata: { assistant_id: assistantId } }
          : assistantId
          ? { metadata: { graph_id: assistantId } }
          : {}),
      });

      return threads.map((thread): ThreadItem => {
        let title = "无标题对话";
        let description = "";

        try {
          if (thread.values && typeof thread.values === "object") {
            const values = thread.values as any;
            const firstHumanMessage = values.messages.find(
              (m: any) => m.type === "human"
            );
            if (firstHumanMessage?.content) {
              const content =
                typeof firstHumanMessage.content === "string"
                  ? firstHumanMessage.content
                  : firstHumanMessage.content[0]?.text || "";
              title = content.slice(0, 50) + (content.length > 50 ? "..." : "");
            }
            const firstAiMessage = values.messages.find(
              (m: any) => m.type === "ai"
            );
            if (firstAiMessage?.content) {
              const content =
                typeof firstAiMessage.content === "string"
                  ? firstAiMessage.content
                  : firstAiMessage.content[0]?.text || "";
              description = content.slice(0, 100);
            }
          }
        } catch {
          // 回退到使用对话 ID
          title = `对话 ${thread.thread_id.slice(0, 8)}`;
        }

        return {
          id: thread.thread_id,
          updatedAt: new Date(thread.updated_at),
          status: thread.status,
          title,
          description,
          assistantId,
        };
      });
    },
    {
      revalidateFirstPage: true,
      revalidateOnFocus: false,
    }
  );
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVc5bk9RPT06OWQ0NzJiN2E=
