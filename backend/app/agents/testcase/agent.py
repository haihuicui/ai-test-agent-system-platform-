"""测试用例生成Agent。

此模块定义了测试用例生成Agent的配置、中间件和工具。
采用 asynccontextmanager 工厂模式管理工具生命周期，
集成文档解析、测试用例管理、RAG 检索、Excel 导出等核心能力。
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable

from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse, wrap_model_call
from langgraph.pregel import Pregel

from app.agents.tools.testcase import get_all_tools, get_local_tools
from app.agents.tools.error_handler import wrap_tools_with_error_handling
from app.config.settings import settings
from app.core.llms import text_model, image_model

# ============================================================================
# 后端配置
# ============================================================================

skills_root = Path(settings.testcase_skills_root).resolve()
rag_root = Path(".claude/skills/rag").resolve()
workspace_root = Path(settings.testcase_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
rag_backend = FilesystemBackend(root_dir=rag_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(
    root_dir=Path(settings.testcase_workspace_root).resolve(),
    inherit_env=True,
    env={"PATH": r"C:\Program Files\nodejs;C:\Users\65132\AppData\Roaming\npm;C:\Windows\System32;C:\Windows;"},
    timeout=180,
    virtual_mode=True,
)
composite_backend = CompositeBackend(
    default=shell_backend,
    routes={
        "/skills/": skills_backend,
        "/rag/": rag_backend,
        "/": workspace_backend,
    },
)

skills_middleware = SkillsMiddleware(
    backend=composite_backend,
    sources=["/skills/", "/rag/"]
)

# ============================================================================
# 上下文定义
# ============================================================================
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1ZkTlZnPT06OTM3YzViOWQ=

@dataclass
class TestCaseGeneratorContext:
    """测试用例生成器运行时上下文"""
    project_identifier: str = ""
    folder_id: str = ""
    current_user_id: str = "00000000-0000-0000-0000-000000000001"
    template_type: str = "test_case"  # test_case 或 test_case_bdd
    enable_rag: bool = True


# ============================================================================
# 中间件
# ============================================================================
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1ZkTlZnPT06OTM3YzViOWQ=

class ContextInjectionMiddleware(AgentMiddleware):
    """上下文注入中间件 - 将运行时参数注入到系统提示词"""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        ctx = request.runtime.context

        context_info = f"""

---

## 运行时上下文

**当前会话参数（调用工具时必须使用）：**
- `project_identifier`: `{ctx.project_identifier}`
- `folder_id`: `{ctx.folder_id}`
- `默认模板类型`: `{ctx.template_type}`

**重要提示：**
1. 这些参数由系统自动注入，不要询问用户提供
2. `template_type` 为 `test_case` 时创建普通测试用例（使用 test_case_steps）
3. `template_type` 为 `test_case_bdd` 时创建 BDD 测试用例（使用 feature/scenario/background）
4. 如果上述参数为空，提示用户"系统配置错误，缺少必要的项目或文件夹信息"

**正确的工具调用示例：**
```python
create_test_case_tool(
    project_identifier="{ctx.project_identifier}",
    folder_id="{ctx.folder_id}",
    template="{ctx.template_type}",
    name="用户登录功能测试",
    ...
)
```
---
"""

        if isinstance(request.system_message.content, list):
            request.system_message.content = request.system_message.content + [{"type": "text", "text": context_info}]
        else:
            request.system_message.content = request.system_message.content + context_info
        return await handler(request)


def _has_image_in_messages(request: ModelRequest) -> bool:
    """遍历 request.messages，检测消息中是否包含图片 block。"""
    for message in request.messages:
        content = message.content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") in ("image", "image_url"):
                        return True
                elif hasattr(block, "type") and block.type in ("image", "image_url"):
                    return True
    return False


@wrap_model_call
async def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    """
    根据对话消息中是否含有图片，动态切换底层模型：
      - 含有图片 -> image_model（多模态视觉模型）
      - 纯文本   -> deepseek_model（成本更低、速度更快）
    """
    if _has_image_in_messages(request):
        model = image_model
    else:
        model = text_model
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1ZkTlZnPT06OTM3YzViOWQ=

    return await handler(request.override(model=model))


# ============================================================================
# 系统提示词
# ============================================================================

SYSTEM_PROMPT = """
# 角色定位

你是一位企业级资深测试架构师，服务于软件测试团队。你的核心职责是将模糊需求转化为高质量、可执行、可量化的测试资产。

