"""
Testcase Agent Package

本包是一个基于 LangChain 和 LangGraph 构建的测试用例生成智能体，
用于自动分析需求文档并生成专业、全面的测试用例。

主要功能：
    - 通过 MCP (Model Context Protocol) 连接 RAG 检索服务
    - 解析各类需求文档（PDF、Word、图片、TXT 等）
    - 管理测试用例生命周期（创建、更新、批量操作）
    - 导出测试用例为 Excel 等格式
    - 基于 LLM 生成结构化的测试用例
    - 支持多模态输入（图文混合需求）

架构设计：
    - Agent: 工作流编排与用户交互（asynccontextmanager 工厂模式）
    - Skills: 领域知识与最佳实践指导（按需加载）
    - Tools: 原子操作（测试用例管理、文档解析、RAG 检索、Excel 导出）

使用示例：
    >>> from app.agents.testcase import make_agent
    >>> async with make_agent() as agent:
    ...     result = await agent.ainvoke({
    ...         "messages": [{"role": "user", "content": "请分析这份需求文档并生成测试用例"}]
    ...     })
"""

from app.agents.testcase.agent import make_agent, agent
# fmt: off  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2Y1hoTU53PT06NGM0MzJlYjM=

__all__ = ["make_agent", "agent"]
# pragma: no cover  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2Y1hoTU53PT06NGM0MzJlYjM=
