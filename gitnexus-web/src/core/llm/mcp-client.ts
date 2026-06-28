// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNSVFRRPT06ZjgyZGQ4OGE=

/**
 * MCP (Model Context Protocol) Client — Backend Proxy Mode
 *
 * Instead of connecting to MCP servers directly from the browser (which fails
 * due to CORS on remote servers), we route all MCP calls through the backend:
 *
 *   Frontend ──→ Backend ──→ MCP Server (Tavily, Brave, etc.)
 *
 * This allows the backend (Node.js/Python) to handle connections without
 * browser CORS restrictions, while keeping the agent running in the frontend.
 */

import { DynamicStructuredTool } from '@langchain/core/tools';
import type { StructuredToolInterface } from '@langchain/core/tools';
import { z } from 'zod';
import type { McpServerConfig } from './types';
import { fetchMcpTools, callMcpTool } from '../../services/backend-client';
// @ts-expect-error  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNSVFRRPT06ZjgyZGQ4OGE=

/**
 * Convert a JSON Schema to a Zod schema.
 * Handles common MCP tool input schemas.
 */
function jsonSchemaToZod(schema: unknown): z.ZodTypeAny {
  if (!schema || typeof schema !== 'object') {
    return z.any();
  }

  const s = schema as Record<string, unknown>;

  // Handle enum
  if (Array.isArray(s.enum) && s.enum.length > 0 && s.enum.every((v) => typeof v === 'string')) {
    const desc = typeof s.description === 'string' ? s.description : undefined;
    const zEnum = z.enum(s.enum as [string, ...string[]]);
    return desc ? zEnum.describe(desc) : zEnum;
  }

  // Handle anyOf / oneOf as union
  const variants = (s.anyOf ?? s.oneOf ?? []) as unknown[];
  if (Array.isArray(variants) && variants.length > 0) {
    const unionSchemas = variants.map((v) => jsonSchemaToZod(v));
    if (unionSchemas.length === 1) return unionSchemas[0];
    return z.union(unionSchemas as [z.ZodTypeAny, z.ZodTypeAny, ...z.ZodTypeAny[]]);
  }

  const type = s.type as string | undefined;
  const description = typeof s.description === 'string' ? s.description : undefined;

  let result: z.ZodTypeAny;

  switch (type) {
    case 'string':
      result = z.string();
      break;
    case 'number':
      result = z.number();
      break;
    case 'integer':
      result = z.number().int();
      break;
    case 'boolean':
      result = z.boolean();
      break;
    case 'array': {
      const itemSchema = jsonSchemaToZod(s.items);
      result = z.array(itemSchema);
      break;
    }
    case 'object': {
      const properties = (s.properties ?? {}) as Record<string, unknown>;
      const required = Array.isArray(s.required) ? (s.required as string[]) : [];
      const shape: Record<string, z.ZodTypeAny> = {};
      for (const [key, propSchema] of Object.entries(properties)) {
        let field = jsonSchemaToZod(propSchema);
        if (!required.includes(key)) {
          field = field.optional();
        }
        shape[key] = field;
      }
      result = z.object(shape).passthrough();
      break;
    }
    case 'null':
      result = z.null();
      break;
    default:
      result = z.any();
  }

  return description ? result.describe(description) : result;
}

/**
 * Build a LangChain tool from a backend-returned MCP tool definition.
 * The tool's invoke() routes through the backend proxy.
 */
function createMcpLangChainTool(
  server: McpServerConfig,
  toolDef: {
    name: string;
    description: string;
    schema: Record<string, unknown>;
    server_id: string;
  },
): StructuredToolInterface {
  const zodSchema = jsonSchemaToZod(toolDef.schema);

  // Ensure the schema is a ZodObject (tools expect object schemas for args)
  const objectSchema =
    zodSchema instanceof z.ZodObject ? zodSchema : z.object({ input: zodSchema });

  return new DynamicStructuredTool({
    name: toolDef.name,
    description: toolDef.description || `MCP tool: ${toolDef.name}`,
    schema: objectSchema as any,
    func: async (args: Record<string, unknown>) => {
      try {
        const { result, error } = await callMcpTool(server, toolDef.name, args);
        if (error) {
          return `MCP tool "${toolDef.name}" failed: ${error}`;
        }
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return `MCP tool "${toolDef.name}" failed: ${message}`;
      }
    },
  });
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNSVFRRPT06ZjgyZGQ4OGE=

export interface McpToolFetchResult {
  tools: StructuredToolInterface[];
  errors: string[];
}

/**
 * Manages MCP server tool fetching via backend proxy.
 * No persistent connections — each request creates a temporary backend session.
 */
export class McpToolManager {
  /**
   * Fetch tools from all configured servers through the backend proxy.
   */
  static async createWithServers(configs: McpServerConfig[]): Promise<{
    manager: McpToolManager;
    result: McpToolFetchResult;
  }> {
    const manager = new McpToolManager();
    const errors: string[] = [];

    const enabledServers = configs.filter((s) => s.enabled && (s.url.trim() || s.transport === 'stdio'));
    if (enabledServers.length === 0) {
      return { manager, result: { tools: [], errors: [] } };
    }

    try {
      const { tools: toolDefs, errors: fetchErrors } = await fetchMcpTools(enabledServers);
      errors.push(...fetchErrors);

      const tools: StructuredToolInterface[] = [];
      for (const def of toolDefs) {
        const server = enabledServers.find((s) => s.id === def.server_id);
        if (!server) {
          errors.push(`Server '${def.server_id}' not found for tool '${def.name}'`);
          continue;
        }
        try {
          const lcTool = createMcpLangChainTool(server, def);
          tools.push(lcTool);
        } catch (toolError) {
          const msg = toolError instanceof Error ? toolError.message : String(toolError);
          errors.push(`Failed to convert MCP tool "${def.name}": ${msg}`);
        }
      }

      return { manager, result: { tools, errors } };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      errors.push(`Failed to fetch MCP tools from backend: ${msg}`);
      return { manager, result: { tools: [], errors } };
    }
  }

  /**
   * No-op for backwards compatibility.
   * Backend proxy mode has no persistent connections to clean up.
   */
  async disconnectAll(): Promise<void> {
    // nothing to do
  }
}
// @ts-expect-error  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNSVFRRPT06ZjgyZGQ4OGE=