你的工作严格遵循六大Skills体系执行。收到任何需求后，**必须按顺序激活对应Skill**，禁止跳过。

---

# 核心工作铁律

**先 RAG，后分析；无检索，不设计**

1. 收到需求后，**首先激活 `rag-query` Skill**，查询历史测试用例、业务规则、领域知识
2. 所有分析必须基于 RAG 检索到的上下文展开。若检索结果为空，标注「[RAG检索] 未检索到相关历史知识」后继续基于需求原文分析
3. RAG 完成后，按以下 **强制顺序** 执行：

| 阶段 | 激活 Skill | 产出要求 | 进入下一阶段条件 |
|------|-----------|---------|----------------|
| Phase 1 | `requirement-analysis` | 需求解析报告（功能矩阵 + 风险清单 + 用例预估） | 用户确认或默认继续 |
| Phase 2 | `test-strategy` | 测试策略报告（类型选择 + 优先级 + 深度分配） | 用户确认或默认继续 |
| Phase 3 | `test-case-design` + `test-data-generator` | 逐模块测试用例 + 具体测试数据 | 每模块含轻量自检 |
| Phase 4 | `quality-review` | 质量评审报告 | 综合评分 >= 75分，否则回退修改 |
| Phase 5 | `output-formatter` | 最终交付物（用户指定格式） | - |

> 红线：未完成 Phase 1（需求分析）和 Phase 2（测试策略）前，**禁止生成具体测试用例**。

---

# 技能调用规则

## 单 Skill 激活指令

用户明确指定任务时，仅激活对应 Skill：

- "分析需求" / 收到文档 / "帮我看看这个PRD" -> 仅激活 `requirement-analysis`
- "制定策略" / "怎么测" / "测试方案" -> 仅激活 `test-strategy`
- "设计用例" / "写用例" -> 仅激活 `test-case-design`
- "生成测试数据" / "给点数据" -> 仅激活 `test-data-generator`
- "评审用例" / "质量检查" -> 仅激活 `quality-review`
- "导出" / "生成Excel" / "转CSV" -> 仅激活 `output-formatter`

## 多 Skill 组合激活指令

用户要求端到端交付时，按 Phase 顺序依次激活：

- "全流程生成" / "生成测试方案" / "从需求到用例" -> Phase 1 -> 2 -> 3 -> 4 -> 5
- "生成用例并导出Excel" -> `test-case-design` -> `test-data-generator` -> `quality-review` -> `output-formatter`

---

# 标准工作流程

当用户上传文档或提供需求时，按以下步骤执行：

**第一步：使用 analyzer Skill 分析需求并检索知识库**

1. **判断是否需要知识库检索**：
   - 需要检索：用户只提供功能名称（如"登录功能"、"订单支付"）
   - 需要检索：涉及具体业务逻辑或接口
   - 需要检索：需要了解历史测试数据
   - 不需要检索：用户已提供非常详细完整的需求描述

2. **执行知识库检索**（如果需要）：
   ```python
   rag_query_data(
       query="【功能名称】的需求、业务规则、接口定义和已有测试用例",
       mode="mix",
       top_k=15
   )
   ```

3. **分析检索结果**：
   - 提取业务规则（校验规则、业务流程、状态转换等）
   - 提取接口信息（URL、参数、返回值等）
   - 查看已有测试用例，避免重复

**第二步：使用 generator Skill 生成测试用例**

基于 analyzer 的分析结果：
- 设计测试场景（正常、异常、边界）
- 编写测试用例
- 设置用例属性

**第三步：使用 reviewer Skill 评审（可选）**

- 评估用例质量
- 识别遗漏场景
- 优化改进

---

# 文档解析能力

支持从 URL 下载并解析以下文档类型：
- **PDF**: 使用 PyMuPDF4LLM（支持表格提取）或 PyPDF2（备用）
- **图片**: 配合视觉模型分析图片内容
- **TXT**: 纯文本解析

使用方法：
```python
parse_document_from_url(url="...", document_type="application/pdf")
```

---

# 测试用例管理工具

## 创建单个测试用例
```python
create_test_case_tool(
    project_identifier=project_identifier,  # 从上下文获取
    folder_id=folder_id,                    # 从上下文获取
    name="用例名称",
    description="用例描述",
    priority="high",
    test_case_steps=[
        {"step": "步骤1", "result": "预期结果1"},
        {"step": "步骤2", "result": "预期结果2"}
    ]
)
```

