"""
MCP 代理路由

为前端提供 MCP 工具的代理访问，解决浏览器 CORS 限制。
后端通过 langchain_mcp_adapters 连接 MCP 服务器，前端只需访问同域后端 API。
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

router = APIRouter(prefix="/mcp", tags=["MCP 代理"])
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjBSaGRnPT06MjlmNDE5NDc=


class McpServerConfig(BaseModel):
    id: str
    name: str
    url: str = ""
    enabled: bool = True
    transport: Literal["sse", "streamableHttp", "stdio"] = "sse"
    command: str | None = None
    args: list[str] | None = None


class McpToolsRequest(BaseModel):
    servers: list[McpServerConfig]


class McpToolDef(BaseModel):
    name: str
    description: str
    schema: dict[str, Any]
    server_id: str


class McpToolsResponse(BaseModel):
    tools: list[McpToolDef]
    errors: list[str]

# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjBSaGRnPT06MjlmNDE5NDc=

class McpCallRequest(BaseModel):
    server: McpServerConfig
    tool_name: str
    args: dict[str, Any]


class McpCallResponse(BaseModel):
    result: str = ""
    error: str | None = None


def _build_connection_config(server: McpServerConfig) -> dict[str, Any]:
    """将前端传来的 MCP 服务器配置转换为 MultiServerMCPClient 连接配置。"""
    if server.transport == "stdio":
        return {
            "transport": "stdio",
            "command": server.command or "",
            "args": server.args or [],
        }
    else:
        transport_type = "http" if server.transport == "streamableHttp" else "sse"
        return {
            "transport": transport_type,
            "url": server.url,
        }


@router.post("/tools", response_model=McpToolsResponse)
async def list_mcp_tools(request: McpToolsRequest):
    """
    连接 MCP 服务器并返回可用工具列表。

    每个工具附带 server_id，以便前端在调用时知道该通过哪个服务器路由。
    """
    enabled_servers = [s for s in request.servers if s.enabled]
    if not enabled_servers:
        return McpToolsResponse(tools=[], errors=[])

    all_tools: list[McpToolDef] = []
    errors: list[str] = []

    for server in enabled_servers:
        try:
            connection = _build_connection_config(server)
            client = MultiServerMCPClient({server.id: connection})
            tools = await client.get_tools(server_name=server.id)
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjBSaGRnPT06MjlmNDE5NDc=

            for tool in tools:
                schema: dict[str, Any] = {}
                if hasattr(tool, "args_schema") and tool.args_schema is not None:
                    if hasattr(tool.args_schema, "model_json_schema"):
                        schema = tool.args_schema.model_json_schema()
                    elif isinstance(tool.args_schema, dict):
                        schema = tool.args_schema
                    elif hasattr(tool.args_schema, "schema"):
                        schema = getattr(tool.args_schema, "schema", {})

                all_tools.append(
                    McpToolDef(
                        name=tool.name,
                        description=tool.description or "",
                        schema=schema,
                        server_id=server.id,
                    )
                )
        except Exception as e:
            errors.append(
                f"Failed to load tools from '{server.name}' ({server.url}): {str(e)}"
            )

    return McpToolsResponse(tools=all_tools, errors=errors)
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjBSaGRnPT06MjlmNDE5NDc=


@router.post("/call", response_model=McpCallResponse)
async def call_mcp_tool(request: McpCallRequest):
    """
    调用指定的 MCP 工具。

    后端创建临时连接，执行工具调用后立刻断开。
    """
    try:
        connection = _build_connection_config(request.server)
        client = MultiServerMCPClient({request.server.id: connection})
        tools = await client.get_tools(server_name=request.server.id)

        target_tool = next(
            (t for t in tools if t.name == request.tool_name), None
        )
        if target_tool is None:
            return McpCallResponse(
                result="",
                error=f"Tool '{request.tool_name}' not found in server '{request.server.id}'",
            )

        result = await target_tool.ainvoke(request.args)
        return McpCallResponse(
            result=result if isinstance(result, str) else str(result),
            error=None,
        )
    except Exception as e:
        return McpCallResponse(result="", error=str(e))
