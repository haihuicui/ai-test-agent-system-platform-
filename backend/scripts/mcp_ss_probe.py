"""直接复现 MCP 链路：run-test-mcp-server -c <ss config> → planner_setup_page → navigate → 看 URL"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    client = MultiServerMCPClient({
        "web_mcp": {
            "transport": "stdio",
            "command": "npx",
            "args": ["playwright", "run-test-mcp-server", "-c",
                     "D:/project/ai-test-agent/backend/workspace/web_mcp/playwright.config.ss-PR-1-b80ec302.js"],
            "cwd": "D:/project/ai-test-agent/backend/workspace/web_mcp",
        }
    })
    async with client.session("web_mcp") as session:
        from langchain_mcp_adapters.tools import load_mcp_tools
        tools = await load_mcp_tools(session)
        by_name = {t.name: t for t in tools}
        r = await by_name["planner_setup_page"].ainvoke({"project": "chromium"})
        print("setup:", str(r)[:120])
        r = await by_name["browser_navigate"].ainvoke({"intent": "验证登录态", "url": "https://xmetrix-sit-15000.chromxhealth.com/gz/customer-management/customers/index"})
        text = str(r)
        for line in text.splitlines():
            if "Page URL" in line:
                print(">>>", line.strip())
        r = await by_name["browser_snapshot"].ainvoke({})
        text = str(r)
        for line in text.splitlines():
            if "Page URL" in line:
                print(">>> after snapshot:", line.strip())

asyncio.run(main())
