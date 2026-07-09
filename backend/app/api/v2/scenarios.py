"""
场景测试管理路由
提供场景 CRUD、步骤管理、执行触发、结果查询等功能
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserIdDep, DbSessionDep
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioListResponse,
    ScenarioStepCreate,
    ScenarioStepUpdate,
    ScenarioStepResponse,
    ScenarioExecuteRequest,
    ScenarioExecuteResponse,
    ScenarioRunResponse,
    ScenarioRunListResponse,
    ScenarioStepResultResponse,
    DataMappingCreate,
)
from app.services.scenario_service import ScenarioService
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjNFd1RBPT06YzQ0MzNhNDY=

router = APIRouter()


async def resolve_project_id(db: AsyncSession, project_identifier: str) -> UUID:
    """将项目标识符解析为项目 UUID"""
    # 尝试直接解析为 UUID
    try:
        return UUID(project_identifier)
    except ValueError:
        # 如果不是 UUID，则查询数据库
        from app.models.project import Project

        result = await db.execute(
            select(Project.id).where(Project.identifier == project_identifier)
        )
        project_id = result.scalar_one_or_none()
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 {project_identifier} 不存在"
            )
        return project_id


# ==================== 场景管理 ====================

@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    project_id: str,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    """
    列出项目的所有测试场景

    支持按状态筛选和分页
    """
    # 解析项目 ID
    resolved_project_id = await resolve_project_id(db, project_id)

    service = ScenarioService(db)
    result = await service.list_scenarios(
        project_id=resolved_project_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ScenarioListResponse(**result)


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    project_id: str,
    scenario_in: ScenarioCreate,
):
    """
    创建新的测试场景

    场景用于编排多个 API 接口的业务流测试
    """
    # 解析项目 ID
    resolved_project_id = await resolve_project_id(db, project_id)

    service = ScenarioService(db)
    return await service.create_scenario(
        project_id=resolved_project_id,
        scenario_in=scenario_in,
        created_by=current_user_id,
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
):
    """获取场景详情（包含所有步骤和数据映射）"""
    service = ScenarioService(db)
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    scenario_in: ScenarioUpdate,
):
    """更新场景基本信息"""
    service = ScenarioService(db)
    scenario = await service.update_scenario(scenario_id, scenario_in)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
):
    """
    删除场景

    级联删除所有步骤、数据映射和执行记录
    """
    service = ScenarioService(db)
    success = await service.delete_scenario(scenario_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )


# ==================== 步骤管理 ====================
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjNFd1RBPT06YzQ0MzNhNDY=

@router.get("/steps/{step_id}", response_model=ScenarioStepResponse)
async def get_scenario_step(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    step_id: UUID,
):
    """获取单个步骤详情"""
    service = ScenarioService(db)
    step = await service.get_step(step_id)
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"步骤 {step_id} 不存在"
        )
    return step


@router.get("/{scenario_id}/steps", response_model=List[ScenarioStepResponse])
async def list_scenario_steps(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
):
    """获取场景的所有步骤（按顺序排列）"""
    service = ScenarioService(db)

    # 验证场景存在
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )

    return await service.list_steps(scenario_id)


@router.post("/{scenario_id}/steps", response_model=ScenarioStepResponse, status_code=status.HTTP_201_CREATED)
async def add_scenario_step(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    step_in: ScenarioStepCreate,
):
    """
    向场景添加步骤

    每个步骤代表一个 API 接口调用，可以配置请求参数、数据提取器、断言等
    """
    service = ScenarioService(db)

    # 验证场景存在
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )

    try:
        return await service.add_step(scenario_id, step_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{scenario_id}/steps/{step_id}", response_model=ScenarioStepResponse)
async def update_scenario_step(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    step_id: UUID,
    step_in: ScenarioStepUpdate,
):
    """更新步骤配置"""
    service = ScenarioService(db)
    step = await service.update_step(scenario_id, step_id, step_in)
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"步骤 {step_id} 不存在"
        )
    return step


@router.delete("/{scenario_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario_step(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    step_id: UUID,
):
    """
    删除步骤

    删除后会自动重新排序剩余步骤
    """
    service = ScenarioService(db)
    success = await service.delete_step(scenario_id, step_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"步骤 {step_id} 不存在"
        )


@router.post("/{scenario_id}/steps/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_scenario_steps(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    step_orders: dict[UUID, int],  # {step_id: new_order}
):
    """
    重新排序步骤

    接收一个字典，key 为 step_id，value 为新的顺序号
    """
    service = ScenarioService(db)

    # 验证场景存在
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )

    await service.reorder_steps(scenario_id, step_orders)


# ==================== 数据映射管理 ====================

@router.post("/{scenario_id}/steps/{step_id}/mappings", response_model=ScenarioStepResponse, status_code=status.HTTP_201_CREATED)
async def add_data_mapping(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    step_id: UUID,
    mapping_in: DataMappingCreate,
):
    """
    为步骤添加数据映射

    数据映射用于将前一个步骤的响应数据传递给当前步骤
    支持的数据源类型：
    - previous_response: 前一个步骤的响应数据
    - variable: 场景变量
    - static: 静态值
    """
    service = ScenarioService(db)
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjNFd1RBPT06YzQ0MzNhNDY=

    # 验证场景和步骤存在
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )

    step = await service.get_step(step_id)
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"步骤 {step_id} 不存在"
        )

    try:
        await service.add_data_mapping(step_id, mapping_in)
        # 重新加载步骤并返回
        return await service.get_step(step_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{scenario_id}/steps/{step_id}/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_mapping(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    step_id: UUID,
    mapping_id: UUID,
):
    """删除数据映射"""
    service = ScenarioService(db)
    await service.delete_data_mapping(mapping_id)


# ==================== 场景执行 ====================

@router.post("/{scenario_id}/execute", response_model=ScenarioExecuteResponse)
async def execute_scenario(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    execute_request: ScenarioExecuteRequest,
    background_tasks: BackgroundTasks,
):
    """
    执行场景

    支持同步和异步两种执行模式：
    - 同步模式：等待执行完成后返回结果
    - 异步模式：立即返回 run_id，后台执行
    """
    service = ScenarioService(db)

    # 验证场景存在
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )

    # 异步执行
    if execute_request.async_mode:
        run_id = await service.execute_scenario_async(
            scenario_id=scenario_id,
            variables=execute_request.variables,
            base_url=execute_request.base_url,
            executed_by=current_user_id,
            env_id=execute_request.env_id,
        )
        return ScenarioExecuteResponse(
            run_id=run_id,
            status="queued",
            message="场景已加入执行队列"
        )

    # 同步执行
    else:
        run = await service.execute_scenario(
            scenario_id=scenario_id,
            variables=execute_request.variables,
            base_url=execute_request.base_url,
            executed_by=current_user_id,
            env_id=execute_request.env_id,
        )
        return ScenarioExecuteResponse(
            run_id=run.id,
            status=run.status,
            message=f"场景执行{'成功' if run.status == 'completed' else '完成'}",
            result=ScenarioRunResponse.model_validate(run)
        )

# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VjNFd1RBPT06YzQ0MzNhNDY=

# ==================== 执行记录查询 ====================

@router.get("/{scenario_id}/runs", response_model=ScenarioRunListResponse)
async def list_scenario_runs(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    page: int = 1,
    page_size: int = 20,
):
    """获取场景的执行记录"""
    service = ScenarioService(db)

    # 验证场景存在
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scenario_id} 不存在"
        )

    runs = await service.list_runs(scenario_id, page, page_size)
    return ScenarioRunListResponse(
        total=len(runs),
        items=runs
    )


@router.get("/{scenario_id}/runs/{run_id}", response_model=ScenarioRunResponse)
async def get_scenario_run(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    run_id: UUID,
):
    """获取执行记录详情"""
    service = ScenarioService(db)
    run = await service.get_run(run_id)
    if not run or run.scenario_id != scenario_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录 {run_id} 不存在"
        )
    return run


@router.get("/{scenario_id}/runs/{run_id}/results", response_model=List[ScenarioStepResultResponse])
async def get_step_results(
    db: DbSessionDep,
    current_user_id: CurrentUserIdDep,
    scenario_id: UUID,
    run_id: UUID,
):
    """
    获取执行记录的详细步骤结果

    包含每个步骤的请求、响应、断言结果等详细信息
    """
    service = ScenarioService(db)

    # 验证执行记录存在
    run = await service.get_run(run_id)
    if not run or run.scenario_id != scenario_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录 {run_id} 不存在"
        )

    return await service.get_step_results(run_id)
