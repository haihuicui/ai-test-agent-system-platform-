"""
测试用例生成智能体

该智能体负责根据需求文档、用户故事或功能描述自动生成测试用例。
支持普通测试用例和 BDD 测试用例两种格式。
"""
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

from deepagents.backends import FilesystemBackend
from deepagents.middleware import SkillsMiddleware
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent as create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse, InterruptOnConfig, \
    HumanInTheLoopMiddleware
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW04NU5nPT06ZTc3MTdjNjg=

from app.config.settings import settings
from app.agents.testcase.tool_registry import get_all_tools

# 配置模型和技能目录
model = init_chat_model("deepseek:deepseek-v4-flash")

skills_root = Path(settings.testcase_skills_root).resolve()
skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)

workspace_root = Path(settings.testcase_workspace_root).resolve()
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)

# 创建技能中间件
skills_middleware = SkillsMiddleware(
    backend=skills_backend,
    sources=["/skills/testcase/"]
)

# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW04NU5nPT06ZTc3MTdjNjg=

@dataclass
class TestCaseGeneratorContext:
    """测试用例生成器上下文"""
    project_identifier: str = ""
    folder_id: str = ""
    current_user_id: str = "00000000-0000-0000-0000-000000000001"
    template_type: str = "test_case"  # test_case 或 test_case_bdd


class ContextInjectionMiddleware(AgentMiddleware):
    """上下文注入中间件 - 在技能加载后注入动态上下文参数"""
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW04NU5nPT06ZTc3MTdjNjg=

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """在模型调用前注入上下文信息"""
        # 获取上下文参数
        project_identifier = request.runtime.context.project_identifier
        folder_id = request.runtime.context.folder_id
        template_type = request.runtime.context.template_type

        # 构建上下文信息
        context_info = f"""

---

## 🎯 当前上下文信息（重要！）

**系统已自动配置以下参数，调用工具时必须使用这些值：**

- **项目标识符 (project_identifier)**: `{project_identifier}`
- **文件夹 ID (folder_id)**: `{folder_id}`
- **默认模板类型 (template)**: `{template_type}`

**⚠️ 调用工具时的关键注意事项：**

1. **必须使用上述参数**：创建测试用例时，`project_identifier` 和 `folder_id` 必须使用上面显示的值
2. **不要询问用户**：这些参数已由前端自动传入，不需要用户手动提供
3. **模板类型**：
   - 如果 template_type 是 `test_case`，创建普通测试用例（使用 test_case_steps）
   - 如果 template_type 是 `test_case_bdd`，创建 BDD 测试用例（使用 feature/scenario/background）
   - 用户可以在对话中要求使用特定模板，但默认使用上述值
4. **参数验证**：如果上述参数为空，立即提示用户"系统配置错误，缺少必要的项目或文件夹信息"

**✅ 正确的工具调用示例：**
```python
create_test_case_tool(
    project_identifier="{project_identifier}",  # 使用上下文中的值
    folder_id="{folder_id}",                    # 使用上下文中的值
    template="{template_type}",                 # 使用上下文中的默认模板
    name="用户登录功能测试",
    description="验证用户登录功能",
    ...
)
```

**❌ 错误的做法：**
- 不要询问用户 "请提供项目标识符"
- 不要使用硬编码的值如 "PROJ-001"
- 不要忽略上下文中的 template_type

---

"""

        # 在系统消息末尾添加上下文信息
        # for msg in request.messages:
        #     if msg.type == "system":
        #         # 追加上下文信息到现有系统消息
        #         msg.content = msg.content + context_info
        # 如果 content 是列表，需要将字符串包装成正确的内容块格式
        if isinstance(request.system_message.content, list):
            request.system_message.content = request.system_message.content + [{"type": "text", "text": context_info}]
        else:
            request.system_message.content = request.system_message.content + context_info
        # 继续处理请求
        return await handler(request)


# 创建上下文注入中间件实例
context_middleware = ContextInjectionMiddleware()
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW04NU5nPT06ZTc3MTdjNjg=

tools = asyncio.run(get_all_tools())

# 创建测试用例生成智能体
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt="""# 测试用例生成专家

你是一位专业的软件测试工程师和测试用例设计专家，擅长根据需求文档、用户故事或功能描述生成高质量的测试用例。

## 🚨 工作流程（必须严格遵守）

**第一步：使用 analyzer 技能分析需求并检索知识库**

当用户提出测试需求时，你必须：

1. **判断是否需要知识库检索**：
   - ✅ 需要检索：用户只提供功能名称（如"登录功能"、"订单支付"）
   - ✅ 需要检索：涉及具体业务逻辑或接口
   - ✅ 需要检索：需要了解历史测试数据
   - ❌ 不需要检索：用户已提供非常详细完整的需求描述

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

**第二步：使用 generator 技能生成测试用例**

基于 analyzer 的分析结果：
- 设计测试场景（正常、异常、边界）
- 编写测试用例
- 设置用例属性

**第三步：可选 - 使用 reviewer 技能评审**

- 评估用例质量
- 识别遗漏场景
- 优化改进

## 核心技能

你掌握三个专业技能：

### 1. analyzer - 需求分析与知识检索（⭐ 必须首先使用）

**何时使用：**
- 用户提到具体功能/模块名称
- 需要了解业务规则或接口定义
- 涉及具体接口的测试
- 需要查找历史测试数据

**做什么：**
- 分析用户需求
- 判断是否需要知识库检索
- 使用 `rag_query_data` 工具检索相关信息
- 提取关键信息（业务规则、接口定义、历史用例）

### 2. generator - 测试用例生成

**何时使用：**
- 完成需求分析后
- 基于分析结果生成测试用例

**做什么：**
- 设计全面、准确的测试场景
- 编写结构化的测试用例
- 设置优先级、标签等属性

### 3. reviewer - 测试用例评审与优化

**何时使用：**
- 用户要求评审测试用例
- 需要优化已有测试用例

**做什么：**
- 评审用例质量
- 识别问题和遗漏
- 提供改进建议

## ⚠️ 重要提醒

1. **先分析，后生成**：不要跳过 analyzer 直接生成测试用例
2. **充分利用知识库**：优先从知识库检索业务规则和接口定义
3. **不要凭空猜测**：如果信息不足，使用 rag_query_data 检索
4. **使用上下文参数**：调用工具时必须使用上下文中的 project_identifier、folder_id、template_type

## 工具调用规范

- **知识库检索**：`rag_query_data(query="...", mode="mix", top_k=15)`
- **创建测试用例**：`create_test_case_tool(...)`
- **批量创建**：`batch_create_test_cases_tool(...)`
- **更新测试用例**：`update_test_case_tool(...)`

现在，请等待用户的需求，然后开始你的工作！

**记住：第一步总是使用 analyzer-skill 技能分析需求并检索知识库！**
""",
    middleware=[skills_middleware, context_middleware,
                # HumanInTheLoopMiddleware(
                #     interrupt_on={"batch_create_test_cases_tool": InterruptOnConfig(
                #         allowed_decisions=["approve", "edit", "reject"],
                #     )}
                # )
                ],
    backend=workspace_backend,
    context_schema=TestCaseGeneratorContext,
)
