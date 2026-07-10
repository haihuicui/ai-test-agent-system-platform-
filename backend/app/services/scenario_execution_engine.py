"""
场景执行引擎

负责执行多接口业务流场景测试
"""

import asyncio
import json
import random
import re
import string
import time
import traceback
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

try:
    from faker import Faker
except ImportError:  # pragma: no cover
    Faker = None  # type: ignore
from jsonpath_ng import parse as jsonpath_parse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_endpoint import APIEndpoint
from app.models.test_scenario import (
    ScenarioRun,
    ScenarioStep,
    ScenarioStepResult,
    StepDataMapping,
    TestScenario,
)
from app.services.environment_service import EnvironmentService


class ExecutionContext:
    """执行上下文 - 存储变量和步骤数据"""

    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.step_data: Dict[str, Dict[str, Any]] = {}  # step_id -> extracted_data

    def initialize(self, global_vars: dict, runtime_vars: dict):
        """初始化变量"""
        self.variables = {**global_vars, **runtime_vars}

    def set_variable(self, name: str, value: Any):
        """设置变量"""
        self.variables[name] = value

    def get_variable(self, name: str) -> Any:
        """获取变量"""
        return self.variables.get(name)

    def update_step_data(self, step_id: str, data: dict):
        """更新步骤数据"""
        self.step_data[step_id] = data

    def get_step_data(self, step_id: str, path: str | None = None) -> Any:
        """获取步骤数据"""
        data = self.step_data.get(step_id, {})
        if path:
            return self._extract_by_jsonpath(data, path)
        return data

    def _extract_by_jsonpath(self, data: dict, path: str) -> Any:
        """使用 JSONPath 提取数据"""
        try:
            jsonpath_expr = jsonpath_parse(path)
            matches = jsonpath_expr.find(data)
            if matches:
                return matches[0].value
        except Exception:
            pass
        return None
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW0xMk5RPT06ZmU0ODI2MTM=


