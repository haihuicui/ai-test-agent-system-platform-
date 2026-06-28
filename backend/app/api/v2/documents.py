"""
文档上传 API

提供文档上传到 MinIO 的接口,用于 AI 智能体处理
"""

from typing import Annotated
from datetime import timedelta

from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.schemas.common import SuccessResponse
from app.config.minio_client import MinIOClient
from pydantic import BaseModel
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtFMVZRPT06ZTQzNzViNGQ=


router = APIRouter(prefix="/documents", tags=["文档管理"])


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    object_name: str
    file_name: str
    file_size: int
    content_type: str
    url: str
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtFMVZRPT06ZTQzNzViNGQ=


@router.post(
    "/upload",
    response_model=SuccessResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="上传文档到 MinIO",
    description="上传文档文件到 MinIO 存储,返回文件 URL 供 AI 智能体使用",
)
async def upload_document(
    file: UploadFile = File(..., description="要上传的文档文件"),
) -> SuccessResponse[DocumentUploadResponse]:
    """
    上传文档到 MinIO
    
    支持的文件类型:
    - 图片: JPG, PNG, GIF, WebP
    - 文档: PDF, Word, TXT
    
    最大文件大小: 10MB
    """
    # 验证文件类型
    valid_types = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]
    
    if file.content_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}",
        )
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtFMVZRPT06ZTQzNzViNGQ=
    
    # 读取文件内容
    content = await file.read()

    # 验证文件非空 (防止 0 字节文件被静默存入，导致后续解析报误导性错误)
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空（0 字节），请确认所选文件本身不是空文件后重试",
        )

    # 验证文件大小 (10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小不能超过 10MB",
        )
    
    # 生成对象名
    import uuid
    from datetime import datetime
    
    file_ext = ""
    if file.filename:
        parts = file.filename.rsplit(".", 1)
        if len(parts) > 1:
            file_ext = f".{parts[1]}"
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    object_name = f"documents/{timestamp}_{unique_id}{file_ext}"
    
    # 上传到 MinIO
    try:
        MinIOClient.upload_bytes(
            object_name=object_name,
            data=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}",
        )
    
    # 生成预签名 URL (24小时有效)
    try:
        url = MinIOClient.get_presigned_url(
            object_name=object_name,
            expires=timedelta(hours=24),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成下载链接失败: {str(e)}",
        )
    
    return SuccessResponse(
        success=True,
        data=DocumentUploadResponse(
            object_name=object_name,
            file_name=file.filename or "unnamed",
            file_size=len(content),
            content_type=file.content_type or "application/octet-stream",
            url=url,
        ),
    )
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtFMVZRPT06ZTQzNzViNGQ=