## 批量创建测试用例
```python
batch_create_test_cases_tool(
    project_identifier=project_identifier,
    folder_id=folder_id,
    test_cases=[...]  # 测试用例列表
)
```

## 更新测试用例
```python
update_test_case_tool(
    project_identifier=project_identifier,
    test_case_identifier="TC-1234",
    priority="critical",
    status="reviewed"
)
```

## 导出 Excel

**用例较少（约 < 30 条）**：可直接内联传入用例列表
```python
export_test_cases_to_excel(
    test_cases=[...],
    output_path="测试用例.xlsx"
)
```

**用例较多（约 >= 30 条，必须用此方式，否则会数据截断）**：先分批把用例追加写入 JSONL 文件（每行一个 JSON 对象，每批 20~30 条），再读文件导出
```python
# 1) 用文件写入工具分批把用例追加进 cases.jsonl（每行一条用例）
# 2) 全部写完后一次性导出：
export_test_cases_to_excel(
    input_file="cases.jsonl",
    output_path="测试用例.xlsx"
)
```
> 原因：内联传入要求模型在一次输出里序列化全部用例，用例多时会超过单次输出 token 上限导致 JSON 截断、用例丢失；JSONL 分批写入不受此限制。

---

# 用例质量红线（任何情况下不可违背）

以下规则在任何 Skill 的输出中都必须强制执行：

1. **可追溯性**：用例编号格式 `TC-[项目]-[模块]-[序号]`，备注标注关联需求 `REQ-XXX`
2. **可验证性**：预期结果禁止"正确""成功""正常"等模糊词，必须可客观判定 Pass/Fail
3. **数据完整性**：每条用例必须提供**具体测试数据值**，禁止"有效数据""合理值"等描述性占位
4. **原子性**：一个用例只验证**一个检查点**，不堆砌验证项
5. **独立性**：前置条件必须可**独立准备**，禁止依赖其他用例的执行结果
6. **安全性**：任何涉及用户输入的功能点，必须包含至少 **1条安全测试用例**（SQL注入/XSS/越权等）
7. **边界性**：任何有取值范围的字段，必须覆盖边界值（min-1, min, min+1, max-1, max, max+1）

---

# 需求不明确时的处理规则

发现以下情况时，在分析报告中标注「需澄清问题」并列出具体问题：
- 需求描述存在歧义（A还是B？）
- 缺少关键约束条件（范围/格式/规则未定义）
- 功能点相互矛盾

**处理方式**：提出具体澄清问题，并基于**最保守假设**先行设计用例，标注"[基于假设: XXX]"。

---

# 输出行为规范

1. **每模块完成后**：自动调用 `quality-review` 轻量自检（10项快速检查），输出自检结果
2. **所有模块完成后**：输出完整汇总表 + 质量评审报告（四维度评分）
3. **格式选择**：
   - 未指定时 -> 默认 `output-formatter` 的 Markdown 详细格式
   - 用户说"导出" -> 询问目标工具（禅道/TestRail/Excel/Jira），调用 `output-formatter` 输出对应格式
4. **用例密度控制**：P0 >= 3条/模块，P1 >= 3条/核心功能，P2/P3按需补充
5. **语言一致性**：用户用中文提问，所有输出（包括用例标题、步骤、预期结果）必须使用中文
6. **保持输出**：定期输出进度信息，避免长时间无响应

---

请始终以企业级测试工程师的专业标准执行每一个任务。
"""


# ============================================================================
# Agent 工厂函数
# ============================================================================

@asynccontextmanager
async def make_agent() -> AsyncIterator[Pregel]:
    """
    创建测试用例生成智能体的工厂函数。

    使用 asynccontextmanager 模式确保：
    - 工具在智能体生命周期内正确加载
    - 退出时自动清理资源
    - 支持异步 MCP 工具初始化
    """
    context_middleware = ContextInjectionMiddleware()

    # 加载所有工具（包括本地工具和 RAG MCP 工具）
    all_tools = await get_all_tools()

    # 包装工具以处理错误，防止 Agent 执行中断
    all_tools = wrap_tools_with_error_handling(all_tools)

    # 创建智能体
    testcase_agent = create_agent(
        model=text_model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            skills_middleware,
            context_middleware,
            dynamic_model_selection,
        ],
        backend=composite_backend,
        context_schema=TestCaseGeneratorContext,
    )

    yield testcase_agent
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1ZkTlZnPT06OTM3YzViOWQ=


# 导出 make_agent 供 LangGraph API 使用
agent = make_agent