class DataDependencyResolver:
    """数据依赖解析器"""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self._faker = Faker('zh_CN') if Faker else None

    def _call_faker(self, method: str) -> str:
        """调用 faker 生成数据，支持常见字段别名"""
        if not self._faker:
            return str(uuid4())

        # 常见字段的 JS 风格 -> Python faker 映射
        aliases = {
            "name": "name",
            "person.full_name": "name",
            "person.fullName": "name",
            "first_name": "first_name",
            "last_name": "last_name",
            "phone_number": "phone_number",
            "phone.number": "phone_number",
            "email": "email",
            "internet.email": "email",
            "company": "company",
            "address": "address",
            "uuid4": "uuid4",
        }
        real_method = aliases.get(method, method)
        try:
            fn = getattr(self._faker, real_method)
            value = fn()
            return str(value)
        except Exception:
            # 未知方法回退到 uuid，避免阻塞执行
            return str(uuid4())

    def _resolve_dynamic_placeholders(self, obj: Any) -> Any:
        """递归替换 {{$...}} 动态占位符

        支持：
        - {{$uuid}}
        - {{$timestamp}}
        - {{$randomString(n)}}
        - {{$randomNumber(n)}}
        - {{$faker.name}} / {{$faker.phone_number}} / {{$faker.email}} 等
        """
        import logging
        logger = logging.getLogger(__name__)

        if isinstance(obj, str):
            pattern = re.compile(r'\{\{\$(\w+(?:\.\w+)*(?:\([^)]*\))?)\}\}')

            def _replacer(match: re.Match) -> str:
                full = match.group(1)
                if "(" in full:
                    name = full.split("(", 1)[0]
                    args_str = full[full.find("(") + 1 : full.rfind(")")]
                    args = [a.strip() for a in args_str.split(",") if a.strip()]
                else:
                    name = full
                    args = []

                try:
                    if name == "uuid":
                        return str(uuid4())
                    if name == "timestamp":
                        return str(int(time.time() * 1000))
                    if name == "randomString":
                        n = int(args[0]) if args else 6
                        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))
                    if name == "randomNumber":
                        n = int(args[0]) if args else 6
                        return "".join(random.choices(string.digits, k=n))
                    if name.startswith("faker."):
                        method = name.split(".", 1)[1]
                        return self._call_faker(method)
                except Exception as e:
                    logger.warning(f"动态占位符解析失败: {match.group(0)}, 错误: {e}")

                # 解析失败时保留原占位符，便于排查
                return match.group(0)

            return pattern.sub(_replacer, obj)
        elif isinstance(obj, dict):
            return {k: self._resolve_dynamic_placeholders(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_dynamic_placeholders(item) for item in obj]
        else:
            return obj

    def _ensure_dict(self, value: Any) -> dict:
        """确保值是一个字典"""
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        # 如果是其他类型，尝试转换为字典
        try:
            return dict(value) if hasattr(value, '__iter__') else {}
        except:
            return {}
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW0xMk5RPT06ZmU0ODI2MTM=

    def _ensure_list(self, value: Any) -> list:
        """确保值是一个列表"""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        # 如果是其他类型，尝试转换为列表
        try:
            return list(value)
        except:
            return []

    async def resolve_request(
        self,
        step: ScenarioStep,
        endpoint: APIEndpoint,
        session: AsyncSession,
    ) -> dict:
        """解析步骤的数据依赖，构建最终请求

        处理步骤：
        1. 从端点获取基础请求
        2. 应用端点的默认参数（query 和 header）
        3. 应用步骤的请求覆盖（body, params/path, headers）
        4. 应用步骤的请求头覆盖
        5. 处理数据映射（从之前的步骤或变量中获取数据）
        6. 替换模板变量 {{variable}}
        """
        import logging
        logger = logging.getLogger(__name__)

        # 1. 从端点获取基础请求
        request = {
            "method": endpoint.method or "POST",
            "url": endpoint.path or "/",
            "headers": {},
            "params": {},
            "body": None,
        }

        # 2. 应用端点的默认参数
        parameters = self._ensure_list(endpoint.parameters)
        for param in parameters:
            if param.get("in") == "query":
                request["params"][param["name"]] = param.get("default")
            elif param.get("in") == "header":
                request["headers"][param["name"]] = param.get("default")

        # 3. 应用步骤的请求覆盖
        request_override = self._ensure_dict(step.request_override)

        # 如果 request_override 中有 method，覆盖端点的 method
        if "method" in request_override:
            request["method"] = request_override["method"]

        # 如果 request_override 中有 url，覆盖端点的 path
        if "url" in request_override:
            request["url"] = request_override["url"]
        elif "path" in request_override:
            request["url"] = request_override["path"]

        # 处理 body
        if "body" in request_override:
            request["body"] = request_override["body"]

        # 处理 params
        if "params" in request_override:
            request["params"].update(request_override["params"])

        # 处理路径参数（如 {orderId}）
        if "path" in request_override:
            request["path"] = request_override["path"]

        # 4. 应用步骤的请求头覆盖
        headers_override = self._ensure_dict(step.headers_override)
        request["headers"].update(headers_override)

        # 5. 处理数据映射（在变量替换之前，这样数据映射的值也可以被替换）
        mappings_stmt = select(StepDataMapping).where(
            StepDataMapping.step_id == step.id
        )
        mappings_result = await session.execute(mappings_stmt)
        mappings = mappings_result.scalars().all()

        if mappings:
            logger.info(f"步骤 {step.name} (ID: {step.id}) 有 {len(mappings)} 个数据映射")
        else:
            logger.info(f"步骤 {step.name} (ID: {step.id}) 没有配置数据映射")

        for mapping in mappings:
            value = await self._resolve_mapping(mapping)
            logger.info(
                f"数据映射: {mapping.source_type} -> {mapping.target_path} = {value}"
            )
            self._set_nested_value(request, mapping.target_path, value)

        # 6. 替换模板变量 {{variable}}（路径参数 {key} 在发送请求时处理）
        request = self._substitute_variables(request)

        logger.info(f"最终请求配置: method={request['method']}, url={request['url']}")
        logger.debug(f"请求头: {request['headers']}")
        logger.debug(f"请求参数: {request['params']}")
        logger.debug(f"请求体: {request['body']}")

        return request

    async def _resolve_mapping(self, mapping: StepDataMapping) -> Any:
        """解析单个数据映射

        Args:
            mapping: 数据映射配置

        Returns:
            解析后的值
        """
        import logging
        logger = logging.getLogger(__name__)

        if mapping.source_type == "previous_response":
            raw_value = self.context.get_step_data(
                str(mapping.source_step_id), mapping.source_path
            )
            logger.debug(
                f"从响应获取数据: step_id={mapping.source_step_id}, "
                f"path={mapping.source_path}, value={raw_value}"
            )
        elif mapping.source_type == "variable":
            raw_value = self.context.get_variable(mapping.source_path)
            logger.debug(
                f"从变量获取数据: variable={mapping.source_path}, value={raw_value}"
            )
        elif mapping.source_type == "static":
            raw_value = mapping.source_path
            logger.debug(f"使用静态值: value={raw_value}")
        else:
            raw_value = None
            logger.warning(f"未知的数据源类型: {mapping.source_type}")

        # 应用转换表达式
        if mapping.transform_expression and raw_value is not None:
            transformed = self._apply_transform(raw_value, mapping.transform_expression)
            logger.debug(
                f"应用转换表达式: '{raw_value}' + '{mapping.transform_expression}' -> {transformed}"
            )
            return transformed

        return raw_value

    def _apply_transform(self, value: Any, expression: str) -> Any:
        """应用转换表达式"""
        try:
            # 简单的表达式求值（安全起见，只支持基本操作）
            # 例如: 'Bearer ' + value
            local_vars = {"value": value}
            return eval(expression, {"__builtins__": {}}, local_vars)
        except Exception:
            return value

    def _set_nested_value(self, obj: dict, path: str, value: Any):
        """设置嵌套路径的值

        例如: "headers.Authorization" -> obj["headers"]["Authorization"] = value
        """
        import logging
        logger = logging.getLogger(__name__)

        parts = path.split(".")
        current = obj
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

        # 添加调试日志
        logger.debug(f"设置嵌套值: {path} = {value}")
        logger.debug(f"更新后的对象: {obj}")

    def _substitute_variables(self, obj: Any) -> Any:
        """递归替换对象中的模板变量 {{variable}}

        支持的语法：
        - {{variable}}: 简单变量
        - {{variable.nested}}: 嵌套属性访问

        注意：路径参数 {key} 应该通过 request["path"] 单独处理，在 _send_request 方法中替换
        """
        if isinstance(obj, str):
            # 替换字符串中的 {{variable}} 占位符
            pattern = r'\{\{(\w+(?:\.\w+)*)\}\}'
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW0xMk5RPT06ZmU0ODI2MTM=

            def replacer(match):
                var_name = match.group(1)
                value = self.context.get_variable(var_name)
                if value is not None:
                    return str(value)
                # 如果变量不存在，保留原始占位符（方便调试）
                return match.group(0)

            return re.sub(pattern, replacer, obj)
        elif isinstance(obj, dict):
            return {k: self._substitute_variables(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_variables(item) for item in obj]
        else:
            return obj


class ScenarioExecutionEngine:
    """场景执行引擎"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.context = ExecutionContext()
        self.resolver = DataDependencyResolver(self.context)
        # 使用异步客户端以兼容 SQLAlchemy AsyncSession
        self.http_client = None  # 延迟初始化，需要在异步上下文中

    def _ensure_dict(self, value: Any) -> dict:
        """确保值是一个字典"""
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        # 如果是其他类型，尝试转换为字典
        try:
            return dict(value) if hasattr(value, '__iter__') else {}
        except:
            return {}

    def _ensure_list(self, value: Any) -> list:
        """确保值是一个列表"""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        # 如果是其他类型，尝试转换为列表
        try:
            return list(value)
        except:
            return []

    def _extract_auth_headers_from_env_vars(self, env_vars: Dict[str, str]) -> Dict[str, str]:
        """从环境变量中提取应自动注入的认证头"""
        auth_headers: Dict[str, str] = {}

        # Bearer / OAuth2 / Dynamic Bearer
        authorization = env_vars.get("Authorization")
        if authorization:
            auth_headers["Authorization"] = authorization

        # API Key：从 AUTH_CONFIG_JSON 中读取 header 名称
        import json
        auth_config = {}
        try:
            auth_config = json.loads(env_vars.get("AUTH_CONFIG_JSON", "{}"))
        except Exception:
            pass

        api_key_header = auth_config.get("api_key_header", "X-API-Key")
        api_key_value = env_vars.get(api_key_header)
        if api_key_value:
            auth_headers[api_key_header] = api_key_value

        return auth_headers

    async def execute(
        self,
        scenario_id: UUID,
        variables: dict,
        base_url: str = "",
        project_id: Optional[UUID] = None,
        env_id: Optional[UUID] = None,
    ) -> ScenarioRun:
        """执行场景"""
        # 初始化异步 HTTP 客户端
        self.http_client = httpx.AsyncClient(timeout=30.0)

        try:
            # 1. 加载场景
            scenario = await self._load_scenario(scenario_id)

            # 使用场景自身的 project_id 作为回退
            if project_id is None:
                project_id = scenario.project_id

            # 2. 创建执行记录
            run = await self._create_run(scenario, variables)

            # 记录执行环境到 execution_config
            if env_id:
                run.execution_config = {"env_id": str(env_id)}
                await self.session.commit()

            # 3. 初始化上下文
            self.context.initialize(scenario.global_variables, variables)

            # 3.1 解析项目环境并注入 baseUrl / 认证信息
            resolved_base_url = base_url
            auth_headers: Dict[str, str] = {}
            if project_id:
                env_service = EnvironmentService(self.session)
                try:
                    env_vars = await env_service.get_execution_env_vars(
                        project_identifier=str(project_id),
                        env_id=env_id,
                        execution_config={"base_url": base_url},
                    )
                    resolved_base_url = env_vars.get("API_BASE_URL", base_url)
                    auth_headers = self._extract_auth_headers_from_env_vars(env_vars)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        "解析项目环境失败，将使用传入的 base_url: %s", e
                    )

            self.context.set_variable("baseUrl", resolved_base_url)
            self.context.set_variable("authHeaders", auth_headers)
            for key, value in auth_headers.items():
                self.context.set_variable(key, value)

            # 4. 按顺序执行步骤
            for step in scenario.steps:
                result = await self._execute_step(step, run)

                # 检查是否需要停止
                if result.status == "failed" and not step.continue_on_failure:
                    run.status = "failed"
                    run.error_message = f"步骤 {step.step_order} 失败: {result.error_message}"
                    break

                # 应用延迟
                if step.delay_ms > 0:
                    await asyncio.sleep(step.delay_ms / 1000.0)

            # 5. 执行 teardown 清理步骤（无论主流程是否失败都会执行）
            await self._run_teardown(scenario, run)

            # 6. 完成执行
            if run.status != "failed":
                run.status = "completed"
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW0xMk5RPT06ZmU0ODI2MTM=

            run.completed_at = datetime.now(timezone.utc)
            run.duration_ms = int(
                (run.completed_at - run.started_at).total_seconds() * 1000
            )

            # 使用 update 语句更新运行记录，避免 refresh 触发的问题
            from sqlalchemy import update
            await self.session.execute(
                update(ScenarioRun)
                .where(ScenarioRun.id == run.id)
                .values(
                    status=run.status,
                    completed_at=run.completed_at,
                    duration_ms=run.duration_ms,
                    error_message=run.error_message
                )
            )

            await self.session.commit()

            # 重新查询 run 对象以获取最新状态
            run_stmt = select(ScenarioRun).where(ScenarioRun.id == run.id)
            run_result = await self.session.execute(run_stmt)
            run = run_result.scalar_one()

            return run
        finally:
            # 关闭 HTTP 客户端
            if self.http_client:
                await self.http_client.aclose()

    async def _load_scenario(self, scenario_id: UUID) -> TestScenario:
        """加载场景"""
        from sqlalchemy.orm import selectinload

        stmt = select(TestScenario).where(TestScenario.id == scenario_id).options(
            selectinload(TestScenario.steps)
        )
        result = await self.session.execute(stmt)
        scenario = result.scalar_one_or_none()

        if not scenario:
            raise ValueError(f"场景 {scenario_id} 不存在")

        return scenario

    async def _create_run(
        self, scenario: TestScenario, variables: dict
    ) -> ScenarioRun:
        """创建执行记录"""
        run_id = uuid4()
        run = ScenarioRun(
            id=run_id,
            scenario_id=scenario.id,
            project_id=scenario.project_id,
            identifier=f"TSR-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            status="running",
            runtime_variables=variables,
            total_steps=scenario.total_steps,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.commit()

        # 重新查询以获取完整的 run 对象
        run_stmt = select(ScenarioRun).where(ScenarioRun.id == run_id)
        run_result = await self.session.execute(run_stmt)
        return run_result.scalar_one()

    async def _execute_step(
        self, step: ScenarioStep, run: ScenarioRun
    ) -> ScenarioStepResult:
        """执行单个步骤"""
        start_time = datetime.now(timezone.utc)
        current_request: dict | None = None

        try:
            # 1. 加载端点（如果没有端点ID则创建虚拟端点）
            endpoint = await self._load_endpoint(step.endpoint_id, step)

            # 2. 解析数据依赖，构建请求
            request = await self.resolver.resolve_request(step, endpoint, self.session)
            current_request = request

            # 2.1 替换动态占位符 {{$uuid}} / {{$timestamp}} / {{$faker.*}} 等
            request = self.resolver._resolve_dynamic_placeholders(request)

            # 3. 发送 HTTP 请求
            response = await self._send_request(request)

            # 4. 提取数据到上下文
            extractors = self._ensure_list(step.extractors)
            extracted = self._extract_data(response, extractors)
            self.context.update_step_data(str(step.id), extracted)

            # 5. 执行断言
            assertions = self._ensure_list(step.assertions)
            assertion_results = self._run_assertions(response, assertions)

            # 6. 判断状态
            status = "passed"
            error_message = None
            for assertion in assertion_results:
                if not assertion["passed"]:
                    status = "failed"
                    error_message = assertion.get("message", "断言失败")
                    break

            # 7. 记录结果
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            result = await self._record_result(
                step, run, request, response, extracted, assertion_results, status, duration_ms, error_message
            )

            # 8. 更新运行统计（使用 update 语句避免触发 ORM 事件）
            from sqlalchemy import update
            if status == "passed":
                await self.session.execute(
                    update(ScenarioRun)
                    .where(ScenarioRun.id == run.id)
                    .values(passed_steps=ScenarioRun.passed_steps + 1)
                )
            else:
                await self.session.execute(
                    update(ScenarioRun)
                    .where(ScenarioRun.id == run.id)
                    .values(failed_steps=ScenarioRun.failed_steps + 1)
                )

            await self.session.commit()

            return result

        except Exception as e:
            # 记录错误（包含完整的堆栈跟踪和上下文信息）
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )

            # 尽可能捕获当前步骤已经产生的请求/响应上下文
            current_response = locals().get("response", {})

            # 构建调试上下文，使用 default=str 避免不可序列化对象导致报错
            context_info = {
                "step_id": str(step.id),
                "step_order": step.step_order,
                "step_name": step.name,
                "endpoint_id": str(step.endpoint_id) if step.endpoint_id else None,
                "request": current_request or {},
                "response": current_response or {},
            }
            try:
                context_info["available_variables"] = dict(self.context.variables)
                context_info["available_step_data"] = dict(self.context.step_data)
            except Exception:
                # 变量/步骤数据无法读取时跳过，保证错误记录不中断
                pass

            try:
                context_json = json.dumps(
                    context_info, indent=2, ensure_ascii=False, default=str
                )
            except Exception:
                context_json = json.dumps(
                    {"error": "无法序列化上下文信息"}, ensure_ascii=False
                )

            error_detail = (
                f"{str(e)}\n\nStack trace:\n{traceback.format_exc()}"
                f"\n\nContext:\n{context_json}"
            )

            result = await self._record_result(
                step,
                run,
                current_request or {},
                current_response or {},
                {},
                [],
                "error",
                duration_ms,
                str(e),
                error_detail,
            )

            # 使用 update 语句更新失败计数
            from sqlalchemy import update
            await self.session.execute(
                update(ScenarioRun)
                .where(ScenarioRun.id == run.id)
                .values(failed_steps=ScenarioRun.failed_steps + 1)
            )

            await self.session.commit()
            return result

    async def _run_teardown(self, scenario: TestScenario, run: ScenarioRun) -> None:
        """执行场景 teardown 清理步骤

        在主流程结束后运行，用于删除/禁用场景中创建的资源。
        teardown 步骤失败不会影响主流程的运行状态，但会记录日志。
        """
        import logging
        logger = logging.getLogger(__name__)

        teardown_config = self._ensure_dict(scenario.teardown_config)
        teardown_steps = self._ensure_list(teardown_config.get("steps"))
        if not teardown_steps:
            return

        logger.info(
            f"场景 {scenario.identifier} 主流程结束，开始执行 {len(teardown_steps)} 个 teardown 步骤"
        )

        for idx, step_def in enumerate(teardown_steps, 1):
            try:
                await self._execute_teardown_step(step_def, idx)
            except Exception as e:
                logger.warning(f"Teardown 步骤 {idx} ({step_def.get('name')}) 执行失败: {e}")
                if not step_def.get("continue_on_failure", True):
                    logger.warning("continue_on_failure=false，停止后续 teardown 步骤")
                    break

    async def _execute_teardown_step(self, step_def: dict, idx: int) -> None:
        """执行单个 teardown 步骤"""
        import logging
        logger = logging.getLogger(__name__)

        endpoint_id = step_def.get("endpoint_id")
        endpoint = await self._load_endpoint(
            UUID(endpoint_id) if endpoint_id else None, None
        )

        # 构造临时 step 对象复用 resolver（不持久化到数据库）
        step_like = SimpleNamespace(
            id=uuid4(),
            name=step_def.get("name", f"teardown-{idx}"),
            request_override=self._ensure_dict(step_def.get("request_override")),
            headers_override=self._ensure_dict(step_def.get("headers_override")),
        )

        request = await self.resolver.resolve_request(step_like, endpoint, self.session)
        request = self.resolver._resolve_dynamic_placeholders(request)

        logger.debug(f"Teardown 步骤 {idx} 请求: {request}")
        await self._send_request(request)
        logger.info(f"Teardown 步骤 {idx} ({step_like.name}) 执行完成")

    async def _load_endpoint(self, endpoint_id: UUID | None, step: ScenarioStep = None) -> APIEndpoint:
        """加载端点，如果没有端点ID则创建虚拟端点"""
        import logging
        logger = logging.getLogger(__name__)

        if not endpoint_id:
            # 如果步骤没有关联端点，尝试智能推断或创建虚拟端点
            if not step:
                raise ValueError("步骤未关联端点。请先关联端点或配置请求信息。")

            request_override = self._ensure_dict(step.request_override)

            # 智能推断：尝试从 request_override 的 body 数据中推断端点信息
            method = request_override.get("method")
            url = request_override.get("url") or request_override.get("path")

            # 如果没有指定 method，根据步骤名称和 body 数据推断
            if not method:
                step_name = step.name or ""
                body_data = request_override.get("body", {})

                # 根据步骤名称关键字推断 HTTP 方法
                if any(keyword in step_name for keyword in ["创建", "新建", "添加", "create", "add", "new"]):
                    method = "POST"
                elif any(keyword in step_name for keyword in ["获取", "查询", "获取", "get", "fetch", "list"]):
                    method = "GET"
                elif any(keyword in step_name for keyword in ["更新", "修改", "更新", "update", "edit", "modify"]):
                    method = "PUT"
                elif any(keyword in step_name for keyword in ["删除", "删除", "delete", "remove"]):
                    method = "DELETE"
                else:
                    # 如果无法推断，默认使用 POST
                    method = "POST"
                    logger.warning(f"无法从步骤名称 '{step_name}' 推断 HTTP 方法，使用默认值 POST")

            # 如果没有指定 url，尝试从 body 数据中推断或使用通用路径
            if not url:
                body_data = request_override.get("body", {})

                # 检查 body 数据中的关键字段来推断资源类型
                if isinstance(body_data, dict):
                    # 尝试从字段名推断资源路径
                    if "orderId" in body_data or "order_id" in body_data:
                        url = "/store/order"
                    elif "activityId" in body_data or "activity_id" in body_data:
                        url = "/store/inventory"  # petstore 可能的端点
                    elif "petId" in body_data or "pet_id" in body_data:
                        url = "/store/pet"
                    elif "userId" in body_data or "user_id" in body_data:
                        url = "/user"
                    elif "categoryId" in body_data or "category_id" in body_data:
                        url = "/store/category"
                    else:
                        # 使用步骤名称作为路径的一部分
                        # 例如：创建活动 -> /activities
                        import re
                        # 移除特殊字符，转换为小写
                        name_slug = re.sub(r'[^\w\-]+', '-', step_name.lower()).strip('-')
                        url = f"/{name_slug}"
                        logger.warning(f"无法从 body 数据推断路径，使用步骤名称作为路径: {url}")
                else:
                    url = "/"

                logger.info(f"智能推断请求配置: method={method}, url={url}")

            # 检查是否有最少必需的配置
            if not url or url == "/":
                # 如果仍然无法确定 URL，给出更友好的提示
                body_preview = str(request_override.get("body", {}))[:100] if request_override.get("body") else "无"
                raise ValueError(
                    f"步骤 '{step.name}' (步骤 {step.step_order}) 未关联端点，且无法从配置中推断 API 路径。\n\n"
                    f"当前配置:\n"
                    f"- request_override.body: {body_preview}...\n\n"
                    f"请选择以下方式之一:\n"
                    f"1. 将步骤关联到项目中的 API 端点（推荐）\n"
                    f"2. 在 request_override 中指定完整的 API 路径（如 '/store/order'）"
                )

            # 创建虚拟端点
            virtual_endpoint = APIEndpoint(
                id=uuid4(),
                method=method,
                path=url,
                display_name=step.name or "自定义请求",
                summary=f"虚拟端点（步骤 {step.step_order}）",
                parameters=[],
                request_body=None,
                responses={},
                security=[],
                tags=[],
                project_id=None,  # 虚拟端点不属于任何项目
                folder_id=None,
            )

            logger.info(f"创建虚拟端点: {virtual_endpoint.method} {virtual_endpoint.path}")
            return virtual_endpoint

        stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
        result = await self.session.execute(stmt)
        endpoint = result.scalar_one_or_none()

        if not endpoint:
            raise ValueError(f"端点 {endpoint_id} 不存在")

        return endpoint

    async def _send_request(self, request: dict) -> dict:
        """发送 HTTP 请求

        处理步骤：
        1. 构建完整 URL（base_url + endpoint.path）
        2. 替换路径参数 {key} 为实际值
        3. 发送 HTTP 请求
        4. 解析响应
        """
        # 1. 构建完整 URL
        base_url = self.context.get_variable("baseUrl") or ""
        url = base_url + request["url"]

        # 2. 替换路径参数 {key} 为实际值
        # 这些参数来自 request["path"]，通常是 request_override["path"]
        if request.get("path"):
            path_params = self._ensure_dict(request.get("path"))
            for key, value in path_params.items():
                if value is not None:
                    # 替换 URL 中的 {key} 占位符
                    placeholder = f"{{{key}}}"
                    if placeholder in url:
                        url = url.replace(placeholder, str(value))
                        # 同时更新 request 中的 url，以便记录时显示正确的 URL
                        request["url"] = request["url"].replace(placeholder, str(value))
                    else:
                        # 如果 URL 中没有对应的占位符，记录警告
                        import logging
                        logging.warning(
                            f"路径参数 '{key}' 已设置值 '{value}'，但 URL 中没有找到占位符 '{placeholder}'"
                        )

        # 确保请求参数安全
        headers = self._ensure_dict(request.get("headers"))
        params = self._ensure_dict(request.get("params"))
        body = request.get("body")

        # 合并环境认证头（步骤级 headers_override 优先级更高）
        auth_headers = self.context.get_variable("authHeaders") or {}
        if isinstance(auth_headers, dict):
            for key, value in auth_headers.items():
                if key not in headers:
                    headers[key] = value

        # 使用异步 HTTP 客户端发送请求
        response = await self.http_client.request(
            method=request["method"],
            url=url,
            headers=headers,
            params=params,
            json=body,
        )

        # 解析响应体（注意：httpx 的 response.json() 是同步方法，不需要 await）
        content_type = response.headers.get("content-type", "")
        if content_type and content_type.startswith("application/json"):
            try:
                response_body = response.json()
            except Exception:
                # 如果解析 JSON 失败，使用原始文本
                response_body = response.text
        else:
            response_body = response.text

        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
            "timing": response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
        }

    def _extract_data(self, response: dict, extractors: list) -> dict:
        """从响应中提取数据"""
        extracted = {}
        for extractor in extractors or []:
            name = extractor["name"]
            path = extractor["path"]

            # 获取响应体，如果是 JSON 字符串则先解析
            body = response.get("body")
            if isinstance(body, str):
                try:
                    import json
                    body = json.loads(body)
                except Exception:
                    pass  # 如果解析失败，保持原样

            value = self.context._extract_by_jsonpath(body, path)
            extracted[name] = value
            # 同时设置为全局变量
            self.context.set_variable(name, value)
        return extracted

    def _run_assertions(self, response: dict, assertions: list) -> list:
        """执行断言"""
        results = []
        for assertion in assertions or []:
            assertion_type = assertion["type"]
            expected = assertion["expected"]
            operator = assertion.get("operator", "eq")

            if assertion_type == "status":
                actual = response["status"]
            elif assertion_type == "jsonpath":
                path = assertion["path"]
                actual = self.context._extract_by_jsonpath(response["body"], path)
            elif assertion_type == "header":
                path = assertion["path"]
                actual = response["headers"].get(path)
            else:
                actual = None

            # 比较
            passed = self._compare(actual, expected, operator)

            results.append({
                "assertion": assertion,
                "passed": passed,
                "actual": actual,
                "expected": expected,
                "message": f"断言{'通过' if passed else '失败'}: {assertion_type}",
            })

        return results

    def _compare(self, actual: Any, expected: Any, operator: str) -> bool:
        """比较值"""
        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "gt":
            return actual > expected
        elif operator == "lt":
            return actual < expected
        elif operator == "contains":
            return expected in actual
        else:
            return False

    async def _record_result(
        self,
        step: ScenarioStep,
        run: ScenarioRun,
        request: dict,
        response: dict,
        extracted: dict,
        assertion_results: list,
        status: str,
        duration_ms: int,
        error_message: str | None,
        error_stack: str | None = None,
    ) -> ScenarioStepResult:
        """记录步骤结果"""
        base_url = self.context.get_variable("baseUrl") or ""
        full_url = base_url + request.get("url", "")

        result = ScenarioStepResult(
            id=uuid4(),
            run_id=run.id,
            step_id=step.id,
            endpoint_id=step.endpoint_id,
            step_order=step.step_order,
            step_name=step.name,
            status=status,
            full_url=full_url,
            request_data=request,
            response_data=response,
            extracted_data=extracted,
            assertion_results=assertion_results,
            duration_ms=duration_ms,
            error_message=error_message,
            error_stack=error_stack or error_message,
        )
        self.session.add(result)
        return result

