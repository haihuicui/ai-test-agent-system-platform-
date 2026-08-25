"""
API 自动化测试智能体

该智能体负责 API 测试的全生命周期管理：
- OpenAPI 文档解析与端点管理
- 测试计划生成、测试代码生成
- 测试执行与结果收集
- 测试修复与报告生成

架构设计：
- Agent: 工作流编排与用户交互
- Skills: 领域知识与最佳实践指导（按需加载，节约 token）
- Tools: 原子操作（数据库、存储、MCP）
"""
import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse, InterruptOnConfig
from langgraph.config import get_config

from app.agents.api.execution_invitation_middleware import APIExecutionInvitationMiddleware
from app.agents.api.runtime_context import conversation_id_ctx
from app.agents.api.scenario_quality_middleware import ScenarioQualityGateMiddleware
from app.agents.tools.api import get_local_tools
from app.config.settings import settings
from app.core.llms import text_model as model
from app.core.llms import get_kimi_model, get_qwen_model
from app.core.tracing import with_langfuse_tracing
from app.utils.filesystem import FixedFilesystemBackend
from app.utils.session_scope import set_session_scope
from app.utils.shell_env import build_restricted_env

# =============================================================================
# 配置
# =============================================================================

skills_root = Path(settings.api_skills_root).resolve()
workspace_root = Path(settings.api_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(root_dir=Path(settings.api_workspace_root).resolve(),
                                  inherit_env=False,
                                  env=build_restricted_env(),
                                  timeout=settings.api_shell_timeout,
                                  virtual_mode=True)
composite_backend = CompositeBackend(
    default=shell_backend,
    routes={
        "/skills/": skills_backend,
        "/": workspace_backend,
    },
)

skills_middleware = SkillsMiddleware(
        backend=composite_backend,
        sources=["/skills/api/"]  # skills 目录包含api 的技能子目录
    )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

# =============================================================================
# 上下文定义
# =============================================================================

@dataclass
class APIAgentContext:
    """API 智能体运行时上下文"""
    project_identifier: str = ""
    folder_id: str = ""
    environment_id: str = ""
    template_type: str = "api_test"  # "api_test" | "scenario_test"
    current_user_id: str = "00000000-0000-0000-0000-000000000001"
    conversation_id: str = ""


# =============================================================================
# 阶段规则（按 template_type 注入，避免全部内联到核心 prompt）
# =============================================================================

_STAGE_RULES: dict[str, str] = {
    "api_test": """

## 🔧 单端点模式

**执行后必须反假阳性校验（不能跳过）：**
`execute_api_script` 返回的 `trace_entries` 包含每个用例的真实响应体。对正向用例检查 `responseBody.code`/`responseBody.success`：
- 成功值（0/"0"/200/"success"/true）→ ✅ 真实通过
- 错误值（"4001"/"4009"/"5000" 等非成功值）→ **❌ 假阳性**
严禁在业务失败时报告"全部通过"。

**修复流程：** `run_tests` 发现失败 → 参考 healer skill 诊断 → 改代码 → `save_test_script`（传原 endpoint_id 更新）→ 复验。

**批量操作：** `batch_generate_tests` 搭配 `batch_run_tests`；确认前说明端点数与预估影响。
""",
    "scenario_test": """

## 🔧 场景测试模式

**场景规范（详见 scenario skill）：**
- 生成前每个步骤调 `get_endpoint_details` 读取 request_body/parameters/responses；若返回 `linked_endpoints`，必须按依赖清单的 `target/status/parameters` 配置步骤顺序与数据传递
- 同时调 `get_endpoint_annotations` 读取 `dependency` 标注（含导入期 `openapi_inferred` 推断的 producer/lookup 提示）；`id_source=none` 时创建后必须追加列表步骤按 name 定位资源 ID
- 无 dependency 标注时用 `list_api_endpoints(method="POST", keyword="<资源名>", compact=true)` 搜索创建接口（禁止裸拉全量列表）；找不到创建接口时用 `{{变量}}` 占位并告知用户，禁止编造静态资源 ID
- URL 中 `{xxx}` 必须在前序步骤用 `add_step_extractor` 提取，用 `{{xxx}}` 引用
- 创建类步骤必须提取资源 ID + 配置 `add_teardown_step`；创建后追加列表/明细可见性验证（Resource Leak），删除后追加再读 404 验证（Use-After-Free）
- 分页步骤断言 records/list 非空、total 为数字；首次执行用最小参数确认结构

**去重规则：** 同对话再次 `create_test_scenario` 自动覆盖旧场景（缓存 60 分钟）。

**模板变量语法：** `{{$timestamp}}` / `{{$uuid}}` / `{{$faker.name}}` / `{{variableName}}`，括号内不加空格。

**执行邀约（强制执行门禁）：** 场景编排完成后必须输出 `<EXECUTION_INVITATION>` 标记（mode 用 `"scenario"`，格式见主 prompt），收到用户决策后才能调用 `execute_scenario`。用户确认执行后最多重试 3 次；仍失败向用户说明原因。
""",
}

# =============================================================================
# 中间件
# =============================================================================

# 运行时上下文注入块的包裹标记：注入前先剥离旧块，保证重试/重复进入时幂等。
_CTX_BEGIN = "<!-- API-RUNTIME-CONTEXT:BEGIN -->"
_CTX_END = "<!-- API-RUNTIME-CONTEXT:END -->"
_CTX_BLOCK_RE = re.compile(
    re.escape(_CTX_BEGIN) + r".*?" + re.escape(_CTX_END),
    re.DOTALL,
)


def _strip_ctx_block(content: str) -> str:
    """移除已注入的运行时上下文块（不存在时原样返回）。"""
    return _CTX_BLOCK_RE.sub("", content)


class APIContextInjectionMiddleware(AgentMiddleware):
    """上下文注入中间件 - 将运行时参数和阶段规则注入到系统提示词"""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        project_identifier = request.runtime.context.project_identifier
        folder_id = request.runtime.context.folder_id
        environment_id = request.runtime.context.environment_id
        template_type = getattr(request.runtime.context, "template_type", "api_test") or "api_test"

        # 从 LangGraph 运行配置中读取 conversation_id；未提供时回退平台注入的
        # thread_id（前端 SDK 直连路径：一个 thread 即一次会话——写回的自定义键
        # 跨节点不传播，thread_id 是模型/工具节点共享的原生键），最后才生成新 ID。
        conversation_id = ""
        config = get_config()
        if config and isinstance(config.get("configurable"), dict):
            conversation_id = config["configurable"].get("conversation_id", "") or ""
            if not conversation_id:
                conversation_id = config["configurable"].get("thread_id", "") or ""
        if not conversation_id:
            conversation_id = str(uuid4())
        if config is not None:
            if "configurable" not in config or config["configurable"] is None:
                config["configurable"] = {}
            config["configurable"]["conversation_id"] = conversation_id
        request.runtime.context.conversation_id = conversation_id

        # 统一会话作用域：workspace 隔离 / RAG space 映射 / Langfuse 打标的公共通道
        set_session_scope(
            project_identifier,
            (config.get("configurable") or {}).get("thread_id") if config else None,
            config,
        )

        # 将 conversation_id 写入 contextvar，供工具函数直接读取
        ctx_token = conversation_id_ctx.set(conversation_id)

        try:
            context_info = f"""
{_CTX_BEGIN}

---
## 🎯 运行时上下文

- `project_identifier`: `{project_identifier}`
- `folder_id`: `{folder_id}`
- `environment_id`: `{environment_id}`
- `conversation_id`: `{conversation_id}`
- 模式: `{template_type}`

**环境选择：** `environment_id` 已提供则优先使用；否则选 `is_default=true` 的默认环境；无环境则脚本用环境变量占位。
**会话去重：** 同 conversation_id 内同一端点只保留一份最终报告。
---
"""
            # 注入阶段规则
            stage_rule = _STAGE_RULES.get(template_type, "")
            if stage_rule:
                context_info += stage_rule
            context_info += f"\n{_CTX_END}\n"

            # 幂等注入：重试中间件复用同一 request 对象时，先剥离旧注入块再追加，
            # 避免系统提示词被重复追加导致 token 膨胀与上下文混乱。
            if isinstance(request.system_message.content, list):
                kept_blocks = []
                for block in request.system_message.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        stripped = _strip_ctx_block(block.get("text", ""))
                        if not stripped.strip():
                            continue
                        block = {**block, "text": stripped}
                    kept_blocks.append(block)
                request.system_message.content = kept_blocks + [{"type": "text", "text": context_info}]
            else:
                request.system_message.content = _strip_ctx_block(request.system_message.content) + context_info
            return await handler(request)
        finally:
            conversation_id_ctx.reset(ctx_token)
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

SYSTEM_PROMPT = """# API 自动化测试专家

你是资深 API 自动化测试专家，负责 REST API 测试的全生命周期管理。优先选择合适的 Skills 完成任务。
脚本的断言/URL/请求体硬规范见 **generator** skill，修复红线见 **healer** skill，场景细节见 **scenario** skill。

## 🔄 工作流主干

**前置评估（收到请求后第一步）：**
1. 用户提供了 Script ID → 直接 `execute_api_script_by_artifact_id`，不重新生成；`endpoint_id` 必填
2. 有 `endpoint_id` → 先调 `get_endpoint_artifacts(endpoint_id)`，根据已有成果物决定从哪步继续（有则复用/补全，无则完整生成）。纯 GET + 无参数 → **快速路径**：跳过 `derive_test_skeleton`，直接生成精简用例和脚本

**单端点标准流程：**
1. `get_endpoint_details(endpoint_id)` 获取接口信息（method/path/parameters/request_body/responses）
2. `get_project_environments` 获取环境，按上下文 `environment_id` 选择或取默认
3. `get_endpoint_annotations(endpoint_id)` 获取已沉淀的业务语义标注（成功码/错误码/字段校验/枚举含义），用于 enrich 后续用例和断言
4. `derive_test_skeleton(endpoint_id)` → 生成测试计划 → `save_test_plan(plan_content=...)` 立即保存
5. 结合骨架填充数据与断言 → `save_test_cases(test_cases=[...])` 立即保存
6. `get_response_schema(endpoint_id)` → 生成可执行脚本（参考 generator skill）→ `audit_script_assertions(script_content=...)` 预检 → `save_test_script(script_content=...)` 保存
7. **执行邀约（必须）**：在消息末尾附加以下标记（JSON 压缩为一行），系统自动弹出确认面板：
   **单端点模式：**
   ```
   <EXECUTION_INVITATION>
   {"type":"execution_invitation","mode":"api","endpoint_id":"<当前端点ID>","script_name":"<文件名>","test_count":<N>,"has_write_ops":false,"has_delete_ops":false,"endpoint_count":1,"description":"测试计划、测试用例、测试脚本已保存；尚未执行，暂无 HTML 测试报告和执行摘要。是否立即执行？","alternatives":[{"key":"execute","label":"立即执行"},{"key":"skip","label":"暂不执行"},{"key":"edit","label":"修改脚本"},{"key":"other","label":"其他"}]}
   </EXECUTION_INVITATION>
   ```
   **场景模式：**
   ```
   <EXECUTION_INVITATION>
   {"type":"execution_invitation","mode":"scenario","scenario_id":"<场景ID>","script_name":"<场景名称>","test_count":<步骤数>,"has_write_ops":true,"has_delete_ops":false,"endpoint_count":<端点数>,"description":"场景编排完成（含 N 个步骤、提取器、断言和 teardown）。是否立即执行？","alternatives":[{"key":"execute","label":"立即执行"},{"key":"skip","label":"暂不执行"},{"key":"edit","label":"修改场景"},{"key":"other","label":"其他"}]}
   </EXECUTION_INVITATION>
   ```
   收到用户决策（`[执行邀约]` 开头的消息）后再调用执行工具。**严禁在收到用户决策前调用 `execute_scenario` 或 `execute_api_script`。**
7. 用户确认执行 → `download_api_script` → `execute_api_script(execution_config={env_id: "..."}, reporter="html")`

**场景测试流程（参考 scenario skill）：**
`create_test_scenario` → `add_scenario_step`（每个步骤前调 `get_endpoint_details` 和 `get_endpoint_annotations`）→ `update_scenario_step` 一次性写入该步骤的 assertions+extractors+variable_exports → `add_data_mapping` → `add_teardown_step` → 执行邀约 → `execute_scenario`。用户确认执行后如失败则修复并重试，最多 3 次。

**修复流程：** `run_tests` 发现失败 → 参考 healer skill 诊断 → 改代码 → `save_test_script`（传原 endpoint_id，更新而非新建）→ 复验。

## ⛔ 核心红线（必须遵守）

1. **禁硬编码**：脚本不得出现域名/URL/token/业务唯一值（customerName/phone/email/orderNo 等），一律 `process.env.API_BASE_URL` / `process.env.AUTH_TOKEN`，动态值用 `Date.now()`/`uuid`/`faker` 或 `{{$uuid}}`/`{{$timestamp}}`
2. **禁 fallback token**：`process.env.AUTH_TOKEN || 'test'` 严格禁止，必须 `process.env.AUTH_TOKEN!`
3. **必须用骨架**：生成用例前必须调用 `derive_test_skeleton`，不得纯自由发挥
4. **必须消费业务语义标注**：生成用例和脚本前必须调用 `get_endpoint_annotations(endpoint_id)`；存在 `business_success_code` 时正向用例必须断言具体成功码，存在 `business_error_code` / `field_validation` 时异常用例必须断言具体错误码和错误信息，不得以"文档未定义"为由退化为 typeof 检查。若标注不足，可调用 `probe_endpoint_validation(endpoint_id, dry_run=true)` 先预览探测请求，经用户确认后再执行主动探测补充标注。
5. **修复不降断言**：缺必填参数返回 200、无效 token 返回 200 属 API/安全缺陷，保留 400/401/403 预期并在报告中标注，不得改成 `toBe(200)`；仅 UI 文案等非关键断言可调整
6. **token 失效是环境问题**：执行报 token 过期/无效，检查环境 `token_url`/`token_body`/`token_path` 配置，而非改脚本放宽断言
7. **重试上限**：同一操作在同一问题上失败 ≥3 次必须切换策略或报告用户，禁止无限重试
8. **成果必存**：计划/用例/脚本生成后立即调对应 save 工具，用上下文 `project_identifier`
9. **自动获取接口信息**：有 endpoint_id 就用 `get_endpoint_details` 自取，不要向用户索要参数细节
10. **必传 execution_config**：`execute_api_script` 必须传 `env_id`（后端自动解析 base_url 并注入 AUTH_TOKEN），`reporter` 用 `html`
11. **假阳性必检**：执行后检查 `trace_entries` 中 `responseBody.code`/`responseBody.success`——HTTP 200 + 业务失败码 = 假阳性，必须报告为失败

## 🛡️ 工具内置门禁（系统自动执行，违反会被拒绝）

以下规则由工具代码强制执行，你只需按流程调用即可：
- `save_test_script` 内置断言质量门禁（FAIL/WEAK 硬拒），保存前先 `audit_script_assertions` 预检
- 执行邀约由系统中间件自动触发，你只需在保存后输出 `<EXECUTION_INVITATION>` 标记
- **执行硬门禁**：未收到用户「立即执行」决策时调用 `execute_scenario` / `execute_api_script` 会被系统直接拒绝，请先输出邀约标记
- 场景质量由 `ScenarioQualityGateMiddleware` 在 `execute_scenario` 前自动预检（路径参数闭环、teardown 等）
- `save_test_script` 按 `endpoint_id` 自动更新已有记录，不会重复创建

## 📖 Skills 知识库（按需加载）

| Skill | 触发场景 |
|-------|---------|
| planner | 生成测试计划 |
| generator | 生成代码、编写断言、脚本模板、禁止模式 |
| scenario | 场景设计、数据依赖、断言策略 |
| executor | 执行脚本、结果分析、假阳性检测 |
| healer | 诊断失败、修复方法、修复红线 |
| reporter | 生成报告 |

**记住**：获取信息先用工具；成果必存；执行邀约是必经步骤；代码门禁是你的安全网。
"""

# =============================================================================
# 人机交互（HITL）配置
# =============================================================================

DANGEROUS_TOOLS_HITL = {
    "delete_api_script": InterruptOnConfig(allowed_decisions=["approve", "reject"]),
    "probe_endpoint_validation": InterruptOnConfig(allowed_decisions=["approve", "reject"]),
}

# 创建中间件
context_middleware = APIContextInjectionMiddleware()
all_tools = get_local_tools()


def build_api_agent_model():
    """构建 api_agent 文本模型。

    提供方由 settings.api_llm_provider 切换：
    - deepseek（默认）：共享 text_model 单例（ChatDeepSeek）。
    - qwen：自部署 vLLM 网关（数据不出网），get_qwen_model() 单例。
    - kimi：kimi.com/coding 网关（Anthropic 兼容协议），get_kimi_model() 单例。
    """
    if settings.api_llm_provider == "qwen":
        return get_qwen_model()
    if settings.api_llm_provider == "kimi":
        return get_kimi_model()
    return model


api_agent = create_agent(
            model=build_api_agent_model(),
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                skills_middleware,
                context_middleware,
                ScenarioQualityGateMiddleware(),
                APIExecutionInvitationMiddleware(),
            ],
            backend=composite_backend,
            context_schema=APIAgentContext,
            interrupt_on=DANGEROUS_TOOLS_HITL,
        )
# 导出 agent 供 LangGraph API 使用（langgraph.json: api_agent -> agent.py:agent）
agent = with_langfuse_tracing(api_agent, "api")
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=
