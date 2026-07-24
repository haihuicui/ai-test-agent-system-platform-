"""
Web 登录态生成 API

提供触发/查询 Playwright storageState.json 生成任务的接口。
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.deps import DbSessionDep, StorageStateServiceDep
from app.schemas.common import SuccessResponse
from app.schemas.storage_state import (
    StorageStateGenerateRequest,
    StorageStateJobInfo,
    StorageStateLatestInfo,
)


from app.utils.storage_state_validator import validate_storage_state

router = APIRouter(prefix="/projects/{project_identifier}/environments/{env_id}/storage-state")


@router.post(
    "/generate",
    response_model=SuccessResponse[StorageStateJobInfo],
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成 Web 登录态",
    description="异步执行表单登录并导出 Playwright storageState.json",
)
async def generate_storage_state(
    project_identifier: str,
    env_id: UUID,
    data: StorageStateGenerateRequest,
    background_tasks: BackgroundTasks,
    service: StorageStateServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[StorageStateJobInfo]:
    """触发生成任务。

    - 密码不会被持久化，仅临时传给后台 Playwright 子进程。
    - 若请求中未传 username/selectors，则从 ProjectEnvironment.auth_config.form_login 读取。
    """
    job, username, captcha, selectors, project, _ = await service.create_job(
        project_identifier=project_identifier,
        env_id=env_id,
        username=data.username,
        password=data.password,
        captcha=data.captcha,
        selectors=data.selectors,
        headless=data.headless,
        save_attachment=data.save_attachment,
    )

    background_tasks.add_task(
        service.execute_generation,
        job_id=job.id,
        username=username,
        password=data.password,
        captcha=captcha,
        selectors=selectors,
        headless=data.headless,
        save_attachment=data.save_attachment,
        project_identifier=project.identifier,
    )

    await db.commit()
    return SuccessResponse(success=True, data=service.to_info(job))


@router.get(
    "/jobs/{job_id}",
    response_model=SuccessResponse[StorageStateJobInfo],
    summary="查询登录态生成任务",
)
async def get_storage_state_job(
    project_identifier: str,
    env_id: UUID,
    job_id: UUID,
    service: StorageStateServiceDep,
) -> SuccessResponse[StorageStateJobInfo]:
    """查询指定生成任务的当前状态与结果。"""
    info = await service.get_job(project_identifier, job_id)
    return SuccessResponse(success=True, data=info)


@router.get(
    "/latest",
    response_model=SuccessResponse[Optional[StorageStateLatestInfo]],
    summary="最近一次成功的登录态",
)
async def get_latest_storage_state(
    project_identifier: str,
    env_id: UUID,
    service: StorageStateServiceDep,
) -> SuccessResponse[Optional[StorageStateLatestInfo]]:
    """返回该项目/环境下最近一次成功生成的 storageState 信息，并附带有效性校验。"""
    job_info = await service.get_latest_success(
        project_identifier, environment_id=env_id
    )
    if not job_info:
        return SuccessResponse(success=True, data=None)

    # 补充 MinIO 对象路径
    object_name = None
    if job_info.attachment_id:
        from app.models.attachment import Attachment
        from app.config.database import async_session_factory

        async with async_session_factory() as session:
            attachment = await session.get(Attachment, job_info.attachment_id)
            object_name = attachment.object_name if attachment else None

    # 实时校验文件：数据库字段可能为空或滞后，以文件内容为准。
    is_valid = job_info.is_valid
    expires_at = job_info.expires_at
    validation_reason = job_info.validation_reason
    if job_info.output_path:
        validation = validate_storage_state(job_info.output_path)
        is_valid = validation.is_valid
        expires_at = validation.earliest_expiry
        validation_reason = validation.reason

    data = StorageStateLatestInfo(
        job_id=job_info.job_id,
        environment_id=job_info.environment_id,
        output_path=job_info.output_path,
        attachment_id=job_info.attachment_id,
        generated_at=job_info.completed_at,
        object_name=object_name,
        is_valid=is_valid,
        expires_at=expires_at,
        validation_reason=validation_reason,
    )
    return SuccessResponse(success=True, data=data)
